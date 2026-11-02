# CounterPilot
A local parts-counter demonstration: interpret a request, ask about missing details, and inspect catalog application evidence.

**Every demo part number, cross-reference, and application is fictional. Do not use this app for purchasing or installation.** The five vehicle descriptions are scenario labels, not independently verified equipment records. The workbook and private research are not imported.

## Start on Windows
Python 3.10+ is required.

```powershell
cd C:\Users\chris\Projects\Meta-Hackathon
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m uvicorn counterpilot.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

Open http://127.0.0.1:8000. For this checkout the virtual environment is already installed; run `start.ps1` or the final command above. Stop with Ctrl+C. No login, database, build step, external fonts, or network dependency in offline mode.

## A two-minute demonstration
1. Choose **A simple match**. Review the interpreted 2019 RAV4 oil-filter request. Acknowledge the displayed engine/trim/drivetrain to inspect its fictional candidate and evidence.
2. Choose **Catch a package split**. Notice that no candidates are returned yet. Choose **standard** or **heavy-duty**, then acknowledge the vehicle configuration. The resulting rear-rotor records differ.
3. Choose **Ask front or rear**, then front. Rear introduces a second clarification for the package.
4. Try `alternator for a 2021 Ford F-150`: outside coverage.
5. Try `oil filter`: enter the missing details or choose a configuration in the details panel.
6. Select manual interpretation to bypass the parser. Optionally decode a VIN; inspect and explicitly confirm its identity before copying fields. Exact vehicle configuration still requires acknowledgment.

## Coverage
30 invented application records: oil, engine-air and cabin filters, front rotors, and two rear-rotor options for each family:
- 2021 Ford F-150 / 3.5L EcoBoost / XLT / 4WD
- 2019 Toyota RAV4 / 2.5L / XLE / AWD
- 2023 Honda CR-V / 1.5T / EX / AWD
- 2021 Chevrolet Silverado 1500 / 5.3L / LT / 4WD
- 2021 Volkswagen Tiguan / 2.0T / SE / FWD

Brake-package labels are fictional teaching examples across all five families. They are not real equipment codes or verified physical dimensions.

## Architecture and interfaces
- `counterpilot/domain.py`: validated criteria, catalog validation, deterministic application matching.
- `counterpilot/providers.py`: `interpret(text) -> Criteria` protocol, bounded offline parser, optional Meta adapter.
- `counterpilot/app.py`: FastAPI API and static single-page interface.
- `counterpilot/catalog.json`: local fictional fixtures with evidence, restrictions, and separate unverified cross-references.
- Existing `counterpilot_vin_lookup.py`: NHTSA identity decoder, not a fitment source.

`GET /api/catalog` returns supported configurations and provider availability.
`POST /api/search` accepts `{text, provider: "mock"|"meta"|"manual", criteria: {...}}`. Criteria fields: year, make, model, category, position, brake_package. Explicit non-null criteria override parsed fields. Results contain status (`candidates`, `needs_clarification`, `outside_coverage`), criteria, questions, candidates and the selected vehicle when known. Unsupported fields/values return 422; provider failures return 503 without silently switching providers.
`POST /api/vin` accepts `{vin, year?}`, returns proposed identity with `requires_confirmation: true`; service failure returns 502. No VIN persistence or intentional logging. The launch command disables access logging.

The catalog matcher does not consume cross-references. The UI requires acknowledgment of engine/trim/drivetrain before displaying candidate cards. API results are fixture matches, not a confirmation of the user's physical vehicle.

## Optional Meta provider
Live Meta integration is **unverified** until an actual successful request. No API key was available during implementation. Mocked adapter tests do not verify service access.

Official documentation checked during implementation:
- https://dev.meta.ai/docs/overview
- https://dev.meta.ai/docs/quickstart
- https://dev.meta.ai/docs/protocols/chat-completions

The adapter uses the documented base URL `https://api.meta.ai/v1`, Chat Completions, bearer `MODEL_API_KEY`, and default model `muse-spark-1.3`. Set these in the same shell that starts the app, then select Meta in the UI:
```powershell
$env:MODEL_API_KEY = 'your-local-key'
$env:META_MODEL = 'muse-spark-1.3'
# Optional: start the UI with Meta selected
$env:COUNTERPILOT_PROVIDER = 'meta'
.\start.ps1
```
Only the request text goes to Meta; catalog data, explicit manual criteria and VIN-decoder output are not sent. Avoid customer identifiers in request text. Keys stay server-side. The adapter rejects malformed or unexpected model output; it never receives or chooses candidate part numbers. A request timeout or invalid output leaves offline/manual modes available.
`.env.example` documents settings; the app does not load .env automatically.

## Validation
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
Tests cover all five families, clarification, package splits, unsupported input, manual overrides, cross-reference boundaries, catalog integrity, provider validation/failure, and VIN mapping/confirmation. See `BUILD_REPORT.md` for actual verification and remaining limits.

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
Browser checks cover configuration acknowledgment, package and position questions, stale-state clearing, manual recovery, simulated VIN confirmation, and mobile overflow. Screenshots and results go in ignored artifacts/.
requirements.lock.txt records the exact installed versions from this build; requirements.txt declares the allowed dependency ranges.
