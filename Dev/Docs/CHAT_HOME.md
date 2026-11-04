# Single-page CounterPilot demo

Updated November 3, 2026. CounterPilot's homepage is now the chat experience. The separate lookup page, its navigation, legacy HTML/client script and old shared stylesheet have been removed. `/chat` redirects to `/` so existing bookmarks continue to work. The catalog, conversation state, Meta adapter, VIN decoder and existing backend lookup APIs remain intact.

## Show the demo

```powershell
cd C:\Users\chris\Projects\Meta-Hackathon
.\start.ps1
```

Open http://127.0.0.1:8000. If the app was already running, stop it first with Ctrl+C and restart to load the route changes.

The opening screen contains the CounterPilot name, **Chat and find your parts.**, a centered input, a small **Chat** button and an example request. The input invites a part, vehicle or VIN. Examples fade between requests derived from loaded vehicle profiles. Clicking an example fills the input but never sends a request automatically. Rotation pauses while composing, when the tab is hidden, and for reduced-motion preferences.

Once the first message is sent, the page becomes a compact conversation with the composer at the bottom. Part numbers remain immediately visible inside their assistant reply, with source disclosures and the existing six-field detail-completeness count. **New chat** resets the page to its centered start state.

A small inline SVG car rests on the input's upper border. Starting a new conversation triggers a brief rev followed by a drive across that border; it runs alongside the request and never delays submission. It does not replay for follow-up messages, retries or restored conversations. New chat resets it. Reduced-motion preferences disable the rev, wheel rotation and travel.

Small hint popovers fade in beneath the composer: how to start, where to edit captured details, and where to inspect retrieved part evidence. Each hint appears once per conversation, disappears after eight seconds and has a keyboard-accessible dismiss button. Hovering or focusing a hint pauses its timeout. Hints never take focus, contain no generated markup and make no API requests. Their reserved space prevents them from covering cards or shifting the input when they fade.

## Details popover and suggestions

- On a wide desktop, the details popover appears on the right when the first facts arrive, without taking keyboard focus from the composer. Closing it keeps it closed until reopened or a new chat starts.
- On smaller screens, the **Details** button shows the captured-field count. The panel opens on demand, keeping results central and visible. It closes with its close button, a click outside, or Escape.
- Detail fields are editable comboboxes: type freely, open the dropdown, or use Arrow Up/Down and Enter to select a suggestion. Escape closes a dropdown before closing the panel. Tab leaves typed text unchanged.
- Year, make and model suggestions narrow in that order. Engine, trim, drivetrain and hybrid suggestions use matching registered profiles. Part names and position/side choices come from loaded catalog types and applications. Symptoms remain free text, not a diagnostic suggestion list.
- Suggestions never populate a field by themselves. Unregistered model names, engines or part wording remain as typed; the backend may report that no matching application is loaded. Year, position, side and hybrid inputs still respect their existing semantic constraints.
- **Update lookup** submits deliberate field corrections through the existing deterministic edit path, without a Meta request. Normal conversation messages continue through the existing Meta path.

The page fetches the existing `/api/catalog` once to build suggestions. Its part-type metadata now includes registered positions/sides and the shared alias mappings. No second catalog, remote autocomplete service, framework, custom font, image asset or new dependency was added.

## Safety and state

The root page has the same no-store headers, self-only content policy and safe DOM text rendering as chat. Credentials remain backend-only. The API returns catalog facts and a configured/not-configured flag, never the API key. Sample parts retain **Demo part — simulated fitment** labeling. The count measures confirmed details, not compatibility or availability.

Tab-scoped text history, card snapshots, retry behavior, source provenance, server sessions/revisions and stale-result handling remain in place. Public hosting/authentication remains outside this local demo change.

## Verification

Backend tests cover the canonical homepage, old-link redirect, retirement of legacy UI assets, registered autocomplete metadata and existing lookup/conversation contracts. Browser checks cover the centered start screen, examples, reduced motion, immediate cards, historical snapshots, retry/reset, editable registered suggestions, preservation of unregistered text, popover dismissal and 360/390 px layouts. These checks use deterministic fixtures; they do not make paid Meta requests.

Completed checks: **101 backend tests and 24 browser scenarios passed** after the prices/photos pass. Checks include sample prices, photo loading and fallback, legacy records, comparison selection limits, keyboard dismissal/focus, stale selections, lightweight CTAs, the car animation and reduced motion. Desktop and 360/390 px screenshots were inspected; no browser exceptions, horizontal overflow or external browser asset requests were observed. No new dependency or paid Meta request was used for this change.

## Prices, photos and comparison

All 180 sample applications now include fictional USD prices with explicit units. Cards show **Demo price**, simulated-fitment status and **Illustrative photo**. Images represent the part type rather than the actual item or vehicle configuration. The 24 generated local JPEGs total approximately 390 KB. Verified records with no explicitly entered price show **Price unavailable**; there is no fallback to demo prices. Prices exclude tax and shipping and do not establish availability or an offer to sell.

When a response contains multiple retrieved records, select two or three and choose **Compare selected**. The accessible dialog shows photos, prices/units, vehicle configurations, restrictions and source evidence. It stacks on mobile and closes with Escape. Corrections clear selections and historical results cannot be selected. A single retrieved record has no comparison controls; no alternatives are invented. Earlier saved cards without new metadata remain readable.

**Try a lookup** fills the registered example, **Use a VIN** prepares the composer, and **How it works** explains the describe/clarify/review flow. Neither fill action sends a request automatically. Price and image metadata remain separate from the text-only history sent to Meta. See [price editing](CATALOG_DATA.md) and [photo provenance and prompts](PART_PHOTOS.md).

Live VIN verification also passed against NHTSA using its public 2003 Honda Accord example: decoded identity required explicit acceptance, confirmed-detail progress increased only after Yes, and oil-filter lookup correctly stayed outside catalog coverage without substitute parts. Meta was disabled for this verification. Routine tests mock NHTSA and Meta; they also cover formatted/invalid VINs, malformed/oversized upstream responses, sanitized transport failures, confirmation conflicts and manual corrections. Explicit drivetrain descriptions are normalized to catalog abbreviations; ambiguous equipment stays unchanged. See [VIN lookup](../../VIN_LOOKUP_README.md).

Screenshots are saved under ignored `artifacts/`: `chat-home-empty-desktop.png`, `chat-home-empty-mobile.png`, `chat-inline-desktop.png` and `chat-inline-mobile-390.png`. Current browser results are in `chat-browser-results.json`.
