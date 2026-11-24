import json
import time
from typing import Any

import azure.functions as func
import pytest
import stripe

from function_app import receive_webhook
from order_sync.models import Order
from order_sync.stripe_webhook import InvalidEvent, InvalidSignature, read_order, verify_signature
from tests.test_models import event_data

SECRET = "test-signing-value"


class FakeOut(func.Out[str]):
    """Stands in for the queue output binding."""

    def __init__(self) -> None:
        self.value: str | None = None

    def set(self, val: str) -> None:
        self.value = val

    def get(self) -> str | None:  # type: ignore[override]
        return self.value


def body(**changes: Any) -> bytes:
    return json.dumps(event_data() | changes).encode()


def session_body(**changes: Any) -> bytes:
    event = event_data()
    event["data"]["object"] |= changes
    return json.dumps(event).encode()


def sign(payload: bytes, timestamp: int | None = None) -> str:
    header: str = stripe.WebhookSignature.generate_signature_header(
        payload.decode(), SECRET, timestamp
    )
    return header


def send(payload: bytes, signature: str | None) -> tuple[func.HttpResponse, str | None]:
    headers = {"Stripe-Signature": signature} if signature is not None else {}
    request = func.HttpRequest("POST", "/api/stripe/webhook", headers=headers, body=payload)
    out = FakeOut()
    return receive_webhook(request, out), out.value


@pytest.fixture(autouse=True)
def webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)


def test_paid_order_is_queued() -> None:
    payload = body()
    response, message = send(payload, sign(payload))
    assert response.status_code == 200
    assert message is not None
    order = Order.model_validate_json(message)
    assert order.order_id == "cs_test_123"
    assert order.amount_total == 2599


@pytest.mark.parametrize("signature", [None, "", "nonsense", "t=1,v1=é", "t=abc,v1=00"])
def test_missing_or_malformed_signature_is_rejected(signature: str | None) -> None:
    response, message = send(body(), signature)
    assert response.status_code == 400
    assert message is None


def test_altered_body_is_rejected() -> None:
    signature = sign(body())
    response, message = send(session_body(amount_total=1), signature)
    assert response.status_code == 400
    assert message is None


def test_old_signature_is_rejected() -> None:
    payload = body()
    with pytest.raises(InvalidSignature):
        verify_signature(payload, sign(payload, int(time.time()) - 600), SECRET)


def test_body_that_is_not_utf8_is_rejected() -> None:
    with pytest.raises(InvalidSignature):
        verify_signature(b"\xff", "t=1,v1=00", SECRET)


def test_signature_error_hides_the_secret() -> None:
    with pytest.raises(InvalidSignature) as error:
        verify_signature(body(), f"t={int(time.time())},v1=00,secret=whsec_****abcd", SECRET)
    assert str(error.value) == ""
    assert error.value.__suppress_context__


def test_other_event_types_are_ignored() -> None:
    payload = body(type="invoice.paid")
    response, message = send(payload, sign(payload))
    assert response.status_code == 200
    assert message is None


def test_live_event_is_rejected() -> None:
    payload = body(livemode=True)
    response, message = send(payload, sign(payload))
    assert response.status_code == 400
    assert message is None


@pytest.mark.parametrize("payload", [b"", b"not json", b"[]", session_body(currency="POUNDS")])
def test_invalid_event_is_rejected(payload: bytes) -> None:
    with pytest.raises(InvalidEvent):
        read_order(payload)


def test_missing_secret_is_a_server_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET")
    with pytest.raises(RuntimeError, match="STRIPE_WEBHOOK_SECRET is not set"):
        send(body(), None)


# EXERCISE: write test_unpaid_order_is_ignored here.
