# Cookie garage

A lightweight bookmark list for catalog vehicle/part applications. There are no accounts, authentication, checkout, orders or server-side saved-bookmark database.

## Use

Restart the existing server after this update:

```powershell
Set-Location -LiteralPath 'C:\Users\chris\Projects\Meta-Hackathon'
.\start.ps1
```

Open http://127.0.0.1:8000 and complete a lookup. For the Suzuki sample, request `Oil filter for my 2007 Suzuki SX4 2.0 AWD` or select `Demo SX4-01` after asking for an oil filter. Click **Add to garage** on its result card. The button changes to **Saved to garage**, and the header count updates. Open **Garage** to view saved applications grouped by the catalog vehicle configuration, including part numbers, source/restrictions and any catalog price. Remove individual applications or use **Clear garage**. A new chat does not clear bookmarks.

## Storage and boundaries

- First-party cookie: `counterpilot_garage_v1`, URL-encoded JSON pairs of `[vehicle_id, part_id]`.
- Expiry: 365 days (`Max-Age=31536000`); `Path=/`, `SameSite=Lax`, and `Secure` on HTTPS. It is intentionally readable by this page's JavaScript. No login/authentication cookie is introduced.
- At most 20 distinct applications, with a 3,800-byte size budget. Full garages require removal before another save; no silent eviction.
- No VINs, messages, user-edited vehicle identity, part descriptions or prices are stored in the cookie. Bookmarks identify the displayed catalog application, not a claim that the customer's vehicle fits it.
- `GET /api/garage` validates IDs and resolves them against the current catalog, preserving sample/verified labels and source data. Missing or mismatched applications are shown as unavailable and can be removed. Cookie text cannot create part numbers or prices.
- Cookie changes stay in this browser. Reloads, other tabs and server restarts retain bookmarks; clearing cookies removes them. Browser profiles and hostnames have separate cookie storage.
- Cookie write failures show an explicit message and never claim success. Malformed/oversized cookies can be cleared from the Garage dialog. API failures preserve the saved cookie and provide Retry.

## Implementation

`counterpilot/garage.py` is the bounded read-only catalog resolver; `app.py` adds its route and response headers. `static/garage.js` owns cookie storage, the dialog and save buttons; `garage.css` supplies small styles using existing theme tokens. `chat.html` loads them and adds the header/dialog. `chat.js` adds one garage button per retrieved application, retaining the existing chat/history/compare behavior. No dependencies were added.

## Verification

- Complete backend suite: 108 tests passed, including seven new garage tests for unauthenticated empty state, cookie resolution, catalog provenance, duplicates, unavailable/mismatched IDs, malformed/oversized cookies, clearing and page integration.
- Nine Edge/Playwright garage scenarios passed: empty state, cookie attributes/ID-only storage, grouped records, reload and another tab, new chat and removal, duplicate cards and clear, capacity/corruption recovery, mobile overflow, and blocked-cookie feedback.
- Garage browser tests mock chat responses using actual catalog fixtures; garage resolution and cookies run against the real local backend. They do not claim live Meta verification.
- The existing chat browser regression suite also passed, including history/reload, correction handling, compare, autocomplete, mobile details and stale-response checks. Desktop and mobile garage screenshots were visually inspected. JavaScript syntax and `git diff --check` passed.
- Screenshots and browser results are in ignored `artifacts/garage-desktop.png`, `garage-mobile.png` and `garage-browser-results.json`.

Run backend checks with `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`. Browser checks use the existing Playwright/Edge setup:

```powershell
$env:COUNTERPILOT_CHAT_URL = 'http://127.0.0.1:8000'
$env:COUNTERPILOT_PLAYWRIGHT = 'C:\Users\chris\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\playwright'
& 'C:\Users\chris\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' .\tests\garage-browser.cjs
```


## Product polish update

Garage applications can now reuse their catalog vehicle through **Use vehicle**. Removal and clearing offer **Undo** for the current page session; adding another application replaces that undo opportunity. **Clear garage** deletes the first-party cookie. Garage fetches have a bounded timeout and preserve cookies on failure. See [the product polish report](PRODUCT_POLISH.md) for current accessibility and workflow verification.
