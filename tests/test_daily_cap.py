from typing import Any

import pytest
from azure.core.exceptions import (
    ResourceExistsError,
    ResourceModifiedError,
    ResourceNotFoundError,
)

from order_sync.daily_cap import DailyCap, daily_limit


class Row(dict[str, Any]):
    metadata = {"etag": "1"}


class FakeTable:
    def __init__(self) -> None:
        self.row: Row | None = None
        self.conflicts = 0

    def get_entity(self, partition: str, row: str) -> Row:
        if self.row is None:
            raise ResourceNotFoundError
        return Row(self.row)

    def create_entity(self, entity: dict[str, Any]) -> None:
        if self.conflicts:
            self.conflicts -= 1
            self.row = Row(entity)
            raise ResourceExistsError
        self.row = Row(entity)

    def update_entity(self, entity: Row, **options: Any) -> None:
        assert options["etag"] == "1"
        if self.conflicts:
            self.conflicts -= 1
            raise ResourceModifiedError
        self.row = entity


def cap(table: FakeTable, limit: int) -> DailyCap:
    return DailyCap(table, limit)  # type: ignore[arg-type]


def test_calls_stop_at_the_limit() -> None:
    limited = cap(FakeTable(), 2)
    assert [limited.try_take() for _ in range(4)] == [True, True, False, False]


@pytest.mark.parametrize("limit", [0, -1])
def test_zero_means_off(limit: int) -> None:
    assert cap(FakeTable(), limit).try_take() is False


def test_another_worker_creating_the_row_is_counted() -> None:
    table = FakeTable()
    table.conflicts = 1
    assert cap(table, 5).try_take() is True
    assert table.row is not None and table.row["count"] == 2


def test_busy_table_does_not_spend() -> None:
    table = FakeTable()
    limited = cap(table, 100)
    limited.try_take()
    table.conflicts = 50
    assert limited.try_take() is False


def test_limit_comes_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_DAILY_CAP", raising=False)
    assert daily_limit() == 100
    monkeypatch.setenv("CLAUDE_DAILY_CAP", "7")
    assert daily_limit() == 7
