"""Remembers which orders are finished, so a repeated message does nothing."""

from datetime import UTC, datetime
from functools import lru_cache

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableClient

from order_sync.tables import connect_table

TABLE = "processedorders"
PARTITION = "order"


class TableOrderStore:
    def __init__(self, table: TableClient) -> None:
        self._table = table

    def is_done(self, order_id: str) -> bool:
        try:
            self._table.get_entity(PARTITION, order_id)
        except ResourceNotFoundError:
            return False
        return True

    def mark_done(self, order_id: str, deal_id: str) -> None:
        # Upsert, so two workers finishing the same order at once is harmless.
        self._table.upsert_entity(
            {
                "PartitionKey": PARTITION,
                "RowKey": order_id,
                "deal_id": deal_id,
                "processed_at": datetime.now(UTC),
            }
        )


@lru_cache  # one client per worker process, like a singleton service
def get_store() -> TableOrderStore:
    return TableOrderStore(connect_table(TABLE))
