import asyncio
from collections.abc import Awaitable, Callable
from time import perf_counter

from pydantic import ValidationError

from app.core.errors import AppError
from app.domain.models import (
    BenefitResult,
    Claim,
    Document,
    DocumentResult,
    MedicalResult,
    MedicalRule,
    Model,
    Money,
    Policy,
    ToolTrace,
    now,
)
from app.domain.rules import calculate_benefit, medical_necessity
from app.providers.llm import Provider


class VerifyArgs(Model):
    documentId: str


class PolicyArgs(Model):
    policyId: str


class MedicalArgs(Model):
    diagnosis: str
    procedures: list[str]


class BenefitArgs(PolicyArgs):
    claimType: str
    amount: Money


SCHEMAS = {
    "verifyDocument": VerifyArgs,
    "lookupPolicy": PolicyArgs,
    "checkMedicalNecessity": MedicalArgs,
    "calculateBenefit": BenefitArgs,
}
ORDER = {"verifyDocument": 0, "lookupPolicy": 1, "checkMedicalNecessity": 2, "calculateBenefit": 3}


class Tools:
    def __init__(
        self, claim: Claim, policy: Policy, documents: list[Document], rules: list[MedicalRule]
    ):
        self.claim = claim
        self.policy = policy
        self.documents = {d.id: d for d in documents}
        self.rules = rules

    def verifyDocument(self, args: VerifyArgs) -> DocumentResult:
        if args.documentId not in self.claim.document_ids or args.documentId not in self.documents:
            raise AppError(404, "document_not_found", "Document is not attached to this claim")
        doc = self.documents[args.documentId]
        issues = list(doc.issues)
        if doc.declared_type != doc.actual_type:
            issues.append(f"Type mismatch: expected {doc.declared_type}, found {doc.actual_type}.")
        if not doc.complete:
            issues.append("Document is incomplete.")
        return DocumentResult(
            document_id=doc.id,
            expected_type=doc.declared_type,
            actual_type=doc.actual_type,
            status="incomplete" if issues else "complete",
            issues=issues,
            evidence_id=f"document:{doc.id}:v{doc.revision}",
        )

    def lookupPolicy(self, args: PolicyArgs) -> Policy:
        if args.policyId != self.claim.policy_id or args.policyId != self.policy.id:
            raise ValueError("Policy does not match current claim")
        return self.policy

    def checkMedicalNecessity(self, args: MedicalArgs) -> MedicalResult:
        return medical_necessity(args.diagnosis, args.procedures, self.rules)

    def calculateBenefit(self, args: BenefitArgs) -> BenefitResult:
        if self.policy.usage_year != self.claim.treatment_start.year:
            raise AppError(
                422, "usage_year_missing", "No benefit usage snapshot for treatment year"
            )
        return calculate_benefit(self.claim, self.policy)


class Executor:
    def __init__(
        self,
        run_id: str,
        mode: str,
        tools: Tools,
        provider: Provider,
        sink: Callable[[ToolTrace], Awaitable[None]],
    ):
        self.run_id, self.mode = run_id, mode
        self.tools, self.provider, self.sink = tools, provider, sink
        self.trace: list[ToolTrace] = []
        self.stage = 0
        self.verified: list[str] = []
        self.called: set[str] = set()

    async def call(
        self, name: str, expected_args: dict
    ) -> DocumentResult | Policy | MedicalResult | BenefitResult:
        if ORDER[name] < self.stage or (name != "verifyDocument" and name in self.called):
            raise ValueError("Duplicate or out-of-order tool stage")
        if name == "lookupPolicy" and self.verified != self.tools.claim.document_ids:
            raise ValueError("Some submitted documents were not checked")
        if name == "checkMedicalNecessity" and "lookupPolicy" not in self.called:
            raise ValueError("Policy lookup is required first")
        if name == "calculateBenefit" and "checkMedicalNecessity" not in self.called:
            raise ValueError("Medical check is required first")
        schema = SCHEMAS[name]
        expected = schema.model_validate(expected_args)
        feedback = ""
        for attempt in (1, 2):
            started, tick = now(), perf_counter()
            proposed = None
            try:
                proposed = await self.provider.propose(
                    name,
                    expected.model_dump(mode="json"),
                    schema.model_json_schema(),
                    {
                        "claim": self.tools.claim.model_dump(mode="json"),
                        "previous_tool_results": [
                            t.model_dump(mode="json") for t in self.trace if t.status == "completed"
                        ],
                    },
                    feedback,
                )
                if proposed.name != name:
                    raise ValueError("Tool name is not allowed at this stage")
                args = schema.model_validate(proposed.args)
                if args != expected:
                    raise ValueError("Tool arguments differ from the required claim snapshot")
            except (ValidationError, ValueError) as exc:
                feedback = "Call only the allowed tool with exactly the required arguments."
                await self._record(
                    name,
                    proposed.model_dump() if proposed else {},
                    None,
                    "rejected",
                    feedback,
                    started,
                    tick,
                    attempt,
                )
                if attempt == 2:
                    raise AppError(502, "invalid_tool_proposal", feedback) from exc
                continue
            except (Exception, asyncio.CancelledError):
                await self._record(
                    name,
                    expected.model_dump(mode="json"),
                    None,
                    "failed",
                    "Provider request failed",
                    started,
                    tick,
                    attempt,
                )
                raise
            try:
                result = getattr(self.tools, name)(args)
            except Exception:
                await self._record(
                    name,
                    args.model_dump(mode="json"),
                    None,
                    "failed",
                    "Tool execution failed",
                    started,
                    tick,
                    attempt,
                )
                raise
            await self._record(
                name,
                args.model_dump(mode="json"),
                result.model_dump(mode="json"),
                "completed",
                None,
                started,
                tick,
                attempt,
            )
            self.stage = ORDER[name]
            self.called.add(name)
            if name == "verifyDocument":
                self.verified.append(args.documentId)
            return result

    async def _record(self, name, inputs, output, status, error, started, tick, attempt):
        trace = ToolTrace(
            run_id=self.run_id,
            sequence=len(self.trace) + 1,
            tool=name,
            inputs=inputs,
            output=output,
            status=status,
            error=error,
            started_at=started,
            ended_at=now(),
            duration_ms=int((perf_counter() - tick) * 1000),
            attempt=attempt,
            mode=self.mode,
        )
        self.trace.append(trace)
        await self.sink(trace)
