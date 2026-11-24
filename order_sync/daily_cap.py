"""Limits how many Claude calls are made each day, across all instances."""

import os
from datetime import UTC, datetime
from functools import lru_cache

from azure.core import MatchConditions
from azure.core.exceptions import (
    ResourceExistsError,
    ResourceModifiedError,
    ResourceNotFoundError,
)
from azure.data.tables import TableClient, UpdateMode

from order_sync.tables import connect_table

TABLE = "dailycalls"
PARTITION = "claude"
DEFAULT_LIMIT = 100
TRIES = 5


def daily_limit() -> int:
    return int(os.environ.get("CLAUDE_DAILY_CAP", DEFAULT_LIMIT))


class DailyCap:
    def __init__(self, table: TableClient, limit: int) -> None:
        self._table = table
        self._limit = limit

    def try_take(self) -> bool:
        """Reserve one call. False if today's calls are used up."""
        if self._limit < 1:
            return False
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        for _ in range(TRIES):
            try:
                row = self._table.get_entity(PARTITION, today)
            except ResourceNotFoundError:
                first = {"PartitionKey": PARTITION, "RowKey": today, "count": 1}
                try:
                    self._table.create_entity(first)
                    return True
                except ResourceExistsError:
                    continue  # another worker made it first
            if row["count"] >= self._limit:
                return False
            row["count"] += 1
            try:
                # Only succeeds if nobody changed the row since we read it.
                self._table.update_entity(
                    row,
                    mode=UpdateMode.REPLACE,
                    etag=row.metadata["etag"],
                    match_condition=MatchConditions.IfNotModified,
                )
                return True
            except ResourceModifiedError:
                continue
        return False  # too busy to be sure, so do not spend


@lru_cache
def get_cap() -> DailyCap:
    return DailyCap(connect_table(TABLE), daily_limit())
