# CounterPilot: An ELI5 Software Architecture Manual

Welcome to CounterPilot! If you are learning software architecture, this manual is written for you. We will explore how CounterPilot is built, why it is structured this way, and how its components work together.

---

## 1. The Big Picture: The Parts Counter Analogy

Imagine walking into an auto parts store.

Behind the counter sits an experienced parts clerk. On the counter sits an order notepad, and behind the clerk stands a giant binder: the official **parts catalog**.

* **The Customer** walks up and says something messy: *"Hey, my truck is squealing when I stop, I think I need rear rotors for a 2021 Ford F-150."*
* **The Clerk (Language Interpreter / AI)** listens to the customer and writes down clean, structured facts on the notepad:
  * Year: `2021`
  * Make: `Ford`
  * Model: `F-150`
  * Category: `brake_rotor`
  * Position: `rear`
* **The Big Binder (Deterministic Catalog Matcher)**: The clerk turns around and opens the binder to the 2021 Ford F-150 section. The binder has an exact rule: *“Rear rotors for 2021 F-150 come in two varieties: Standard brake package or Heavy-Duty brake package.”*
* **Clarification**: Instead of guessing which package the customer has, the clerk turns back and asks: *“Is your truck fitted with the standard or heavy-duty brake package?”*
* **Verification**: Once the customer answers, the clerk pulls the candidate box off the shelf, shows the customer the vehicle equipment description (engine, trim, drivetrain), and says: *“Check this label against your vehicle before we finalize this.”*

CounterPilot automates this parts-counter experience on your computer.

```
+------------------------------------------------------------------------------------------------+
|                                    PARTS COUNTER ANALOGY                                       |
|                                                                                                |
|   [ Customer Request ]  --->  [ Counter Clerk ]  --->  [ Order Notepad ]  --->  [ Catalog ]    |
|   "Rear rotors for a            (AI / Heuristic          (Structured            (Deterministic |
|    2021 Ford F-150"              Provider)                Criteria)              Matcher)      |
+------------------------------------------------------------------------------------------------+
```

---

## 2. What CounterPilot Does (and Its Strict Boundaries)

### What It Does
1. **Interprets plain English requests**: Takes conversational queries like *"Oil filter for a 2019 Toyota RAV4"* and extracts structured criteria.
2. **Identifies missing details**: Detects when crucial fitment variables (like vehicle year, front vs. rear, or brake package) are missing and generates targeted questions.
3. **Deterministically searches an application catalog**: Compares validated criteria against an exact catalog fixture.
4. **Presents evidence and enforces verification**: Displays the exact catalog application note and requires the user to acknowledge the vehicle configuration before seeing candidates.
5. **Decodes VINs safely**: Optionally looks up vehicle identity via public NHTSA records as a suggestion, keeping it distinct from fitment.

### Current Limitations & Scope
* **Fictional Demonstration Data**: Every part number (e.g. `DEMO-RAV4-OIL_FILTER`), cross-reference, and application record in `counterpilot/catalog.json` is entirely fictional. It must never be used for real vehicle purchasing or installation.
* **Bounded Scenario Scope**: The catalog covers exactly 5 vehicle families and 30 fictional part records (filters and brake rotors). Unsupported categories (like alternators, brake pads, or spark plugs) return an explicit out-of-coverage response.
* **No Automatic Fitment Guarantee**: CounterPilot provides catalog evidence; it does not physically inspect vehicles.

---

## 3. High-Level Architecture & Request Flow

### Complete Request-to-Result Flow
1. **User input**: The user types text into the textarea or fills in manual criteria in the web browser (`counterpilot/static/index.html`).
2. **HTTP Dispatch**: The browser script (`counterpilot/static/app.js`) sends a `POST /api/search` request with `{ text, provider, criteria }`.
3. **Interpretation**: In `counterpilot/app.py`, the backend checks the provider:
   - If `manual`: Skips language parsing completely.
   - If `mock`: Calls `MockProvider.interpret()` in `counterpilot/providers.py` (local regex parser).
   - If `meta`: Calls `MetaProvider.interpret()` in `counterpilot/providers.py` (external Chat Completions API).
4. **Criteria Merging**: Explicit manual inputs from the UI are merged over the parsed criteria. Explicit entries always override parsed fields.
5. **Deterministic Search**: `counterpilot/domain.py:search()` validates the merged `Criteria`:
   - Checks for unsupported categories.
   - Checks for missing required vehicle/category fields.
   - Checks if the vehicle exists in `catalog.json`.
   - Checks position requirements (e.g., front vs. rear rotor).
   - Checks option splits (e.g., standard vs. heavy-duty brake package).
6. **JSON Response**: Returns a JSON payload containing `status` (`candidates`, `needs_clarification`, or `outside_coverage`), questions, and matching candidates.
7. **Frontend Safety Gate**:
   - If `needs_clarification`: Displays clickable choice buttons.
   - If `candidates`: Renders a **vehicle configuration confirmation box**. The user must explicitly click *“These vehicle details match · inspect candidates”* before candidate part cards and cross-references appear.

---

## 4. Architecture Diagram

```mermaid
flowchart TD
    subgraph Browser ["Web Browser (Frontend SPA)"]
        UI["User Interface (index.html / style.css)"]
        JS["Client State & Controller (app.js)"]
        UI -->|Events & Input| JS
    end

    subgraph Backend ["Python / FastAPI Server (app.py)"]
        RouteSearch["POST /api/search"]
        RouteCatalog["GET /api/catalog"]
        RouteVIN["POST /api/vin"]
        MergeLogic["Merge Criteria:\nParsed + Manual Overrides"]
    end

    subgraph Providers ["Language Interpretation (providers.py)"]
        ProviderProto["LanguageProvider (Protocol)"]
        MockP["MockProvider\n(Bounded Heuristics / Regex)"]
        MetaP["MetaProvider\n(Chat Completions Adapter)"]
        ProviderProto -.-> MockP
        ProviderProto -.-> MetaP
    end

    subgraph External ["External Services (Optional & Network Dependent)"]
        MetaAPI["Meta API\n(api.meta.ai/v1/chat/completions)"]
        NHTSA["NHTSA vPIC API\n(vpic.nhtsa.dot.gov)"]
    end

    subgraph Domain ["Deterministic Domain Engine (domain.py)"]
        CriteriaModel["Criteria Model (Pydantic, extra='forbid')"]
        CatalogData[("catalog.json\n(30 Fictional Records)")]
        SearchEngine["search(criteria, catalog)\nDeterministic Matching & Staged Clarification"]
    end

    JS -->|1. POST text & criteria| RouteSearch
    JS -->|Initial catalog fetch| RouteCatalog
    JS -->|Optional VIN decode| RouteVIN

    RouteSearch -->|Manual Mode| MergeLogic
    RouteSearch -->|Mock Mode| MockP
    RouteSearch -->|Meta Mode| MetaP

    MetaP -->|HTTPS request (Text only)| MetaAPI
    RouteVIN -->|HTTPS request (VIN only)| NHTSA

    MockP -->|Returns Criteria| MergeLogic
    MetaP -->|Returns Criteria| MergeLogic

    MergeLogic -->|Validate Merged Dict| CriteriaModel
    CriteriaModel --> SearchEngine
    CatalogData --> SearchEngine
    SearchEngine -->|2. Status, Questions, Candidates| RouteSearch
    RouteSearch -->|3. JSON Response| JS
    JS -->|4. Interactive Clarification or Acknowledgment Gate| UI
```

### Readable Text Explanation of the Flow
1. **Frontend**: `app.js` runs entirely inside the user's browser, managing UI updates and tracking async request versions.
2. **Backend Gateway**: FastAPI (`app.py`) serves static files and receives JSON requests at `/api/search` and `/api/vin`.
3. **Language Interpretation Barrier**: The providers module (`providers.py`) isolates AI / heuristic text translation from catalog search.
4. **Deterministic Domain**: The domain module (`domain.py`) holds all rules regarding what fits what. It queries local in-memory fixtures loaded from `catalog.json`.

---

## 5. Annotated Folder Tree

```text
├── counterpilot/                       # Main application Python package
│   ├── __init__.py                     # Package marker
│   ├── app.py                          # FastAPI web server, routes, request merging, and error handling
│   ├── catalog.json                    # Fictional catalog: 5 vehicles, 30 parts with evidence
│   ├── domain.py                       # Pydantic Criteria schema, catalog loading, deterministic search
│   ├── providers.py                    # LanguageProvider protocol, MockProvider, MetaProvider adapter
│   └── static/                         # Static web frontend files
│       ├── app.js                      # Browser UI logic, race-condition handling, DOM rendering
│       ├── index.html                  # Semantic single-page HTML layout
│       └── style.css                   # Custom responsive styling (no external font or CDN dependencies)
├── counterpilot_vin_lookup.py          # Standalone public NHTSA vPIC VIN decoder (stdlib urllib only)
├── docs/                               # Documentation folder
│   └── ELI5_ARCHITECTURE_MANUAL.md     # This comprehensive architecture manual
├── tests/                              # Automated test suites
│   ├── browser.cjs                     # Playwright regression script testing UI states and layout
│   └── test_counterpilot.py            # 26 Python unittest tests (domain, provider, API, and VIN)
├── Dev/Agents/                         # Planning artifacts and build orders
├── BUILD_REPORT.md                     # Verification report of delivered features and test runs
├── README.md                           # Quickstart guide and run instructions
├── requirements.txt                    # Abstract Python dependency ranges
├── requirements.lock.txt               # Exact pinned Python dependencies
└── start.ps1                           # PowerShell launch script for local execution
```

---

## 6. Core Architectural Concepts & Decisions

Every major architectural decision in CounterPilot follows a simple formula:
> **What problem does this solve?**
> **How does this code solve it?**
> **What tradeoff does that create?**

---

### A. Deterministic Catalog Matching vs. AI Interpretation

* **What problem does this solve?**
  Large Language Models (LLMs) are probabilistic text generators. In automotive parts matching, a "hallucinated" part number or guessed brake rotor diameter leads to failed repairs, wasted shipping costs, or safety hazards.
* **How does this code solve it?**
  CounterPilot strictly divides the job into two stages:
  1. *Translation*: The AI / Language Provider (`providers.py`) converts natural language into structured search parameters (`Criteria`). It never sees parts inventory and has no authority to decide fitment.
  2. *Matching*: A deterministic engine (`domain.py:search`) compares criteria against explicit catalog rules (`catalog.json`). Fitment is purely a boolean logic check:
     $$\text{Candidate matches} \iff (\text{Year, Make, Model match}) \land (\text{Category matches}) \land (\text{All part requirements match})$$
* **What tradeoff does that create?**
  The system cannot automatically "fuzzily match" a part that isn't explicitly recorded in `catalog.json`. If a vehicle or part variation isn't in the catalog fixtures, it cannot be returned, even if an AI might know from general web knowledge that it fits.

---

### B. The Three Interpretation Paths (Mock, Meta, Manual)

CounterPilot supports three distinct paths to obtain `Criteria`:

```
                       +-----------------------+
                       | Customer Query String |
                       +-----------------------+
                                   |
        +--------------------------+--------------------------+
        |                          |                          |
 [ Mock Provider ]          [ Meta Provider ]          [ Manual Mode ]
  - Regex / Heuristic        - Remote LLM               - Bypasses Providers
  - Bounded vocabulary       - Strict JSON Schema       - Pure user UI inputs
  - Fast & Offline           - Remote API call          - Ultimate fallback
```

1. **Offline Mock Provider (`MockProvider` in `counterpilot/providers.py`)**:
   - *Problem*: You want to run the app, run automated tests, or develop offline without internet access or paid API keys.
   - *Solution*: A bounded regex parser that detects years, makes, canonical models (F-150, RAV4, CR-V, Silverado 1500, Tiguan), categories, positions, and brake packages.
   - *Tradeoff*: It only understands a small vocabulary and specific patterns. Complex conversational phrasing outside those patterns will not be parsed.
2. **Optional Meta Provider (`MetaProvider` in `counterpilot/providers.py`)**:
   - *Problem*: Real customers phrase requests in unexpected ways.
   - *Solution*: Uses Meta’s Chat Completions API with a system prompt and JSON schema enforcement (`Criteria.model_json_schema()`).
   - *Tradeoff*: Requires network access and a valid `MODEL_API_KEY`. It adds latency and external service dependency. Note: Live Meta integration is unverified until an actual successful request is made with a live key.
3. **Manual Interpretation Mode**:
   - *Problem*: The user wants total control, or both providers failed or misunderstood.
   - *Solution*: In `counterpilot/app.py:lookup()`, if `request.provider == "manual"`, interpretation is completely skipped:
     ```python
     parsed = Criteria() if request.provider == "manual" else get_provider(request.provider).interpret(request.text)
     ```
     The user selects vehicle, category, position, and package directly using dropdowns.
   - *Tradeoff*: Requires manual selection by the user rather than conversational convenience.

---

### C. Combining Parsed Criteria and Manual Overrides

* **What problem does this solve?**
  Suppose an AI correctly identifies `year=2019`, `make=Toyota`, `model=RAV4`, but misses the category or the user wants to change the category to `cabin_filter` using the UI dropdown.
* **How does this code solve it?**
  In `counterpilot/app.py:lookup()`:
  ```python
  merged = parsed.model_dump()
  merged.update(request.criteria.model_dump(exclude_none=True))
  result = search(Criteria(**merged))
  ```
  The server starts with the parsed fields, then overlays any explicit non-null values provided in `request.criteria`. Explicit manual controls always win.
* **What tradeoff does that create?**
  If a user leaves an old dropdown selected in the manual drawer, that dropdown value will override what they type in the text box. CounterPilot mitigates this in the frontend by resetting manual fields when the user edits the text box.

---

### D. Why Missing Details Trigger Clarification Instead of Guessing

* **What problem does this solve?**
  In software, when data is missing, developers often default to sensible fallbacks (e.g., defaulting position to `"front"`). In auto parts, defaulting causes the wrong part to be shipped.
* **How does this code solve it?**
  In `counterpilot/domain.py`, missing required fields never receive default values. If `category` or `model` is `None`, `search()` appends questions to `base["questions"]` and returns `status="needs_clarification"`:
  ```python
  for field, label in [("year", "What model year?"), ("make", "Which make?"),
                       ("model", "Which model?"), ("category", "Which part do you need?")]:
      if getattr(criteria, field) is None:
          clarify(field, label)
  ```
* **What tradeoff does that create?**
  The user has to take an extra step (clicking an option or typing a value) before receiving part candidates.

---

### E. Position Splits and Brake Package Splits

* **What problem does this solve?**
  Brake rotors differ between the front and rear axles. Furthermore, rear rotors often depend on vehicle options (such as heavy-duty payload packages). If you ask all questions at once, a customer asking for *front* rotors would unnecessarily be asked about rear brake packages.
* **How does this code solve it?**
  `domain.py:search()` uses a **two-stage clarification tree**:
  1. *Stage 1 (Position)*: If `category == "brake_rotor"` and `position is None`, CounterPilot asks *“Are the rotors for the front or rear?”* and stops there.
  2. *Stage 2 (Package)*: Only after `position` is known does it filter candidate parts by position. If the remaining parts have requirements (such as `requires: {"brake_package": "standard"}`), it checks if those specific options are known:
     ```python
     if not base["questions"]:
         for field in sorted({key for p in parts for key in p["requires"]}):
             if getattr(criteria, field) is None:
                 clarify(field, "Which brake package is fitted? Check the vehicle equipment record.",
                         sorted({p["requires"][field] for p in parts if field in p["requires"]}))
     ```
     Because front rotors have `requires: {}`, front rotor searches never trigger a brake package question!
* **What tradeoff does that create?**
  A user asking for rear rotors without specifying package experiences two consecutive clarification steps: first front vs. rear, then standard vs. heavy-duty.

---

### F. Catalog Application Evidence vs. Cross-Reference Information

* **What problem does this solve?**
  In the automotive aftermarket, *Application Evidence* (certifying that part X fits vehicle Y) is fundamentally different from an *Interchange / Cross-Reference* (a manufacturer claiming part X is equivalent to part Z). Third-party cross-references are notoriously prone to errors.
* **How does this code solve it?**
  - **Application Evidence** is the primary driver of fitment in `catalog.json` and is displayed prominently on candidate cards.
  - **Cross-References** (`p["interchanges"]`) are kept inside a collapsible `<details>` disclosure in the UI.
  - In `domain.py`, the search engine completely ignores `p["interchanges"]`. A test (`test_interchange_is_not_fitment`) asserts that adding a cross-reference for another vehicle will *never* cause the part to be returned as a candidate for that vehicle.
* **What tradeoff does that create?**
  CounterPilot cannot automatically cross-reference parts across different vehicle manufacturers without explicit application records for each vehicle.

---

### G. VIN Decoding: Proposing Identity vs. Proving Fitment

* **What problem does this solve?**
  Users often expect entering a 17-character VIN to immediately identify every part on their car. However, public government decoders (like NHTSA vPIC) decode manufacturer identity (Make, Model, Engine, DriveType), but do not record factory option codes (like heavy-duty brakes or suspension packages).
* **How does this code solve it?**
  1. `counterpilot_vin_lookup.py` queries NHTSA vPIC using Python's standard library and returns vehicle attributes.
  2. `POST /api/vin` returns the decoded vehicle with `"requires_confirmation": True`.
  3. The frontend displays the decoded identity but **does not automatically copy it** into the search criteria. The user must review the fields and click:
     *“Confirm identity & use these fields”*.
  4. The UI reminds the user that option-sensitive details (like brake package) still need manual verification.
* **What tradeoff does that create?**
  The user cannot perform a "one-click VIN-to-part" lookup; they must participate in the identity confirmation step.

---

### H. Frontend State, Async Versioning, and Stale-Result Clearing

* **What problem does this solve?**
  In single-page applications, two common bugs occur:
  - *Race conditions*: The user types "oil filter", then quickly changes to "rotors". If the first network response arrives after the second, the screen displays outdated information.
  - *Stale results*: The user has candidate oil filters on screen, edits the search text to "alternator", but the old oil filters remain visible.
* **How does this code solve it?**
  In `counterpilot/static/app.js`:
  1. **Monotonic Request Versioning**: Every new search increments `searchVersion`. When an async `fetch` completes, it checks `if (version !== searchVersion) return;`. Stale responses are silently dropped.
  2. **Aggressive Stale Clearing**: Whenever `#request`, `#vehicle`, or any manual field changes, the UI immediately increments `searchVersion` and replaces `#result-body` with a notice (*"Request changed. Run a new application check."*), wiping prior candidate cards.
  3. **Configuration Acknowledgment**: Candidate cards are never rendered upon search completion. The UI renders an acknowledgment block showing the full engine, trim, and drivetrain description. The user must click the acknowledgment button to render the part cards.
* **What tradeoff does that create?**
  Every keystroke wipes current results, requiring the user to submit or select an option to see updated results.

---

### I. Data Privacy & External Boundaries

CounterPilot enforces strict boundaries regarding what data leaves your machine:

| Data Element | Where It Goes | Why |
| :--- | :--- | :--- |
| **Request Text** (`text`) | Local (Mock) OR Meta API (if Meta selected) | Only conversational text is sent to Meta to parse criteria. |
| **Catalog Data** (`catalog.json`) | **Never leaves local server** | Private fixtures and inventory stay strictly local. |
| **Manual Criteria** | **Never leaves local server** | Explicit dropdown values stay local and are never sent to Meta. |
| **VIN** (`vin`) | Local OR NHTSA vPIC API (`POST /api/vin`) | Sent only to the public US government decoder; never sent to Meta. |
| **API Keys** (`MODEL_API_KEY`) | Server environment only | Never sent to browser client or logged to disk. |

The server launch command disables access logging (`--no-access-log`), preventing customer queries or VINs from being written to access logs.

---

## 7. Technology Stack Choices: Tradeoffs and Context

Why does CounterPilot use a local JSON file, Python/FastAPI, and vanilla HTML/JS?

1. **Local JSON (`catalog.json`)**:
   - *Why*: Self-contained demonstration fixture without external database setup (PostgreSQL, SQLite, Redis).
   - *Observed Tradeoff*: In-memory list filtering is fine for 30 records, but would not scale to a production catalog of 500,000 SKUs without database indexing.
2. **Python / FastAPI (`app.py`)**:
   - *Why*: High-performance asynchronous API framework with native Pydantic validation and automatic JSON schema generation (`Criteria.model_json_schema()`), which directly feeds the LLM provider prompt.
   - *Observed Tradeoff*: Requires Python 3.10+ runtime and lockfile management.
3. **Vanilla HTML/CSS/JavaScript (No Build Step)**:
   - *Why*: Can be opened and inspected directly in any browser without Node.js build pipelines (`npm run build`, Webpack, Vite). Zero CDN or remote font dependencies.
   - *Observed Tradeoff*: Requires manual DOM manipulation (`node()` helper in `app.js`) instead of declarative component rendering (like React or Vue).

---

## 8. Two Worked Step-by-Step Function Traces

Let's trace two real requests step by step through the exact code.

---

### Trace 1: A Simple Match ("Oil filter for a 2019 Toyota RAV4")

```
[ User types prompt ]
       │
       ▼
`app.js:runSearch()`
  Dispatches POST /api/search with:
  { text: "Oil filter for a 2019 Toyota RAV4", provider: "mock", criteria: {} }
       │
       ▼
`app.py:lookup(request)`
  Calls `MockProvider.interpret("Oil filter for a 2019 Toyota RAV4")`
       │
       ▼
`providers.py:MockProvider.interpret()`
  - Finds year: `2019`
  - Matches alias `r"\brav[ -]?4\b"` -> make="Toyota", model="RAV4"
  - Matches category `r"\boil\s+filter\b"` -> category="oil_filter"
  - Returns `Criteria(year=2019, make='Toyota', model='RAV4', category='oil_filter')`
       │
       ▼
`app.py:lookup()`
  Merges parsed with `request.criteria` (empty). Calls `domain.py:search(criteria)`
       │
       ▼
`domain.py:search(criteria)`
  1. Checks baseline fields (year=2019, make="Toyota", model="RAV4", category="oil_filter"): all present!
  2. Finds vehicle: matches vehicle `id="RAV4-01"` ("2.5L · XLE · AWD").
  3. Filters parts: finds `DEMO-RAV4-OIL_FILTER`.
  4. Checks category: `oil_filter` is not `brake_rotor`, so position is not needed.
  5. Checks restrictions: `p["requires"]` is empty `{}`.
  6. Returns:
     {
       status: "candidates",
       vehicle: { id: "RAV4-01", description: "2.5L · XLE · AWD", ... },
       candidates: [ { id: "DEMO-RAV4-OIL_FILTER", name: "oil filter", ... } ],
       questions: []
     }
       │
       ▼
`app.js:render(result)`
  1. Displays badge: `APPLICATION RECORD FOUND`.
  2. Renders confirmation box: *"Confirm the vehicle configuration: 2019 Toyota RAV4 · 2.5L · XLE · AWD"*.
  3. User clicks *"These vehicle details match · inspect candidates"*.
  4. Calls `showCards()`, revealing `DEMO-RAV4-OIL_FILTER` and its evidence statement.
```

---

### Trace 2: Clarification Flow ("Rotors for a 2021 Ford F-150")

```
[ User types prompt ]
       │
       ▼
`app.js:runSearch()`
  Dispatches POST /api/search with:
  { text: "Rotors for a 2021 Ford F-150", provider: "mock", criteria: {} }
       │
       ▼
`providers.py:MockProvider.interpret()`
  - Matches year: `2021`
  - Matches alias `r"\bf[ -]?150\b"` -> make="Ford", model="F-150"
  - Matches category `r"\brotors?\b"` -> category="brake_rotor"
  - Position: None. Brake package: None.
  - Returns `Criteria(year=2021, make='Ford', model='F-150', category='brake_rotor', position=None)`
       │
       ▼
`domain.py:search(criteria)`
  1. Baseline vehicle fields are present. Matches vehicle `F150-01`.
  2. Part category is `brake_rotor`, but `criteria.position is None`.
  3. Triggers clarification:
     `clarify("position", "Are the rotors for the front or rear?", ["front", "rear"])`
  4. Returns `status="needs_clarification"`, `candidates=[]`, `questions=[{"field": "position", ...}]`.
       │
       ▼
`app.js:render(result)`
  Displays badge: `ONE MORE DETAIL`.
  Renders two interactive buttons: `[ front ]` and `[ rear ]`.
       │
       ▼
[ User clicks "rear" ]
  Button click handler sets `$('position').value = 'rear'` and calls `runSearch()`.
  Dispatches POST /api/search with:
  { text: "Rotors for a 2021 Ford F-150", criteria: { position: "rear" } }
       │
       ▼
`domain.py:search(criteria)`
  1. Position is now `"rear"`. Parts filtered to rear rotors:
     - `DEMO-F150-BRAKE_ROTOR-REAR-STANDARD` (requires brake_package: "standard")
     - `DEMO-F150-BRAKE_ROTOR-REAR-HEAVY-DUTY` (requires brake_package: "heavy-duty")
  2. Evaluates option restrictions: `brake_package` is required by rear parts, but `criteria.brake_package is None`.
  3. Triggers clarification:
     `clarify("brake_package", "Which brake package is fitted?...", ["heavy-duty", "standard"])`
  4. Returns `status="needs_clarification"`, `candidates=[]`, `questions=[{"field": "brake_package", ...}]`.
       │
       ▼
`app.js:render(result)`
  Renders package choice buttons: `[ heavy-duty ]` and `[ standard ]`.
       │
       ▼
[ User clicks "standard" ]
  Sets `$('brake_package').value = 'standard'` and calls `runSearch()`.
  Dispatches POST with criteria: `{ position: "rear", brake_package: "standard" }`.
       │
       ▼
`domain.py:search(criteria)`
  All requirements satisfied! Returns `status="candidates"` with `DEMO-F150-BRAKE_ROTOR-REAR-STANDARD`.
  Frontend requires vehicle acknowledgment, then displays the candidate card!
```

---

## 9. API Reference & Contract

CounterPilot exposes three JSON endpoints:

### 1. `GET /api/catalog`
Returns catalog metadata and current provider capabilities.
* **Request**: None.
* **Sample Response (200 OK)**:
  ```json
  {
    "vehicles": [
      {
        "id": "F150-01",
        "year": 2021,
        "make": "Ford",
        "model": "F-150",
        "description": "3.5L EcoBoost · XLT · 4WD",
        "fictional": true
      }
    ],
    "categories": ["oil_filter", "air_filter", "cabin_filter", "brake_rotor"],
    "fictional": true,
    "default_provider": "mock",
    "meta_configured": false,
    "meta_verification": "Live integration is unverified until a successful request."
  }
  ```

---

### 2. `POST /api/search`
Interprets customer text, merges explicit manual fields, and evaluates catalog fitment.
* **Request Payload**:
  ```json
  {
    "text": "Oil filter for a 2019 Toyota RAV4",
    "provider": "mock",
    "criteria": {
      "category": null,
      "year": null
    }
  }
  ```
* **Sample Response (`candidates`)**:
  ```json
  {
    "status": "candidates",
    "message": "Listed in the fictional demo application data; confirm vehicle details.",
    "criteria": {
      "year": 2019,
      "make": "Toyota",
      "model": "RAV4",
      "category": "oil_filter",
      "position": null,
      "brake_package": null
    },
    "vehicle": {
      "id": "RAV4-01",
      "year": 2019,
      "make": "Toyota",
      "model": "RAV4",
      "description": "2.5L · XLE · AWD"
    },
    "candidates": [
      {
        "id": "DEMO-RAV4-OIL_FILTER",
        "part_number": "DEMO-RAV4-OIL_FILTER",
        "name": "oil filter",
        "evidence": [
          {
            "source": "CounterPilot fictional application fixture v1",
            "statement": "Invented application for 2019 Toyota RAV4 (2.5L · XLE · AWD). Not a manufacturer fitment claim."
          }
        ],
        "restrictions": ["Confirm the displayed engine, trim and drivetrain before proceeding."],
        "interchanges": [
          {
            "number": "XREF-DEMO-RAV4-OIL_FILTER",
            "status": "Unverified fictional reference only; not application evidence."
          }
        ]
      }
    ],
    "questions": [],
    "provider": "mock",
    "notice": "Fictional demonstration catalog. Not for purchasing or installation."
  }
  ```
* **Sample Response (`needs_clarification`)**:
  ```json
  {
    "status": "needs_clarification",
    "message": "A fitment detail is needed before selecting candidates.",
    "questions": [
      {
        "field": "position",
        "label": "Are the rotors for the front or rear?",
        "options": ["front", "rear"]
      }
    ]
  }
  ```
* **Error Behaviors**:
  - `422 Unprocessable Entity`: Invalid schema (e.g., year outside 1980-2100, text > 2000 chars, extra unexpected JSON keys).
  - `503 Service Unavailable`: Interpretation provider failure (e.g., missing Meta API key or malformed LLM response).

---

### 3. `POST /api/vin`
Decodes 17-character VIN via NHTSA vPIC to propose vehicle identity.
* **Request Payload**:
  ```json
  {
    "vin": "1HGCM82633A004352",
    "year": 2003
  }
  ```
* **Sample Response (200 OK)**:
  ```json
  {
    "vehicle": {
      "vin": "1HGCM82633A004352",
      "model_year": "2003",
      "make": "HONDA",
      "model": "Accord",
      "trim": "EX",
      "engine": {
        "displacement_l": "2.4",
        "cylinders": "4"
      },
      "drivetrain": "FWD",
      "source": "NHTSA vPIC"
    },
    "requires_confirmation": true,
    "message": "Confirm these identity details. VIN decoding does not confirm parts fitment."
  }
  ```
* **Error Behaviors**:
  - `502 Bad Gateway`: Network error, invalid VIN checksum, or upstream NHTSA service failure. Upstream trace details are sanitized to protect sensitive information.

---

## 10. The "Where Would I Change...?" Guide

If you need to make changes to CounterPilot in the future, here is your roadmap:

| To change this... | Go to this file... | What to look for... |
| :--- | :--- | :--- |
| **Add a new vehicle or part** | `counterpilot/catalog.json` | Add a vehicle object under `"vehicles"` and part applications under `"parts"`. Ensure part `requires` matches schema. |
| **Add a new part category** | `counterpilot/domain.py` & `providers.py` | Add category literal to `Category` in `domain.py`, add parser regex to `MockProvider`, and add `<option>` to `index.html`. |
| **Change clarification rules** | `counterpilot/domain.py` | Inspect `search()` function: adjust the staged order of `base["questions"]` generation. |
| **Add an AI provider (e.g. Claude/OpenAI)** | `counterpilot/providers.py` | Implement `LanguageProvider` protocol with `.interpret(text: str) -> Criteria`. Register in `get_provider()`. |
| **Modify UI layout or confirmation gate** | `counterpilot/static/app.js` & `index.html` | Inspect `render()` and `showCards()` in `app.js`. |
| **Add backend unit tests** | `tests/test_counterpilot.py` | Add test methods inheriting from `unittest.TestCase`. |

---

## 11. Setup, Running, and Troubleshooting

### Prerequisites
* Python 3.10+
* Windows, macOS, or Linux

### Quickstart
1. **Install dependencies**:
   ```bash
   pip install -r requirements.lock.txt
   ```
2. **Start the local server**:
   ```bash
   python3 -m uvicorn counterpilot.app:app --host 127.0.0.1 --port 8000 --no-access-log
   ```
   *(Or run `./start.ps1` on Windows PowerShell).*
3. **Open in browser**:
   Navigate to `http://127.0.0.1:8000`.

### Running Tests
To run the full Python test suite (26 tests covering all vehicles, categories, splits, and edge cases):
```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

### Basic Troubleshooting
* **Error: `ModuleNotFoundError: No module named 'fastapi'`**:
  You are running outside the configured environment. Run `pip install -r requirements.lock.txt`.
* **503 Service Unavailable when selecting Meta**:
  `MODEL_API_KEY` environment variable is not set. Export the variable or switch the dropdown back to "Offline demo parser" or "Manual details only".
* **502 Bad Gateway on VIN Lookup**:
  NHTSA vPIC requires internet connectivity. If offline or if the VIN is invalid, the decoder returns 502. Enter vehicle details manually using the drawer.

---

## 12. Implemented Behavior vs. Future Possibilities

To keep architecture clear, we separate what is **actually implemented** from **future possibilities**:

### What Is Implemented Today
- [x] 5 vehicle families, 30 fictional catalog fixture records with evidence statements.
- [x] Deterministic matching engine with two-stage clarification (position, then option split).
- [x] Offline heuristic parser (`MockProvider`) with contradiction protection.
- [x] Remote LLM adapter (`MetaProvider`) with JSON schema enforcement (live connection unverified).
- [x] Manual entry fallback bypassing AI providers.
- [x] Stale result clearing and async request version tracking.
- [x] Vehicle configuration acknowledgment safety barrier.
- [x] NHTSA vPIC VIN identity decoding with mandatory confirmation gate.

### Future Possibilities (Not Implemented)
- [ ] Real relational / document database backend (e.g. SQLite, PostgreSQL).
- [ ] OEM equipment build sheet decoding (e.g., matching exact factory option codes like RPO codes).
- [ ] Customer account authentication and saved garage vehicles.
- [ ] Real-time inventory, pricing, warehouse shelf bin locations, or e-commerce ordering.
- [ ] Multi-part bundle searches (e.g., "pads and rotors front and rear in one query").
