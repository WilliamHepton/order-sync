import json
from typing import Any

import pytest
import stripe

from order_sync.models import LineItem
from order_sync.stripe_items import LineItemsError, fetch_line_items


class FakeHttp(stripe.HTTPClient):
    """Returns one canned reply instead of calling Stripe."""

    name = "fake"
    reply: tuple[str, int] = ("", 200)

    def request(self, *args: Any, **kwargs: Any) -> tuple[str, int, dict[str, str]]:
        return self.reply[0], self.reply[1], {}

    def close(self) -> None:
        pass


@pytest.fixture
def http(monkeypatch: pytest.MonkeyPatch) -> FakeHttp:
    fake = FakeHttp()
    real = stripe.StripeClient
    monkeypatch.setenv("STRIPE_API_KEY", "rk_test_fake")
    monkeypatch.setattr(stripe, "StripeClient", lambda key, **_: real(key, http_client=fake))
    return fake


def test_items_are_converted(http: FakeHttp) -> None:
    items = [
        {"id": "li_1", "object": "item", "description": "Mug", "quantity": 2, "amount_total": 3000},
        {"id": "li_2", "object": "item", "description": None, "quantity": None, "amount_total": 0},
    ]
    page = {"object": "list", "has_more": False, "url": "/x", "data": items}
    http.reply = (json.dumps(page), 200)
    assert fetch_line_items("cs_test_1") == (
        LineItem(description="Mug", quantity=2, amount_total=3000),
        LineItem(description="Item", quantity=1, amount_total=0),
    )


def test_error_hides_stripes_message(http: FakeHttp) -> None:
    http.reply = ('{"error": {"message": "Bad key rk_test_fake", "type": "x"}}', 403)
    with pytest.raises(LineItemsError) as error:
        fetch_line_items("cs_test_1")
    assert str(error.value) == "Stripe returned 403"


def test_live_key_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRIPE_API_KEY", "not-a-test-key")
    with pytest.raises(RuntimeError, match="must be a test key"):
        fetch_line_items("cs_test_1")
