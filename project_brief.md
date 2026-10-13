# My agent: ClaimLens AI
Tagline: “Every claim, checked with evidence.”

One-liner: A conversational agent that helps enterprise finance reviewers audit reimbursement claims by comparing synthetic receipts against company policy with evidence-based findings.

## Core Problem & Workflow
- Synthetic expense receipts and reimbursement claims are verified deterministically.
- Comparison against synthetic company policy rules (category caps, receipt matching, required fields).
- Evidence-based discrepancy calculation and recommended next actions without hallucination.
- A final approval decision is made only by a human finance reviewer (`review_status: pending_human_review`).

Tool coverage:
- Memory: Reviewer preferences and session audit context (planned)
- Tools: `audit_expense` (deterministic expense validation, exact arithmetic, and policy rule checks)
- Catalog/UI: Audit findings and discrepancy cards/tables (planned via A2UI)
- Image gen: n/a
- Sandbox: n/a (deterministic Python calculations using Decimal/paise in function tool)

Recommended for every project: memory, storage, tools, image generation, A2UI
Agent-specific / stretch (pick what fits): Deterministic policy engine, A2UI discrepancy summary cards, multi-modal receipt document parsing.

## Scope Boundaries
### Implemented in Current Milestone:
- Deterministic `audit_expense` Python tool with Decimal arithmetic.
- Synthetic policy `PP-DEMO-001` (business travel, INR 7,500 limit).
- Structured validation of claim amounts, receipt amounts, dates, and mandatory fields.
- Nonzero difference calculations and policy limit excess tracking.
- Output schema enforcing `pending_human_review` status.
- ADK Gemini 3.8 Flash agent prompt grounding explanations strictly on deterministic findings.

### Later Features (Not Implemented Yet):
- PDF / JPG / PNG OCR and document extraction
- Web dashboard interface
- Downloadable audit reports (CSV/PDF)
- Duplicate claim detection
- Persistent audit history / Vertex AI Memory Bank
- Production cloud deployment
