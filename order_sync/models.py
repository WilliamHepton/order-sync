"""The data shapes used by Order Sync."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Money is a whole number of minor units (pence, cents), as Stripe sends it. Never use float.
MinorUnits = Annotated[int, Field(strict=True, ge=0)]
Currency = Annotated[str, Field(pattern=r"^[a-z]{3}$")]
NonEmptyStr = Annotated[str, Field(min_length=1)]


class CustomerDetails(BaseModel):
    email: EmailStr
    name: str | None = None


class CheckoutSession(BaseModel):
    """The parts of a Stripe Checkout Session we use. Other fields are ignored."""

    id: NonEmptyStr
    payment_status: Literal["paid", "unpaid", "no_payment_required"]
    amount_total: MinorUnits
    currency: Currency
    customer_details: CustomerDetails


class StripeEventData(BaseModel):
    object: CheckoutSession


class StripeEvent(BaseModel):
    """A Checkout event. Live events are rejected because this project is test mode only."""

    id: NonEmptyStr
    type: Literal["checkout.session.completed", "checkout.session.async_payment_succeeded"]
    livemode: Literal[False]
    data: StripeEventData


class LineItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    description: NonEmptyStr
    quantity: Annotated[int, Field(strict=True, ge=1)]
    amount_total: MinorUnits


class Order(BaseModel):
    """Our own order format, the same whether it came from Stripe or a CSV file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    order_id: NonEmptyStr
    email: EmailStr
    customer_name: str | None = None
    amount_total: MinorUnits
    currency: Currency
    # Empty until the worker fetches them: Stripe events do not include line items.
    items: tuple[LineItem, ...] = ()
    customer_note: Annotated[str, Field(max_length=500)] = ""


class Enrichment(BaseModel):
    """What Claude returns about an order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    customer_segment: Literal["new", "returning", "business", "unknown"]
    priority: Literal["low", "normal", "high"]
    summary: NonEmptyStr
    follow_up_needed: Annotated[bool, Field(strict=True)]
