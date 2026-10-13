"""Synthetic seed records for ClaimLens AI workshop demo data."""

from typing import Any, Dict, List, Optional
from google.cloud import firestore

# Verified Project ID per workshop instruction:
# Hardcoded to prevent project number resolution on Agent Platform
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-cff970f17c66"
COLLECTION_NAME = "expense_audits"

# 3 Synthetic Workshop Demo Records
SEED_RECORDS: List[Dict[str, Any]] = [
    {
        "claim_id": "CLM-DEMO-VALID-001",
        "employee": "Aarav Sharma",
        "merchant": "Hotel Taj Residency",
        "receipt_date": "2026-10-10",
        "category": "business_travel",
        "currency": "INR",
        "claimed_amount": 690000,  # 6,900.00 INR in paise
        "receipt_amount": 690000,  # 6,900.00 INR in paise
        "policy_id": "PP-DEMO-001",
        "policy_version": "1.0",
        "findings": [],
        "audit_summary": {
            "total_findings": 0,
            "has_discrepancies": False,
            "policy_compliant": True,
            "summary_notes": "All policy checks passed without discrepancy.",
        },
        "review_status": "pending_human_review",
        "created_at": "2026-10-10T10:00:00Z",
        "is_demo_data": True,
        "demo_note": "Workshop synthetic demo record - Valid",
    },
    {
        "claim_id": "CLM-DEMO-MISMATCH-002",
        "employee": "Priya Patel",
        "merchant": "BlueDart Courier & Transit",
        "receipt_date": "2026-10-11",
        "category": "business_travel",
        "currency": "INR",
        "claimed_amount": 700000,  # 7,000.00 INR in paise
        "receipt_amount": 690000,  # 6,900.00 INR in paise
        "policy_id": "PP-DEMO-001",
        "policy_version": "1.0",
        "findings": [
            {
                "code": "CLAIM_RECEIPT_MISMATCH",
                "severity": "HIGH",
                "observed_values": {
                    "claimed_amount": "7000.00",
                    "receipt_amount": "6900.00",
                    "difference": "100.00",
                },
                "policy_id": "PP-DEMO-001",
                "rule": "Claimed amount must match the receipt amount.",
                "explanation": "Claimed amount (7000.00 INR) does not match the receipt amount (6900.00 INR). Discrepancy: 100.00 INR.",
                "recommended_next_action": "Reconcile claim with receipt line items; adjust reimbursement to verified receipt total.",
            }
        ],
        "audit_summary": {
            "total_findings": 1,
            "has_discrepancies": True,
            "policy_compliant": False,
            "summary_notes": "Audit completed with discrepancies identified.",
        },
        "review_status": "pending_human_review",
        "created_at": "2026-10-11T12:00:00Z",
        "is_demo_data": True,
        "demo_note": "Workshop synthetic demo record - Mismatch",
    },
    {
        "claim_id": "CLM-DEMO-OVERLIMIT-003",
        "employee": "Rohan Verma",
        "merchant": "Grand Hyatt Mumbai",
        "receipt_date": "2026-10-12",
        "category": "business_travel",
        "currency": "INR",
        "claimed_amount": 840000,  # 8,400.00 INR in paise
        "receipt_amount": 840000,  # 8,400.00 INR in paise
        "policy_id": "PP-DEMO-001",
        "policy_version": "1.0",
        "findings": [
            {
                "code": "POLICY_LIMIT_EXCEEDED",
                "severity": "HIGH",
                "observed_values": {
                    "policy_limit": "7500.00",
                    "claimed_amount_above_limit": "900.00",
                    "receipt_amount_above_limit": "900.00",
                },
                "policy_id": "PP-DEMO-001",
                "rule": "Maximum reimbursement per claim: 7500.00 INR.",
                "explanation": "Expense exceeds policy threshold of 7500.00 INR. Claimed amount above limit: 900.00 INR; Receipt amount above limit: 900.00 INR.",
                "recommended_next_action": "Cap approved reimbursement at policy ceiling (7500.00 INR) or obtain executive manager exception approval.",
            }
        ],
        "audit_summary": {
            "total_findings": 1,
            "has_discrepancies": True,
            "policy_compliant": False,
            "summary_notes": "Audit completed with discrepancies identified.",
        },
        "review_status": "pending_human_review",
        "created_at": "2026-10-12T14:30:00Z",
        "is_demo_data": True,
        "demo_note": "Workshop synthetic demo record - Over-limit",
    },
]


def seed_firestore(client: Optional[firestore.Client] = None) -> List[str]:
    """Insert synthetic demo records into Firestore expense_audits collection."""
    if client is None:
        client = firestore.Client(project=FIRESTORE_PROJECT_ID)

    inserted_ids = []
    for record in SEED_RECORDS:
        claim_id = record["claim_id"]
        doc_ref = client.collection(COLLECTION_NAME).document(claim_id)
        doc_ref.set(record)
        inserted_ids.append(claim_id)

    return inserted_ids


if __name__ == "__main__":
    print(f"Prepared {len(SEED_RECORDS)} synthetic demo records for {COLLECTION_NAME}.")
