import asyncio

import pytest

from app.core.errors import AppError
from app.domain.models import Assessment, CreateClaim, ToolProposal, now, uid
from app.providers.llm import OfflineProvider
from app.repositories.database import Database
from app.repositories.fixtures import Catalog
from app.services.assessment import AssessmentService


async def service_claim(settings, factory=OfflineProvider):
    db = Database(settings.database_url)
    await db.start()
    service = AssessmentService(db, Catalog(), settings, factory)
    session_id = uid()
    await db.put("session", session_id, "", {"id": session_id})
    claim = await service.create_claim(CreateClaim(session_id=session_id, case_id="approval_001"))
    return service, claim


class WrongTool(OfflineProvider):
    async def propose(self, *args, **kwargs):
        return ToolProposal(name="calculateBenefit", args={})


async def test_bad_tool_proposals_are_bounded_and_logged(settings):
    service, claim = await service_claim(settings, WrongTool)
    try:
        with pytest.raises(AppError, match="allowed tool"):
            await service.assess(claim.id)
        run = (await service.db.list_runs(claim.id))[0]
        assert run["status"] == "failed"
        traces = await service.db.list("tool_call", run["id"])
        assert len(traces) == 2
        assert all(t["status"] == "rejected" and t["output"] is None for t in traces)
        assert claim.id not in service.busy
    finally:
        await service.db.close()


class RepairableTool(OfflineProvider):
    def __init__(self):
        super().__init__()
        self.first = True

    async def propose(self, name, args, schema, context, feedback=""):
        if self.first:
            self.first = False
            return ToolProposal(name=name, args={"documentId": "foreign"})
        return await super().propose(name, args, schema, context, feedback)


async def test_one_repair_then_success(settings):
    service, claim = await service_claim(settings, RepairableTool)
    try:
        run = await service.assess(claim.id)
        assert run.report.recommendation.outcome == "APPROVE"
        calls = sorted(await service.db.list("tool_call", run.id), key=lambda t: t["sequence"])
        assert calls[0]["status"] == "rejected"
        assert calls[1]["status"] == "completed"
    finally:
        await service.db.close()


class FailedProvider(OfflineProvider):
    async def propose(self, *args, **kwargs):
        raise AppError(502, "provider_failure", "LLM request failed or timed out")


async def test_provider_failure_never_turns_into_recommendation(settings):
    service, claim = await service_claim(settings, FailedProvider)
    try:
        with pytest.raises(AppError):
            await service.assess(claim.id)
        run = (await service.db.list_runs(claim.id))[0]
        assert run["status"] == "failed" and run["report"] is None
        assert (await service.db.list("tool_call", run["id"]))[0]["status"] == "failed"
    finally:
        await service.db.close()


async def test_concurrent_assessment_rejected(settings):
    entered, release = asyncio.Event(), asyncio.Event()

    class WaitingProvider(OfflineProvider):
        async def propose(self, *args, **kwargs):
            entered.set()
            await release.wait()
            return await super().propose(*args, **kwargs)

    service, claim = await service_claim(settings, WaitingProvider)
    try:
        task = asyncio.create_task(service.assess(claim.id))
        await asyncio.wait_for(entered.wait(), 5)
        with pytest.raises(AppError) as caught:
            await service.assess(claim.id)
        assert caught.value.status == 409
        release.set()
        assert (await task).status == "completed"
    finally:
        release.set()
        await service.db.close()


async def test_restart_marks_interrupted_run_failed(settings):
    db = Database(settings.database_url)
    await db.start()
    run = Assessment(
        id=uid(),
        claim_id="claim",
        session_id="session",
        version=1,
        status="running",
        snapshot={},
        created_at=now(),
    )
    await db.create_run(run.model_dump(mode="json"))
    await db.close()
    restarted = Database(settings.database_url)
    try:
        await restarted.start()
        saved = await restarted.get_run(run.id)
        assert saved["status"] == "failed" and saved["error"] == "interrupted_by_restart"
    finally:
        await restarted.close()
