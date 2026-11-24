"""Remembers which orders are finished, so a repeated message does nothing."""

import os
from datetime import UTC, datetime
from functools import lru_cache

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableClient, TableServiceClient
from azure.identity import ManagedIdentityCredential

from order_sync.settings import required

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
    account = os.environ.get("AzureWebJobsStorage__accountName")
    if account:  # in Azure: managed identity, no password
        service = TableServiceClient(
            f"https://{account}.table.core.windows.net",
            credential=ManagedIdentityCredential(
                client_id=required("AzureWebJobsStorage__clientId")
            ),
        )
    else:  # on this PC: Azurite
        service = TableServiceClient.from_connection_string(required("AzureWebJobsStorage"))
    return TableOrderStore(service.create_table_if_not_exists(TABLE))
