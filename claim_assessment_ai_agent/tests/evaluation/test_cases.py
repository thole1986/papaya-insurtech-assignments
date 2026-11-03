import pytest

from tests.conftest import assess, create_claim


@pytest.mark.parametrize(
    "case_id,outcome,expected_tools",
    [
        (
            "approval_001",
            "APPROVE",
            ["verifyDocument"] * 3 + ["lookupPolicy", "checkMedicalNecessity", "calculateBenefit"],
        ),
        ("rejection_002", "REJECT", ["verifyDocument"] * 3 + ["lookupPolicy"]),
        ("more_info_003", "REQUEST_MORE_INFO", ["verifyDocument"] * 2 + ["lookupPolicy"]),
    ],
)
def test_expected_outcomes_and_trace(client, case_id, outcome, expected_tools):
    claim = create_claim(client, case_id)
    run = assess(client, claim)
    report = run["report"]
    assert report["recommendation"]["outcome"] == outcome
    calls = client.get(f"/api/v1/assessments/{run['id']}/tool-calls").json()
    assert [c["tool"] for c in calls] == expected_tools
    assert [c["inputs"]["documentId"] for c in calls if c["tool"] == "verifyDocument"] == claim[
        "document_ids"
    ]
    assert all(c["output"] and c["status"] == "completed" for c in calls)
    lookup = next(c["output"] for c in calls if c["tool"] == "lookupPolicy")
    clauses = {v["id"]: v for v in lookup["clauses"].values()}
    for reason in report["recommendation"]["reasons"]:
        assert reason["evidence_refs"]
        assert all(c in clauses for c in reason["clause_ids"])
    assert all(c == clauses[c["id"]] for c in report["policy_citations"])
    if outcome == "APPROVE":
        assert report["benefit_calculation"]["covered_amount"] == "800000"
    else:
        assert report["benefit_calculation"]["covered_amount"] is None
