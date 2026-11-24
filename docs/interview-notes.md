# Interview notes

## M0: Setup

**How do you keep secrets out of a public repository?**
Real values live in a git-ignored `local.settings.json`; only a blank example file is committed.
A gitleaks pre-commit hook scans staged changes and blocks the commit if it finds a secret or cannot
run. Hooks are local and can be skipped, so a scan in CI is a useful second check. If a key leaks, I
revoke it first, because deleting it from a later commit leaves it in the history.

**What does least privilege mean here?**
Each key gets only the permissions it needs. The HubSpot key has read and write access to contacts and
deals only. A leak could still affect those records, but no other parts of the account.

**Does a cloud budget stop you overspending?**
No. An Azure budget sends alerts, based on cost data that can lag. I also use free tiers, cap paid API
calls, and delete the resource group when finished.

## M1: Models and CI

**Why validate data with Pydantic when Python already has type hints?**
Python does not enforce type hints at run time. mypy checks our code before it runs, but data from Stripe
or Claude arrives at run time, so Pydantic checks it at the boundary and rejects bad input.

**Why store money as an integer?**
Floats cannot represent many decimal amounts exactly, so totals can drift. We store minor units such as
pence, with the currency alongside, as Stripe does.

**What does your CI pipeline protect against?**
It runs linting, formatting, type checks, tests and a secret scan on a clean machine for every pull
request, so it catches "works on my machine" problems and skipped local hooks. Actions are pinned to
commit hashes because tags can be moved. To block a bad merge, the checks must also be required in
GitHub's branch rules.

## M2: Stripe webhook

**How do you know a webhook really came from Stripe?**
Stripe signs the timestamp and raw body with a shared secret (HMAC-SHA256). We repeat the calculation on
the exact bytes received and compare. Parsing and rewriting the JSON first could change the bytes and
break the check. Signatures older than five minutes are refused, which limits replays.

**Why put the order on a queue instead of calling HubSpot in the request?**
Stripe needs a quick reply and HubSpot may be slow or down. The queue keeps the order safe until a worker
can process it. The trade-off is that it may be delivered more than once, so the worker must be
idempotent.

**What status code do you return in each case?**
200 when the order is queued or the event is not one we handle, so Stripe does not retry. 400 for a bad
signature or invalid event. A missing secret or queue failure gives a 500, so Stripe retries later.

## Early Azure deployment

**Why use a managed identity instead of a connection string?**
There is no stored password to leak or rotate. Azure issues short-lived tokens to the app, and roles limit
what it can do. Shared keys are disabled, so a storage key cannot be used at all.

**Tell me about a production problem you diagnosed.**
Every second request failed with a 503 after 60 seconds. Raising the instance limit from one to two changed
the pattern to every third request, so the limit was not the cause, but capacity per instance was a clue.
Raising HTTP concurrency stopped the failures, and I put the limit back to one. I could not confirm why
Azure treated instances as busy.

**What does Flex Consumption give you, and what is the catch?**
It scales to zero and bills on-demand use. The catch is cold starts: the first real order took about three
seconds, probably while the app was waking up.

## M3: Queue worker and duplicates

**What does idempotent mean, and how did you achieve it?**
Processing the same order twice has the same result as once. Finished order IDs are stored in Table Storage
and skipped. The HubSpot contact and deal are upserts with unique keys, so a repeat updates the same records.

**Isn't checking a table enough?**
No. Two copies arriving together can both pass the check before either is marked done. I saw this in a local
test. The unique `order_sync_id` property lets HubSpot settle it: four simultaneous writes made one deal.

**Why mark the order done last?**
If the worker crashes after the HubSpot write, the message is retried and the upsert repeats safely. Marking
it done first could lose the order if the HubSpot write then failed.

## M4: Resilience

**What is exponential backoff with jitter?**
Each wait is longer than the last (about 1s, then 2s), which gives a struggling service time to recover. A
small random extra stops many workers retrying at the same moment.

**Which errors do you retry?**
Temporary ones: lost connections, 429 and most 5xx. A 401 or 400 will not fix itself. Retrying is only safe
because the HubSpot calls are upserts.

**What happens if HubSpot is down for an hour?**
The order fails 5 tries and moves to a poison queue, where it waits. A script puts it back after the fix. I
tested this locally with HubSpot unreachable: the order was parked, then recovered.
