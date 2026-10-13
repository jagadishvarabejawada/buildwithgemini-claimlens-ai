"""Mocked integration tests for ClaimLens AI frontend chat proxy."""

import json
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from google.adk.events import Event
from google.genai import types

from frontend.main import app, _local_runner

client = TestClient(app)


@pytest.fixture(autouse=True)
def force_local_mode(monkeypatch):
    """Ensure tests target the local runner mock regardless of deployed environment variables."""
    monkeypatch.setattr("frontend.main.get_agent_resource", lambda: "")


def test_chat_status_endpoint():
    """Verify truthful status endpoint reports local runner configuration."""
    res = client.get("/api/chat/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["mode"] == "local_runner"
    assert data["model"] == "gemini-3.8-flash"
    assert data["agent_name"] == "root_agent"
    assert data["cloud_project"] == "qwiklabs-gcp-03-cff970f17c66"


@pytest.mark.asyncio
async def test_chat_request_forwarding_and_text_response():
    """Verify chat endpoint forwards message to local runner and returns structured text parts."""
    mock_event = Event(
        message=types.Content(
            role="model",
            parts=[types.Part.from_text(
                text="Reimbursement claims under PP-DEMO-001 require receipts and final human review."
            )],
        )
    )

    async def mock_run_async(*args, **kwargs):
        assert kwargs["user_id"] == "test-user-1"
        assert kwargs["new_message"].parts[0].text == "How to reimburse claim"
        yield mock_event

    with patch.object(_local_runner, "run_async", side_effect=mock_run_async):
        res = client.post(
            "/chat",
            json={
                "message": "How to reimburse claim",
                "user_id": "test-user-1",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "session_id" in data
        assert len(data["parts"]) == 1
        assert data["parts"][0]["kind"] == "text"
        assert "PP-DEMO-001" in data["parts"][0]["text"]
        assert "final human review" in data["parts"][0]["text"]


@pytest.mark.asyncio
async def test_chat_session_id_persistence_across_turns():
    """Verify session_id is preserved between user turns."""
    mock_event = Event(
        message=types.Content(
            role="model",
            parts=[types.Part.from_text(text="Please provide the currency and receipt amount.")],
        )
    )

    calls = []

    async def mock_run_async(*args, **kwargs):
        calls.append(kwargs)
        yield mock_event

    with patch.object(_local_runner, "run_async", side_effect=mock_run_async):
        # Turn 1: Explicit session ID
        res1 = client.post(
            "/chat",
            json={
                "message": "An Employee want to reimburse 12000",
                "user_id": "auditor-vikram",
                "session_id": "session-audit-999",
            },
        )
        assert res1.status_code == 200
        assert res1.json()["session_id"] == "session-audit-999"
        assert calls[0]["session_id"] == "session-audit-999"

        # Turn 2: Omitted session ID from same user - proxy retains existing session
        res2 = client.post(
            "/chat",
            json={
                "message": "Currency is INR, category is business_travel",
                "user_id": "auditor-vikram",
            },
        )
        assert res2.status_code == 200
        assert res2.json()["session_id"] == "session-audit-999"
        assert calls[1]["session_id"] == "session-audit-999"


@pytest.mark.asyncio
async def test_chat_a2ui_extraction():
    """Verify A2UI components are correctly converted to a2ui parts."""
    a2ui_sample = {
        "beginRendering": {
            "surfaceId": "claim-surface",
            "root": "card-root",
        }
    }
    raw_text = f"<a2a_datapart_json>{json.dumps({'kind': 'data', 'data': a2ui_sample})}</a2a_datapart_json>"

    mock_event = Event(
        message=types.Content(
            role="model",
            parts=[types.Part.from_text(text=raw_text)],
        )
    )

    async def mock_run_async(*args, **kwargs):
        yield mock_event

    with patch.object(_local_runner, "run_async", side_effect=mock_run_async):
        res = client.post(
            "/chat",
            json={"message": "Show audit card"},
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["parts"]) == 1
        assert data["parts"][0]["kind"] == "a2ui"
        assert data["parts"][0]["data"]["beginRendering"]["surfaceId"] == "claim-surface"


@pytest.mark.asyncio
async def test_chat_backend_error_propagation():
    """Verify backend errors are explicitly surfaced to the user with diagnostics instead of silent fallbacks."""
    async def mock_run_async_failing(*args, **kwargs):
        raise ConnectionError("Vertex AI API unreachable or authentication failed")
        yield None

    with patch.object(_local_runner, "run_async", side_effect=mock_run_async_failing):
        res = client.post(
            "/chat",
            json={"message": "Audit claim"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "error"
        assert data["connected"] is False
        assert data["error_type"] == "ConnectionError"
        assert "Vertex AI API unreachable" in data["error_detail"]
        assert len(data["parts"]) == 1
        assert "ClaimLens AI Backend Notice" in data["parts"][0]["text"]
        assert "Disconnected" in data["parts"][0]["text"]
