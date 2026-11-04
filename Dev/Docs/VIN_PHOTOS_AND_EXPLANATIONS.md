# VIN photos and grounded result explanations

Implemented and verified November 3, 2026 in `C:\Users\chris\Projects\Meta-Hackathon`.

## Delivered

The chat remains the primary page. The opening composer is larger and more prominent than the supporting controls. **Scan VIN** sits beside the composer before and during a conversation. **Why this result?** appears on current retrieved part cards. Existing typing, lookups, corrections, source disclosures, comparison, garage, and recovery behavior are preserved.

### VIN photo flow

1. Choose **Scan VIN**, then select a photo or use the camera picker where supported.
2. Review the local preview. **Read VIN** explicitly sends the image to the configured Meta model.
3. Review/edit the extracted characters. Unclear, missing, multiple, or invalid-format readings leave the VIN blank with retake/manual guidance.
4. **Confirm VIN & look up vehicle** sends a normal VIN message through the existing chat pipeline and NHTSA decoder.
5. Confirm the proposed decoded vehicle in chat. Vehicle details are applied only after acceptance. Conflicts use the existing explicit confirmation flow; the current part request is preserved.

Supported uploads: single-frame JPEG, PNG, or WebP, up to 4 MiB and 12 megapixels. HEIC must be converted first. Server-side Pillow decoding validates the content, rejects mismatched types and excessive dimensions, applies orientation, removes metadata, and produces a bounded JPEG in memory for Meta. Format validation is not a guarantee of accurate transcription.

The image adapter follows [Meta's documented Chat Completions vision format](https://dev.meta.ai/docs/image-understanding): user-message `image_url` content with a base64 data URL. It reuses the existing model, endpoint, private key, bounded transport, and output validation.

### Grounded explanation flow

**Why this result?** makes an explicit Meta request. The server resolves the active session, exact lookup revision, and retrieved record ID; client-authored evidence and unrelated records are rejected. Meta selects relevant field references and one of three permitted next-check categories. It cannot author new factual claims: server validation checks those references, and the server supplies all displayed values, provenance, application scope, restrictions, missing details, and required disclosures.

The explanation distinguishes customer details, unconfirmed lookup inputs, demo profiles, VIN-decoded identity, and VIN-confirmed identity. Sample applications are prominently identified as simulated. Verified-source status is explicitly limited to the maintained record, not a compatibility guarantee. A failed or invalid model reply produces a labeled factual catalog summary.

Duplicate explanation clicks reuse a bounded session cache. Every successful conversation turn clears the cache; stale revisions and previous cards cannot be explained as current. Closing a scan, changing/resetting its content, or correcting a lookup invalidates late UI responses.

## Start and demonstrate

In PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\chris\Projects\Meta-Hackathon'
.\start.ps1
```

Open http://127.0.0.1:8000. Stop an older process on that port in its own terminal before restarting, then refresh the page. The existing `.env` is loaded without changes. Pillow 13.0.0 was installed in this checkout and added to the declared and locked dependencies. Fresh environments should install `requirements.lock.txt` first.

A separate verification preview was started on http://127.0.0.1:8017; the user's existing port-8000 process was not changed.

### Short judge-facing demonstration

1. Start with the prominent chat input: `Oil filter for a 2019 Toyota RAV4 2.5L`.
2. Open **Why this result?**. Show the customer-supplied facts, exact catalog record, simulated-application disclosure, unresolved equipment details, and next check. Explain that Meta organizes the evidence while catalog retrieval controls part numbers.
3. Start a new chat, choose **Scan VIN**, and select `artifacts/vin-ai/clear.png`. Explicitly identify this as a synthetic test label containing an existing public NHTSA example VIN.
4. Choose **Read VIN**, compare the extracted characters, and confirm the VIN. Show the proposed Honda identity and accept it. That vehicle is outside the sample catalog; do not imply it has matching parts.
5. Optionally show the obscured synthetic label: the model should request a retake rather than invent characters. This is a tested behavior, not a promise that every future ambiguous image will be recognized correctly.

Use a real photo only with permission, and test it before a live presentation. No real-photo accuracy or customer time savings have been established.

## Verification results

- **126 backend tests passed**: all 114 previous tests plus 12 focused feature tests. Checks include actual image decoding/type/dimension validation, metadata removal, bounded bodies and origin checks, sanitized errors, no automatic decoding after extraction, deferred vehicle adoption, preservation of the part request, server-owned evidence, unknown/unretrieved records, expired/stale sessions, cache invalidation, malformed model output, source-text injection boundaries, and fallback disclosures.
- **61 deterministic browser checks passed**: 24 existing chat checks, 16 product checks, 9 garage checks, 9 new feature checks, and 3 new failure/recovery checks. Model responses are intercepted in these checks. Coverage includes explicit review before lookup, manual correction, unreadable/multiple VIN states, invalid files, network retry, duplicate-click prevention, modal focus, photo cleanup, late scan/explanation responses, historical explanations, fallback labeling, safe text rendering, and layouts at 320/390/768/1440 pixels. Existing suites also cover 360 pixels.
- A bounded live evaluation made **six Meta calls**: five synthetic image cases and one evidence explanation. A separate live browser walkthrough made **three Meta calls**: normal chat interpretation, an explanation, and VIN extraction. Total: **nine live Meta calls** during this feature pass.
- The live browser reached successful image extraction, explanation rendering, and NHTSA decoding. Its initial final assertion expected `Honda` while NHTSA returned `HONDA`; this test assertion was corrected. A follow-up browser run verified proposal-before-adoption, explicit acceptance, and no fabricated parts for the unsupported Honda, using **zero additional Meta calls**.
- Desktop/mobile screenshots were visually inspected. No browser exceptions were observed in the passing deterministic suites. `pip check` passed. Existing Starlette/HTTPX test-client deprecation warnings remain non-fatal.

### Measured live evaluation

These are individual local observations on generated labels, not a representative real-world accuracy benchmark. Latency includes local validation and the provider round trip.

| Synthetic case / task | Observed result | Seconds |
| --- | --- | ---: |
| Clear printed VIN | Exact 17-character transcription | 2.28 |
| Same VIN, rotated 7 degrees | Exact transcription | 2.78 |
| VIN characters obscured | `unclear`; no VIN returned | 1.96 |
| No VIN present | `not_found`; no VIN returned | 1.62 |
| Two distinct VINs | `multiple`; no VIN selected | 1.72 |
| RAV4 sample-record explanation | Valid AI evidence references and sample disclosure | 2.73 |

Two readable synthetic cases were exact; all three negative cases returned no VIN. This tiny curated set does not establish performance on windshield glare, worn labels, camera blur, or real customer photos. No verified catalog applications or customer-benefit measurements were added.

## Data handling and limits

- Uploaded photos and their base64 content are not written to disk, chat messages, browser storage, or intentional logs. Object URLs are revoked and preview state cleared on close/reset. Incoming images are processed transiently; metadata is removed before the upstream request. Meta's own processing and retention policies still apply. Closing a dialog cancels the browser request but may not cancel an upstream call already in progress.
- After confirmation, the VIN becomes an ordinary chat message. Existing chat history, snapshots, pending requests, and VIN details are stored in this tab's `sessionStorage`; new chat clears them. Browser session restoration may retain session storage. The server keeps bounded conversation state in memory, expiring after two hours idle (failed empty sessions after one minute), or until process restart. VINs are not saved in the garage cookie.
- The server sends lookup details and the selected record's evidence to Meta for explanations. It does not send the uploaded image, raw VIN, credentials, or whole catalog in that explanation request.
- JSON body limits are enforced before parsing (5,600,000 bytes for photos, 48,000 for chat/explanation); cross-origin browser requests are rejected. Responses use no-store and same-origin policies. Image previews use local blob URLs. Keys remain server-side and unchanged.
- Current deployment remains a localhost demonstration with capability-style session IDs, in-memory sessions, a simulated catalog, and no account system. Real fitment data and public-hosting controls remain separate work.
- Photo extraction needs the configured Meta service. Manual VIN entry remains available if it fails; explanation failures produce the catalog summary. Camera capture depends on device/browser support.

## Reproduce checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m pip check
```

For browser checks, start a separate local server and set `COUNTERPILOT_CHAT_URL` accordingly. Set `COUNTERPILOT_PLAYWRIGHT` to the available Playwright package, then run `tests/vin-ai-browser.cjs` and `tests/vin-ai-extra-browser.cjs` with Node. Existing regression scripts remain `tests/chat-browser.cjs`, `tests/polish-browser.cjs`, and `tests/garage-browser.cjs`.

**Live scripts incur API usage:** `python -m scripts.verify_vin_ai_live` makes at most six calls; `tests/vin-ai-live-browser.cjs` makes at most three. The browser script supports `COUNTERPILOT_VIN_CONFIRM_ONLY=1` for a zero-Meta-call NHTSA confirmation check.

Evidence is in ignored `artifacts/vin-ai/`: `live-results.json`, `browser-results.json`, `extra-browser-results.json`, `live-browser-confirmation.json`, labeled synthetic fixtures, and desktop/mobile screenshots. Original edited source files from before this pass are preserved in ignored `artifacts/vin-ai-baseline/`. No commits, pushes, deployment, catalog-record edits, or credential changes were made.
