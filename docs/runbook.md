# Runbook: failed orders

An order that fails 5 times moves to the `orders-poison` queue. Nothing retries it automatically, and queue
messages can expire, so check promptly.

1. **Find the cause.** Search the logs for `Failed order_id=`. `ConnectError` or `HubSpot returned 503` means
   HubSpot was unreachable. `401` or `403` means a key or permission problem. `InvalidMessage` means the data
   is wrong, and replaying will not help.
2. **Fix it**, or wait for the other service to recover.
3. **List the failed orders.** With `.venv` active: `python scripts/replay_poison.py`
4. **Replay one** and check it works: `python scripts/replay_poison.py --replay --limit 1`
5. **Replay the rest:** `python scripts/replay_poison.py --replay --limit 100`

Replaying is safe to repeat, because finished orders are skipped and HubSpot writes are upserts.

For Azure, add `--account <storage account>` after `az login`. Your own account needs the **Storage Queue Data
Contributor** role on the storage account.

## How retries work

- **Within one try:** up to 3 attempts, waiting about 1s then 2s, or `Retry-After` up to 10s. Only for lost
  connections and 423, 429, 500, 502, 503 and 504. HubSpot's daily limit is not retried.
- **Across tries:** the message returns to the queue and is tried again after 60s, 5 times in all.
