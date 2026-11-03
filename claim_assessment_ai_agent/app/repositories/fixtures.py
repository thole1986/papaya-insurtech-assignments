import json
from pathlib import Path

from app.core.config import ROOT
from app.core.errors import AppError
from app.domain.models import ClaimInput, Document, MedicalRule, Model, Policy


class Case(Model):
    id: str
    title: str
    claim: ClaimInput
    policy: Policy
    documents: list[Document]
    available_documents: list[Document]
    expected: dict


class Catalog:
    """Trusted local fixtures; expected labels never enter agent context."""

    def __init__(self, root: Path = ROOT / "data"):
        self.cases = {
            case.id: case
            for path in sorted((root / "cases").glob("*.json"))
            if (case := Case.model_validate_json(path.read_text(encoding="utf-8")))
        }
        self.medical_rules = [
            MedicalRule.model_validate(item)
            for item in json.loads((root / "medical_rules.json").read_text(encoding="utf-8"))
        ]
        self.policies: dict[str, Policy] = {}
        for case in self.cases.values():
            previous = self.policies.get(case.policy.id)
            if previous and previous != case.policy:
                raise ValueError("Conflicting policies in fixture catalog")
            self.policies[case.policy.id] = case.policy

    def case(self, case_id: str) -> Case:
        if case_id not in self.cases:
            raise AppError(404, "case_not_found", "Unknown demo case")
        return self.cases[case_id].model_copy(deep=True)

    def policy(self, policy_id: str) -> Policy:
        if policy_id not in self.policies:
            raise AppError(404, "policy_not_found", "Unknown policy ID")
        return self.policies[policy_id].model_copy(deep=True)
