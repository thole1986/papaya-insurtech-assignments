# Claim assessment 4cae3d1c-25b2-46ce-9fad-5cc39a8035cb

Mode: offline | Model: offline-deterministic-v1 | Revision: 1

## Document Review

```json
[
  {
    "document_id": "78619fab-a7db-4263-81a5-90a5f3a7e870:approval_001-claim_form",
    "expected_type": "claim_form",
    "actual_type": "claim_form",
    "status": "complete",
    "issues": [],
    "evidence_id": "document:78619fab-a7db-4263-81a5-90a5f3a7e870:approval_001-claim_form:v1"
  },
  {
    "document_id": "78619fab-a7db-4263-81a5-90a5f3a7e870:approval_001-invoice",
    "expected_type": "invoice",
    "actual_type": "invoice",
    "status": "complete",
    "issues": [],
    "evidence_id": "document:78619fab-a7db-4263-81a5-90a5f3a7e870:approval_001-invoice:v1"
  },
  {
    "document_id": "78619fab-a7db-4263-81a5-90a5f3a7e870:approval_001-medical_report",
    "expected_type": "medical_report",
    "actual_type": "medical_report",
    "status": "complete",
    "issues": [],
    "evidence_id": "document:78619fab-a7db-4263-81a5-90a5f3a7e870:approval_001-medical_report:v1"
  }
]
```

## Policy Verification

```json
{
  "policy_id": "POL-DEMO",
  "policy_version": "v1",
  "active_for_treatment": true,
  "member_covered": true,
  "claim_type_covered": true,
  "waiting_period_satisfied": true,
  "findings": []
}
```

## Medical Necessity

```json
{
  "status": "APPROPRIATE",
  "explanation": "Synthetic interview rule: consultation and throat test match pharyngitis.",
  "rule_ids": [
    "DEMO-MED:v1:PHARYNGITIS"
  ]
}
```

## Benefit Calculation

```json
{
  "status": "CALCULATED",
  "submitted_amount": "1000000",
  "covered_amount": "800000",
  "copay": "200000",
  "eligible_insurer_amount": "800000",
  "limit_excess": "0",
  "member_responsibility": "200000",
  "remaining_limit_before": "4000000",
  "remaining_limit_after": "3200000",
  "explanation": "Copay first; insurer payout capped at remaining annual limit."
}
```

## Recommendation

```json
{
  "outcome": "APPROVE",
  "reasons": [
    {
      "code": "ELIGIBLE_BENEFIT",
      "explanation": "Documentation, coverage and medical checks passed; approve the calculated insurer amount, capped at the remaining limit.",
      "clause_ids": [
        "POL-DEMO:v1:DOC-01",
        "POL-DEMO:v1:COV-01",
        "POL-DEMO:v1:MEM-01",
        "POL-DEMO:v1:BEN-01",
        "POL-DEMO:v1:WAIT-01",
        "POL-DEMO:v1:EXC-COSMETIC",
        "POL-DEMO:v1:MED-01",
        "POL-DEMO:v1:COP-01",
        "POL-DEMO:v1:LIM-01"
      ],
      "evidence_refs": [
        "policy:verification",
        "medical:result",
        "benefit:result",
        "document:78619fab-a7db-4263-81a5-90a5f3a7e870:approval_001-claim_form:v1",
        "document:78619fab-a7db-4263-81a5-90a5f3a7e870:approval_001-invoice:v1",
        "document:78619fab-a7db-4263-81a5-90a5f3a7e870:approval_001-medical_report:v1"
      ]
    }
  ]
}
```

## Policy Citations

```json
[
  {
    "id": "POL-DEMO:v1:COV-01",
    "title": "Coverage period",
    "text": "Treatment must fall entirely between 2026-01-01 and 2026-12-31 inclusive and before any effective lapse date."
  },
  {
    "id": "POL-DEMO:v1:MEM-01",
    "title": "Insured members",
    "text": "Only member DEMO-MEMBER is insured."
  },
  {
    "id": "POL-DEMO:v1:BEN-01",
    "title": "Outpatient benefit",
    "text": "Outpatient treatment is covered subject to eligibility, documentation, medical necessity and exclusions."
  },
  {
    "id": "POL-DEMO:v1:DOC-01",
    "title": "Required evidence",
    "text": "A complete claim form, invoice and medical report of the correct document type are required. Request missing or incomplete evidence before deciding the claim."
  },
  {
    "id": "POL-DEMO:v1:MED-01",
    "title": "Medical necessity",
    "text": "Treatment must be appropriate for the diagnosis under the demo medical rules. Unknown appropriateness requires additional medical evidence; inappropriate treatment is excluded."
  },
  {
    "id": "POL-DEMO:v1:EXC-COSMETIC",
    "title": "Cosmetic exclusion",
    "text": "Procedure cosmetic_surgery is excluded from cover. This demo policy has no accident exception."
  },
  {
    "id": "POL-DEMO:v1:LIM-01",
    "title": "Annual insurer payout limit",
    "text": "Annual outpatient insurer payout limit is VND 5000000. Previously used insurer payout in 2026 is VND 1000000. Cap payout at the remaining limit; partially approve when remaining limit is positive; reject if exhausted. Assessment does not reserve or pay funds."
  },
  {
    "id": "POL-DEMO:v1:COP-01",
    "title": "Member copay",
    "text": "Member copay is 20% of eligible submitted amount, rounded half up to whole VND, before capping insurer payout. Member also bears excess above remaining limit. No deductible applies."
  },
  {
    "id": "POL-DEMO:v1:WAIT-01",
    "title": "Waiting period",
    "text": "Treatment may start 30 calendar days after 2026-01-01, including day 30. Earlier treatment is excluded."
  }
]
```

## Model summary

[Offline demo] APPROVE: Documentation, coverage and medical checks passed; approve the calculated insurer amount, capped at the remaining limit.
