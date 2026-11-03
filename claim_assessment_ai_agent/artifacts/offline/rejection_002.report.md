# Claim assessment 65890fd7-bfc4-4607-a6d1-57cdf36409aa

Mode: offline | Model: offline-deterministic-v1 | Revision: 1

## Document Review

```json
[
  {
    "document_id": "f1853e58-72b7-4308-b7e7-e9b4838fa14e:rejection_002-claim_form",
    "expected_type": "claim_form",
    "actual_type": "claim_form",
    "status": "complete",
    "issues": [],
    "evidence_id": "document:f1853e58-72b7-4308-b7e7-e9b4838fa14e:rejection_002-claim_form:v1"
  },
  {
    "document_id": "f1853e58-72b7-4308-b7e7-e9b4838fa14e:rejection_002-invoice",
    "expected_type": "invoice",
    "actual_type": "invoice",
    "status": "complete",
    "issues": [],
    "evidence_id": "document:f1853e58-72b7-4308-b7e7-e9b4838fa14e:rejection_002-invoice:v1"
  },
  {
    "document_id": "f1853e58-72b7-4308-b7e7-e9b4838fa14e:rejection_002-medical_report",
    "expected_type": "medical_report",
    "actual_type": "medical_report",
    "status": "complete",
    "issues": [],
    "evidence_id": "document:f1853e58-72b7-4308-b7e7-e9b4838fa14e:rejection_002-medical_report:v1"
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
  "findings": [
    {
      "code": "EXCLUDED_PROCEDURE",
      "explanation": "Submitted procedure is excluded.",
      "clause_ids": [
        "POL-DEMO:v1:EXC-COSMETIC"
      ],
      "evidence_refs": [
        "claim:procedures",
        "policy:exclusions"
      ]
    }
  ]
}
```

## Medical Necessity

```json
{
  "status": "NOT_EVALUATED",
  "explanation": "Policy eligibility failed: EXCLUDED_PROCEDURE",
  "rule_ids": []
}
```

## Benefit Calculation

```json
{
  "status": "NOT_EVALUATED",
  "submitted_amount": "3000000",
  "covered_amount": null,
  "copay": null,
  "eligible_insurer_amount": null,
  "limit_excess": null,
  "member_responsibility": null,
  "remaining_limit_before": null,
  "remaining_limit_after": null,
  "explanation": "Policy eligibility failed: EXCLUDED_PROCEDURE"
}
```

## Recommendation

```json
{
  "outcome": "REJECT",
  "reasons": [
    {
      "code": "EXCLUDED_PROCEDURE",
      "explanation": "Submitted procedure is excluded.",
      "clause_ids": [
        "POL-DEMO:v1:EXC-COSMETIC"
      ],
      "evidence_refs": [
        "claim:procedures",
        "policy:exclusions"
      ]
    }
  ]
}
```

## Policy Citations

```json
[
  {
    "id": "POL-DEMO:v1:EXC-COSMETIC",
    "title": "Cosmetic exclusion",
    "text": "Procedure cosmetic_surgery is excluded from cover. This demo policy has no accident exception."
  }
]
```

## Model summary

[Offline demo] REJECT: Submitted procedure is excluded.
