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
