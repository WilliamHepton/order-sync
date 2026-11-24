"""Processes one order from the queue."""

import logging
from collections.abc import Callable
from typing import Protocol

from pydantic import ValidationError

from order_sync.crm import Crm
from order_sync.models import LineItem, Order
from order_sync.stripe_items import fetch_line_items

ItemFetcher = Callable[[str], tuple[LineItem, ...]]


class OrderStore(Protocol):
    def is_done(self, order_id: str) -> bool: ...

    def mark_done(self, order_id: str, deal_id: str) -> None: ...


class InvalidMessage(Exception):
    """The queue message is not a valid order."""


def parse_order(body: bytes) -> Order:
    # `from None` keeps the customer's details out of the logs.
    try:
        return Order.model_validate_json(body)
    except ValidationError:
        raise InvalidMessage from None


def process_order(
    order: Order, store: OrderStore, crm: Crm, fetch_items: ItemFetcher = fetch_line_items
) -> bool:
    """Sync the order. Returns False if it was already done."""
    # Two copies arriving together can both pass this check, so the CRM write must be an upsert too.
    if store.is_done(order.order_id):
        logging.info("Skipped, already processed order_id=%s", order.order_id)
        return False
    if not order.items and order.order_id.startswith("cs_"):  # a Stripe Checkout Session
        order = order.model_copy(update={"items": fetch_items(order.order_id)})
    deal_id = crm.sync_order(order)
    # Last on purpose: if this fails, the message is retried and the CRM upsert repeats safely.
    store.mark_done(order.order_id, deal_id)
    logging.info("Processed order_id=%s", order.order_id)
    return True
