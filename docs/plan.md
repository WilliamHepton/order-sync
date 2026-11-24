# Build plan

Order: M0 setup and Azure budget, M1 models and CI, M2 webhook, **early Azure deploy of the webhook**,
M3 worker and idempotency, M4 resilience, M5 Claude enrichment, M6 CSV import, M7 finish the Azure
deployment, M8 OIDC deployment, M9 monitoring, M10 write-up.

The early deploy is there because the Azure credit expires on 24 December 2026.
Every Azure resource needs approval before it is created.
What was created and how to deploy: [deployment.md](deployment.md).

Each milestone: explain, build, the developer writes one piece, review, live check, interview notes, PR.

## Decisions that differ from the brief

- HubSpot service key instead of a private app (creation ended October 2026). Confirmed on a free account (contacts read).
- Deals are upserted by a unique `order_id`, as well as the Table Storage idempotency check.
- The worker fetches Stripe line items (events omit them) and checks `payment_status`;
  `checkout.session.async_payment_succeeded` is handled too. The order key is the Checkout Session ID.
- CSV import requires a function key. The webhook is anonymous but signature-checked.
- Queue: `visibilityTimeout` 60s, `maxPollingInterval` 5s, `maxDequeueCount` 5.
- A timer function checks the poison queue, because the built-in metric is account-wide and slow.
- Lint, type check and tests run in CI from M1.
- Python 3.13. Managed identity for storage in Azure.
- `respx` mocks HubSpot; Claude is replaced by a fake client (the SDK uses `httpx2`).
- Claude cap: 100 calls a day, configurable.
