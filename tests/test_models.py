from typing import Any

import pytest
from pydantic import ValidationError

from order_sync.models import Enrichment, LineItem, Order, StripeEvent


def order_data() -> dict[str, Any]:
    return {
        "order_id": "cs_test_123",
        "email": "ada@example.com",
        "customer_name": "Test Customer",
        "amount_total": 2599,
        "currency": "gbp",
        "items": [{"description": "Mug", "quantity": 1, "amount_total": 2599}],
    }


def event_data() -> dict[str, Any]:
    return {
        "id": "evt_test_123",
        "type": "checkout.session.completed",
        "livemode": False,
        "api_version": "ignored",
        "data": {
            "object": {
                "id": "cs_test_123",
                "payment_status": "paid",
                "amount_total": 2599,
                "currency": "gbp",
                "customer_details": {"email": "ada@example.com", "name": "Test Customer"},
            }
        },
    }


def enrichment_data() -> dict[str, Any]:
    return {
        "customer_segment": "new",
        "priority": "normal",
        "summary": "One mug ordered.",
        "follow_up_needed": False,
    }


def test_valid_order() -> None:
    order = Order.model_validate(order_data())
    assert order.amount_total == 2599
    assert order.items == (LineItem(description="Mug", quantity=1, amount_total=2599),)
    assert order.customer_note == ""


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("order_id", ""),
        ("order_id", "has/slash"),
        ("email", "not-an-email"),
        ("amount_total", 25.99),
        ("amount_total", "2599"),
        ("amount_total", -1),
        ("currency", "GBP"),
        ("customer_note", "x" * 501),
        ("items", [{"description": "Mug", "quantity": 0, "amount_total": 0}]),
        ("unexpected", "value"),
    ],
)
def test_invalid_order_is_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError) as error:
        Order.model_validate(order_data() | {field: value})
    assert error.value.errors()[0]["loc"][0] == field


def test_order_cannot_be_changed() -> None:
    order = Order.model_validate(order_data())
    with pytest.raises(ValidationError):
        order.amount_total = 1  # type: ignore[misc]


def test_order_survives_json_round_trip() -> None:
    order = Order.model_validate(order_data())
    assert Order.model_validate_json(order.model_dump_json()) == order


def test_valid_event_ignores_extra_fields() -> None:
    event = StripeEvent.model_validate(event_data())
    assert event.data.object.id == "cs_test_123"
    assert not hasattr(event, "api_version")


@pytest.mark.parametrize(("field", "value"), [("livemode", True), ("type", "invoice.paid")])
def test_unwanted_event_is_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        StripeEvent.model_validate(event_data() | {field: value})


def test_valid_enrichment() -> None:
    assert Enrichment.model_validate(enrichment_data()).priority == "normal"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("customer_segment", "vip"),
        ("priority", "urgent"),
        ("summary", ""),
        ("follow_up_needed", "yes"),
    ],
)
def test_invalid_enrichment_is_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Enrichment.model_validate(enrichment_data() | {field: value})


def test_twenty_word_summary_is_accepted() -> None:
    summary = " ".join(["word"] * 20)
    enrichment = Enrichment.model_validate(enrichment_data() | {"summary": summary})
    assert enrichment.summary == summary


def test_twenty_one_word_summary_is_rejected() -> None:
    summary = " ".join(["word"] * 21)
    with pytest.raises(ValidationError, match="20 words or fewer"):
        Enrichment.model_validate(enrichment_data() | {"summary": summary})
