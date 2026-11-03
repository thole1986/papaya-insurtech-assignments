from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.models import Claim, ClaimInput, Policy
from app.domain.rules import calculate_benefit, medical_necessity, verify_policy
from app.repositories.fixtures import Catalog


@pytest.fixture
def inputs():
    case = Catalog().case("approval_001")
    return Claim(**case.claim.model_dump(), id="test", session_id="test"), case.policy


@pytest.mark.parametrize(
    "amount,used,expected,member",
    [
        ("1000000", "1000000", "800000", "200000"),
        ("10000000", "1000000", "4000000", "6000000"),
        ("1000000", "5000000", "0", "1000000"),
        ("1000000", "6000000", "0", "1000000"),
        ("3", "0", "2", "1"),
    ],
)
def test_money_invariants(inputs, amount, used, expected, member):
    claim, policy = inputs
    claim.amount = Decimal(amount)
    policy.benefits[claim.claim_type].used_payout = Decimal(used)
    result = calculate_benefit(claim, policy)
    assert result.covered_amount == Decimal(expected)
    assert result.member_responsibility == Decimal(member)
    assert result.covered_amount + result.member_responsibility == claim.amount
    assert 0 <= result.covered_amount <= result.remaining_limit_before
    assert result.remaining_limit_after >= 0


def test_half_up_rounding(inputs):
    claim, policy = inputs
    claim.amount = Decimal("5")
    policy.benefits[claim.claim_type].copay_rate = Decimal("0.1")
    assert calculate_benefit(claim, policy).copay == Decimal("1")


@pytest.mark.parametrize(
    "start,end,active,waiting",
    [
        ("2026-01-01", "2026-01-01", True, False),
        ("2026-01-30", "2026-01-30", True, False),
        ("2026-01-31", "2026-01-31", True, True),
        ("2026-12-31", "2026-12-31", True, True),
        ("2027-01-01", "2027-01-01", False, True),
        ("2025-12-31", "2025-12-31", False, False),
    ],
)
def test_coverage_and_waiting(inputs, start, end, active, waiting):
    claim, policy = inputs
    claim = Claim.model_validate(
        {**claim.model_dump(), "treatment_start": start, "treatment_end": end}
    )
    result = verify_policy(claim, policy)
    assert result.active_for_treatment is active
    assert result.waiting_period_satisfied is waiting


def test_lapse_effective_date_not_present_day_status(inputs):
    claim, policy = inputs
    policy.lapse_date = date(2026, 7, 1)
    policy.status = "lapsed"
    assert verify_policy(claim, policy).active_for_treatment
    policy.lapse_date = date(2026, 6, 10)
    assert not verify_policy(claim, policy).active_for_treatment


def test_invalid_inputs(inputs):
    claim, _ = inputs
    for changes in [
        {"amount": "-1"},
        {"amount": "0.5"},
        {"amount": "NaN"},
        {"treatment_end": "2025-01-01"},
        {"treatment_end": "2027-01-01"},
        {"document_ids": ["a", "a"]},
        {"currency": "USD"},
    ]:
        with pytest.raises(ValidationError):
            ClaimInput.model_validate(
                {
                    **claim.model_dump(exclude={"id", "session_id", "revision", "created_at"}),
                    **changes,
                }
            )


def test_policy_clause_registry_required(inputs):
    _, policy = inputs
    data = policy.model_dump()
    del data["clauses"]["limit"]
    with pytest.raises(ValidationError):
        Policy.model_validate(data)


def test_medical_rules_are_explicit():
    rules = Catalog().medical_rules
    assert medical_necessity("unknown", ["consultation"], rules).status == "UNKNOWN"
    assert medical_necessity("pharyngitis", ["cosmetic_surgery"], rules).status == "INAPPROPRIATE"
    assert medical_necessity("pharyngitis", ["consultation"], rules).status == "APPROPRIATE"
