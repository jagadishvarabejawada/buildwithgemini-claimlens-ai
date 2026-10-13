"""Unit tests for ClaimLens AI Firestore storage engine with local mocking."""

from unittest.mock import MagicMock
import pytest

from app.audit import audit_expense
from app.seed_data import SEED_RECORDS, seed_firestore
from app.storage import (
    COLLECTION_NAME,
    FIRESTORE_PROJECT_ID,
    amount_to_paise,
    get_audit_record,
    list_latest_audits,
    paise_to_inr_str,
    save_audit_record,
)


def test_hardcoded_project_id():
    """Verify that the project ID is hardcoded and matches gcloud config value."""
    assert FIRESTORE_PROJECT_ID == "qwiklabs-gcp-03-cff970f17c66"
    assert COLLECTION_NAME == "expense_audits"


def test_paise_conversion():
    """Verify monetary conversion to and from integer paise."""
    assert amount_to_paise(6900) == 690000
    assert amount_to_paise("6900.50") == 690050
    assert amount_to_paise(8400) == 840000
    assert amount_to_paise(None) == 0
    assert amount_to_paise("invalid") == 0

    assert paise_to_inr_str(690000) == "6900.00"
    assert paise_to_inr_str(690050) == "6900.50"
    assert paise_to_inr_str(840000) == "8400.00"


def test_save_audit_record_success():
    """Test successful save without silent overwrite."""
    mock_client = MagicMock()
    mock_coll = MagicMock()
    mock_doc = MagicMock()
    mock_snap = MagicMock()

    mock_snap.exists = False
    mock_doc.get.return_value = mock_snap
    mock_coll.document.return_value = mock_doc
    mock_client.collection.return_value = mock_coll

    res = save_audit_record(
        claim_id="CLM-TEST-001",
        employee="Aarav Sharma",
        merchant="Hotel Taj",
        receipt_date="2026-10-10",
        category="business_travel",
        currency="INR",
        claimed_amount=6900,
        receipt_amount=6900,
        _client=mock_client,
    )

    assert res["status"] == "success"
    assert res["claim_id"] == "CLM-TEST-001"
    mock_doc.set.assert_called_once()
    saved_payload = mock_doc.set.call_args[0][0]

    assert saved_payload["claim_id"] == "CLM-TEST-001"
    assert saved_payload["claimed_amount"] == 690000  # Stored as integer paise
    assert saved_payload["receipt_amount"] == 690000  # Stored as integer paise
    assert saved_payload["review_status"] == "pending_human_review"
    assert "created_at" in saved_payload


def test_save_audit_record_rejects_silent_overwrite():
    """Test that saving rejects existing claim_id to avoid silent overwrite."""
    mock_client = MagicMock()
    mock_coll = MagicMock()
    mock_doc = MagicMock()
    mock_snap = MagicMock()

    mock_snap.exists = True  # Already exists in Firestore!
    mock_doc.get.return_value = mock_snap
    mock_coll.document.return_value = mock_doc
    mock_client.collection.return_value = mock_coll

    res = save_audit_record(
        claim_id="CLM-EXISTING-999",
        employee="Priya Patel",
        claimed_amount=7000,
        receipt_amount=6900,
        _client=mock_client,
    )

    assert res["status"] == "error"
    assert "already exists" in res["message"]
    mock_doc.set.assert_not_called()


def test_get_audit_record_found():
    """Test fetching an existing audit record."""
    mock_client = MagicMock()
    mock_coll = MagicMock()
    mock_doc = MagicMock()
    mock_snap = MagicMock()

    mock_snap.exists = True
    mock_snap.to_dict.return_value = {
        "claim_id": "CLM-FETCH-123",
        "employee": "Rohan Verma",
        "claimed_amount": 840000,
        "review_status": "pending_human_review",
    }
    mock_doc.get.return_value = mock_snap
    mock_coll.document.return_value = mock_doc
    mock_client.collection.return_value = mock_coll

    res = get_audit_record("CLM-FETCH-123", _client=mock_client)
    assert res["status"] == "success"
    assert res["record"]["claim_id"] == "CLM-FETCH-123"
    assert res["record"]["review_status"] == "pending_human_review"


def test_get_audit_record_not_found():
    """Test fetching a non-existent audit record."""
    mock_client = MagicMock()
    mock_coll = MagicMock()
    mock_doc = MagicMock()
    mock_snap = MagicMock()

    mock_snap.exists = False
    mock_doc.get.return_value = mock_snap
    mock_coll.document.return_value = mock_doc
    mock_client.collection.return_value = mock_coll

    res = get_audit_record("NON-EXISTENT", _client=mock_client)
    assert res["status"] == "not_found"


def test_list_latest_audits():
    """Test listing latest audit records."""
    mock_client = MagicMock()
    mock_coll = MagicMock()
    mock_query = MagicMock()

    mock_doc1 = MagicMock()
    mock_doc1.to_dict.return_value = {"claim_id": "CLM-002", "created_at": "2026-10-12T10:00:00Z"}
    mock_doc2 = MagicMock()
    mock_doc2.to_dict.return_value = {"claim_id": "CLM-001", "created_at": "2026-10-10T10:00:00Z"}

    mock_query.stream.return_value = [mock_doc1, mock_doc2]
    mock_query.limit.return_value = mock_query
    mock_coll.order_by.return_value = mock_query
    mock_client.collection.return_value = mock_coll

    res = list_latest_audits(limit=5, _client=mock_client)
    assert res["status"] == "success"
    assert res["count"] == 2
    assert res["records"][0]["claim_id"] == "CLM-002"


def test_seed_records_schema_and_integrity():
    """Verify the 3 synthetic workshop demo records adhere to specifications."""
    assert len(SEED_RECORDS) == 3

    categories = {r["claim_id"]: r for r in SEED_RECORDS}
    valid = categories["CLM-DEMO-VALID-001"]
    mismatch = categories["CLM-DEMO-MISMATCH-002"]
    overlimit = categories["CLM-DEMO-OVERLIMIT-003"]

    # All must be marked as demo data with review_status=pending_human_review
    for r in SEED_RECORDS:
        assert r["is_demo_data"] is True
        assert r["review_status"] == "pending_human_review"
        assert isinstance(r["claimed_amount"], int)
        assert isinstance(r["receipt_amount"], int)

    # Valid record (6900 INR = 690000 paise)
    assert valid["claimed_amount"] == 690000
    assert valid["receipt_amount"] == 690000
    assert len(valid["findings"]) == 0

    # Mismatch record (Claim 7000 INR = 700000 paise; Receipt 6900 INR = 690000 paise)
    assert mismatch["claimed_amount"] == 700000
    assert mismatch["receipt_amount"] == 690000
    assert any(f["code"] == "CLAIM_RECEIPT_MISMATCH" for f in mismatch["findings"])

    # Overlimit record (8400 INR = 840000 paise; limit 7500 INR)
    assert overlimit["claimed_amount"] == 840000
    assert overlimit["receipt_amount"] == 840000
    assert any(f["code"] == "POLICY_LIMIT_EXCEEDED" for f in overlimit["findings"])


def test_seed_firestore_execution():
    """Test seed execution with mock client."""
    mock_client = MagicMock()
    mock_coll = MagicMock()
    mock_doc = MagicMock()
    mock_coll.document.return_value = mock_doc
    mock_client.collection.return_value = mock_coll

    seeded_ids = seed_firestore(client=mock_client)
    assert len(seeded_ids) == 3
    assert mock_doc.set.call_count == 3
