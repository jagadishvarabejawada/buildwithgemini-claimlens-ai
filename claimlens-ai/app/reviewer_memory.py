"""Reviewer preference and memory integration for ClaimLens AI.

Distinguishes reviewer preferences (Memory Bank) from transactional
audit history (Firestore).
"""

from typing import Any, Dict, Optional

# In-memory preference store for local development
_LOCAL_REVIEWER_PREFERENCES: Dict[str, Dict[str, Any]] = {
    "default_reviewer": {
        "reviewer_id": "auditor_ops_01",
        "display_name": "Senior Expense Auditor",
        "detail_level": "comprehensive",
        "auto_highlight_mismatches": True,
    }
}


def get_reviewer_preferences(user_id: str = "default_reviewer") -> Dict[str, Any]:
    """Retrieve durable preferences for a reviewer."""
    return _LOCAL_REVIEWER_PREFERENCES.get(
        user_id,
        {
            "reviewer_id": user_id,
            "display_name": "Reviewer",
            "detail_level": "standard",
            "auto_highlight_mismatches": True,
        },
    )


def save_reviewer_preference(
    key: str,
    value: Any,
    user_id: str = "default_reviewer",
) -> Dict[str, Any]:
    """Update a specific reviewer preference."""
    if user_id not in _LOCAL_REVIEWER_PREFERENCES:
        _LOCAL_REVIEWER_PREFERENCES[user_id] = {}
    _LOCAL_REVIEWER_PREFERENCES[user_id][key] = value
    return {
        "status": "success",
        "user_id": user_id,
        "preferences": _LOCAL_REVIEWER_PREFERENCES[user_id],
    }
