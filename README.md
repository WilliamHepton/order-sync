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
