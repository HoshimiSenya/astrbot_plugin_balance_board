"""Shared result models."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal

from .accounts import Account
from .errors import BalanceError


@dataclass(frozen=True)
class BalanceSnapshot:
    """A successful balance query."""

    account: Account
    available: Decimal
    currency: str
    metric: str
    value_text: str = ""
    metric_text: str = ""
    secondary: str = ""
    fetched_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class AccountResult:
    """Query result for one account, including failures."""

    account: Account
    balance: BalanceSnapshot | None = None
    error: BalanceError | None = None

    @property
    def ok(self) -> bool:
        return self.balance is not None
