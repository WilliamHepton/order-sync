"""The CRM the worker writes to. The real HubSpot client replaces the fake one next."""

import logging
import os
from functools import lru_cache
from typing import Protocol

from order_sync.models import Order


class Crm(Protocol):
    def sync_order(self, order: Order) -> str:
        """Create or update the contact and deal. Returns the deal ID."""
        ...


class FakeCrm:
    """Keeps deals in memory. Local use and tests only."""

    def __init__(self) -> None:
        self.deals: dict[str, Order] = {}

    def sync_order(self, order: Order) -> str:
        self.deals[order.order_id] = order
        logging.info("Fake CRM: wrote deal order_id=%s total=%s", order.order_id, len(self.deals))
        return f"fake-{order.order_id}"


@lru_cache
def get_crm() -> Crm:
    # No default: an accidental fake in Azure would mark orders done without syncing them.
    if os.environ.get("CRM_BACKEND") == "fake":
        return FakeCrm()
    raise RuntimeError("CRM_BACKEND is not set")
