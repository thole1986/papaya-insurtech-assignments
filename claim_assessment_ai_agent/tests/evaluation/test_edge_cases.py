from datetime import date
from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.domain.models import Document, ToolProposal
from app.domain.rules import validate_report
from app.providers.llm import OfflineProvider
from tests.integration.test_failures import service_claim


@pytest.mark.parametrize(
    "change,expected,code",
    [
        ("wrong_type", "REQUEST_MORE_INFO", "DOCUMENT_REQUIRED:claim_form"),
        ("incomplete", "REQUEST_MORE_INFO", "DOCUMENT_REQUIRED:claim_form"),
        ("incomplete_and_excluded", "REQUEST_MORE_INFO", "DOCUMENT_REQUIRED:claim_form"),
        ("unknown_diagnosis", "REQUEST_MORE_INFO", "MEDICAL_EVIDENCE_REQUIRED"),
        ("inappropriate", "REJECT", "MEDICALLY_INAPPROPRIATE"),
        ("member", "REJECT", "MEMBER_NOT_COVERED"),
        ("waiting", "REJECT", "WAITING_PERIOD"),
        ("coverage_end", "REJECT", "OUTSIDE_COVERAGE"),
        ("outside_policy_year", "REJECT", "OUTSIDE_COVERAGE"),
        ("claim_type", "REJECT", "TYPE_NOT_COVERED"),
        ("exhausted", "REJECT", "NO_PAYABLE_BENEFIT"),
        ("partial", "APPROVE", "ELIGIBLE_BENEFIT"),
    ],
)
async def test_business_edges(settings, change, expected, code):
    service, claim = await service_claim(settings)
    try:
        policy = service.catalog.policies[claim.policy_id]
        if change in {"wrong_type", "incomplete", "incomplete_and_excluded"}:
            doc = Document.model_validate(await service.db.get("document", claim.document_ids[0]))
            if change == "wrong_type":
                doc.actual_type = "other"
            else:
                doc.complete = False
            await service.db.replace("document", doc.id, doc.model_dump(mode="json"))
        if change == "incomplete_and_excluded":
            claim.procedures = ["cosmetic_surgery"]
        elif change == "unknown_diagnosis":
            claim.diagnosis = "not_in_rules"
        elif change == "inappropriate":
            claim.procedures = ["unsupported_procedure"]
        elif change == "member":
            claim.member_id = "FOREIGN"
        elif change == "waiting":
            claim = claim.model_copy(
                update={"treatment_start": date(2026, 1, 5), "treatment_end": date(2026, 1, 5)}
            )
        elif change == "coverage_end":
            policy.coverage_end = date(2026, 6, 9)
        elif change == "outside_policy_year":
            claim = claim.model_copy(
                update={"treatment_start": date(2027, 6, 10), "treatment_end": date(2027, 6, 10)}
            )
        elif change == "claim_type":
            claim.claim_type = "inpatient"
        elif change == "exhausted":
            policy.benefits[claim.claim_type].used_payout = Decimal("5000000")
        elif change == "partial":
            claim.amount = Decimal("10000000")
        await service.db.replace("claim", claim.id, claim.model_dump(mode="json"))
        run = await service.assess(claim.id)
        assert run.report.recommendation.outcome == expected
        assert code in [r.code for r in run.report.recommendation.reasons]
        calls = await service.db.list("tool_call", run.id)
        verified_ids = [t["inputs"]["documentId"] for t in calls if t["tool"] == "verifyDocument"]
        assert set(verified_ids) == set(claim.document_ids)
        assert len(verified_ids) == len(claim.document_ids)
        if change == "partial":
            assert run.report.benefit_calculation.covered_amount == Decimal("4000000")
            assert run.report.benefit_calculation.member_responsibility == Decimal("6000000")
        if change == "incomplete_and_excluded":
            assert run.report.policy_verification.findings[0].code == "EXCLUDED_PROCEDURE"
    finally:
        await service.db.close()


async def test_citation_validator_rejects_existing_but_wrong_clause(settings):
    service, claim = await service_claim(settings)
    try:
        run = await service.assess(claim.id)
        report = run.report.model_copy(deep=True)
        report.recommendation.reasons[0].clause_ids = [
            service.catalog.policy(claim.policy_id).clauses["exclusion"].id
        ]
        with pytest.raises(ValueError, match="mapping"):
            validate_report(
                report,
                claim,
                service.catalog.policy(claim.policy_id),
                run.report.document_review,
                run.report.medical_necessity,
                run.report.benefit_calculation,
            )
    finally:
        await service.db.close()


async def test_summary_citation_repair_is_bounded(settings):
    class FabricatedSummary(OfflineProvider):
        async def summarize(self, report, feedback=""):
            result = await super().summarize(report, feedback)
            result.clause_ids = ["invented-clause"]
            return result

    service, claim = await service_claim(settings, FabricatedSummary)
    try:
        with pytest.raises(AppError):
            await service.assess(claim.id)
        run = (await service.db.list_runs(claim.id))[0]
        assert run["status"] == "failed" and run["report"] is None
    finally:
        await service.db.close()


async def test_tool_failure_keeps_partial_trace(settings, monkeypatch):
    from app.agent.tools import Tools

    def fail(self, args):
        raise RuntimeError("Synthetic verifier unavailable")

    service, claim = await service_claim(settings)
    monkeypatch.setattr(Tools, "lookupPolicy", fail)
    try:
        with pytest.raises(AppError):
            await service.assess(claim.id)
        run = (await service.db.list_runs(claim.id))[0]
        trace = await service.db.list("tool_call", run["id"])
        assert len(trace) == 4
        assert len([t for t in trace if t["status"] == "failed"]) == 1
        assert run["report"] is None
    finally:
        await service.db.close()


async def test_total_timeout_releases_claim_lock(settings):
    import asyncio

    class Slow(OfflineProvider):
        async def propose(self, *args, **kwargs):
            await asyncio.sleep(1)
            return ToolProposal(name="verifyDocument", args={})

    settings.assessment_timeout_seconds = 0.05
    service, claim = await service_claim(settings, Slow)
    try:
        with pytest.raises(AppError) as exc:
            await service.assess(claim.id)
        assert exc.value.status == 504
        assert claim.id not in service.busy
        assert (await service.db.list_runs(claim.id))[0]["status"] == "failed"
    finally:
        await service.db.close()


async def test_missing_usage_year_fails_only_when_calculator_is_needed(settings):
    service, claim = await service_claim(settings)
    service.catalog.policies[claim.policy_id].usage_year = 2025
    try:
        with pytest.raises(AppError) as caught:
            await service.assess(claim.id)
        assert caught.value.code == "usage_year_missing" and caught.value.status == 422
        run = (await service.db.list_runs(claim.id))[0]
        assert run["status"] == "failed" and run["report"] is None
    finally:
        await service.db.close()
