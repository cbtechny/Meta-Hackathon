# CounterPilot live Meta verification

Current catalog migration: see [CSV catalog maintenance](CATALOG_DATA.md). The verification below records the earlier catalog; current sample numbers, applications and position/side flow come from CSV.

Verified locally on November 3, 2026, using the key already stored in the ignored project-root `.env`. No credential values, authorization headers or raw upstream responses are included in this report.

## Result

The running CounterPilot demo successfully calls the real Meta API with `COUNTERPILOT_PROVIDER=meta`, `MODEL_API_KEY` and `META_MODEL=muse-spark-1.3`. The endpoint and authentication match the [official Meta Chat Completions documentation](https://dev.meta.ai/docs/protocols/chat-completions).

Twelve live requests succeeded: an initial smoke request, ten API scenarios below, and one browser request. The ten API scenarios each returned HTTP 200 from Meta and HTTP 200 from CounterPilot. Returned candidates exactly matched records in the local fictional catalog.

## Live scenarios

| Scenario | Expected behavior | Result |
| --- | --- | --- |
| 2019 Toyota RAV4 oil filter | `DEMO-RAV4-OIL_FILTER` | Passed |
| 2023 Honda CR-V cabin air filter | `DEMO-CRV-CABIN_FILTER` | Passed |
| 2021 Chevrolet Silverado 1500 engine air filter | `DEMO-SIL1500-AIR_FILTER` | Passed |
| 2021 Volkswagen Tiguan front rotors | `DEMO-TIGUAN-BRAKE_ROTOR-FRONT` | Passed |
| 2021 Ford F-150 rear rotors, heavy-duty package | `DEMO-F150-BRAKE_ROTOR-REAR-HEAVY-DUTY` | Passed |
| F-150 rear rotors without package | Asks for brake package; no candidates | Passed |
| Tiguan rotors without position | Asks front or rear; no candidates | Passed |
| Oil filter without vehicle | Asks year, make and model | Passed |
| F-150 alternator | Outside category coverage; no candidates | Passed |
| 2018 RAV4 oil filter | Outside vehicle-year coverage; no candidates | Passed |

## Credential and failure checks

- The effective key matched the key loaded from local `.env`; the key itself was not printed.
- Git ignores `.env`, and `.env` is not tracked. No exact copy of the effective key was found in current tracked working files. This was not an exhaustive Git-history or machine-wide secret audit.
- The Meta adapter sent requests only to `https://api.meta.ai/v1/chat/completions`, using the expected model and authorization header. The request body contained model, interpretation messages and output-token limit, with no catalog records or manually supplied criteria.
- Checked HTML, JavaScript, stylesheet, catalog, OpenAPI schema and live search responses did not contain the key.
- Requests for `/.env`, `/static/.env`, `/static/%2e%2e/.env` and `/.git/config` returned 404.
- A simulated upstream exception containing the key produced a generic HTTP 503 response without exposing the key. Offline and manual searches remained functional without network calls.
- The live browser flow made no external browser requests; the Meta call ran server-side.
- The current launch configuration binds to `127.0.0.1`. These checks validate the local demo, not readiness for public hosting.

## Regression and browser checks

- All 26 Python unittest tests passed; `pip check` found no broken requirements.
- All nine existing browser scenarios passed, plus checks for no browser exceptions or external asset requests. The browser test now explicitly selects the offline parser and simulates its Meta-failure scenario so it works with a valid local key.
- A separate browser check confirmed the already-running server had loaded the key, selected Meta by default and returned the expected RAV4 record from a real request.
- Candidate cards remained hidden until the vehicle configuration was acknowledged.
- Desktop (1440 px) and mobile (390 px) screenshots were rendered and inspected; no horizontal overflow was found.

## Local evidence and limits

Sanitized results and screenshots are in ignored `artifacts/`: `meta-live-results.json`, `meta-browser-results.json`, `browser-results.json`, `meta-live-desktop.png` and `meta-live-mobile.png`. The local API-check script is `artifacts/verify_meta_live.py` and can incur API usage when rerun.

All fitment/application records remain fictional. Successful interpretation does not establish real-world parts compatibility. Live NHTSA VIN decoding was not repeated in this verification; its failure and simulated-confirmation browser flows passed. Meta availability, quotas and future model outputs can change. The UI's generic “unverified until a successful request” wording is static rather than a persistent health monitor; this report records the actual successful checks.

An existing Starlette/HTTPX test-client deprecation warning remains; it did not cause test or runtime failure. No key changes, deployment, commit, push or remote repository changes were performed.
