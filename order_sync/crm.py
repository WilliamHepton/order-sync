"""The CRM the worker writes to: HubSpot, or a fake for local use."""

import logging
import os
from functools import lru_cache
from typing import Protocol

from order_sync.hubspot_client import create_hubspot_crm
from order_sync.models import Enrichment, Order
from order_sync.settings import required


class Crm(Protocol):
    def sync_order(self, order: Order, enrichment: Enrichment | None = None) -> str:
        """Create or update the contact and deal. Returns the deal ID."""
        ...


class FakeCrm:
    """Keeps deals in memory. Local use and tests only."""

    def __init__(self) -> None:
        self.deals: dict[str, Order] = {}

    def sync_order(self, order: Order, enrichment: Enrichment | None = None) -> str:
        self.deals[order.order_id] = order
        logging.info("Fake CRM: wrote deal order_id=%s total=%s", order.order_id, len(self.deals))
        return f"fake-{order.order_id}"


@lru_cache
def get_crm() -> Crm:
    # No default: an accidental fake in Azure would mark orders done without syncing them.
    backend = os.environ.get("CRM_BACKEND")
    if backend == "hubspot":
        return create_hubspot_crm(required("HUBSPOT_SERVICE_KEY"))
    if backend == "fake":
        return FakeCrm()
    raise RuntimeError("CRM_BACKEND must be hubspot or fake")
