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
    model_config = ConfigDict(extra="forbid")
    text: str = Field(default="", max_length=2000)
    provider: Literal["mock", "meta", "manual"] = "mock"
    criteria: Criteria = Field(default_factory=Criteria)


class VinRequest(BaseModel):
    vin: str = Field(min_length=1, max_length=40)
    year: int | None = Field(default=None, ge=1980, le=2100)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/catalog")
def coverage():
    return {"vehicles": CATALOG["vehicles"], "categories": ["oil_filter", "air_filter", "cabin_filter", "brake_rotor"],
            "fictional": True, "default_provider": "meta" if os.environ.get("COUNTERPILOT_PROVIDER") == "meta" else "mock",
            "meta_configured": bool(os.environ.get("MODEL_API_KEY")),
            "meta_verification": "Live integration is unverified until a successful request."}


@app.post("/api/search")
def lookup(request: SearchRequest):
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
    try:
        decoded = decode_vin(request.vin, request.year)
    except (VinLookupError, ValueError, TypeError, KeyError, AttributeError) as exc:
        # Do not include the VIN or upstream exception detail in the HTTP response.
        raise HTTPException(502, "VIN could not be decoded. Enter vehicle details manually.") from exc
    return {"vehicle": decoded, "requires_confirmation": True,
            "message": "Confirm these identity details. VIN decoding does not confirm parts fitment."}
