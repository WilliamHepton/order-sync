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
