"""Show failed orders, or put them back on the orders queue.

py scripts/replay_poison.py                      list failed orders (local)
py scripts/replay_poison.py --replay --limit 1   put one back (local)
Add --account <storage account> to use Azure, signed in with `az login`.
"""

import argparse
import base64
import binascii
import json

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import AzureCliCredential
from azure.storage.queue import QueueClient

LOCAL = "UseDevelopmentStorage=true"
# Azurite does not support the newest storage version this library asks for.
LOCAL_API_VERSION = "2025-05-05"


def connect(queue: str, account: str | None) -> QueueClient:
    if account is None:
        return QueueClient.from_connection_string(LOCAL, queue, api_version=LOCAL_API_VERSION)
    url = f"https://{account}.queue.core.windows.net"
    return QueueClient(url, queue, credential=AzureCliCredential())


def order_id(content: str) -> str:
    """Only the order ID is shown, never the customer's details."""
    try:
        return str(json.loads(base64.b64decode(content))["order_id"])
    except (binascii.Error, ValueError, KeyError, TypeError):
        return "(unreadable)"


def show(poison: QueueClient) -> int:
    messages = poison.peek_messages(max_messages=32)
    for message in messages:
        print(f"{order_id(message.content)}  failed-since={message.inserted_on:%Y-%m-%d %H:%M} UTC")
    print(f"{len(messages)} shown (32 at most)")
    return len(messages)


def replay(poison: QueueClient, orders: QueueClient, limit: int) -> int:
    count = 0
    for message in poison.receive_messages(max_messages=limit, visibility_timeout=60):
        # Copy first, delete second. A crash in between leaves two copies, which the worker handles.
        orders.send_message(message.content)
        poison.delete_message(message)
        print(f"Replayed {order_id(message.content)}")
        count += 1
    print(f"{count} replayed")
    return count


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Show or replay failed orders.")
    parser.add_argument("--replay", action="store_true", help="put failed orders back")
    parser.add_argument("--limit", type=int, default=10, help="most orders to replay")
    parser.add_argument("--account", help="Azure storage account (default: Azurite)")
    options = parser.parse_args(arguments)

    poison = connect("orders-poison", options.account)
    try:
        if options.replay:
            replay(poison, connect("orders", options.account), options.limit)
        else:
            show(poison)
    except ResourceNotFoundError:
        print("No failed orders: the queue does not exist yet")


if __name__ == "__main__":
    main()
