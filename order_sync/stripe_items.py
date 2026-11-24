"""Fetches what was bought. Stripe's webhook leaves this out."""

import stripe

from order_sync.models import LineItem
from order_sync.settings import required


class LineItemsError(Exception):
    """Stripe did not return the line items. The message never contains the key."""


def fetch_line_items(session_id: str) -> tuple[LineItem, ...]:
    key = required("STRIPE_API_KEY")
    if not key.startswith(("rk_test_", "sk_test_")):
        raise RuntimeError("STRIPE_API_KEY must be a test key")
    try:
        page = stripe.StripeClient(key).v1.checkout.sessions.line_items.list(
            session_id, {"limit": 100}
        )
        return tuple(
            LineItem(
                description=item.description or "Item",
                quantity=item.quantity or 1,
                amount_total=item.amount_total,
            )
            for item in page.auto_paging_iter()
        )
    except stripe.StripeError as error:
        # `from None` hides Stripe's message, which can include part of the key.
        raise LineItemsError(f"Stripe returned {error.http_status}") from None
