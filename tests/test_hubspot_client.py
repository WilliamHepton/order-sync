import json
from collections.abc import Iterator

import httpx
import pytest
import respx

from order_sync.crm import get_crm
from order_sync.hubspot_client import HubSpotCrm, HubSpotError, create_hubspot_crm
from order_sync.models import Order
from order_sync.money import to_decimal
from tests.test_models import order_data

ORDER = Order.model_validate(order_data())
CONTACTS = "/crm/objects/2026-03/contacts/batch/upsert"
DEALS = "/crm/objects/2026-03/0-3/batch/upsert"
LINK = "/crm/objects/2026-03/0-3/22/associations/default/contacts/11"


@pytest.fixture
def api() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url="https://api.hubapi.com", assert_all_called=False) as router:
        router.post(CONTACTS, name="contacts").respond(200, json={"results": [{"id": "11"}]})
        router.post(DEALS, name="deals").respond(200, json={"results": [{"id": "22"}]})
        router.put(LINK, name="link").respond(200, json={})
        yield router


def crm() -> HubSpotCrm:
    return create_hubspot_crm("test-key")


def sent(api: respx.MockRouter, name: str) -> dict[str, object]:
    data: dict[str, object] = json.loads(api[name].calls.last.request.content)["inputs"][0]
    return data


def test_order_becomes_contact_and_linked_deal(api: respx.MockRouter) -> None:
    assert crm().sync_order(ORDER) == "22"
    assert sent(api, "contacts") == {
        "idProperty": "email",
        "id": "ada@example.com",
        "properties": {"email": "ada@example.com", "firstname": "Test", "lastname": "Customer"},
    }
    assert sent(api, "deals") == {
        "idProperty": "order_sync_id",
        "id": "cs_test_123",
        "properties": {
            "order_sync_id": "cs_test_123",
            "dealname": "Order test_123 (25.99 GBP)",
            "amount": "25.99",
            "description": "1 x Mug",
            "pipeline": "default",
            "dealstage": "closedwon",
        },
    }
    assert api["link"].called
    assert api["link"].calls.last.request.headers["Authorization"] == "Bearer test-key"


def test_missing_name_is_left_out(api: respx.MockRouter) -> None:
    crm().sync_order(ORDER.model_copy(update={"customer_name": None}))
    assert sent(api, "contacts")["properties"] == {"email": "ada@example.com"}


@pytest.mark.parametrize("status", [207, 400, 401, 409, 429, 500])
@pytest.mark.parametrize("step", ["contacts", "deals", "link"])
def test_any_failure_raises_without_details(api: respx.MockRouter, step: str, status: int) -> None:
    api[step].respond(status, json={"message": "ada@example.com is bad", "results": []})
    with pytest.raises(HubSpotError) as error:
        crm().sync_order(ORDER)
    assert str(error.value) == f"HubSpot returned {status}"


def test_timeout_is_raised(api: respx.MockRouter) -> None:
    api["contacts"].mock(side_effect=httpx.ConnectTimeout)
    with pytest.raises(httpx.TimeoutException):
        crm().sync_order(ORDER)


def test_hubspot_backend_can_be_chosen(monkeypatch: pytest.MonkeyPatch) -> None:
    get_crm.cache_clear()
    monkeypatch.setenv("CRM_BACKEND", "hubspot")
    monkeypatch.setenv("HUBSPOT_SERVICE_KEY", "test-key")
    assert isinstance(get_crm(), HubSpotCrm)
    get_crm.cache_clear()


@pytest.mark.parametrize(
    ("minor", "currency", "expected"),
    [(2599, "gbp", "25.99"), (5, "usd", "0.05"), (500, "jpy", "500"), (1234, "kwd", "1.234")],
)
def test_money_uses_the_currency_decimal_places(minor: int, currency: str, expected: str) -> None:
    assert str(to_decimal(minor, currency)) == expected
