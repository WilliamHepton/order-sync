# Order Sync

A learning project: Stripe test orders are synced to HubSpot with Python and Azure Functions.
Work in progress. See the [build plan](docs/plan.md). It uses test data only.

## Local setup

1. Copy `local.settings.example.json` to `local.settings.json` and fill in your own test keys.
2. Install gitleaks, then run `git config core.hooksPath .githooks`.
3. Check the HubSpot key with `py -3.13 scripts/check_hubspot.py`.
