# CounterPilot
A local parts-counter demonstration: interpret a request, ask about missing details, and inspect catalog application evidence.

**Demo parts use simulated fitment and must not be used for purchasing or installation.** The six vehicle descriptions are scenario labels, not independently verified equipment records. Real applications belong in the separate manually maintained verified CSV with source references and verification dates. No real records are seeded by the generator.

## Start on Windows
Python 3.10+ is required.

```powershell
cd C:\Users\chris\Projects\Meta-Hackathon
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m uvicorn counterpilot.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

Open http://127.0.0.1:8000. For this checkout the virtual environment is already installed; run `start.ps1` or the final command above. Stop with Ctrl+C. No login, database, build step, external fonts, or network dependency in offline mode.

## Generate and edit the catalog

```powershell
.\.venv\Scripts\python.exe .\scripts\generate_demo_catalog.py
```

Canonical files are `counterpilot/data/vehicles.csv`, `parts.csv`, `part_aliases.csv` and `parts_verified.csv`. The command creates missing files and validates all records without overwriting edited CSVs or calling the network/Meta. It initially produces six profiles, 180 sample applications and 86 aliases. No workbook dependency was available, so CSV is the only output format.

Edit the CSV sources directly, run the command again to validate, then restart the server. Add real parts only to `parts_verified.csv`, with a source reference and verification date. See [the complete guide and first real RAV4-part instructions](Dev/Docs/CATALOG_DATA.md). Sample numbers use category prefixes and a deterministic sequence, with no vehicle fitment encoded in the number.

## Show the demo

The homepage is now the complete chat experience: one centered input, a short instruction, a small **Look up** button and gently rotating example requests. There is no separate lookup page or navigation. Old `/chat` links redirect to `/`.

1. Open http://127.0.0.1:8000 and enter `Oil filter for a 2019 Toyota RAV4`, or click the suggested example to fill the input.
2. Send the request and follow the conversation. Part cards appear directly inside the reply, with their number, source status and expandable evidence.
3. The details popover appears on the right on wide screens; on mobile, open **Details** when needed. Fields support both typing and dropdown suggestions from registered catalog data. Suggestions narrow by year, make and model and never silently fill unknown facts.
4. Edit a field and choose **Update lookup** to correct the lookup without a Meta call. Free text outside the catalog remains as typed; unsupported applications are reported honestly.
5. Use **New chat** to return to the centered start screen.

The six-field count measures detail completeness, not fitment probability. Unknown and skipped details stay unresolved, and earlier cards remain marked as previous results after corrections. Messages go through the existing Meta backend; your API key stays server-side. Example animation and opening a suggestion dropdown make no Meta calls.

See [the single-page demo guide](Dev/Docs/CHAT_HOME.md) and [inline result behavior](Dev/Docs/INLINE_CHAT_RESULTS.md). Restart an existing server to load backend changes, then refresh the page. Conversation history/card snapshots remain in the tab; an expired server session still requires a new chat to continue.

## Coverage
180 sample applications (30 per vehicle), covering filters, ignition, brakes, starting/charging, suspension, steering, cooling, fuel delivery, axles, hubs, belts and wipers:
- 2021 Ford F-150 / 3.5L EcoBoost / XLT / 4WD
- 2019 Toyota RAV4 / 2.5L / XLE / AWD
- 2023 Honda CR-V / 1.5T / EX / AWD
- 2021 Chevrolet Silverado 1500 / 5.3L / LT / 4WD
- 2021 Volkswagen Tiguan / 2.0T / SE / FWD
- 2007 Suzuki SX4 / 2.0L / trim unknown / AWD (fictional sample profile)

Every sample application discloses simulated fitment and unverified equipment assumptions. Left/right and front/rear distinctions are stored in CSV. The previous fictional brake-package variants are retired because the new schema does not represent package options.

## Architecture and interfaces
- `counterpilot/domain.py`: validated criteria, catalog validation, deterministic application matching.
- `counterpilot/providers.py`: `interpret(text) -> Criteria` protocol, bounded offline parser, optional Meta adapter.
- `counterpilot/app.py`: FastAPI API and static single-page interface.
- `counterpilot/data/*.csv`: canonical editable vehicle, sample application, alias and verified-record sources.
- `counterpilot/catalog_io.py`: shared schema, taxonomy and CSV validation.
- `scripts/generate_demo_catalog.py`: standard-library-only generator; creates missing files and preserves all existing CSV edits.
- Existing `counterpilot_vin_lookup.py`: NHTSA identity decoder, not a fitment source.

`GET /api/catalog` returns supported configurations and provider availability.
`POST /api/search` accepts `{text, provider: "mock"|"meta"|"manual", criteria: {...}}`. Criteria fields: year, make, model, category (the specific part_type selector), position, side. Explicit non-null criteria override parsed fields. Results contain status (`candidates`, `needs_clarification`, `outside_coverage`), criteria, questions, candidates and the selected vehicle when known. Unsupported fields/values return 422; provider failures return 503 without silently switching providers.
`POST /api/vin` accepts `{vin, year?}`, returns proposed identity with `requires_confirmation: true`; service failure returns 502. No VIN persistence or intentional logging. The launch command disables access logging.

The catalog matcher does not consume interchanges or model-authored part numbers. The chat homepage shows labeled application previews immediately; there is no separate lookup page. Sample results display **Demo part ? simulated fitment**. For the same vehicle, part type, position and side, manually sourced verified records replace sample results and display their source reference and verification date.

## Optional Meta provider
Live Meta integration was verified locally on November 3, 2026, with ten API scenarios across all five vehicle families and a real browser search. See [the verification report](Dev/Docs/META_API_VERIFICATION.md) for results, credential checks and limits. Mocked adapter tests alone do not verify service access; availability and model outputs can change.

Official documentation checked during implementation:
- https://dev.meta.ai/docs/overview
- https://dev.meta.ai/docs/quickstart
- https://dev.meta.ai/docs/protocols/chat-completions

The adapter uses the documented base URL `https://api.meta.ai/v1`, Chat Completions, bearer `MODEL_API_KEY`, and default model `muse-spark-1.3`. The app automatically loads the project-root `.env` at startup, including when launched with Uvicorn directly. Existing shell environment variables take precedence.

For a fresh checkout, copy the template once (keep an existing `.env`):
```powershell
Copy-Item .env.example .env
```
Edit `.env` locally and fill in `MODEL_API_KEY`:
```dotenv
COUNTERPILOT_PROVIDER=meta
MODEL_API_KEY=your-local-key
META_MODEL=muse-spark-1.3
```
`COUNTERPILOT_PROVIDER=meta` selects the real Meta adapter by default in the UI; use `mock` for offline interpretation. Without a key, Meta requests fail with a recoverable error and offline/manual modes remain available. Restart after editing `.env`:
```powershell
.\start.ps1
```
Only the request text goes to Meta; catalog data, explicit manual criteria and VIN-decoder output are not sent. Avoid customer identifiers in request text. Keys stay server-side. The adapter rejects malformed or unexpected model output; it never receives or chooses candidate part numbers. A request timeout or invalid output leaves offline/manual modes available.
`.env` is ignored by Git; `.env.example` contains no credentials. Keys are never returned by the API or served as static files.

## Validation
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
Tests cover all six families, position/side questions, symptom clarification, every generated application, canonical CSV loading, deterministic generation, preservation of manual edits, verified-record preference, provenance validation, provider safety and VIN confirmation. See [catalog maintenance](Dev/Docs/CATALOG_DATA.md) for the CSV workflow and limits.

## Data and privacy
Keep private workbook content, screenshots, customer VINs, API keys and proprietary catalog data outside Git. All fixtures were authored for this demo; there is no copied catalog data and no manufacturer compatibility assertion. Replace fixtures only with data you have permission to use and traceable application evidence.

Existing planning documents and VIN files have been retained. No deployment or remote Git changes are required.

## Optional browser regression checks
The backend tests need only the Python dependencies. Browser tests additionally use Node.js, Playwright, and installed Microsoft Edge:
```powershell
npm install --no-save --package-lock=false playwright
New-Item -ItemType Directory -Force artifacts | Out-Null
# Start the local server in another terminal first.
node tests/browser.cjs
```
If using the bundled Codex Playwright package, set COUNTERPILOT_PLAYWRIGHT to its absolute package directory instead of installing it.
Browser checks cover the centered chat homepage, example animation and reduced motion, inline cards, source disclosures, retry/reset, registered autocomplete, free text, popover controls and mobile overflow. Screenshots and results go in ignored artifacts/.
requirements.lock.txt records the exact installed versions from this build; requirements.txt declares the allowed dependency ranges.


## Cookie garage

Use **Add to garage** on a retrieved part card to bookmark its catalog vehicle application. **Garage** in the header groups saved records by vehicle, with remove and clear controls. No login or authentication is used. Up to 20 applications persist in a first-party cookie for a year, across reloads, new chats and server restarts. Only vehicle/part IDs are saved; displayed records and prices are resolved from the current catalog. Clearing browser cookies clears the garage. Restart with `start.ps1` after updating. See [Garage behavior and verification](Dev/Docs/GARAGE.md).


## Product polish and demonstration readiness

The current workspace includes the refined visual system, catalog vehicle browser, accessible mobile details, part-number copying, actionable no-match recovery, editable failed requests, expired-session continuation, and garage vehicle reuse/undo. No dependencies were added. See [product polish, audit findings, verification, and launch boundaries](Dev/Docs/PRODUCT_POLISH.md) for the exact demo path and checks. `GET /healthz` provides credential-safe process/catalog readiness without an upstream model call. This remains a deliberately labeled demo; it does not claim completed multi-tenant SaaS infrastructure or verified commercial fitment data.


## VIN photos and grounded explanations

**Scan VIN** is beside the main chat input before and during a conversation. Select/take a JPEG, PNG or WebP photo, explicitly choose **Read VIN** to send it to Meta, then review/edit the characters before confirming a decoder lookup. Confirm the proposed vehicle in chat before its details are adopted. Typed VIN entry remains available. Photos are processed transiently and are not saved by CounterPilot; confirmed VIN text follows existing chat retention.

Current part cards include **Why this result?**. Meta selects relevant evidence references; the server renders the retrieved record's actual facts, provenance, restrictions, unknowns, and required simulated-fitment disclosures. Invalid/unavailable AI output produces a labeled catalog summary. Corrections invalidate earlier explanations, and repeated clicks reuse the current explanation.

The opening chat composer is the visual focus. Restart with `start.ps1` and refresh to load both features. Pillow 13.0.0 is the only new dependency and is included in `requirements.lock.txt`.

Verified: 126 backend tests, 61 deterministic browser checks, a bounded live Meta evaluation on labeled synthetic VIN images, and live NHTSA confirmation. Synthetic-image outcomes are not real-photo accuracy claims. See [feature behavior, data handling, measured results, and the short demo sequence](Dev/Docs/VIN_PHOTOS_AND_EXPLANATIONS.md).
