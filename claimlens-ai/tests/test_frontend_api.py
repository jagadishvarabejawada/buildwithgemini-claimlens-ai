"""Integration tests for ClaimLens AI frontend FastAPI endpoints."""

import json
from fastapi.testclient import TestClient
import pytest

from frontend.main import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ClaimLens AI"


def test_fixtures_endpoint():
    res = client.get("/api/fixtures")
    assert res.status_code == 200
    data = res.json()
    assert "scenario_a_valid" in data
    assert "scenario_d_combined" in data


def test_upload_endpoint():
    with open("fixtures/scenario_d_combined.pdf", "rb") as f:
        file_bytes = f.read()

    res = client.post(
        "/api/upload",
        files={"receipt": ("scenario_d_combined.pdf", file_bytes, "application/pdf")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "extracted" in data
    assert "Grand Hyatt" in data["extracted"]["merchant"]
    assert data["extracted"]["receipt_amount"] == "6900.00"


def test_audit_endpoint_scenario_d():
    payload = {
        "claim_id": "CLM-API-TEST-001",
        "employee": "Vikram Patel",
        "merchant": "Grand Hyatt Delhi",
        "receipt_date": "2026-10-13",
        "category": "business_travel",
        "currency": "INR",
        "claimed_amount": "8400.00",
        "receipt_amount": "6900.00",
        "notes": "API test for scenario D",
    }
    res = client.post("/api/audit", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    rec = data["audit_record"]
    assert rec["claimed_amount"] == 840000
    assert rec["receipt_amount"] == 690000
    assert rec["review_status"] == "pending_human_review"

    # Verify findings & non-overlapping arithmetic
    summary = data["summary"]
    assert summary["claim_receipt_difference_paise"] == 150000
    assert summary["claimed_amount_above_limit_paise"] == 90000
    assert summary["receipt_amount_above_limit_paise"] == 0


def test_human_review_workflow():
    cid = "CLM-API-TEST-001"
    review_payload = {
        "action": "approved",
        "reviewer_id": "finance_lead_01",
        "notes": "Approved up to verified receipt amount of 6900.00 INR",
    }
    res = client.post(f"/api/audits/{cid}/review", json=review_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["new_review_status"] == "approved"
    assert data["record"]["human_reviewer"]["reviewer_id"] == "finance_lead_01"


def test_download_reports():
    cid = "CLM-API-TEST-001"
    res_json = client.get(f"/api/audits/{cid}/report.json")
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers["content-type"]
    assert cid in res_json.text

    res_html = client.get(f"/api/audits/{cid}/report.html")
    assert res_html.status_code == 200
    assert "text/html" in res_html.headers["content-type"]
    assert "ClaimLens AI" in res_html.text
    assert cid in res_html.text
