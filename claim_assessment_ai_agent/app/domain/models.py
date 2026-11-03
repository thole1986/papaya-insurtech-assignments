from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=15, decimal_places=0)]
Outcome = Literal["APPROVE", "REJECT", "REQUEST_MORE_INFO"]
DocType = Literal["claim_form", "invoice", "medical_report", "other"]


def uid() -> str:
    return str(uuid4())


def now() -> str:
    return datetime.now(UTC).isoformat()


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ClaimInput(Model):
    policy_id: str = Field(min_length=1, max_length=80)
    member_id: str = Field(min_length=1, max_length=80)
    claim_type: str = Field(min_length=1, max_length=80)
    amount: Money = Field(gt=0)
    currency: Literal["VND"] = "VND"
    diagnosis: str = Field(min_length=1, max_length=200)
    procedures: list[str] = Field(min_length=1, max_length=30)
    treatment_start: date
    treatment_end: date
    document_ids: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def valid_period(self) -> Self:
        if self.treatment_end < self.treatment_start:
            raise ValueError("treatment_end precedes treatment_start")
        if self.treatment_end.year != self.treatment_start.year:
            raise ValueError("Split treatment across benefit years into separate claims")
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("Duplicate document IDs")
        return self


class Claim(ClaimInput):
    id: str
    session_id: str
    revision: int = 1
    created_at: str = Field(default_factory=now)


class Clause(Model):
    id: str
    title: str
    text: str


class Benefit(Model):
    annual_limit: Money
    used_payout: Money
    copay_rate: Decimal = Field(ge=0, le=1)
    required_documents: list[DocType]


class Policy(Model):
    id: str
    version: str
    status: Literal["active", "lapsed"]
    coverage_start: date
    coverage_end: date
    lapse_date: date | None = None
    members: list[str]
    waiting_days: int = Field(ge=0)
    benefits: dict[str, Benefit]
    usage_year: int
    excluded_procedures: list[str]
    clauses: dict[str, Clause]

    @model_validator(mode="after")
    def valid_policy(self) -> Self:
        required = {
            "coverage",
            "member",
            "benefit",
            "documents",
            "medical",
            "exclusion",
            "limit",
            "copay",
            "waiting",
        }
        if not required.issubset(self.clauses):
            raise ValueError("Missing policy rule clauses")
        if self.coverage_end < self.coverage_start:
            raise ValueError("Invalid policy period")
        if self.status == "lapsed" and self.lapse_date is None:
            raise ValueError("Lapsed policy needs effective lapse_date")
        if len({c.id for c in self.clauses.values()}) != len(self.clauses):
            raise ValueError("Clause IDs must be unique")
        return self


class Document(Model):
    id: str
    owner_ref: str
    declared_type: DocType
    actual_type: DocType
    complete: bool
    issues: list[str] = Field(default_factory=list)
    revision: int = 1


class DocumentResult(Model):
    document_id: str | None
    expected_type: DocType
    actual_type: DocType | None
    status: Literal["complete", "incomplete", "missing"]
    issues: list[str]
    evidence_id: str


class MedicalRule(Model):
    id: str
    diagnosis: str
    allowed_procedures: list[str]
    explanation: str


class MedicalResult(Model):
    status: Literal["APPROPRIATE", "INAPPROPRIATE", "UNKNOWN", "NOT_EVALUATED"]
    explanation: str
    rule_ids: list[str] = Field(default_factory=list)


class BenefitResult(Model):
    status: Literal["CALCULATED", "NOT_EVALUATED"]
    submitted_amount: Money
    covered_amount: Money | None = None
    copay: Money | None = None
    eligible_insurer_amount: Money | None = None
    limit_excess: Money | None = None
    member_responsibility: Money | None = None
    remaining_limit_before: Money | None = None
    remaining_limit_after: Money | None = None
    explanation: str


class Finding(Model):
    code: str
    explanation: str
    clause_ids: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)


class PolicyVerification(Model):
    policy_id: str
    policy_version: str
    active_for_treatment: bool
    member_covered: bool
    claim_type_covered: bool
    waiting_period_satisfied: bool
    findings: list[Finding]


class Recommendation(Model):
    outcome: Outcome
    reasons: list[Finding] = Field(min_length=1)


class Report(Model):
    assessment_id: str
    claim_id: str
    session_id: str
    claim_revision: int
    created_at: str
    mode: Literal["offline", "live"]
    model: str
    prompt_version: str
    document_review: list[DocumentResult]
    policy_verification: PolicyVerification
    medical_necessity: MedicalResult
    benefit_calculation: BenefitResult
    recommendation: Recommendation
    policy_citations: list[Clause]
    narrative: str = ""


class ToolTrace(Model):
    id: str = Field(default_factory=uid)
    run_id: str
    sequence: int
    tool: str
    inputs: dict
    output: dict | None = None
    status: Literal["completed", "failed", "rejected"]
    error: str | None = None
    started_at: str
    ended_at: str
    duration_ms: int
    attempt: int
    mode: Literal["offline", "live"]


class Assessment(Model):
    id: str
    claim_id: str
    session_id: str
    version: int
    status: Literal["running", "completed", "failed"]
    snapshot: dict
    created_at: str
    report: Report | None = None
    error: str | None = None


class ReviewInput(Model):
    decision: Outcome
    reviewer: str = Field(min_length=1, max_length=100, pattern=r"\S")
    reason: str = Field(min_length=1, max_length=2000, pattern=r"\S")


class Review(ReviewInput):
    id: str
    assessment_id: str
    original_recommendation: Outcome
    created_at: str


class CreateClaim(Model):
    session_id: str = Field(min_length=1, max_length=80)
    case_id: str | None = Field(default=None, min_length=1, max_length=80)
    claim: ClaimInput | None = None

    @model_validator(mode="after")
    def one_source(self) -> Self:
        if (self.case_id is None) == (self.claim is None):
            raise ValueError("Provide exactly one of case_id or claim")
        return self


class AttachDocument(Model):
    document_id: str


class ChatInput(Model):
    assessment_id: str
    content: str = Field(min_length=1, max_length=4000, pattern=r"\S")


class Narrative(Model):
    summary: str = Field(min_length=1, max_length=4000)
    reason_codes: list[str]
    clause_ids: list[str]


class ToolProposal(Model):
    name: str
    args: dict
