"""Connects to Azure Table Storage, or to Azurite on this PC."""

import os

from azure.data.tables import TableClient, TableServiceClient
from azure.identity import ManagedIdentityCredential

from order_sync.settings import required


def connect_table(name: str) -> TableClient:
    account = os.environ.get("AzureWebJobsStorage__accountName")
    if account:  # in Azure: managed identity, no password
        service = TableServiceClient(
            f"https://{account}.table.core.windows.net",
            credential=ManagedIdentityCredential(
                client_id=required("AzureWebJobsStorage__clientId")
            ),
        )
    else:
        service = TableServiceClient.from_connection_string(required("AzureWebJobsStorage"))
    return service.create_table_if_not_exists(name)
