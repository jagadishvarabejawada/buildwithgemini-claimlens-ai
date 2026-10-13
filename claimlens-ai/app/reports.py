"""Downloadable audit report generation for ClaimLens AI."""

import json
from typing import Any, Dict


def generate_json_report(audit_record: Dict[str, Any]) -> str:
    """Generate structured JSON report representation."""
    report_data = {
        "report_type": "ClaimLens AI Professional Expense Audit Report",
        "generated_by": "ClaimLens AI Audit Engine v1.0",
        "demo_disclaimer": "SYNTHETIC WORKSHOP DEMO DATA - FOR EVALUATION ONLY",
        "audit_record": audit_record,
    }
    return json.dumps(report_data, indent=2)


def generate_html_report(audit_record: Dict[str, Any]) -> str:
    """Generate a clean, printable HTML report suitable for browser print-to-PDF."""
    cid = audit_record.get("claim_id", "N/A")
    emp = audit_record.get("employee", "N/A")
    mer = audit_record.get("merchant", "N/A")
    rdate = audit_record.get("receipt_date", "N/A")
    cat = audit_record.get("category", "N/A")
    curr = audit_record.get("currency", "INR")
    c_paise = audit_record.get("claimed_amount", 0)
    r_paise = audit_record.get("receipt_amount", 0)
    pid = audit_record.get("policy_id", "PP-DEMO-001")
    pver = audit_record.get("policy_version", "1.0")
    status = audit_record.get("review_status", "pending_human_review")
    created = audit_record.get("created_at", "N/A")
    findings = audit_record.get("findings", [])
    summary = audit_record.get("audit_summary", {})

    c_amt_str = f"{c_paise / 100:.2f}"
    r_amt_str = f"{r_paise / 100:.2f}"

    findings_rows = ""
    if findings:
        for f in findings:
            code = f.get("code", "UNKNOWN")
            sev = f.get("severity", "MEDIUM")
            rule = f.get("rule", "")
            exp = f.get("explanation", "")
            rec = f.get("recommended_next_action", "")
            findings_rows += f"""
            <tr>
              <td><strong>{code}</strong></td>
              <td><span class="badge badge-{sev.lower()}">{sev}</span></td>
              <td>{rule}</td>
              <td>{exp}</td>
              <td>{rec}</td>
            </tr>
            """
    else:
        findings_rows = """
        <tr>
          <td colspan="5" style="text-align: center; color: #137333;">
            &check; No policy violations or discrepancies found.
          </td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ClaimLens AI Audit Report - {cid}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      margin: 40px;
      color: #202124;
      line-height: 1.5;
    }}
    .header {{
      border-bottom: 2px solid #005a70;
      padding-bottom: 16px;
      margin-bottom: 24px;
    }}
    .demo-banner {{
      background: #e8f0fe;
      color: #1a73e8;
      padding: 8px 12px;
      font-size: 13px;
      font-weight: bold;
      border-radius: 4px;
      margin-bottom: 16px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    h1 {{ margin: 0 0 4px 0; color: #003644; font-size: 24px; }}
    .tagline {{ color: #5f6368; font-style: italic; margin-bottom: 12px; }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 16px;
      margin-bottom: 24px;
    }}
    .card {{
      background: #f8f9fa;
      border: 1px solid #dadce0;
      border-radius: 6px;
      padding: 16px;
    }}
    .card-title {{ font-weight: bold; color: #3c4043; margin-bottom: 8px; font-size: 14px; text-transform: uppercase; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 16px;
      margin-bottom: 24px;
    }}
    th, td {{
      border: 1px solid #dadce0;
      padding: 10px 12px;
      text-align: left;
      font-size: 14px;
    }}
    th {{ background: #f1f3f4; font-weight: 600; color: #3c4043; }}
    .badge {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 600;
    }}
    .badge-high {{ background: #fce8e6; color: #c5221f; }}
    .badge-medium {{ background: #fef7e0; color: #b06000; }}
    .badge-low {{ background: #e6f4ea; color: #137333; }}
    .status-badge {{
      background: #fef7e0;
      color: #b06000;
      border: 1px solid #f9ab00;
      padding: 6px 12px;
      border-radius: 4px;
      font-weight: bold;
      display: inline-block;
    }}
    .footer {{
      margin-top: 40px;
      border-top: 1px solid #dadce0;
      padding-top: 12px;
      font-size: 12px;
      color: #70757a;
      display: flex;
      justify-content: space-between;
    }}
  </style>
</head>
<body>
  <div class="demo-banner">Workshop Demo Only — Synthetic Expense Audit</div>
  <div class="header">
    <h1>ClaimLens AI — Audit Evidence Report</h1>
    <div class="tagline">“Every claim, checked with evidence.”</div>
    <div><strong>Claim Reference:</strong> {cid} &nbsp;|&nbsp; <strong>Generated:</strong> {created}</div>
  </div>

  <div class="meta-grid">
    <div class="card">
      <div class="card-title">Expense & Claimant Details</div>
      <div><strong>Employee:</strong> {emp}</div>
      <div><strong>Merchant:</strong> {mer}</div>
      <div><strong>Receipt Date:</strong> {rdate}</div>
      <div><strong>Category:</strong> {cat}</div>
    </div>
    <div class="card">
      <div class="card-title">Financial & Policy Verification</div>
      <div><strong>Claimed Amount:</strong> {c_amt_str} {curr}</div>
      <div><strong>Receipt Amount:</strong> {r_amt_str} {curr}</div>
      <div><strong>Applied Policy:</strong> {pid} (v{pver})</div>
      <div><strong>Review Status:</strong> <span class="status-badge">{status}</span></div>
    </div>
  </div>

  <h3>Audit Findings & Evidence Excerpts</h3>
  <table>
    <thead>
      <tr>
        <th>Finding Code</th>
        <th>Severity</th>
        <th>Policy Rule</th>
        <th>Explanation / Discrepancy</th>
        <th>Recommended Next Action</th>
      </tr>
    </thead>
    <tbody>
      {findings_rows}
    </tbody>
  </table>

  <div class="card">
    <div class="card-title">Human Review Notice</div>
    <p style="margin: 0;">
      All findings provided by ClaimLens AI are advisory based on deterministic policy evaluation.
      Final approval or rejection requires explicit action from an authorized human reviewer.
    </p>
  </div>

  <div class="footer">
    <div>ClaimLens AI Engine</div>
    <div>Confidential Internal Document</div>
  </div>
</body>
</html>
"""
