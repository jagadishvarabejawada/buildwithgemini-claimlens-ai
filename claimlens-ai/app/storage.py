"""Firestore persistent storage module for ClaimLens AI expense audits."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional
from google.cloud import firestore

# Verified Project ID per workshop instruction:
# Hardcoded to prevent project number resolution on Agent Platform
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-cff970f17c66"
COLLECTION_NAME = "expense_audits"


def amount_to_paise(val: Any) -> int:
    """Convert a monetary value to integer paise (1 INR = 100 paise)."""
    if val is None:
        return 0
    try:
        dec = Decimal(str(val).strip())
        paise = int((dec * Decimal("100")).to_integral_value())
        return paise
    except (InvalidOperation, TypeError, ValueError):
        return 0


def paise_to_inr_str(paise: int) -> str:
    """Convert integer paise to standard 2-decimal INR string."""
    dec = Decimal(paise) / Decimal("100")
    return f"{dec:.2f}"


def get_firestore_client(_client: Any = None) -> firestore.Client:
    """Return provided client or create one using the hardcoded project ID."""
    if _client is not None:
        return _client
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


def save_audit_record(
    claim_id: str,
    employee: str = "",
    merchant: str = "",
    receipt_date: str = "",
    category: str = "business_travel",
    currency: str = "INR",
    claimed_amount: float = 0.0,
    receipt_amount: float = 0.0,
    policy_id: str = "PP-DEMO-001",
    policy_version: str = "1.0",
    _client: Any = None,
) -> Dict[str, Any]:
    """Save an expense audit record to Firestore without silent overwrite.

    Args:
        claim_id: Unique claim identifier.
        employee: Name of the claimant.
        merchant: Vendor/merchant name.
        receipt_date: Date of receipt in YYYY-MM-DD.
        category: Expense category.
        currency: Expense currency.
        claimed_amount: Submitted claim amount in standard currency units.
        receipt_amount: Verified receipt amount in standard currency units.
        policy_id: Policy ID (default: 'PP-DEMO-001').
        policy_version: Policy version string (default: '1.0').
        _client: Internal client override (for testing/mocking).

    Returns:
        Result dictionary indicating success or rejection.
    """
    if not claim_id or not str(claim_id).strip():
        return {
            "status": "error",
            "message": "Cannot save audit record: 'claim_id' is required.",
        }

    cid = str(claim_id).strip()
    db = get_firestore_client(_client)
    doc_ref = db.collection(COLLECTION_NAME).document(cid)

    # 1. Prevent silent overwrite
    doc_snap = doc_ref.get()
    if doc_snap.exists:
        return {
            "status": "error",
            "message": f"Conflict: Claim ID '{cid}' already exists in collection '{COLLECTION_NAME}'. Silent overwrite is rejected.",
        }

    # Record schema per workshop spec:
    record = {
        "claim_id": cid,
        "employee": str(employee),
        "merchant": str(merchant),
        "receipt_date": str(receipt_date),
        "category": str(category),
        "currency": str(currency),
        "claimed_amount": amount_to_paise(claimed_amount),
        "receipt_amount": amount_to_paise(receipt_amount),
        "policy_id": str(policy_id),
        "policy_version": str(policy_version),
        "findings": [],
        "audit_summary": {},
        "review_status": "pending_human_review",  # Human review required
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    doc_ref.set(record)

    return {
        "status": "success",
        "claim_id": cid,
        "message": f"Audit record for claim '{cid}' successfully saved.",
        "record": record,
    }


def get_audit_record(
    claim_id: str,
    _client: Any = None,
) -> Dict[str, Any]:
    """Fetch an audit record by claim_id from Firestore.

    Args:
        claim_id: Unique claim identifier.
        _client: Internal client override (for testing/mocking).

    Returns:
        Dictionary with record data if found, or not_found status.
    """
    if not claim_id or not str(claim_id).strip():
        return {
            "status": "error",
            "message": "'claim_id' is required to fetch an audit record.",
        }

    cid = str(claim_id).strip()
    db = get_firestore_client(_client)
    doc_ref = db.collection(COLLECTION_NAME).document(cid)
    doc_snap = doc_ref.get()

    if not doc_snap.exists:
        return {
            "status": "not_found",
            "message": f"No audit record found for claim ID '{cid}'.",
        }

    return {
        "status": "success",
        "claim_id": cid,
        "record": doc_snap.to_dict(),
    }


def list_latest_audits(
    limit: int = 10,
    _client: Any = None,
) -> Dict[str, Any]:
    """List the latest expense audit records from Firestore.

    Args:
        limit: Maximum number of audits to return (default: 10).
        _client: Internal client override (for testing/mocking).

    Returns:
        Dictionary containing list of audit records.
    """
    db = get_firestore_client(_client)
    query = (
        db.collection(COLLECTION_NAME)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )

    docs = query.stream()
    records = [doc.to_dict() for doc in docs]

    return {
        "status": "success",
        "count": len(records),
        "records": records,
    }
