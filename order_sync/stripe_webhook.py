"""Check that a webhook came from Stripe, then turn it into our own Order."""

import stripe
from pydantic import BaseModel, ValidationError

from order_sync.models import Order, StripeEvent

HANDLED_TYPES = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
# Older signed requests are refused, so a captured request cannot be replayed later.
MAX_AGE_SECONDS = 300


class InvalidSignature(Exception):
    """The request was not provably sent by Stripe."""


class InvalidEvent(Exception):
    """The request came from Stripe, but is not a valid test-mode event."""


class EventHeader(BaseModel):
    """Just enough of any Stripe event to decide whether we handle it."""

    type: str


def verify_signature(payload: bytes, signature: str | None, secret: str) -> None:
    # `from None` hides the original error: Stripe's message can contain part of the secret.
    try:
        stripe.WebhookSignature.verify_header(payload, signature, secret, MAX_AGE_SECONDS)
    except (stripe.SignatureVerificationError, UnicodeDecodeError, TypeError):
        raise InvalidSignature from None


def read_order(payload: bytes) -> Order | None:
    """Return the paid order, or None if this event needs no action."""
    # `from None` again: validation errors contain the customer's details.
    try:
        header = EventHeader.model_validate_json(payload)
        if header.type not in HANDLED_TYPES:
            return None
        session = StripeEvent.model_validate_json(payload).data.object
    except ValidationError:
        raise InvalidEvent from None

    if session.payment_status == "unpaid":
        return None
    return Order(
        order_id=session.id,
        email=session.customer_details.email,
        customer_name=session.customer_details.name,
        amount_total=session.amount_total,
        currency=session.currency,
    )
