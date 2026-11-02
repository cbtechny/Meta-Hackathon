"""FastAPI application endpoints and request orchestration for CounterPilot.

Architectural Role:
    This module ties together the frontend interface, language interpretation providers,
    deterministic catalog search, and optional VIN decoding.
    It exposes HTTP endpoints for:
      - Serving the static SPA interface (`/` and `/static/*`)
      - Inspecting supported catalog coverage and provider configuration (`GET /api/catalog`)
      - Interpreting customer queries and executing catalog checks (`POST /api/search`)
      - Performing vehicle identity lookups via NHTSA vPIC (`POST /api/vin`)

Request Orchestration & State Decisions:
    - In `POST /api/search`:
        1. Parse natural language request using the selected provider (or bypass if 'manual').
        2. Merge: Explicit, non-null manual fields always override parsed fields.
        3. Match: Run deterministic catalog search using the combined `Criteria`.
    - Error Isolation:
        * Provider failures return HTTP 503 without crashing the server or silently swapping providers.
        * VIN lookup failures return HTTP 502 with generic user advice, protecting private inputs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from counterpilot_vin_lookup import decode_vin, VinLookupError
from .domain import CATALOG, Criteria, search
from .providers import ProviderError, get_provider

app = FastAPI(title="CounterPilot", version="0.1.0")
STATIC = Path(__file__).with_name("static")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class SearchRequest(BaseModel):
    """Payload schema for the `/api/search` endpoint.

    Fields:
        text: Unstructured human request string.
        provider: Which interpretation engine to invoke ('mock', 'meta', or 'manual').
        criteria: Explicit structured fields from UI dropdowns/inputs, overriding parsed text.
    """
    model_config = ConfigDict(extra="forbid")
    text: str = Field(default="", max_length=2000)
    provider: Literal["mock", "meta", "manual"] = "mock"
    criteria: Criteria = Field(default_factory=Criteria)


class VinRequest(BaseModel):
    """Payload schema for the `/api/vin` endpoint.

    Fields:
        vin: 1-40 character string (format validation occurs inside `decode_vin`).
        year: Optional model year hint to assist NHTSA decoder.
    """
    vin: str = Field(min_length=1, max_length=40)
    year: int | None = Field(default=None, ge=1980, le=2100)


@app.get("/")
def index():
    """Serve the single-page application entrypoint."""
    return FileResponse(STATIC / "index.html")


@app.get("/api/catalog")
def coverage():
    """Return supported vehicle configurations, part categories, and provider metadata.

    The frontend consumes this on initial page load to populate vehicle selector dropdowns
    and display status notices regarding Meta API configuration and unverified status.
    """
    return {"vehicles": CATALOG["vehicles"], "categories": ["oil_filter", "air_filter", "cabin_filter", "brake_rotor"],
            "fictional": True, "default_provider": "meta" if os.environ.get("COUNTERPILOT_PROVIDER") == "meta" else "mock",
            "meta_configured": bool(os.environ.get("MODEL_API_KEY")),
            "meta_verification": "Live integration is unverified until a successful request."}


@app.post("/api/search")
def lookup(request: SearchRequest):
    """Orchestrate customer request parsing, explicit criteria merging, and catalog search.

    How parsed criteria and explicit manual fields are combined:
      1. If provider == "manual", interpretation is completely bypassed (starts with empty Criteria).
      2. If provider is "mock" or "meta", `provider.interpret(request.text)` produces a candidate `Criteria`.
      3. `merged = parsed.model_dump()` converts parsed criteria to a dictionary.
      4. `merged.update(request.criteria.model_dump(exclude_none=True))` overlays any explicit,
         non-null fields chosen in the UI. Explicit manual entries take precedence over AI interpretation.
      5. The merged dictionary is validated back into `Criteria` and passed to deterministic `search()`.
    """
    try:
        parsed = Criteria() if request.provider == "manual" else get_provider(request.provider).interpret(request.text)
    except ProviderError as exc:
        raise HTTPException(503, str(exc)) from exc
    # Non-null explicit selections override interpretation. Unknown fields stay unknown.
    merged = parsed.model_dump()
    merged.update(request.criteria.model_dump(exclude_none=True))
    result = search(Criteria(**merged))
    return {**result, "provider": request.provider}


@app.post("/api/vin")
def vin_lookup(request: VinRequest):
    """Decode a vehicle identification number using NHTSA vPIC to propose identity details.

    Why VIN decoding proposes identity rather than proving part compatibility:
      - NHTSA vPIC reports broad manufacturer-level attributes (Make, Model, Year, Engine displacement).
      - It does NOT track factory brake packages, mid-year production splits, or aftermarket interchange.
      - Therefore, this endpoint sets `requires_confirmation: True`. The user must explicitly inspect
        and confirm the proposed fields before they can be copied into search criteria.
    """
    try:
        decoded = decode_vin(request.vin, request.year)
    except (VinLookupError, ValueError, TypeError, KeyError, AttributeError) as exc:
        # Do not include the VIN or upstream exception detail in the HTTP response.
        raise HTTPException(502, "VIN could not be decoded. Enter vehicle details manually.") from exc
    return {"vehicle": decoded, "requires_confirmation": True,
            "message": "Confirm these identity details. VIN decoding does not confirm parts fitment."}
