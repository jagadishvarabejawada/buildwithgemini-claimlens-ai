"""Deterministic test suite for ClaimLens AI expense audit engine."""

import pytest
from app.audit import audit_expense


def test_scenario_a_valid_claim():
    """Scenario A: Valid claim within limits and matching receipt.
    Claim 6900; receipt 6900; limit 7500.
    Expected: No monetary violations, pending human review.
    """
    result = audit_expense(
        claim_id="CLM-001-A",
        employee="Aarav Sharma",
        merchant="Hotel Taj Residency",
        receipt_date="2026-10-10",
        category="business_travel",
        currency="INR",
        claimed_amount=6900,
        receipt_amount=6900,
        receipt_reference="INV-2026-8801",
    )

    assert result["review_status"] == "pending_human_review"
    assert result["audit_summary"]["policy_compliant"] is True
    assert result["audit_summary"]["has_discrepancies"] is False
    assert len(result["findings"]) == 0

    arithmetic = result["arithmetic"]
    assert arithmetic["claimed_amount"] == "6900.00"
    assert arithmetic["receipt_amount"] == "6900.00"
    assert arithmetic["policy_limit"] == "7500.00"
    assert arithmetic["claim_receipt_difference"] == "0.00"
    assert arithmetic["claimed_amount_above_limit"] == "0.00"
    assert arithmetic["receipt_amount_above_limit"] == "0.00"


def test_scenario_b_mismatch_claim():
    """Scenario B: Discrepancy between claim and receipt.
    Claim 7000; receipt 6900; limit 7500.
    Expected: Difference 100, no limit excess.
    """
    result = audit_expense(
        claim_id="CLM-002-B",
        employee="Priya Patel",
        merchant="BlueDart Courier & Transit",
        receipt_date="2026-10-11",
        category="business_travel",
        currency="INR",
        claimed_amount=7000,
        receipt_amount=6900,
        receipt_reference="INV-2026-8802",
    )

    assert result["review_status"] == "pending_human_review"
    assert result["audit_summary"]["policy_compliant"] is False
    assert result["audit_summary"]["has_discrepancies"] is True

    arithmetic = result["arithmetic"]
    assert arithmetic["claimed_amount"] == "7000.00"
    assert arithmetic["receipt_amount"] == "6900.00"
    assert arithmetic["claim_receipt_difference"] == "100.00"
    assert arithmetic["claimed_amount_above_limit"] == "0.00"
    assert arithmetic["receipt_amount_above_limit"] == "0.00"

    finding_codes = [f["code"] for f in result["findings"]]
    assert "CLAIM_RECEIPT_MISMATCH" in finding_codes
    assert "POLICY_LIMIT_EXCEEDED" not in finding_codes


def test_scenario_c_over_limit_claim():
    """Scenario C: Expense over policy limit without mismatch.
    Claim 8400; receipt 8400; limit 7500.
    Expected: Claimed & receipt limit excess 900, no mismatch.
    """
    result = audit_expense(
        claim_id="CLM-003-C",
        employee="Rohan Verma",
        merchant="Grand Hyatt Mumbai",
        receipt_date="2026-10-12",
        category="business_travel",
        currency="INR",
        claimed_amount=8400,
        receipt_amount=8400,
        receipt_reference="INV-2026-8803",
    )

    assert result["review_status"] == "pending_human_review"
    assert result["audit_summary"]["policy_compliant"] is False
    assert result["audit_summary"]["has_discrepancies"] is True

    arithmetic = result["arithmetic"]
    assert arithmetic["claimed_amount"] == "8400.00"
    assert arithmetic["receipt_amount"] == "8400.00"
    assert arithmetic["claim_receipt_difference"] == "0.00"
    assert arithmetic["claimed_amount_above_limit"] == "900.00"
    assert arithmetic["receipt_amount_above_limit"] == "900.00"

    finding_codes = [f["code"] for f in result["findings"]]
    assert "CLAIM_RECEIPT_MISMATCH" not in finding_codes
    assert "POLICY_LIMIT_EXCEEDED" in finding_codes


def test_scenario_d_combined_workshop_demo():
    """Scenario D: Combined mismatch and policy limit excess.
    Claim 8400; receipt 6900; limit 7500.
    Expected:
      Claim/receipt difference: 1500.00
      Claimed amount above limit: 900.00
      Receipt amount above limit: 0.00
      Pending human review.
    """
    result = audit_expense(
        claim_id="CLM-004-D",
        employee="Ananya Roy",
        merchant="AeroClub Executive Transit",
        receipt_date="2026-10-13",
        category="business_travel",
        currency="INR",
        claimed_amount=8400,
        receipt_amount=6900,
        receipt_reference="INV-2026-8804",
    )

    assert result["review_status"] == "pending_human_review"
    assert result["audit_summary"]["policy_compliant"] is False
    assert result["audit_summary"]["has_discrepancies"] is True

    arithmetic = result["arithmetic"]
    assert arithmetic["claimed_amount"] == "8400.00"
    assert arithmetic["receipt_amount"] == "6900.00"
    assert arithmetic["claim_receipt_difference"] == "1500.00"
    assert arithmetic["claimed_amount_above_limit"] == "900.00"
    assert arithmetic["receipt_amount_above_limit"] == "0.00"

    finding_codes = [f["code"] for f in result["findings"]]
    assert "CLAIM_RECEIPT_MISMATCH" in finding_codes
    assert "POLICY_LIMIT_EXCEEDED" in finding_codes


def test_missing_required_fields():
    """Test flagging missing mandatory information without inventing values."""
    result = audit_expense(
        claim_id="CLM-005-MISSING",
        employee="Vikram Malhotra",
        merchant=None,  # Missing merchant
        receipt_date="",  # Empty date
        category="business_travel",
        currency="INR",
        claimed_amount=1500,
        receipt_amount=None,  # Missing receipt amount
        receipt_reference=None,
    )

    assert result["review_status"] == "pending_human_review"
    assert result["audit_summary"]["policy_compliant"] is False

    missing_fields = [
        f["observed_values"]["field"]
        for f in result["findings"]
        if f["code"] == "MISSING_REQUIRED_FIELD"
    ]
    assert "merchant" in missing_fields
    assert "receipt_date" in missing_fields
    assert "receipt_amount" in missing_fields
    assert "receipt_reference" in missing_fields


def test_invalid_negative_and_malformed_amounts():
    """Test rejection of negative, non-finite, and malformed amounts."""
    result = audit_expense(
        claim_id="CLM-006-INVALID",
        employee="Siddharth Rao",
        merchant="Metro Cab Services",
        receipt_date="2026-10-10",
        category="business_travel",
        currency="INR",
        claimed_amount=-500,
        receipt_amount="invalid_currency_str",
        receipt_reference="REF-9921",
    )

    assert result["review_status"] == "pending_human_review"
    finding_codes = [f["code"] for f in result["findings"]]
    assert "INVALID_CLAIMED_AMOUNT" in finding_codes
    assert "INVALID_RECEIPT_AMOUNT" in finding_codes


def test_unsupported_currency_and_category():
    """Test policy review findings for unsupported currencies or categories."""
    result = audit_expense(
        claim_id="CLM-007-INTL",
        employee="Kavita Iyer",
        merchant="Tokyo Shinkansen",
        receipt_date="2026-10-10",
        category="equipment_purchase",
        currency="USD",
        claimed_amount=100,
        receipt_amount=100,
        receipt_reference="TX-9901",
    )

    finding_codes = [f["code"] for f in result["findings"]]
    assert "UNSUPPORTED_CURRENCY" in finding_codes
    assert "UNSUPPORTED_CATEGORY" in finding_codes
    assert result["review_status"] == "pending_human_review"
