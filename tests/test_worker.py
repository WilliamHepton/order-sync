import azure.functions as func
import pytest
from azure.core.exceptions import ResourceNotFoundError

import function_app
from order_sync.crm import FakeCrm, get_crm
from order_sync.idempotency import TableOrderStore
from order_sync.models import LineItem, Order
from order_sync.worker import InvalidMessage, parse_order, process_order
from tests.test_models import order_data


class FakeTable:
    """Stands in for an Azure table."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict[str, object]] = {}

    def get_entity(self, partition: str, row: str) -> dict[str, object]:
        if (partition, row) not in self.rows:
            raise ResourceNotFoundError
        return self.rows[partition, row]

    def upsert_entity(self, entity: dict[str, object]) -> None:
        self.rows[str(entity["PartitionKey"]), str(entity["RowKey"])] = entity


class CountingCrm(FakeCrm):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def sync_order(self, order: Order) -> str:
        self.calls += 1
        return super().sync_order(order)


def new_store() -> TableOrderStore:
    return TableOrderStore(FakeTable())  # type: ignore[arg-type]


ORDER = Order.model_validate(order_data())


def test_order_is_synced_and_marked_done() -> None:
    store, crm = new_store(), CountingCrm()
    assert process_order(ORDER, store, crm) is True
    assert store.is_done(ORDER.order_id)
    assert crm.deals == {ORDER.order_id: ORDER}


def test_same_order_twice_makes_one_deal() -> None:
    store, crm = new_store(), CountingCrm()
    assert process_order(ORDER, store, crm) is True
    assert process_order(ORDER, store, crm) is False
    assert crm.calls == 1
    assert len(crm.deals) == 1


def test_different_orders_are_both_synced() -> None:
    store, crm = new_store(), CountingCrm()
    other = Order.model_validate(order_data() | {"order_id": "cs_test_456"})
    process_order(ORDER, store, crm)
    process_order(other, store, crm)
    assert crm.calls == 2


def test_crash_before_marking_done_is_safe_to_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    store, crm = new_store(), CountingCrm()

    def crash(order_id: str, deal_id: str) -> None:
        raise ConnectionError

    with monkeypatch.context() as patch:
        patch.setattr(store, "mark_done", crash)
        with pytest.raises(ConnectionError):
            process_order(ORDER, store, crm)
    process_order(ORDER, store, crm)
    assert crm.calls == 2
    assert len(crm.deals) == 1


@pytest.mark.parametrize("body", [b"", b"not json", b"{}"])
def test_invalid_message_is_rejected_without_details(body: bytes) -> None:
    with pytest.raises(InvalidMessage) as error:
        parse_order(body)
    assert str(error.value) == ""


def test_queue_function_processes_message(monkeypatch: pytest.MonkeyPatch) -> None:
    store, crm = new_store(), CountingCrm()
    monkeypatch.setattr(function_app, "get_store", lambda: store)
    monkeypatch.setattr(function_app, "get_crm", lambda: crm)
    function_app.process_order_message(func.QueueMessage(body=ORDER.model_dump_json().encode()))
    assert crm.calls == 1


def test_crm_backend_must_be_chosen(monkeypatch: pytest.MonkeyPatch) -> None:
    get_crm.cache_clear()
    monkeypatch.delenv("CRM_BACKEND", raising=False)
    with pytest.raises(RuntimeError):
        get_crm()
    monkeypatch.setenv("CRM_BACKEND", "fake")
    assert isinstance(get_crm(), FakeCrm)
    get_crm.cache_clear()


def test_missing_items_are_fetched_once_per_order() -> None:
    store, crm = new_store(), CountingCrm()
    calls: list[str] = []

    def fetch(session_id: str) -> tuple[LineItem, ...]:
        calls.append(session_id)
        return (LineItem(description="Mug", quantity=2, amount_total=2599),)

    order = ORDER.model_copy(update={"items": ()})
    process_order(order, store, crm, fetch)
    process_order(order, store, crm, fetch)
    assert calls == [ORDER.order_id]
    assert crm.deals[ORDER.order_id].items[0].quantity == 2


def test_items_are_not_fetched_for_other_sources() -> None:
    crm = CountingCrm()
    order = ORDER.model_copy(update={"items": (), "order_id": "csv-1"})

    def fetch(session_id: str) -> tuple[LineItem, ...]:
        raise AssertionError("should not be called")

    assert process_order(order, new_store(), crm, fetch)


# EXERCISE: write test_failed_order_is_not_marked_done here.
