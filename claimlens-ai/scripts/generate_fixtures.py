"""Generate synthetic receipt fixtures for ClaimLens AI Scenarios A, B, C, D."""

import json
import os

FIXTURES_DIR = "fixtures"
os.makedirs(FIXTURES_DIR, exist_ok=True)

SCENARIOS = {
    "scenario_a_valid": {
        "claim_id": "CLM-DEMO-VALID-001",
        "employee": "Priya Sharma",
        "merchant": "Taj Palace Bengaluru",
        "date": "2026-10-10",
        "category": "business_travel",
        "currency": "INR",
        "claimed_amount": "6900.00",
        "receipt_amount": "6900.00",
        "reference": "INV-BLR-8841",
        "notes": "Annual Client Planning Conference - Standard Hotel Stay",
    },
    "scenario_b_mismatch": {
        "claim_id": "CLM-DEMO-MISMATCH-002",
        "employee": "Rahul Verma",
        "merchant": "Oberoi Mumbai",
        "date": "2026-10-11",
        "category": "business_travel",
        "currency": "INR",
        "claimed_amount": "7000.00",
        "receipt_amount": "6900.00",
        "reference": "INV-BOM-5412",
        "notes": "Partner Advisory Summit - Tip/incidentals claimed without separate receipt",
    },
    "scenario_c_overlimit": {
        "claim_id": "CLM-DEMO-OVERLIMIT-003",
        "employee": "Ananya Iyer",
        "merchant": "ITC Grand Chola Chennai",
        "date": "2026-10-12",
        "category": "business_travel",
        "currency": "INR",
        "claimed_amount": "8400.00",
        "receipt_amount": "8400.00",
        "reference": "INV-MAA-9923",
        "notes": "Regional Executive Review - Peak season room rate exceeded policy cap",
    },
    "scenario_d_combined": {
        "claim_id": "CLM-DEMO-COMBINED-004",
        "employee": "Vikram Patel",
        "merchant": "Grand Hyatt Delhi",
        "date": "2026-10-13",
        "category": "business_travel",
        "currency": "INR",
        "claimed_amount": "8400.00",
        "receipt_amount": "6900.00",
        "reference": "INV-DEL-1049",
        "notes": "Workshop Benchmark Demo - Claimed 8400.00 against verified receipt 6900.00",
    },
}


def create_minimal_pdf(content: str) -> bytes:
    """Generate a valid minimal single-page PDF containing text content."""
    # PDF stream content
    escaped_content = content.replace("(", "\\(").replace(")", "\\)")
    lines = escaped_content.split("\n")
    text_ops = []
    y = 700
    for line in lines:
        text_ops.append(f"1 0 0 1 50 {y} Tm ({line}) Tj")
        y -= 18

    stream_data = "BT\n/F1 12 Tf\n" + "\n".join(text_ops) + "\nET\n"
    stream_len = len(stream_data.encode("latin1"))

    pdf = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length {stream_len} >>
stream
{stream_data}endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000300 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
370
%%EOF"""
    return pdf.encode("latin1")


def create_minimal_png() -> bytes:
    """Generate a minimal valid 1x1 PNG byte stream."""
    # Valid 1x1 transparent PNG
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
    )


def generate_all():
    summary_manifest = {}
    for key, data in SCENARIOS.items():
        doc_text = f"""--- SYNTHETIC EXPENSE RECEIPT ---
Receipt Reference: {data['reference']}
Merchant: {data['merchant']}
Date: {data['date']}
Employee: {data['employee']}
Category: {data['category']}
Total: {data['currency']} {data['receipt_amount']}
Notes: {data['notes']}
--- DEMO DATA ONLY ---"""

        pdf_path = os.path.join(FIXTURES_DIR, f"{key}.pdf")
        with open(pdf_path, "wb") as f:
            f.write(create_minimal_pdf(doc_text))

        png_path = os.path.join(FIXTURES_DIR, f"{key}.png")
        with open(png_path, "wb") as f:
            f.write(create_minimal_png())

        meta_path = os.path.join(FIXTURES_DIR, f"{key}.json")
        with open(meta_path, "w") as f:
            json.dump(data, f, indent=2)

        summary_manifest[key] = {
            "meta": data,
            "pdf_file": pdf_path,
            "png_file": png_path,
        }

    with open(os.path.join(FIXTURES_DIR, "manifest.json"), "w") as f:
        json.dump(summary_manifest, f, indent=2)
    print(f"Generated {len(SCENARIOS)} synthetic fixtures in {FIXTURES_DIR}/")


if __name__ == "__main__":
    generate_all()
