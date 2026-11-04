from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from counterpilot_vin_lookup import decode_vin, VinLookupError
from .domain import CATALOG, Criteria, search
from .providers import MetaProvider, ProviderError, get_provider
from .chat import ChatRequest, lookup_reply, merge_details
from .conversation import respond
from .catalog_io import PART_TYPES
from .garage import COOKIE_NAME, read_garage
from .vin_photo import PhotoRequest, read_photo, MAX_PHOTO_BODY
from .explanations import ExplainRequest, explain

# Use this checkout's configuration regardless of the launch directory.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

app = FastAPI(title="CounterPilot", version="0.1.0")
STATIC = Path(__file__).with_name("static")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
CHAT_HEADERS = {
    "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
}


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
    return FileResponse(STATIC / "chat.html")


@app.middleware("http")
async def protect_chat(request: Request, call_next):
    if request.url.path not in {"/", "/chat", "/api/chat", "/api/catalog", "/api/garage", "/api/vin-photo", "/api/explain"} and not request.url.path.startswith(("/static/chat.", "/static/garage.", "/static/product.", "/static/polish.", "/static/mark.", "/static/assist.")):
        return await call_next(request)
    if request.url.path in {"/api/chat", "/api/vin-photo", "/api/explain"}:
        # Reject cross-origin browser calls and oversized bodies before parsing.
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Use the chat from this site."}, status_code=403, headers=CHAT_HEADERS)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > (MAX_PHOTO_BODY if request.url.path == "/api/vin-photo" else 48000):
                return JSONResponse({"detail": "Message context is too large."}, status_code=413, headers=CHAT_HEADERS)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers.update(CHAT_HEADERS)
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    if request.url.path in {"/api/chat", "/api/vin-photo", "/api/explain"}:
        # Default validation errors echo invalid input; chat never does.
        return JSONResponse({"detail": "Check the message and lookup details, then try again."}, status_code=422)
    from fastapi.exception_handlers import request_validation_exception_handler
    return await request_validation_exception_handler(request, exc)


@app.get("/chat")
def chat_page():
    return RedirectResponse("/", status_code=307)


@app.post("/api/chat")
def chat_lookup(request: ChatRequest):
    try:
        return respond(request, decode_vin)
    except ProviderError:
        raise HTTPException(503, "Chat couldn't reach Meta or read its reply. Your message is kept; retry shortly.") from None


@app.get("/api/catalog")
def coverage():
    kinds = sorted({p["part_type"] for p in CATALOG["parts"]})
    return {"vehicles": CATALOG["vehicles"], "categories": kinds,
            "part_types": [{"id": kind, "name": PART_TYPES[kind][2],
                            "positions": sorted({p["position"] for p in CATALOG["parts"] if p["part_type"] == kind and p["position"]}),
                            "sides": sorted({p["side"] for p in CATALOG["parts"] if p["part_type"] == kind and p["side"]})} for kind in kinds],
            "part_aliases": CATALOG["aliases"],
            "application_count": len(CATALOG["parts"]), "sample_count": CATALOG["sample_count"], "verified_count": CATALOG["verified_count"],
            "fictional": CATALOG["verified_count"] == 0, "default_provider": "meta" if os.environ.get("COUNTERPILOT_PROVIDER") == "meta" else "mock",
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


@app.get("/api/garage")
def garage_applications(request: Request):
    return read_garage(request.cookies.get(COOKIE_NAME), CATALOG)


@app.get("/healthz")
def health_check():
    # Process/catalog readiness only. Never spend a model call or expose settings.
    return JSONResponse({"status": "ok", "catalog_loaded": bool(CATALOG["vehicles"] and CATALOG["parts"])},
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.post("/api/vin-photo")
def vin_photo_lookup(request: PhotoRequest):
    try:
        return read_photo(request)
    except ProviderError:
        raise HTTPException(503, "Photo reading is unavailable. Retry or type the VIN.") from None


@app.post("/api/explain")
def explain_record(request: ExplainRequest):
    return explain(request)
