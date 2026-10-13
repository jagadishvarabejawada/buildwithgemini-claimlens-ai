"""ClaimLens AI - FastAPI proxy & audit service.

Serves the branded dashboard, handles receipt upload, deterministic audit
pipeline, human review workflow, downloadable evidence reports, and A2A chat proxy.
"""

from decimal import Decimal
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

try:
    from app.audit import audit_expense
    from app.duplicate_detection import check_for_duplicates
    from app.extraction import extract_receipt_facts
    from app.gcs_storage import StorageManager, validate_file_content
    from app.reports import generate_html_report, generate_json_report
    from app.seed_data import SEED_RECORDS
    from app.storage import (
        amount_to_paise,
        get_audit_record,
        list_latest_audits,
        save_audit_record,
    )
except ImportError:
    audit_expense = None
    check_for_duplicates = None
    extract_receipt_facts = None
    StorageManager = None
    validate_file_content = None
    generate_html_report = None
    generate_json_report = None
    SEED_RECORDS = []
    amount_to_paise = lambda x: int(float(x or 0) * 100)
    get_audit_record = None
    list_latest_audits = None
    save_audit_record = None

import logging
import re

try:
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    from app.a2ui_utils import _extract_a2ui_messages
    from app.agent import root_agent
except ImportError:
    Runner = None
    InMemorySessionService = None
    types = None
    _extract_a2ui_messages = None
    root_agent = None

logger = logging.getLogger("claimlens_frontend")

# Optional A2A / Deployed Agent Engine settings
RESOURCE = os.environ.get("AGENT_ENGINE_RESOURCE_NAME", "").strip()
if not RESOURCE:
    _meta_file = Path(__file__).resolve().parent.parent / "deployment_metadata.json"
    if _meta_file.exists():
        try:
            with open(_meta_file, encoding="utf-8") as _f:
                RESOURCE = json.load(_f).get("remote_agent_runtime_id", "").strip()
        except Exception:
            pass
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")


def get_agent_resource() -> str:
    """Return configured Agent Engine resource name or empty string if local mode."""
    return os.environ.get("AGENT_ENGINE_RESOURCE_NAME", "").strip() or RESOURCE


app = FastAPI(title="ClaimLens AI - Enterprise Expense Audit Assistant")

storage_mgr = StorageManager(local_dir="data/storage")

# Session tracking for user conversations across chat turns
_contexts: Dict[str, str] = {}

# Local in-memory ADK runner for dev environment
_session_service = InMemorySessionService()
_local_runner = Runner(
    agent=root_agent,
    app_name="app",
    session_service=_session_service,
    auto_create_session=True,
)

# Cache for local demo records (in addition to Firestore)
_LOCAL_AUDITS: Dict[str, Dict[str, Any]] = {
    rec["claim_id"]: rec for rec in SEED_RECORDS
}


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": type(exc).__name__, "message": str(exc)},
    )


@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "service": "ClaimLens AI",
        "version": "1.0.0",
        "has_agent_resource": bool(RESOURCE),
    }


@app.get("/api/fixtures")
async def get_fixtures():
    """Return synthetic workshop demo scenarios with complete data."""
    manifest_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            return json.load(f)
    return {}


@app.post("/api/upload")
async def upload_receipt(receipt: UploadFile = File(...)):
    """Validate and upload receipt document (max 10MB, PDF/PNG/JPEG)."""
    file_bytes = await receipt.read()
    is_valid, mime_type, err = validate_file_content(file_bytes, receipt.filename)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err)

    temp_id = f"TEMP-{uuid.uuid4().hex[:6]}"
    stored = storage_mgr.store_receipt(
        file_bytes=file_bytes,
        claim_id=temp_id,
        filename=receipt.filename,
    )
    if stored.get("status") == "error":
        raise HTTPException(status_code=400, detail=stored.get("message"))

    extracted = extract_receipt_facts(
        file_bytes=file_bytes,
        filename=receipt.filename,
    )

    existing_list = list(_LOCAL_AUDITS.values())
    dup_check = check_for_duplicates(
        claim_id=temp_id,
        file_hash=stored.get("file_hash"),
        merchant=extracted.get("merchant") or "",
        receipt_date=extracted.get("receipt_date") or "",
        receipt_amount_paise=int(Decimal(extracted.get("receipt_amount") or "0") * 100),
        currency=extracted.get("currency") or "INR",
        receipt_reference=extracted.get("receipt_reference"),
        existing_audits=existing_list,
    )

    return {
        "status": "success",
        "storage": stored,
        "extracted": extracted,
        "duplicate_analysis": dup_check,
    }


@app.post("/api/audit")
async def run_audit(req: Request):
    """Run deterministic audit against PP-DEMO-001 and persist to storage."""
    data = await req.json()
    claim_id = data.get("claim_id")
    if not claim_id:
        claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"

    audit_res = audit_expense(
        claim_id=claim_id,
        employee=data.get("employee", "Unknown Employee"),
        merchant=data.get("merchant", "Unknown Merchant"),
        receipt_date=data.get("receipt_date", "2026-10-13"),
        category=data.get("category", "business_travel"),
        currency=data.get("currency", "INR"),
        claimed_amount=str(data.get("claimed_amount", "0")),
        receipt_amount=str(data.get("receipt_amount", "0")),
        receipt_reference=data.get("receipt_reference"),
    )

    if audit_res.get("status") == "error":
        return JSONResponse(status_code=400, content=audit_res)

    exp = audit_res.get("expense", {})
    arith = audit_res.get("arithmetic", {})
    record = {
        "claim_id": claim_id,
        "employee": exp.get("employee", "Unknown Employee"),
        "merchant": exp.get("merchant", "Unknown Merchant"),
        "receipt_date": exp.get("receipt_date", "2026-10-13"),
        "category": exp.get("category", "business_travel"),
        "currency": exp.get("currency", "INR"),
        "claimed_amount": amount_to_paise(arith.get("claimed_amount")),
        "receipt_amount": amount_to_paise(arith.get("receipt_amount")),
        "policy_id": audit_res.get("policy", {}).get("policy_id", "PP-DEMO-001"),
        "policy_version": audit_res.get("policy", {}).get("version", "1.0"),
        "findings": audit_res.get("findings", []),
        "audit_summary": {
            **audit_res.get("audit_summary", {}),
            "claim_receipt_difference_paise": amount_to_paise(arith.get("claim_receipt_difference")),
            "claimed_amount_above_limit_paise": amount_to_paise(arith.get("claimed_amount_above_limit")),
            "receipt_amount_above_limit_paise": amount_to_paise(arith.get("receipt_amount_above_limit")),
        },
        "review_status": "pending_human_review",
        "created_at": "2026-10-13T12:00:00Z",
        "notes": data.get("notes"),
        "file_hash": data.get("file_hash"),
        "storage_uri": data.get("storage_uri"),
        "receipt_reference": data.get("receipt_reference"),
    }

    # Duplicate check against existing audits
    existing_list = list(_LOCAL_AUDITS.values())
    dup_check = check_for_duplicates(
        claim_id=claim_id,
        file_hash=record.get("file_hash"),
        merchant=record.get("merchant", ""),
        receipt_date=record.get("receipt_date", ""),
        receipt_amount_paise=record.get("receipt_amount", 0),
        currency=record.get("currency", "INR"),
        receipt_reference=record.get("receipt_reference"),
        existing_audits=existing_list,
    )
    record["duplicate_analysis"] = dup_check

    # Persist locally and attempt Firestore
    _LOCAL_AUDITS[claim_id] = record
    try:
        save_audit_record(
            claim_id=record["claim_id"],
            employee=record.get("employee", ""),
            merchant=record.get("merchant", ""),
            receipt_date=record.get("receipt_date", ""),
            category=record.get("category", "business_travel"),
            currency=record.get("currency", "INR"),
            claimed_amount=float(record.get("claimed_amount", 0)) / 100.0,
            receipt_amount=float(record.get("receipt_amount", 0)) / 100.0,
            policy_id=record.get("policy_id", "PP-DEMO-001"),
            policy_version=record.get("policy_version", "1.0"),
        )
    except Exception:
        # Graceful fallback to local store if Firestore isn't provisioned yet
        pass

    return {
        "status": "success",
        "audit_record": record,
        "summary": record.get("audit_summary"),
        "findings": audit_res.get("findings"),
    }


@app.get("/api/audits")
async def get_audits():
    """List recent audited records."""
    # Try Firestore first; if empty or unprovisioned, return local records
    try:
        firestore_records = list_latest_audits(limit=25)
        if firestore_records:
            return {"audits": firestore_records, "source": "firestore"}
    except Exception:
        pass
    audits_list = sorted(
        _LOCAL_AUDITS.values(),
        key=lambda x: x.get("created_at", ""),
        reverse=True,
    )
    return {"audits": audits_list, "source": "local_store"}


@app.get("/api/audits/{claim_id}")
async def get_audit(claim_id: str):
    """Retrieve audit record by claim_id."""
    if claim_id in _LOCAL_AUDITS:
        return _LOCAL_AUDITS[claim_id]
    try:
        rec = get_audit_record(claim_id)
        if rec:
            return rec
    except Exception:
        pass
    raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found.")


@app.post("/api/audits/{claim_id}/review")
async def review_claim(claim_id: str, req: Request):
    """Explicit human reviewer action: approve, reject, or request clarification."""
    data = await req.json()
    action = data.get("action")  # 'approved', 'rejected', 'clarification_requested'
    reviewer_id = data.get("reviewer_id", "auditor_ops_01")
    notes = data.get("notes", "")

    if action not in ["approved", "rejected", "clarification_requested"]:
        raise HTTPException(
            status_code=400,
            detail="Action must be 'approved', 'rejected', or 'clarification_requested'.",
        )

    record = None
    if claim_id in _LOCAL_AUDITS:
        record = _LOCAL_AUDITS[claim_id]
    else:
        try:
            record = get_audit_record(claim_id)
        except Exception:
            pass

    if not record:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found.")

    record["review_status"] = action
    record["human_reviewer"] = {
        "reviewer_id": reviewer_id,
        "action": action,
        "notes": notes,
        "reviewed_at": "2026-10-13T12:00:00Z",
    }
    _LOCAL_AUDITS[claim_id] = record

    return {
        "status": "success",
        "claim_id": claim_id,
        "new_review_status": action,
        "record": record,
    }


@app.get("/api/audits/{claim_id}/report.json")
async def get_report_json(claim_id: str):
    """Download audit report in JSON format."""
    if claim_id not in _LOCAL_AUDITS:
        raise HTTPException(status_code=404, detail="Claim record not found.")
    record = _LOCAL_AUDITS[claim_id]
    json_str = generate_json_report(record)
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=claimlens_report_{claim_id}.json"},
    )


@app.get("/api/audits/{claim_id}/report.html")
async def get_report_html(claim_id: str):
    """View/Download printable audit report in HTML format."""
    if claim_id not in _LOCAL_AUDITS:
        raise HTTPException(status_code=404, detail="Claim record not found.")
    record = _LOCAL_AUDITS[claim_id]
    html_content = generate_html_report(record)
    return HTMLResponse(content=html_content)


def _extract_adk_event_parts(event: Any) -> List[Dict[str, Any]]:
    """Turn ADK Event parts into structured parts for the chat UI."""
    parts: List[Dict[str, Any]] = []
    if not hasattr(event, "message") or not event.message:
        return parts

    msg_parts = getattr(event.message, "parts", []) or []
    for p in msg_parts:
        text = getattr(p, "text", None)
        if text:
            if "<a2a_datapart_json>" in text or any(k in text for k in ("beginRendering", "surfaceUpdate", "dataModelUpdate")):
                clean = re.sub(r"</?a2a_datapart_json>", "", text).strip()
                try:
                    parsed = json.loads(clean)
                    if isinstance(parsed, dict) and "data" in parsed:
                        parts.append({"kind": "a2ui", "data": parsed["data"]})
                    else:
                        parts.append({"kind": "a2ui", "data": parsed})
                except Exception:
                    a2ui_msgs = _extract_a2ui_messages(text)
                    if a2ui_msgs:
                        for m in a2ui_msgs:
                            parts.append({"kind": "a2ui", "data": m})
                    else:
                        parts.append({"kind": "text", "text": text})
            else:
                parts.append({"kind": "text", "text": text})

        inline_data = getattr(p, "inline_data", None)
        if inline_data:
            data_bytes = getattr(inline_data, "data", b"")
            try:
                data_str = data_bytes.decode("utf-8") if isinstance(data_bytes, bytes) else str(data_bytes)
                if "<a2a_datapart_json>" in data_str:
                    clean = re.sub(r"</?a2a_datapart_json>", "", data_str).strip()
                    parsed = json.loads(clean)
                    if isinstance(parsed, dict) and "data" in parsed:
                        parts.append({"kind": "a2ui", "data": parsed["data"]})
                    else:
                        parts.append({"kind": "a2ui", "data": parsed})
                else:
                    parts.append({"kind": "text", "text": data_str})
            except Exception:
                pass
    return parts


@app.get("/api/chat/status")
async def chat_status():
    """Return explicit truthful status of chat backend."""
    active_resource = get_agent_resource()
    return {
        "status": "ready",
        "mode": "deployed_a2a" if bool(active_resource) else "local_runner",
        "has_agent_resource": bool(active_resource),
        "resource_name": active_resource or None,
        "model": "gemini-3.8-flash",
        "agent_name": root_agent.name,
        "cloud_project": os.environ.get("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-03-cff970f17c66"),
        "cloud_location": os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
    }


@app.post("/chat")
async def chat(req: Request):
    """Chat proxy to ClaimLens AI agent with session preservation and explicit diagnostics."""
    body = await req.json()
    message = (body.get("message") or "").strip()
    user_id = body.get("user_id") or "web-user"
    session_id = body.get("session_id") or _contexts.get(user_id) or str(uuid.uuid4())
    _contexts[user_id] = session_id

    if not message:
        return JSONResponse({"status": "error", "error": "Empty message", "parts": []})

    parts: List[Dict[str, Any]] = []

    # If RESOURCE is configured, use A2A proxy logic as defined in template
    active_resource = get_agent_resource()
    if active_resource:
        try:
            import google.auth
            import google.auth.transport.requests
            from google.protobuf.json_format import MessageToDict
            import httpx
            from a2a.client import ClientConfig, create_client
            from a2a.types import (
                Message,
                Part,
                Role,
                SendMessageRequest,
            )
            from a2a.utils.constants import TransportProtocol

            creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            creds.refresh(google.auth.transport.requests.Request())
            headers = {
                "Authorization": f"Bearer {creds.token}",
                "X-A2A-Version": "1.0",
            }
            loc = RESOURCE.split("/locations/")[1].split("/")[0]
            a2a_base = f"https://{loc}-aiplatform.googleapis.com/reasoningEngines/v1/{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"

            async with httpx.AsyncClient(headers=headers, timeout=120) as client:
                config = ClientConfig(
                    httpx_client=client,
                    supported_protocol_bindings=[
                        TransportProtocol.JSONRPC,
                        TransportProtocol.HTTP_JSON,
                    ],
                )
                a2a_client = await create_client(a2a_base, config)
                msg = Message(
                    message_id=str(uuid.uuid4()),
                    role=Role.ROLE_USER,
                    parts=[Part(text=message)],
                    context_id=session_id or "",
                )
                def _extract_part(p):
                    if getattr(p, "text", None):
                        t = p.text
                        if "<a2a_datapart_json>" in t:
                            try:
                                clean = re.sub(r"</?a2a_datapart_json>", "", t).strip()
                                payload = json.loads(clean)
                                inner = payload.get("data", payload)
                                if "beginRendering" in inner or "surfaceUpdate" in inner:
                                    return {"kind": "a2ui", "data": inner}
                            except Exception:
                                pass
                        return {"kind": "text", "text": t}
                    if hasattr(p, "HasField") and p.HasField("data"):
                        d = MessageToDict(p.data)
                        inner = d.get("data", d)
                        if "beginRendering" in inner or "surfaceUpdate" in inner:
                            return {"kind": "a2ui", "data": inner}
                        elif "beginRendering" in d or "surfaceUpdate" in d:
                            return {"kind": "a2ui", "data": d}
                    return None

                seen_a2ui = set()
                seen_text = set()
                async for chunk in a2a_client.send_message(SendMessageRequest(message=msg)):
                    cand_parts = []
                    if chunk.HasField("status_update"):
                        if chunk.status_update.context_id:
                            _contexts[user_id] = chunk.status_update.context_id
                        if chunk.status_update.status.HasField("message"):
                            cand_parts.extend(chunk.status_update.status.message.parts)
                    if chunk.HasField("artifact_update"):
                        if chunk.artifact_update.context_id:
                            _contexts[user_id] = chunk.artifact_update.context_id
                        if chunk.artifact_update.HasField("artifact"):
                            cand_parts.extend(chunk.artifact_update.artifact.parts)
                    if chunk.HasField("task"):
                        if chunk.task.context_id:
                            _contexts[user_id] = chunk.task.context_id
                        for artifact in chunk.task.artifacts:
                            cand_parts.extend(artifact.parts)
                    if chunk.HasField("message"):
                        cand_parts.extend(chunk.message.parts)

                    for cp in cand_parts:
                        ep = _extract_part(cp)
                        if not ep:
                            continue
                        if ep["kind"] == "a2ui":
                            key = json.dumps(ep["data"], sort_keys=True)
                            if key in seen_a2ui:
                                continue
                            seen_a2ui.add(key)
                        elif ep["kind"] == "text":
                            t = ep.get("text", "").strip()
                            if t in seen_text:
                                continue
                            seen_text.add(t)
                        parts.append(ep)
        except Exception as exc:
            logger.error("Deployed A2A agent invocation failed: %s", exc, exc_info=True)
            return JSONResponse(
                status_code=200,
                content={
                    "status": "error",
                    "connected": False,
                    "session_id": session_id,
                    "error_type": type(exc).__name__,
                    "error_detail": str(exc),
                    "parts": [
                        {
                            "kind": "text",
                            "text": (
                                f"⚠️ [ClaimLens AI Proxy Notice: Deployed A2A Connection Error]\n"
                                f"Failed to communicate with deployed Agent Engine at {RESOURCE}.\n"
                                f"Diagnostic: {type(exc).__name__}: {exc}"
                            ),
                        }
                    ],
                },
            )
    else:
        # Local ADK runner connection
        try:
            os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
            os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-03-cff970f17c66")
            os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")

            msg = types.Content(
                role="user",
                parts=[types.Part.from_text(text=message)],
            )
            async for event in _local_runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=msg,
            ):
                event_parts = _extract_adk_event_parts(event)
                if event_parts:
                    parts.extend(event_parts)
        except Exception as exc:
            logger.error("Local ADK runner invocation failed: %s", exc, exc_info=True)
            return JSONResponse(
                status_code=200,
                content={
                    "status": "error",
                    "connected": False,
                    "session_id": session_id,
                    "error_type": type(exc).__name__,
                    "error_detail": str(exc),
                    "parts": [
                        {
                            "kind": "text",
                            "text": (
                                f"⚠️ [ClaimLens AI Backend Notice: Disconnected / LLM Call Error]\n"
                                f"The local ADK agent runner could not generate a response.\n"
                                f"Diagnostic ({type(exc).__name__}): {exc}\n"
                                f"Note: Live Gemini model execution requires Vertex AI connectivity and cost approval. For offline verification, run mocked integration tests."
                            ),
                        }
                    ],
                },
            )

    if not parts:
        parts.append({"kind": "text", "text": "(The agent didn't return a reply.)"})

    return JSONResponse({
        "status": "success",
        "session_id": session_id,
        "parts": parts,
    })


# Mount static files
static_dir = "frontend/static" if os.path.exists("frontend/static") else "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
