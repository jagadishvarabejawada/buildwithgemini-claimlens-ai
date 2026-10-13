"""Unit tests for ClaimLens AI document pipeline, extraction, duplicate detection, and reports."""

import hashlib
import os
import pytest

from app.duplicate_detection import check_for_duplicates
from app.extraction import extract_receipt_facts, parse_synthetic_text
from app.gcs_storage import (
    MAX_UPLOAD_SIZE_BYTES,
    StorageManager,
    compute_sha256,
    generate_object_path,
    validate_file_content,
)
from app.reports import generate_html_report, generate_json_report
from app.seed_data import SEED_RECORDS


def test_file_validation_valid_pdf_and_png():
    valid_pdf = b"%PDF-1.4\n%test content\n%%EOF"
    valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    invalid_bytes = b"This is just plain text, not a PDF or image."

    ok_pdf, mime_pdf, err = validate_file_content(valid_pdf, "receipt.pdf")
    assert ok_pdf is True
    assert mime_pdf == "application/pdf"
    assert err == ""

    ok_png, mime_png, err = validate_file_content(valid_png, "receipt.png")
    assert ok_png is True
    assert mime_png == "image/png"
    assert err == ""

    ok_inv, _, err = validate_file_content(invalid_bytes, "receipt.txt")
    assert ok_inv is False
    assert "Invalid file format" in err


def test_file_validation_empty_and_oversize():
    ok_empty, _, err = validate_file_content(b"", "receipt.pdf")
    assert ok_empty is False
    assert "empty" in err

    # Create dummy chunk over 10 MB limit
    oversize = b"%PDF-1.4" + b"0" * (MAX_UPLOAD_SIZE_BYTES + 100)
    ok_over, _, err = validate_file_content(oversize, "huge.pdf")
    assert ok_over is False
    assert "exceeds 10 MB limit" in err


def test_storage_manager_local_store(tmp_path):
    mgr = StorageManager(local_dir=str(tmp_path))
    content = b"%PDF-1.4\nsynthetic invoice content"
    res = mgr.store_receipt(content, "CLM-TEST-001", "invoice.pdf")
    assert res["status"] == "success"
    assert res["file_hash"] == hashlib.sha256(content).hexdigest()
    assert res["size_bytes"] == len(content)
    assert "receipts/CLM-TEST-001" in res["object_path"]


def test_synthetic_extraction_from_fixture():
    fixture_path = "fixtures/scenario_d_combined.pdf"
    assert os.path.exists(fixture_path), "Fixture scenario_d_combined.pdf must exist"

    with open(fixture_path, "rb") as f:
        file_bytes = f.read()

    extracted = extract_receipt_facts(file_bytes, "scenario_d_combined.pdf")
    assert extracted["status"] == "success"
    assert "Grand Hyatt" in extracted["merchant"]
    assert extracted["receipt_amount"] == "6900.00"
    assert extracted["currency"] == "INR"
    assert extracted["receipt_date"] == "2026-10-13"
    assert extracted["receipt_reference"] == "INV-DEL-1049"
    assert len(extracted["evidence_excerpts"]) > 0


def test_duplicate_detection_exact_and_similar():
    mock_hash = "abcdef1234567890abcdef1234567890"
    existing = [
        {
            "claim_id": "CLM-PRIOR-001",
            "file_hash": mock_hash,
            "merchant": "Grand Hyatt Delhi",
            "receipt_date": "2026-10-13",
            "receipt_amount": 690000,
            "currency": "INR",
            "receipt_reference": "INV-DEL-1049",
        }
    ]

    # Exact hash match
    dup1 = check_for_duplicates(
        claim_id="CLM-NEW-002",
        file_hash=mock_hash,
        merchant="Different Merchant",
        receipt_date="2026-10-14",
        receipt_amount_paise=100000,
        currency="INR",
        receipt_reference="OTHER",
        existing_audits=existing,
    )
    assert dup1["is_potential_duplicate"] is True
    assert len(dup1["exact_file_matches"]) == 1

    # Same claim retry (should NOT be flagged as duplicate of itself)
    self_retry = check_for_duplicates(
        claim_id="CLM-PRIOR-001",
        file_hash=mock_hash,
        merchant="Grand Hyatt Delhi",
        receipt_date="2026-10-13",
        receipt_amount_paise=690000,
        currency="INR",
        receipt_reference="INV-DEL-1049",
        existing_audits=existing,
    )
    assert self_retry["is_potential_duplicate"] is False

    # Attribute match (different hash, but same merchant, date, amount, currency)
    dup2 = check_for_duplicates(
        claim_id="CLM-NEW-003",
        file_hash="different_hash_99999",
        merchant="grand hyatt delhi",
        receipt_date="2026-10-13",
        receipt_amount_paise=690000,
        currency="INR",
        receipt_reference="INV-DEL-1049",
        existing_audits=existing,
    )
    assert dup2["is_potential_duplicate"] is True
    assert len(dup2["similar_claim_matches"]) == 1


def test_report_generation():
    rec = SEED_RECORDS[1]  # Mismatch record
    json_out = generate_json_report(rec)
    html_out = generate_html_report(rec)

    assert rec["claim_id"] in json_out
    assert "SYNTHETIC WORKSHOP DEMO DATA" in json_out
    assert rec["claim_id"] in html_out
    assert "ClaimLens AI" in html_out
    assert "CLAIM_RECEIPT_MISMATCH" in html_out
