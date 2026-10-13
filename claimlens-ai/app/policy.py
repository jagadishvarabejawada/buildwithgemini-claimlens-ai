"""Synthetic corporate policy definitions for ClaimLens AI."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

@dataclass(frozen=True)
class ExpensePolicy:
    policy_id: str = "PP-DEMO-001"
    version: str = "1.0"
    category: str = "business_travel"
    currency: str = "INR"
    max_reimbursement: Decimal = Decimal("7500.00")
    require_receipt_match: bool = True
    require_human_decision: bool = True

DEFAULT_POLICY = ExpensePolicy()
