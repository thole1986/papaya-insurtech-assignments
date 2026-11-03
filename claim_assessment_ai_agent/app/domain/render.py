import json

from app.domain.models import Report


def markdown_report(report: Report) -> str:
    """Export exact facts; user content is never interpreted as HTML in the UI."""
    sections = [
        f"# Claim assessment {report.assessment_id}",
        f"Mode: {report.mode} | Model: {report.model} | Revision: {report.claim_revision}",
    ]
    labels = {
        "document_review": "Document Review",
        "policy_verification": "Policy Verification",
        "medical_necessity": "Medical Necessity",
        "benefit_calculation": "Benefit Calculation",
        "recommendation": "Recommendation",
        "policy_citations": "Policy Citations",
    }
    data = report.model_dump(mode="json")
    for field, label in labels.items():
        sections.extend(
            [
                f"## {label}",
                "```json\n" + json.dumps(data[field], indent=2, ensure_ascii=False) + "\n```",
            ]
        )
    sections.extend(["## Model summary", report.narrative])
    return "\n\n".join(sections) + "\n"
