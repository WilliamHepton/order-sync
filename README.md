# Order Sync

A learning project: Stripe test orders are synced to HubSpot with Python and Azure Functions.
Work in progress. See the [build plan](docs/plan.md). It uses test data only.

## Local setup

1. Copy `local.settings.example.json` to `local.settings.json` and fill in your own test keys.
2. Install gitleaks, then run `git config core.hooksPath .githooks`.
3. Check the HubSpot key with `py -3.13 scripts/check_hubspot.py`.

## Run the webhook locally

Create a Python 3.13 virtual environment in `.venv`, activate it and run
`pip install -r requirements-dev.txt`. Put the value from `stripe listen --print-secret` in
`STRIPE_WEBHOOK_SECRET`, then run each of these in its own terminal (activate `.venv` first for `func`):

    azurite --silent --location .azurite
    func start
    stripe listen --events checkout.session.completed,checkout.session.async_payment_succeeded --forward-to localhost:7071/api/stripe/webhook

Send a test order with `stripe trigger checkout.session.completed`.

## HubSpot setup

Create a single-line text deal property with the internal name `order_sync_id`, ticking **Require unique
values** while creating it (it cannot be added later). Set `CRM_BACKEND` to `hubspot`, or to `fake` to run
without HubSpot.

## Stripe key

The worker needs `STRIPE_API_KEY`: a sandbox secret key whose only permission is **Checkout Sessions: Read**.
Live keys are refused.

## Claude enrichment

Off unless `ANTHROPIC_API_KEY` is set. `CLAUDE_DAILY_CAP` limits the calls made each day (default 100; 0 turns
it off). Before switching it on, create these single-line text deal properties in HubSpot, or its writes will
fail: `ai_customer_segment`, `ai_priority`, `ai_summary`, `ai_follow_up_needed`. Names and emails are not sent
to Claude.

## CSV import

POST a UTF-8 CSV (up to 1 MB and 1,000 orders) to `/api/orders/import`. Required columns: `order_id`, `email`,
`amount`, `currency`. Optional: `customer_name`, `customer_note`. Amounts are like `25.99`. In Azure, send a
function key in the `x-functions-key` header.
