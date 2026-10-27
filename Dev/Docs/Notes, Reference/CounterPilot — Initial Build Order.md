# CounterPilot — Initial Build Order

## Goal

Build a small, trustworthy parts-finder demo that turns a customer’s plain-language request into structured vehicle and part criteria, then shows matching candidates with clear fitment evidence. The catalog and fitment logic remain deterministic; AI helps interpret language but does not decide compatibility.

## Build order

### 1. Create a mock vehicle and parts catalog

Start with local JSON data containing:

- **5–10 vehicles**, with year, make, model, and any needed trim or engine details.
- **20–30 parts**, with part number, name, category, position (such as front/rear or left/right), supported vehicle fitment, and interchange or cross-reference numbers where applicable.
- Clear, traceable sample or properly licensed data. Keep source and license notes with the dataset; do not use proprietary catalog data without permission.

Keep the initial catalog intentionally small and internally consistent so it can support useful searches and tests.

### 2. Implement deterministic lookup

Build ordinary application logic for:

- Year, make, and model selection or matching.
- Part category matching.
- Fitment checks against the catalog’s explicit vehicle and part data.
- Interchange lookup where the catalog provides a relationship.

This lookup must work independently of any AI provider. It is the source of truth for whether a part is listed as fitting a vehicle. Return the matched catalog records and the evidence used to reach the result.

### 3. Add a replaceable language-understanding provider

Define a small modular provider interface that accepts a customer’s fuzzy request and returns structured fields, such as vehicle year/make/model, part category, position, and any stated symptoms or constraints.

First, implement a mock provider with predictable behavior and representative examples. Keep the interface isolated so it can later be swapped for Meta Muse Spark when hackathon credits arrive. The provider translates language into search criteria; deterministic catalog lookup still finds and verifies candidates. Ask for clarification when required fields are missing or ambiguous.

### 4. Build the minimal web demo

Create a focused web experience that lets someone:

1. Enter a natural-language request or provide vehicle and part details.
2. See a clarification question when the request lacks required information.
3. Review candidate parts returned by deterministic lookup.
4. Inspect fitment evidence, including the vehicle fields and catalog data that support each result.
5. Read a concise explanation of how the request was interpreted and why each candidate was returned.

Make uncertainty visible. Do not imply a fitment is confirmed when the catalog has no supporting record.

## Implementation principles

- Start in a **private GitHub repository**.
- Use a **Python backend**.
- Keep the AI or language-understanding provider behind a **modular interface** so the mock can be replaced with Meta Muse Spark without rewriting lookup logic.
- **Never commit API keys, credentials, or proprietary data.** Keep secrets in local environment configuration that is excluded from version control.
- Include tests for catalog validation, deterministic vehicle/category/fitment lookup, interchange behavior, clarification cases, and provider output handling.
- Maintain a README with setup steps, data provenance and license notes, architecture, test instructions, and a clear explanation of the mock provider and the planned Muse Spark integration.

## Completion sequence

Treat each numbered stage as the prerequisite for the next. Establish and test the catalog and deterministic fitment behavior before adding language interpretation; build the web demo only after those interfaces and result evidence are stable.
