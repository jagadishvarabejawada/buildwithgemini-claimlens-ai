"""Duplicate detection module for ClaimLens AI expense claims."""

from typing import Any, Dict, List, Optional
import unicodedata


def normalize_text(val: Optional[str]) -> str:
    """Normalize string for fuzzy-resistant duplicate lookup."""
    if not val:
        return ""
    normalized = unicodedata.normalize("NFKD", str(val))
    return "".join(c for c in normalized if c.isalnum()).lower()


def check_for_duplicates(
    claim_id: str,
    file_hash: Optional[str],
    merchant: str,
    receipt_date: str,
    receipt_amount_paise: int,
    currency: str,
    receipt_reference: Optional[str],
    existing_audits: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Check if the submission matches existing claims by hash or attributes.

    Returns:
        Dict detailing duplicate findings without alleging fraud.
    """
    exact_hash_match = []
    metadata_match = []

    norm_merchant = normalize_text(merchant)
    norm_ref = normalize_text(receipt_reference) if receipt_reference else ""

    for audit in existing_audits:
        existing_id = audit.get("claim_id")
        # Exclude same claim on retry / update
        if existing_id == claim_id:
            continue

        existing_hash = audit.get("file_hash")
        if file_hash and existing_hash and file_hash == existing_hash:
            exact_hash_match.append({
                "claim_id": existing_id,
                "reason": "Exact file content match (identical SHA-256 hash)",
                "created_at": audit.get("created_at"),
            })

        # Attribute lookup: merchant + date + currency + amount
        existing_merchant = normalize_text(audit.get("merchant"))
        existing_date = str(audit.get("receipt_date", "")).strip()
        existing_curr = str(audit.get("currency", "")).upper()
        existing_paise = audit.get("receipt_amount", 0)
        existing_ref = normalize_text(audit.get("receipt_reference"))

        same_merchant = norm_merchant and (norm_merchant == existing_merchant)
        same_date = receipt_date and (receipt_date == existing_date)
        same_amount = receipt_amount_paise and (receipt_amount_paise == existing_paise)
        same_curr = currency and (currency == existing_curr)
        same_ref = norm_ref and existing_ref and (norm_ref == existing_ref)

        if (same_merchant and same_date and same_amount and same_curr) or same_ref:
            metadata_match.append({
                "claim_id": existing_id,
                "merchant": audit.get("merchant"),
                "date": existing_date,
                "amount_paise": existing_paise,
                "reason": "Matching merchant, date, currency, and verified receipt amount",
            })

    is_duplicate = bool(exact_hash_match or metadata_match)
    return {
        "is_potential_duplicate": is_duplicate,
        "exact_file_matches": exact_hash_match,
        "similar_claim_matches": metadata_match,
        "requires_human_verification": is_duplicate,
        "note": "Requires human reviewer confirmation to verify whether this represents a re-submission or separate transaction."
        if is_duplicate
        else "No duplicate claims detected.",
    }
