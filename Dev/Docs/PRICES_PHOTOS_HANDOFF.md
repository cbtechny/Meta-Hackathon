# Prices, photos and polish - handoff

Updated November 3, 2026. Checkout: `C:\Users\chris\Projects\Meta-Hackathon`.

## Final status: implemented and verified

This note was requested during the pass when usage was running low. The work subsequently completed in the same session. No known blocking issue remains from this pass. Nothing was committed, pushed or deployed. Preserve the extensive pre-existing worktree changes and deliberately removed legacy files.

## Delivered

- All 180 sample applications have fixed fictional USD prices, with explicit each/axle set/pair units. Every original CSV field was preserved; `parts_verified.csv` was untouched.
- Legacy CSV headers remain supported. New optional fields are `price_amount,currency,price_unit`. Decimal validation rejects zero/negative/nonfinite/overprecise prices, missing currency/unit, non-USD currency and unsupported units. Verified records never inherit sample prices.
- The existing catalog loader attaches structured price and image metadata. No competing catalog or matching system was added. The generator still preserves existing files and only prices newly created sample rows.
- All 24 generic photos were generated separately with the built-in imagegen tool, visually inspected and encoded as local 480x360 JPEGs. Assets are in `counterpilot/static/parts/`, totaling 390108 bytes. Photos are illustrative, not exact products or fitment evidence.
- Inline cards show photo, name, number, price/unit, brand, record status and source disclosure immediately. Missing photos and older snapshots have safe fallbacks.
- Multiple retrieved records can be selected for comparison, up to three. The native dialog is keyboard accessible and stacks on mobile. Corrections clear selections; previous cards cannot be selected; New chat resets comparison. Single matches have no comparison controls. Production never invents alternatives.
- Added lightweight Try a lookup / Use a VIN / How it works CTAs and explanatory text while preserving Chat and find your parts, the single-page chat, car animation, hints, corrections and backend-only key access.

## Verification

- **101 backend tests passed.** Includes price validation, legacy CSV compatibility, deterministic generation and preservation, verified records with/without explicit prices, plus existing lookup/chat/VIN regression tests.
- **24 browser scenarios passed** using deterministic fixtures and intercepted Meta calls. Includes photos/prices/reload/fallback, comparison selection limit, mobile dialog, keyboard dismissal/focus restoration, stale selections, reset, retry, autocomplete, invalid VIN, safe rendering, car/reduced motion and CTAs without automatic submission.
- Desktop and mobile screenshots were visually inspected, including 360/390 px part-number visibility. No horizontal overflow, browser exceptions or external browser requests were observed.
- All 24 image subjects were visually inspected in a contact sheet. No readable brand/product text was found.
- Catalog generator rerun preserved every existing CSV; validation errors: 0. Six profiles, 180 sample applications, 86 aliases, zero verified rows.
- `.env` remains Git-ignored. The actual configured key was compared internally against source/assets/docs and representative public page/API/photo responses without printing it; no exposure was found.
- No new dependency, paid Meta request or fresh NHTSA request was needed for this presentation pass. Prior live VIN verification is documented in CHAT_HOME.md. Real Meta availability/quotas were not rechecked here.
- Owned preview on port 8007 was stopped. The user's port 8000 process was not modified.

## Key files and docs

- Data/runtime: `counterpilot/catalog_io.py`, `counterpilot/domain.py`, `counterpilot/data/parts.csv`, `scripts/generate_demo_catalog.py`.
- UI: `counterpilot/static/chat.html`, `chat.js`, `chat.css` and local `parts/*.jpg`.
- Tests: `tests/test_product_cards.py`, updated `tests/test_counterpilot.py` and `tests/chat-browser.cjs`.
- Current usage: [CHAT_HOME.md](CHAT_HOME.md).
- Editing prices/adding verified parts: [CATALOG_DATA.md](CATALOG_DATA.md).
- Photo provenance, final prompt set and all 24 subjects: [PART_PHOTOS.md](PART_PHOTOS.md).
- Ignored screenshots/results: `artifacts/chat-browser-results.json`, `chat-home-empty-mobile.png`, `chat-inline-mobile-360.png`, `chat-inline-mobile-390.png`, `chat-compare-mobile.png`, `part-photo-contact-sheet.jpg`.

## Start or resume

```powershell
cd C:\Users\chris\Projects\Meta-Hackathon
.\start.ps1
```

Open http://127.0.0.1:8000. Restart an already running server to load backend changes, then refresh. Try Oil filter for a 2019 Toyota RAV4 and answer the follow-up questions. Its sample price is $12.95 each. Comparison appears only if the catalog actually retrieves multiple records; browser tests use clearly isolated multi-record fixtures without adding fake alternatives to production CSVs.

For another verification run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe scripts\generate_demo_catalog.py
# Separate preview terminal; no access logs and local binding only
.\.venv\Scripts\python.exe -m uvicorn counterpilot.app:app --host 127.0.0.1 --port 8007 --no-access-log
```

```powershell
$env:COUNTERPILOT_PLAYWRIGHT = 'C:\Users\chris\AppData\Local\OpenAI\Codex\runtimes\cua_node\989c7523a11c09b9\bin\node_modules\playwright'
$env:COUNTERPILOT_CHAT_URL = 'http://127.0.0.1:8007'
$env:COUNTERPILOT_CHAT_LIVE = '0'
& 'C:\Users\chris\AppData\Local\OpenAI\Codex\runtimes\cua_node\989c7523a11c09b9\bin\node.exe' tests\chat-browser.cjs
```

## Image recovery (generation is complete)

No image generation task remains running. Originals remain at `C:\Users\chris\.codex\generated_images\01a1a373-25b0-70c3-9bbe-e09f88fea60f`. Ignored `artifacts/photo-sources.json` maps all 24 filenames. Do not regenerate completed images unnecessarily. Local re-encoding is available with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\prepare_part_photos.ps1 -Manifest artifacts\photo-sources.json
```

The process-local execution policy switch is needed on this Windows setup; it does not change machine policy. Re-encoding is optional; final JPEGs are already installed in the workspace.

## Boundaries for future work

All sample prices and fitment are fictional. Photos do not identify exact equipment or quantities. Verified-source status concerns the manually maintained source record and does not prove a price is current. No stock, order, checkout or payment behavior was added. Any later real commerce workflow needs a separate specification. Keep credentials backend-only and do not print `.env`, keys or auth headers.
