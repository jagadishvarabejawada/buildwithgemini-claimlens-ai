"""Deterministic expense audit engine for ClaimLens AI."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
import math
from typing import Any, Dict, List, Optional

from app.policy import DEFAULT_POLICY, ExpensePolicy


def _parse_decimal(value: Any) -> Optional[Decimal]:
    """Parse a monetary value into Decimal, rejecting non-finite, negative, or invalid formats."""
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    try:
        dec = Decimal(str(value).strip())
        if dec.is_nan() or dec.is_infinite() or dec < 0:
            return None
        # Quantize to 2 decimal places (paise precision)
        return dec.quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None


def audit_expense(
    claim_id: Optional[str] = None,
    employee: Optional[str] = None,
    merchant: Optional[str] = None,
    receipt_date: Optional[str] = None,
    category: Optional[str] = None,
    currency: Optional[str] = None,
    claimed_amount: Any = None,
    receipt_amount: Any = None,
    receipt_reference: Optional[str] = None,
    policy: ExpensePolicy = DEFAULT_POLICY,
) -> Dict[str, Any]:
    """Deterministically audit an expense claim against company policy.

    Args:
        claim_id: Unique claim identifier.
        employee: Name or employee ID of the claimant.
        merchant: Vendor/merchant name.
        receipt_date: Date of receipt in YYYY-MM-DD format.
        category: Expense category (e.g. 'business_travel').
        currency: Expense currency (e.g. 'INR').
        claimed_amount: Amount submitted for reimbursement.
        receipt_amount: Amount shown on the supporting receipt.
        receipt_reference: Invoice or receipt transaction number.
        policy: The ExpensePolicy instance applied to this audit.

    Returns:
        Structured JSON audit dictionary with expense, policy, arithmetic,
        findings, audit_summary, and review_status.
    """
    findings: List[Dict[str, Any]] = []

    if not claim_id or not str(claim_id).strip():
        emp_tag = "".join(filter(str.isalnum, (employee or "AUDIT").split()[0])).upper()
        claim_id = f"CLM-{emp_tag}-001"

    raw_expense = {
        "claim_id": claim_id,
        "employee": employee,
        "merchant": merchant,
        "receipt_date": receipt_date,
        "category": category,
        "currency": currency,
        "claimed_amount": str(claimed_amount) if claimed_amount is not None else None,
        "receipt_amount": str(receipt_amount) if receipt_amount is not None else None,
        "receipt_reference": receipt_reference,
    }

    # 1. Required Field Validation
    required_fields = {
        "claim_id": claim_id,
        "employee": employee,
        "merchant": merchant,
        "receipt_date": receipt_date,
        "category": category,
        "currency": currency,
        "claimed_amount": claimed_amount,
        "receipt_amount": receipt_amount,
        "receipt_reference": receipt_reference,
    }

    for field_name, field_val in required_fields.items():
        if field_val is None or (isinstance(field_val, str) and not field_val.strip()):
            findings.append({
                "code": "MISSING_REQUIRED_FIELD",
                "severity": "HIGH",
                "observed_values": {"field": field_name, "value": field_val},
                "policy_id": policy.policy_id,
                "rule": "Employee, merchant, receipt date, category, currency, amounts, and receipt reference are required.",
                "explanation": f"Mandatory field '{field_name}' is missing or empty.",
                "recommended_next_action": f"Request claimant provide missing '{field_name}'.",
            })

    # 2. Date Validation
    if receipt_date and isinstance(receipt_date, str) and receipt_date.strip():
        try:
            datetime.strptime(receipt_date.strip(), "%Y-%m-%d")
        except ValueError:
            findings.append({
                "code": "INVALID_DATE_FORMAT",
                "severity": "MEDIUM",
                "observed_values": {"receipt_date": receipt_date},
                "policy_id": policy.policy_id,
                "rule": "Receipt date must be a valid date in YYYY-MM-DD format.",
                "explanation": f"Receipt date '{receipt_date}' could not be parsed as a valid YYYY-MM-DD date.",
                "recommended_next_action": "Verify receipt image/document for valid date.",
            })

    # 3. Monetary Validation
    dec_claimed = _parse_decimal(claimed_amount)
    dec_receipt = _parse_decimal(receipt_amount)

    if claimed_amount is not None and dec_claimed is None:
        findings.append({
            "code": "INVALID_CLAIMED_AMOUNT",
            "severity": "HIGH",
            "observed_values": {"claimed_amount": claimed_amount},
            "policy_id": policy.policy_id,
            "rule": "Claimed amount must be a valid, finite, non-negative number.",
            "explanation": f"Claimed amount '{claimed_amount}' is negative, non-finite, or malformed.",
            "recommended_next_action": "Request corrected positive reimbursement amount from claimant.",
        })

    if receipt_amount is not None and dec_receipt is None:
        findings.append({
            "code": "INVALID_RECEIPT_AMOUNT",
            "severity": "HIGH",
            "observed_values": {"receipt_amount": receipt_amount},
            "policy_id": policy.policy_id,
            "rule": "Receipt amount must be a valid, finite, non-negative number.",
            "explanation": f"Receipt amount '{receipt_amount}' is negative, non-finite, or malformed.",
            "recommended_next_action": "Inspect attached receipt for legible positive total amount.",
        })

    # 4. Scope & Policy Alignment (Currency and Category)
    currency_match = (
        currency and currency.strip().upper() == policy.currency.upper()
    )
    category_match = (
        category and category.strip().lower() == policy.category.lower()
    )

    if currency and not currency_match:
        findings.append({
            "code": "UNSUPPORTED_CURRENCY",
            "severity": "MEDIUM",
            "observed_values": {"submitted_currency": currency, "policy_currency": policy.currency},
            "policy_id": policy.policy_id,
            "rule": f"Standard automated policy applies to {policy.currency}.",
            "explanation": f"Submitted currency '{currency}' does not match standard policy currency '{policy.currency}'.",
            "recommended_next_action": "Forward to international finance desk for forex conversion and regional policy review.",
        })

    if category and not category_match:
        findings.append({
            "code": "UNSUPPORTED_CATEGORY",
            "severity": "MEDIUM",
            "observed_values": {"submitted_category": category, "policy_category": policy.category},
            "policy_id": policy.policy_id,
            "rule": f"Standard automated policy applies to {policy.category}.",
            "explanation": f"Category '{category}' does not match policy category '{policy.category}'.",
            "recommended_next_action": "Route claim to corresponding category policy reviewer.",
        })

    # 5. Arithmetic and Limits (only evaluate if both amounts are valid and currency/category match)
    arithmetic: Dict[str, Optional[str]] = {
        "claimed_amount": str(dec_claimed) if dec_claimed is not None else None,
        "receipt_amount": str(dec_receipt) if dec_receipt is not None else None,
        "policy_limit": str(policy.max_reimbursement),
        "claim_receipt_difference": None,
        "claimed_amount_above_limit": None,
        "receipt_amount_above_limit": None,
    }

    if dec_claimed is not None and dec_receipt is not None:
        claim_receipt_diff = dec_claimed - dec_receipt
        claimed_above_limit = max(dec_claimed - policy.max_reimbursement, Decimal("0.00"))
        receipt_above_limit = max(dec_receipt - policy.max_reimbursement, Decimal("0.00"))

        arithmetic["claim_receipt_difference"] = str(claim_receipt_diff)
        arithmetic["claimed_amount_above_limit"] = str(claimed_above_limit)
        arithmetic["receipt_amount_above_limit"] = str(receipt_above_limit)

        # Discrepancy: Claimed amount != Receipt amount
        if claim_receipt_diff != Decimal("0.00"):
            findings.append({
                "code": "CLAIM_RECEIPT_MISMATCH",
                "severity": "HIGH",
                "observed_values": {
                    "claimed_amount": str(dec_claimed),
                    "receipt_amount": str(dec_receipt),
                    "difference": str(claim_receipt_diff),
                },
                "policy_id": policy.policy_id,
                "rule": "Claimed amount must match the receipt amount.",
                "explanation": (
                    f"Claimed amount ({dec_claimed} {policy.currency}) does not match the receipt amount "
                    f"({dec_receipt} {policy.currency}). Discrepancy: {claim_receipt_diff} {policy.currency}."
                ),
                "recommended_next_action": "Reconcile claim with receipt line items; adjust reimbursement to verified receipt total.",
            })

        # Policy Limit Check (only if category & currency match standard policy)
        if currency_match and category_match:
            if claimed_above_limit > Decimal("0.00") or receipt_above_limit > Decimal("0.00"):
                findings.append({
                    "code": "POLICY_LIMIT_EXCEEDED",
                    "severity": "HIGH",
                    "observed_values": {
                        "policy_limit": str(policy.max_reimbursement),
                        "claimed_amount_above_limit": str(claimed_above_limit),
                        "receipt_amount_above_limit": str(receipt_above_limit),
                    },
                    "policy_id": policy.policy_id,
                    "rule": f"Maximum reimbursement per claim: {policy.max_reimbursement} {policy.currency}.",
                    "explanation": (
                        f"Expense exceeds policy threshold of {policy.max_reimbursement} {policy.currency}. "
                        f"Claimed amount above limit: {claimed_above_limit} {policy.currency}; "
                        f"Receipt amount above limit: {receipt_above_limit} {policy.currency}."
                    ),
                    "recommended_next_action": (
                        f"Cap approved reimbursement at policy ceiling ({policy.max_reimbursement} {policy.currency}) "
                        "or obtain executive manager exception approval."
                    ),
                })

    has_violations = len(findings) > 0

    return {
        "expense": raw_expense,
        "policy": {
            "policy_id": policy.policy_id,
            "version": policy.version,
            "category": policy.category,
            "currency": policy.currency,
            "max_reimbursement": str(policy.max_reimbursement),
            "require_receipt_match": policy.require_receipt_match,
        },
        "arithmetic": arithmetic,
        "findings": findings,
        "audit_summary": {
            "total_findings": len(findings),
            "has_discrepancies": has_violations,
            "policy_compliant": not has_violations,
            "summary_notes": (
                "Audit completed with discrepancies identified."
                if has_violations
                else "All policy checks passed without discrepancy."
            ),
        },
        "review_status": "pending_human_review",
    }
