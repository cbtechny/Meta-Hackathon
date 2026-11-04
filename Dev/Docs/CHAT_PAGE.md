# CounterPilot chat behavior and demo

Current result presentation: [inline part cards and confirmed-detail counts](INLINE_CHAT_RESULTS.md). The extra chat reveal button is retired; the workflow notes below describe the earlier conversation work.

Updated November 3, 2026. The original lookup page, Meta endpoint/configuration, CSV catalog and NHTSA decoder remain in place. This change affects chat and its supporting state/lookup code.

## Startup for the existing checkout

Stop an older server in its terminal with Ctrl+C, then run:

```powershell
Set-Location -LiteralPath 'C:\Users\chris\Projects\Meta-Hackathon'
$env:COUNTERPILOT_PROVIDER = 'meta'
$env:META_MODEL = 'muse-spark-1.3'
.\start.ps1
```

Open [CounterPilot Chat](http://127.0.0.1:8000/chat), then click **New conversation** to clear an older or expired tab session. The existing `.venv` is used by `start.ps1`; no dependencies were added or changed for this work. The project-root `.env` loads automatically. Its existing `MODEL_API_KEY` stays private; shell environment values take precedence. Never paste a key into chat.

If restoring the environment from its existing manifest is necessary:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements.lock.txt
```

## Five-step demo

1. **Ambiguous filter:** send `Need a filter for my rav 4`. The assistant asks which filter. Reply `Oil`; it asks the RAV4's year, retaining Toyota/RAV4 and the part.
2. **No VIN:** reply `2019`, then `I don't have the VIN`. It continues manually and remembers the decline. The single loaded application can be reviewed without forcing an engine answer. Unknown engine/trim/drivetrain/hybrid values remain unknown; the loaded profile is not universal fitment evidence.
3. **Engine correction:** send `Actually mine is a 3.5`. Engine becomes `3.5L`, old candidates disappear, and the assistant explains that only 2.5L records are loaded. It does not reject the customer's engine or force it back to 2.5L.
4. **Successful demo application:** send `demo vehicles`, then choose `Demo RAV4-01`. This explicitly selects the fictional 2019 Toyota RAV4, 2.5L, XLE, AWD profile while preserving the oil-filter request. Review the displayed configuration and click **These details match · inspect candidates**. The CSV-backed oil filter is `FL-00131`, brand `CounterPilot Demo`, labeled **Demo part — simulated fitment**. `2.5L` is also a supported manual correction, but a profile selection makes the demo/customer distinction visible.
5. **Honest no match:** send `Actually the year is 2017`. Year changes, vehicle-specific equipment and old candidates clear, and the catalog coverage limit is explained. Toyota/RAV4 and oil filter stay saved. No 2017 fixture is invented.

Additional checks: `Skip that, I need wipers` preserves the vehicle and asks front/rear. The loaded 2019 RAV4 front-wiper sample is `WP-00160`; no engine question is needed. `Change vehicle` invalidates vehicle facts/results and keeps the part. `Start over` clears the lookup. Symptoms such as `Clicking when turning` prompt clarification rather than a CV-axle diagnosis.

## Root cause and implementation

The exact phrase “engine must be” was not present in the inspected source. The equivalent restriction was in `chat.py`: chat searched without engine, selected the first year/make/model demo profile, then unconditionally asked engine and compared the customer's engine against that profile's description. A single 2.5L catalog application was treated as a vehicle constraint. `domain.search` also returns the first profile; chat now retrieves relevant applications across profiles before choosing questions. The original lookup endpoint remains intact.

The latest customer message already reached Meta as the final user message. The failure was not a missing user-message transport. Previously the browser resubmitted details/history each turn, while the backend had no authoritative session, pending-question state, attempt tracking, VIN provenance or correction confirmation.

- `chat.py`: validated details/state models, normalization, careful merging and application-dependent catalog replies. Generic filter/brakes requests are clarified before vehicle fields. An engine/hybrid/trim/drivetrain question is asked only when it separates loaded applications. Missing coverage stops questions. Single-profile previews explicitly leave unknown configuration unconfirmed and never establish universal fitment.
- `conversation.py`: small, bounded in-memory sessions; revision checks; successful-request replay within a session; source facts; original decoded details; overrides; confirmations; VIN-declined flag; unresolved attempts; reset/part/vehicle changes. Changes recompute results. No agent framework or database.
- `providers.py`: real Meta extraction remains mandatory for ordinary language, with current state, pending question, recent history, source facts and relevant catalog profiles. Structured output is validated; nulls and inferred engines cannot silently replace known facts. Backend rules write the catalog-grounded replies; the model cannot author UI part records.
- `app.py`: routes chat through the state transition service and reuses the existing decoder. Provider errors remain explicit HTTP 503 responses; no simulated AI-success fallback.
- `static/chat.js` / `chat.html`: server session/revision payloads, source labels, VIN/edited-identity status, unknown fields, and unconfirmed-application notes. Existing draft/retry, duplicate-submit prevention, stale-response cancellation, styling and mobile layout are retained.

VIN decoding is optional. Only syntactically valid 17-character VINs reach NHTSA; demo identifiers never do. Failed/incomplete decodes retain manual details and never substitute a demo vehicle. Decoded details are shown for confirmation; unknown decoded fields remain unknown. A conflicting customer correction requires confirmation and retains the original decode separately. Changing the identity detaches the active VIN so it cannot appear to belong to another vehicle. A decode is vehicle identity evidence, not parts-fitment authority.

## Verification

Run the complete repeatable mocked suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

79 tests passed, including the requested conversation scenarios, Meta request validation/transport/failures, NHTSA mocking, source tracking, stale revisions, request replay, all existing lookup/catalog checks, and clearly labeled synthetic engine/hybrid variants. Synthetic variants exercise configuration distinctions absent from the real demo catalog; they are not inserted into the CSV files. A pre-existing Starlette/HTTPX deprecation warning is non-fatal.

A final 21-turn acceptance run used real Meta calls and successfully decoded the public NHTSA sample VIN. It verified ambiguous filter/short replies, missing-year coverage, year and engine corrections, unknown-engine alternatives, VIN decline, wiper switching, full requests, cabin AC filter and stabilizer-link terminology, symptoms, reset and VIN confirmation. Sanitized results are in ignored `artifacts/chat-conversation-live-results.json`; its repeatable script is `artifacts/verify_chat_conversation_live.py` (verification port 8011).

All 10 chat browser scenarios passed. The original lookup page also passed its 9 scenarios and the browser error/network check. Desktop and mobile screenshots were visually inspected. Browser results are recorded in ignored `artifacts/chat-browser-live-results.json`, with screenshots `chat-live-desktop.png` and `chat-mobile.png`. The existing Playwright harness checks real Meta chat, corrections, no-match behavior, request failure/retry, manual edits and reload, duplicate Enter, reset during slow responses, plain-text rendering and mobile overflow. It uses the existing Playwright/Edge setup, not a new project dependency.

```powershell
# With the app running; use this machine's existing bundled Playwright/Node runtime.
$env:COUNTERPILOT_CHAT_URL = 'http://127.0.0.1:8000'
$env:COUNTERPILOT_CHAT_LIVE = '1'
$env:COUNTERPILOT_PLAYWRIGHT = 'C:\Users\chris\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\playwright'
& 'C:\Users\chris\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' .\tests\chat-browser.cjs
```

## Limits

The current catalog has six fictional profiles, 180 sample applications and zero verified part records. Applications can be inspected; none establish real purchasing/installation fitment. Unrepresented configurations and missing equipment/date distinctions require better application data. Sessions are local-process memory, expire after two hours idle, and clear on restart; start a new conversation after restart. Meta and NHTSA availability can change. The existing localhost hosting model remains unchanged.
