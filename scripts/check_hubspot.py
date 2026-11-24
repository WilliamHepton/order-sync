"""Check that the HubSpot service key can read contacts. Never prints the key."""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

SETTINGS = Path(__file__).resolve().parent.parent / "local.settings.json"
URL = "https://api.hubapi.com/crm/objects/2026-03/contacts?limit=1"


def main() -> int:
    # utf-8-sig also accepts files saved with a byte order mark.
    settings = json.loads(SETTINGS.read_text(encoding="utf-8-sig"))
    key = settings["Values"].get("HUBSPOT_SERVICE_KEY", "").strip()
    if not key:
        print("HUBSPOT_SERVICE_KEY is empty in local.settings.json")
        return 1

    request = urllib.request.Request(URL, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            print(f"OK: HubSpot returned {response.status}")
            return 0
    except urllib.error.HTTPError as error:
        print(f"Failed: HubSpot returned {error.code}")
    except urllib.error.URLError as error:
        print(f"Failed: could not reach HubSpot ({error.reason})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
