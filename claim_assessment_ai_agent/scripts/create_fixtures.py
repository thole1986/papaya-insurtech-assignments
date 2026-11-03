"""Generate synthetic, self-contained interview cases. Never called by the app."""

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    (ROOT / "cases").mkdir(parents=True, exist_ok=True)
    texts = {
        "coverage": (
            "COV-01",
            "Coverage period",
            "Treatment must fall entirely between "
            "2026-01-01 and 2026-12-31 inclusive and before any effective lapse date.",
        ),
        "member": ("MEM-01", "Insured members", "Only member DEMO-MEMBER is insured."),
        "benefit": (
            "BEN-01",
            "Outpatient benefit",
            "Outpatient treatment is covered subject "
            "to eligibility, documentation, medical necessity and exclusions.",
        ),
        "documents": (
            "DOC-01",
            "Required evidence",
            "A complete claim form, invoice and medical "
            "report of the correct document type are required. Request missing or "
            "incomplete evidence before deciding the claim.",
        ),
        "medical": (
            "MED-01",
            "Medical necessity",
            "Treatment must be appropriate for the "
            "diagnosis under the demo medical rules. Unknown appropriateness requires "
            "additional medical evidence; inappropriate treatment is excluded.",
        ),
        "exclusion": (
            "EXC-COSMETIC",
            "Cosmetic exclusion",
            "Procedure cosmetic_surgery is excluded from cover. "
            "This demo policy has no accident exception.",
        ),
        "limit": (
            "LIM-01",
            "Annual insurer payout limit",
            "Annual outpatient insurer payout "
            "limit is VND 5000000. Previously used insurer payout in 2026 is VND 1000000. "
            "Cap payout at the remaining limit; partially approve when remaining limit "
            "is positive; reject if exhausted. Assessment does not reserve or pay funds.",
        ),
        "copay": (
            "COP-01",
            "Member copay",
            "Member copay is 20% of eligible submitted amount, "
            "rounded half up to whole VND, before capping insurer payout. Member also "
            "bears excess above remaining limit. No deductible applies.",
        ),
        "waiting": (
            "WAIT-01",
            "Waiting period",
            "Treatment may start 30 calendar days after "
            "2026-01-01, including day 30. Earlier treatment is excluded.",
        ),
    }
    policy = {
        "id": "POL-DEMO",
        "version": "v1",
        "status": "active",
        "coverage_start": "2026-01-01",
        "coverage_end": "2026-12-31",
        "lapse_date": None,
        "members": ["DEMO-MEMBER"],
        "waiting_days": 30,
        "usage_year": 2026,
        "benefits": {
            "outpatient": {
                "annual_limit": "5000000",
                "used_payout": "1000000",
                "copay_rate": "0.20",
                "required_documents": ["claim_form", "invoice", "medical_report"],
            }
        },
        "excluded_procedures": ["cosmetic_surgery"],
        "clauses": {
            key: {"id": f"POL-DEMO:v1:{value[0]}", "title": value[1], "text": value[2]}
            for key, value in texts.items()
        },
    }
    cases = [
        ("approval_001", "Straightforward outpatient approval", "APPROVE"),
        ("rejection_002", "Excluded cosmetic procedure", "REJECT"),
        ("more_info_003", "Missing medical report", "REQUEST_MORE_INFO"),
    ]
    for case_id, title, outcome in cases:
        documents = [
            {
                "id": f"{case_id}-{kind}",
                "owner_ref": case_id,
                "declared_type": kind,
                "actual_type": kind,
                "complete": True,
                "issues": [],
                "revision": 1,
            }
            for kind in ["claim_form", "invoice", "medical_report"]
        ]
        available = []
        if case_id == "more_info_003":
            available = [documents.pop()]
        claim = {
            "policy_id": policy["id"],
            "member_id": "DEMO-MEMBER",
            "claim_type": "outpatient",
            "amount": "3000000" if outcome == "REJECT" else "1000000",
            "currency": "VND",
            "diagnosis": "cosmetic_non_accident" if outcome == "REJECT" else "pharyngitis",
            "procedures": ["cosmetic_surgery"]
            if outcome == "REJECT"
            else ["consultation", "throat_test"],
            "treatment_start": "2026-06-10",
            "treatment_end": "2026-06-10",
            "document_ids": [doc["id"] for doc in documents],
        }
        expected = {"outcome": outcome}
        if outcome == "APPROVE":
            expected.update(
                covered_amount="800000",
                copay="200000",
                member_responsibility="200000",
                remaining_limit_after="3200000",
            )
        bundle = {
            "id": case_id,
            "title": title,
            "claim": claim,
            "policy": deepcopy(policy),
            "documents": documents,
            "available_documents": available,
            "expected": expected,
        }
        (ROOT / "cases" / f"{case_id}.json").write_text(
            json.dumps(bundle, indent=2) + "\n", encoding="utf-8"
        )
    rules = [
        {
            "id": "DEMO-MED:v1:PHARYNGITIS",
            "diagnosis": "pharyngitis",
            "allowed_procedures": ["consultation", "throat_test"],
            "explanation": "Synthetic interview rule: consultation and throat test "
            "match pharyngitis.",
        },
        {
            "id": "DEMO-MED:v1:COSMETIC",
            "diagnosis": "cosmetic_non_accident",
            "allowed_procedures": ["cosmetic_surgery"],
            "explanation": "Synthetic rule; medical appropriateness does not establish coverage.",
        },
    ]
    (ROOT / "medical_rules.json").write_text(json.dumps(rules, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
