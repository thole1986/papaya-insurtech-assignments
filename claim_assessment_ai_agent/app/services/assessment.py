import asyncio
import logging
from collections.abc import Callable

from sqlalchemy.exc import IntegrityError

from app.agent.graph import build_graph
from app.agent.tools import Executor, Tools
from app.core.config import Settings
from app.core.errors import AppError
from app.domain.models import (
    Assessment,
    Claim,
    CreateClaim,
    Document,
    Policy,
    Review,
    ReviewInput,
    ToolTrace,
    now,
    uid,
)
from app.providers.llm import Provider, make_provider
from app.repositories.database import Database
from app.repositories.fixtures import Catalog

logger = logging.getLogger(__name__)


class AssessmentService:
    def __init__(
        self,
        db: Database,
        catalog: Catalog,
        settings: Settings,
        provider_factory: Callable[[], Provider] | None = None,
    ):
        self.db, self.catalog, self.settings = db, catalog, settings
        self.provider_factory = provider_factory or (lambda: make_provider(settings))
        self.busy: set[str] = set()

    async def create_claim(self, request: CreateClaim) -> Claim:
        await self.db.get("session", request.session_id)
        id_ = uid()
        docs = []
        if request.case_id is not None:
            case = self.catalog.case(request.case_id)
            claim = Claim(**case.claim.model_dump(), id=id_, session_id=request.session_id)
            for doc in [*case.documents, *case.available_documents]:
                item = doc.model_copy(update={"id": f"{id_}:{doc.id}", "owner_ref": id_})
                docs.append(item)
            claim.document_ids = [f"{id_}:{doc_id}" for doc_id in claim.document_ids]
        else:
            claim = Claim(**request.claim.model_dump(), id=id_, session_id=request.session_id)
            self.catalog.policy(claim.policy_id)
            if claim.document_ids:
                raise AppError(
                    422,
                    "foreign_document",
                    "Create custom claims without document IDs; "
                    "document registry is scoped to each claim",
                )
        await self.db.create_claim(
            claim.model_dump(mode="json"), [d.model_dump(mode="json") for d in docs]
        )
        return claim

    async def claim(self, claim_id: str) -> Claim:
        return Claim.model_validate(await self.db.get("claim", claim_id))

    async def add_document(self, claim_id: str, document_id: str) -> Claim:
        if claim_id in self.busy:
            raise AppError(409, "claim_busy", "Assessment is running for this claim")
        self.busy.add(claim_id)
        try:
            claim = await self.claim(claim_id)
            doc = Document.model_validate(await self.db.get("document", document_id))
            if doc.owner_ref != claim_id:
                raise AppError(422, "foreign_document", "Document belongs to another claim")
            if document_id in claim.document_ids:
                raise AppError(409, "duplicate_document", "Document is already attached")
            claim.document_ids = [*claim.document_ids, document_id]
            claim.revision += 1
            await self.db.replace("claim", claim_id, claim.model_dump(mode="json"))
            return claim
        finally:
            self.busy.discard(claim_id)

    async def assess(self, claim_id: str) -> Assessment:
        if claim_id in self.busy:
            raise AppError(409, "claim_busy", "Assessment is running for this claim")
        self.busy.add(claim_id)
        run = None
        run_created = False
        provider = None
        try:
            claim = await self.claim(claim_id)
            policy = self.catalog.policy(claim.policy_id)
            documents = []
            for id_ in claim.document_ids:
                doc = Document.model_validate(await self.db.get("document", id_))
                if doc.owner_ref != claim.id:
                    raise AppError(422, "foreign_document", "Document belongs to another claim")
                documents.append(doc)
            previous = await self.db.list_runs(claim_id)
            run = Assessment(
                id=uid(),
                claim_id=claim_id,
                session_id=claim.session_id,
                version=len(previous) + 1,
                status="running",
                created_at=now(),
                snapshot={
                    "claim": claim.model_dump(mode="json"),
                    "policy": policy.model_dump(mode="json"),
                    "documents": [d.model_dump(mode="json") for d in documents],
                    "medical_rules": [
                        r.model_dump(mode="json") for r in self.catalog.medical_rules
                    ],
                },
            )
            try:
                await self.db.create_run(run.model_dump(mode="json"))
                run_created = True
            except IntegrityError as exc:
                raise AppError(
                    409, "claim_busy", "A conflicting assessment already exists"
                ) from exc
            provider = self.provider_factory()

            async def sink(trace: ToolTrace):
                await self.db.put("tool_call", trace.id, run.id, trace.model_dump(mode="json"))

            executor = Executor(
                run.id,
                self.settings.run_mode,
                Tools(claim, policy, documents, self.catalog.medical_rules),
                provider,
                sink,
            )
            async with asyncio.timeout(self.settings.assessment_timeout_seconds):
                state = await build_graph(executor, provider).ainvoke(
                    {"claim": claim}, {"recursion_limit": 20}
                )
            run.report = state["report"]
            run.status = "completed"
            await self.db.update_run(run.model_dump(mode="json"))
            return run
        except BaseException as exc:
            if run_created:
                run.status = "failed"
                run.error = exc.code if isinstance(exc, AppError) else type(exc).__name__
                await asyncio.shield(self.db.update_run(run.model_dump(mode="json")))
                logger.warning("assessment_failed run_id=%s error=%s", run.id, run.error)
            if isinstance(exc, AppError) or not isinstance(exc, Exception):
                raise
            raise AppError(
                504 if isinstance(exc, TimeoutError) else 502,
                "assessment_failed",
                "Assessment failed; inspect its run and tool trace",
            ) from exc
        finally:
            try:
                if provider:
                    await provider.aclose()
                    if run_created:
                        await self.db.put(
                            "model_usage",
                            uid(),
                            run.id,
                            {
                                "model": provider.model,
                                "mode": self.settings.run_mode,
                                "requests": provider.usage,
                            },
                        )
            except Exception as exc:
                logger.warning(
                    "assessment_cleanup_failed run_id=%s error=%s",
                    run.id if run else "none",
                    type(exc).__name__,
                )
            finally:
                self.busy.discard(claim_id)

    async def review(self, assessment_id: str, request: ReviewInput) -> Review:
        run = Assessment.model_validate(await self.db.get_run(assessment_id))
        if run.status != "completed":
            raise AppError(
                409, "assessment_incomplete", "Only completed assessments can be reviewed"
            )
        review = Review(
            **request.model_dump(),
            id=uid(),
            assessment_id=assessment_id,
            original_recommendation=run.report.recommendation.outcome,
            created_at=now(),
        )
        await self.db.put("review", review.id, assessment_id, review.model_dump(mode="json"))
        return review

    async def validate_saved_report(self, assessment_id: str) -> tuple[Assessment, Claim, Policy]:
        """Resolve immutable snapshot for offline audit/replay, not current catalog data."""
        run = Assessment.model_validate(await self.db.get_run(assessment_id))
        return (
            run,
            Claim.model_validate(run.snapshot["claim"]),
            Policy.model_validate(run.snapshot["policy"]),
        )
