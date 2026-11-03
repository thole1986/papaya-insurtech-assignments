# Claim assessment 4bd1d8ca-a3cc-49b4-baf4-7a7296c84591

Mode: offline | Model: offline-deterministic-v1 | Revision: 1

## Document Review

```json
[
  {
    "document_id": "9acdad40-d514-4abb-9949-c804a484805c:more_info_003-claim_form",
    "expected_type": "claim_form",
    "actual_type": "claim_form",
    "status": "complete",
    "issues": [],
    "evidence_id": "document:9acdad40-d514-4abb-9949-c804a484805c:more_info_003-claim_form:v1"
  },
  {
    "document_id": "9acdad40-d514-4abb-9949-c804a484805c:more_info_003-invoice",
    "expected_type": "invoice",
    "actual_type": "invoice",
    "status": "complete",
    "issues": [],
    "evidence_id": "document:9acdad40-d514-4abb-9949-c804a484805c:more_info_003-invoice:v1"
  },
  {
    "document_id": null,
    "expected_type": "medical_report",
    "actual_type": null,
    "status": "missing",
    "issues": [
      "Submit a complete medical_report."
    ],
    "evidence_id": "missing:medical_report"
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
  "status": "NOT_EVALUATED",
  "explanation": "Required documents are missing, incomplete or the wrong type.",
  "rule_ids": []
}
```

## Benefit Calculation

```json
{
  "status": "NOT_EVALUATED",
  "submitted_amount": "1000000",
  "covered_amount": null,
  "copay": null,
  "eligible_insurer_amount": null,
  "limit_excess": null,
  "member_responsibility": null,
  "remaining_limit_before": null,
  "remaining_limit_after": null,
  "explanation": "Required documents are missing, incomplete or the wrong type."
}
```

## Recommendation

```json
{
  "outcome": "REQUEST_MORE_INFO",
  "reasons": [
    {
      "code": "DOCUMENT_REQUIRED:medical_report",
      "explanation": "Provide a complete, correctly typed medical_report.",
      "clause_ids": [
        "POL-DEMO:v1:DOC-01"
      ],
      "evidence_refs": [
        "missing:medical_report"
      ]
    }
  ]
}
```

## Policy Citations

```json
[
  {
    "id": "POL-DEMO:v1:DOC-01",
    "title": "Required evidence",
    "text": "A complete claim form, invoice and medical report of the correct document type are required. Request missing or incomplete evidence before deciding the claim."
  }
]
```

## Model summary

[Offline demo] REQUEST_MORE_INFO: Provide a complete, correctly typed medical_report.
