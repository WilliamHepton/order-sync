"""Writes orders to HubSpot. Every call is safe to repeat."""

from typing import Any

import httpx

from order_sync.models import Enrichment, Order
from order_sync.money import to_decimal
from order_sync.retry import send_with_retry

BASE_URL = "https://api.hubapi.com"
DEALS = "0-3"  # HubSpot's ID for the deal object
PIPELINE = "default"
PAID_STAGE = "closedwon"


class HubSpotError(Exception):
    """A HubSpot call failed. The message holds only the status, never customer details."""


class HubSpotCrm:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def sync_order(self, order: Order, enrichment: Enrichment | None = None) -> str:
        contact_id = self._upsert("contacts", "email", order.email.lower(), contact(order))
        deal_id = self._upsert(DEALS, "order_sync_id", order.order_id, deal(order, enrichment))
        link = f"{DEALS}/{deal_id}/associations/default/contacts/{contact_id}"
        self._send("PUT", f"/crm/objects/2026-03/{link}")
        return deal_id

    def _upsert(self, kind: str, key: str, value: str, properties: dict[str, str]) -> str:
        """Create the record, or update it if one with this unique value exists."""
        result = self._send(
            "POST",
            f"/crm/objects/2026-03/{kind}/batch/upsert",
            {"inputs": [{"idProperty": key, "id": value, "properties": properties}]},
        )
        return str(result["results"][0]["id"])

    def _send(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        response = send_with_retry(lambda: self._client.request(method, path, json=body))
        # 207 means part of a batch failed. We send one record, so that is a failure.
        if response.is_error or response.status_code == 207:
            raise HubSpotError(f"HubSpot returned {response.status_code}")
        data: dict[str, Any] = response.json()
        return data


def contact(order: Order) -> dict[str, str]:
    properties = {"email": order.email.lower()}
    if order.customer_name:
        first, _, last = order.customer_name.partition(" ")
        properties |= {"firstname": first, "lastname": last}
    return properties


def deal(order: Order, enrichment: Enrichment | None = None) -> dict[str, str]:
    amount = to_decimal(order.amount_total, order.currency)
    properties = {
        "order_sync_id": order.order_id,
        # The currency is in the name because a free account may have only one currency.
        "dealname": f"Order {order.order_id[-8:]} ({amount} {order.currency.upper()})",
        "amount": str(amount),
        "description": "; ".join(f"{i.quantity} x {i.description}" for i in order.items)[:1000],
        "pipeline": PIPELINE,
        "dealstage": PAID_STAGE,
    }
    if enrichment:
        properties |= {
            "ai_customer_segment": enrichment.customer_segment,
            "ai_priority": enrichment.priority,
            "ai_summary": enrichment.summary,
            "ai_follow_up_needed": str(enrichment.follow_up_needed).lower(),
        }
    return properties


def create_hubspot_crm(key: str) -> HubSpotCrm:
    client = httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {key}"}, timeout=15)
    return HubSpotCrm(client)
