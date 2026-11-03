from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.domain.models import (
    BenefitResult,
    Claim,
    DocumentResult,
    Finding,
    MedicalResult,
    MedicalRule,
    Policy,
    PolicyVerification,
    Recommendation,
    Report,
)


def finding(policy: Policy, code: str, text: str, rules: list[str], refs: list[str]) -> Finding:
    return Finding(
        code=code,
        explanation=text,
        clause_ids=[policy.clauses[r].id for r in rules],
        evidence_refs=refs,
    )


def verify_policy(claim: Claim, policy: Policy) -> PolicyVerification:
    active = (
        policy.coverage_start <= claim.treatment_start <= claim.treatment_end <= policy.coverage_end
        and (policy.lapse_date is None or claim.treatment_end < policy.lapse_date)
    )
    member = claim.member_id in policy.members
    covered = claim.claim_type in policy.benefits
    waiting = claim.treatment_start >= policy.coverage_start + timedelta(days=policy.waiting_days)
    findings = []
    for ok, code, text, rule, refs in [
        (
            active,
            "OUTSIDE_COVERAGE",
            "Treatment is outside the effective coverage period.",
            "coverage",
            ["claim:treatment_period", "policy:coverage"],
        ),
        (
            member,
            "MEMBER_NOT_COVERED",
            "Member is not insured by this policy.",
            "member",
            ["claim:member_id", "policy:members"],
        ),
        (
            covered,
            "TYPE_NOT_COVERED",
            "Claim type has no policy benefit.",
            "benefit",
            ["claim:claim_type", "policy:benefits"],
        ),
        (
            waiting,
            "WAITING_PERIOD",
            "Treatment starts before the waiting period ends.",
            "waiting",
            ["claim:treatment_period", "policy:waiting_days"],
        ),
    ]:
        if not ok:
            findings.append(finding(policy, code, text, [rule], refs))
    if set(claim.procedures) & set(policy.excluded_procedures):
        findings.append(
            finding(
                policy,
                "EXCLUDED_PROCEDURE",
                "Submitted procedure is excluded.",
                ["exclusion"],
                ["claim:procedures", "policy:exclusions"],
            )
        )
    return PolicyVerification(
        policy_id=policy.id,
        policy_version=policy.version,
        active_for_treatment=active,
        member_covered=member,
        claim_type_covered=covered,
        waiting_period_satisfied=waiting,
        findings=findings,
    )


def required_documents(
    claim: Claim, policy: Policy, checked: list[DocumentResult]
) -> list[DocumentResult]:
    result = list(checked)
    benefit = policy.benefits.get(claim.claim_type)
    if benefit:
        for kind in benefit.required_documents:
            matching = [d for d in checked if d.expected_type == kind and d.actual_type == kind]
            if not matching:
                result.append(
                    DocumentResult(
                        document_id=None,
                        expected_type=kind,
                        actual_type=None,
                        status="missing",
                        issues=[f"Submit a complete {kind}."],
                        evidence_id=f"missing:{kind}",
                    )
                )
    return result


def document_findings(policy: Policy, claim: Claim, docs: list[DocumentResult]) -> list[Finding]:
    benefit = policy.benefits.get(claim.claim_type)
    required = benefit.required_documents if benefit else []
    findings = []
    for kind in required:
        # A complete correctly typed replacement satisfies a previously incomplete submission.
        if any(
            d.expected_type == kind and d.actual_type == kind and d.status == "complete"
            for d in docs
        ):
            continue
        refs = [d.evidence_id for d in docs if d.expected_type == kind]
        findings.append(
            finding(
                policy,
                f"DOCUMENT_REQUIRED:{kind}",
                f"Provide a complete, correctly typed {kind}.",
                ["documents"],
                refs or [f"missing:{kind}"],
            )
        )
    return findings


def medical_necessity(
    diagnosis: str, procedures: list[str], rules: list[MedicalRule]
) -> MedicalResult:
    rule = next((r for r in rules if r.diagnosis == diagnosis), None)
    if rule is None:
        return MedicalResult(status="UNKNOWN", explanation="No matching synthetic medical rule.")
    appropriate = set(procedures).issubset(rule.allowed_procedures)
    return MedicalResult(
        status="APPROPRIATE" if appropriate else "INAPPROPRIATE",
        explanation=rule.explanation
        if appropriate
        else "Procedure is outside the matching synthetic medical rule.",
        rule_ids=[rule.id],
    )


def calculate_benefit(claim: Claim, policy: Policy) -> BenefitResult:
    if claim.treatment_start.year != policy.usage_year:
        raise ValueError("Benefit usage snapshot does not cover the treatment year")
    benefit = policy.benefits[claim.claim_type]
    copay = (claim.amount * benefit.copay_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    eligible = claim.amount - copay
    remaining = max(benefit.annual_limit - benefit.used_payout, Decimal(0))
    payout = min(eligible, remaining)
    excess = eligible - payout
    return BenefitResult(
        status="CALCULATED",
        submitted_amount=claim.amount,
        covered_amount=payout,
        copay=copay,
        eligible_insurer_amount=eligible,
        limit_excess=excess,
        member_responsibility=copay + excess,
        remaining_limit_before=remaining,
        remaining_limit_after=remaining - payout,
        explanation="Copay first; insurer payout capped at remaining annual limit.",
    )


def decide(
    claim: Claim,
    policy: Policy,
    docs: list[DocumentResult],
    verification: PolicyVerification,
    medical: MedicalResult,
    benefit: BenefitResult,
) -> Recommendation:
    missing = document_findings(policy, claim, docs)
    if missing:
        return Recommendation(outcome="REQUEST_MORE_INFO", reasons=missing)
    if verification.findings:
        return Recommendation(outcome="REJECT", reasons=verification.findings)
    if medical.status == "UNKNOWN":
        return Recommendation(
            outcome="REQUEST_MORE_INFO",
            reasons=[
                finding(
                    policy,
                    "MEDICAL_EVIDENCE_REQUIRED",
                    "Provide additional evidence of medical necessity.",
                    ["medical"],
                    ["medical:result"],
                )
            ],
        )
    if medical.status == "INAPPROPRIATE":
        return Recommendation(
            outcome="REJECT",
            reasons=[
                finding(
                    policy,
                    "MEDICALLY_INAPPROPRIATE",
                    "Treatment does not match the diagnosis rule.",
                    ["medical"],
                    ["medical:result", *medical.rule_ids],
                )
            ],
        )
    if benefit.status != "CALCULATED" or medical.status != "APPROPRIATE":
        raise ValueError("Cannot decide an eligible claim before medical/benefit evaluation")
    if benefit.covered_amount == 0:
        return Recommendation(
            outcome="REJECT",
            reasons=[
                finding(
                    policy,
                    "NO_PAYABLE_BENEFIT",
                    "No insurer benefit remains payable.",
                    ["limit", "copay"],
                    ["benefit:result"],
                )
            ],
        )
    return Recommendation(
        outcome="APPROVE",
        reasons=[
            finding(
                policy,
                "ELIGIBLE_BENEFIT",
                "Documentation, coverage and medical checks passed; "
                "approve the calculated insurer amount, capped at the remaining limit.",
                [
                    "documents",
                    "coverage",
                    "member",
                    "benefit",
                    "waiting",
                    "exclusion",
                    "medical",
                    "copay",
                    "limit",
                ],
                [
                    "policy:verification",
                    "medical:result",
                    "benefit:result",
                    *[d.evidence_id for d in docs],
                ],
            )
        ],
    )


def validate_report(
    report: Report,
    claim: Claim,
    policy: Policy,
    docs: list[DocumentResult],
    medical: MedicalResult,
    benefit: BenefitResult,
) -> None:
    verification = verify_policy(claim, policy)
    expected = decide(claim, policy, docs, verification, medical, benefit)
    if report.recommendation != expected:
        raise ValueError("Recommendation/rule/evidence mapping differs from deterministic facts")
    if (
        report.document_review != docs
        or report.policy_verification != verification
        or report.medical_necessity != medical
        or report.benefit_calculation != benefit
    ):
        raise ValueError("Report facts differ from verified tool outputs")
    ids = {id_ for reason in expected.reasons for id_ in reason.clause_ids}
    expected_clauses = [c for c in policy.clauses.values() if c.id in ids]
    if report.policy_citations != expected_clauses:
        raise ValueError("Citation text/version differs from policy lookup")
    if benefit.status == "CALCULATED":
        if benefit != calculate_benefit(claim, policy):
            raise ValueError("Benefit calculation differs from policy")
        if (
            benefit.covered_amount + benefit.member_responsibility != claim.amount
            or benefit.covered_amount > benefit.remaining_limit_before
        ):
            raise ValueError("Money invariant violated")
