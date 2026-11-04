"""Conversation state and catalog-grounded replies; no model-authored fitment claims."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .domain import CATALOG, Criteria, resolve_part_type


class ChatDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    year: int | None = Field(default=None, ge=1980, le=2100)
    make: str | None = Field(default=None, max_length=40)
    model: str | None = Field(default=None, max_length=40)
    engine: str | None = Field(default=None, max_length=80)
    part: str | None = Field(default=None, max_length=80)
    position: Literal["front", "rear"] | None = None
    side: Literal["left", "right"] | None = None
    trim: str | None = Field(default=None, max_length=80)
    drivetrain: str | None = Field(default=None, max_length=40)
    hybrid: bool | None = None
    symptoms: str | None = Field(default=None, max_length=300)

    @field_validator("engine")
    @classmethod
    def normalize_engine(cls, value):
        if value:
            value = re.sub(r"(?i)\b(liters?|litres?)\b", "L", value).strip()
            if re.fullmatch(r"\d+(?:\.\d+)?\s*[lL]?", value):
                return f"{float(re.search(r'\d+(?:\.\d+)?', value).group()):g}L"
        return value

    @field_validator("make", "model", "engine", "part")
    @classmethod
    def blank_is_unknown(cls, value):
        return value or None


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(default="", max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=24)
    details: ChatDetails = Field(default_factory=ChatDetails)
    edits: ChatDetails | None = None
    session_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    revision: int = Field(default=0, ge=0)
    request_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    # Filled by the backend from its session, never accepted as model authority.
    context: str = Field(default="", max_length=16000, exclude=True)

    @model_validator(mode="after")
    def bounded_conversation(self):
        if not self.message and not (self.edits and self.edits.model_fields_set):
            raise ValueError("A message or detail correction is required.")
        if self.message and self.edits is not None:
            raise ValueError("Send a message or detail correction separately.")
        if sum(len(item.content) for item in self.history) + len(self.message) > 24000:
            raise ValueError("Conversation context is too long.")
        return self


def merge_details(current: ChatDetails, update: ChatDetails) -> ChatDetails:
    delta = update.model_dump(exclude_unset=True)
    values = current.model_dump()
    changed = {field for field, value in delta.items() if value != values[field]}
    # Equipment facts do not automatically transfer to a corrected vehicle.
    if changed & {"year", "make", "model"}:
        values.update(engine=None, trim=None, drivetrain=None, hybrid=None, side=None)
    if "make" in changed and "model" not in delta:
        values["model"] = None
    if "part" in changed:
        values.update(position=None, side=None, symptoms=None)
    values.update(delta)
    return ChatDetails(**values)


class Conversation(BaseModel):
    details: ChatDetails = Field(default_factory=ChatDetails)
    sources: dict[str, str] = Field(default_factory=dict)
    decoded: ChatDetails | None = None
    vin: str | None = None
    confirmed: bool = False
    overrides: dict = Field(default_factory=dict)
    pending: dict | None = None
    proposed: ChatDetails | None = None
    vin_declined: bool = False
    attempts: dict[str, int] = Field(default_factory=dict)
    history: list[ChatMessage] = Field(default_factory=list)
    revision: int = 0
    candidate_ids: list[str] = Field(default_factory=list)
    skipped_preview_fields: set[str] = Field(default_factory=set)


def question(field, label, options=None):
    return {"field": field, "label": label, "options": options or []}


VEHICLE_DETAIL_FIELDS = ("year", "make", "model", "engine", "trim", "drivetrain")


def detail_progress(state: Conversation) -> dict:
    confirmed = [field for field in VEHICLE_DETAIL_FIELDS
                 if getattr(state.details, field) is not None
                 and str(getattr(state.details, field)).strip().casefold() not in {"", "unknown", "unsure", "not sure"}
                 and state.sources.get(field) in {"customer", "customer override", "VIN confirmed"}]
    return {"confirmed": len(confirmed), "total": len(VEHICLE_DETAIL_FIELDS),
            "confirmed_fields": confirmed,
            "unconfirmed_fields": [field for field in VEHICLE_DETAIL_FIELDS if field not in confirmed],
            "meaning": "Detail completeness, not fitment probability. Even 6 of 6 does not establish compatibility or availability."}


def stated_engine_displacement(text: str, engine: str) -> bool:
    """Compare complete numeric tokens, allowing units and sentence punctuation.

    Float equivalence handles 2L/2.0L without deriving displacement from a
    cylinder count or from digits embedded in a model name.
    """
    displacement = re.match(r"\d+(?:\.\d+)?", engine)
    if not displacement:
        return False
    tokens = re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?!\d)", text)
    return any(float(token) == float(displacement[0]) for token in tokens)


def engine_matches(stated, expected):
    def norm(s):
        return re.sub(r"[^a-z0-9.]", "", s.casefold())
    if norm(stated) == norm(expected):
        return True
    # Only a bare displacement can match an engine with extra profile qualifiers.
    bare = re.fullmatch(r"(\d+(?:\.\d+)?)[lL]?", stated.strip())
    displacement = re.match(r"\d+(?:\.\d+)?", expected)
    return bool(bare and displacement and float(bare[1]) == float(displacement[0]))


def application_facts(details, catalog=CATALOG):
    """Retrieve only relevant profiles, before deciding which question matters."""
    return [v for v in catalog["vehicles"]
            if all(getattr(details, f) is None or str(getattr(details, f)).casefold() == str(v[f]).casefold()
                   for f in ("year", "make", "model"))]


def lookup_reply(details: ChatDetails, state: Conversation | None = None, catalog=None) -> dict:
    catalog = catalog or CATALOG
    state = state or Conversation(details=details)
    kind = resolve_part_type(details.part, catalog)
    result = {"status": "needs_clarification", "candidates": [], "questions": [],
              "criteria": {**details.model_dump(), "category": kind},
              "notice": "Catalog applications only. Demo records have simulated fitment; availability is unverified."}
    q = None
    reply = ""
    if state.pending and state.pending["field"] in {"vin_confirmation", "override_confirmation"}:
        q = state.pending
    elif not details.part or details.part.casefold() in {"filter", "filters", "brakes", "brake"}:
        if details.part and "filter" in details.part.casefold():
            q = question("part", "Which filter—oil, engine air, or cabin air?", ["Oil", "Engine air", "Cabin air"])
        elif details.part:
            q = question("part", "Do you need brake pads, rotors, calipers, or help describing a brake problem?", ["Brake pads", "Brake rotors", "Brake calipers"])
        elif details.symptoms:
            q = question("part", "That symptom can have several causes. Which part are you looking for, or has a mechanic identified one?")
        else:
            q = question("part", "What part do you need?")
    else:
        if kind == "unsupported":
            result["status"] = "outside_coverage"
            return {"details": details.model_dump(), "reply": "I don't have that part category loaded. I'll keep your request; you can try another part or a demo vehicle.", "question": None, "lookup": result, "pending": None}
        for field, label in [("year", f"What year is your {details.model or 'vehicle'}?"),
                             ("make", "What make is it?"), ("model", "Which model?")]:
            if getattr(details, field) is None:
                q = question(field, label)
                break
        if not q:
            vehicles = application_facts(details, catalog)
            parts = [p for p in catalog["parts"] if p["vehicle_id"] in {v["id"] for v in vehicles} and p["part_type"] == kind]
            if not parts:
                result["status"] = "outside_coverage"
                reply = "I don't have a matching application loaded for that request. I'll keep your details; you can try another part or a demo vehicle."
            else:
                profiles = {v["id"]: v for v in vehicles}
                def profile_value(v, field):
                    if field == "hybrid":
                        fuel = v.get("fuel_type", "").casefold()
                        return True if "hybrid" in fuel else False if fuel in {"gasoline", "diesel"} else None
                    return v.get(field)
                # Catalog constraints never rewrite customer facts.
                for field in ("engine", "trim", "drivetrain", "hybrid"):
                    stated = getattr(details, field)
                    if stated is None:
                        continue
                    def matches(p):
                        v = profiles[p["vehicle_id"]]
                        expected = profile_value(v, field)
                        if expected in (None, "", "unknown"):
                            return False
                        return engine_matches(stated, expected) if field == "engine" else str(stated).casefold() == str(expected).casefold()
                    filtered = [p for p in parts if matches(p)]
                    if not filtered:
                        result["status"] = "outside_coverage"
                        loaded = ", ".join(sorted({v.get(field, "unknown") for v in vehicles})) if field != "hybrid" else "the listed demo configuration"
                        reply = f"This demo only has {loaded} records loaded for that request. I can keep your vehicle details, but I don't have a matching part loaded yet."
                        parts = []
                        break
                    parts = filtered
                for field, label in [("position", "Do you need front or rear?"), ("side", "Do you need the left or right side?")]:
                    if not parts:
                        break
                    choices = sorted({p[field] for p in parts if p.get(field)})
                    value = getattr(details, field)
                    if choices and value:
                        parts = [p for p in parts if p.get(field) == value]
                    elif choices:
                        q = question(field, label, choices)
                        break
                if parts and not q:
                    engines = sorted({profiles[p["vehicle_id"]].get("engine", "unknown") for p in parts})
                    def signatures(field):
                        groups = {}
                        for p in parts:
                            value = profile_value(profiles[p["vehicle_id"]], field)
                            groups.setdefault(value, set()).add((p["part_number"], p.get("position"), p.get("side")))
                        return {frozenset(group) for group in groups.values()}
                    # Ask only when the answer separates loaded applications. A single
                    # demo profile is a preview to review, never proof of universal fitment.
                    if details.engine is None and len(engines) > 1 and len(signatures("engine")) > 1:
                        q = question("engine", "What engine does it have? The loaded applications differ by engine.", engines)
                    elif any(not profiles[p["vehicle_id"]].get("engine") or profiles[p["vehicle_id"]].get("engine") == "unknown" for p in parts):
                        result["status"] = "outside_coverage"
                        reply = "These records lack enough application details to verify a match. We can keep your request, but need better catalog data."
                    elif len({p["vehicle_id"] for p in parts}) > 1 and len(signatures("id")) > 1:
                        # Do not silently pick the first profile when equipment differs.
                        remaining = [profiles[p["vehicle_id"]] for p in parts]
                        for field in ("hybrid", "trim", "drivetrain"):
                            choices = {profile_value(v, field) for v in remaining}
                            if len(choices) > 1 and None not in choices and "unknown" not in choices and getattr(details, field) is None and len(signatures(field)) > 1:
                                options = ["Hybrid", "Non-hybrid"] if field == "hybrid" else sorted(choices)
                                q = question(field, "Is it hybrid or non-hybrid?" if field == "hybrid" else f"Which {field} does it have?", options)
                                break
                        if not q:
                            result["status"] = "outside_coverage"
                            reply = "Several applications remain, and this catalog lacks the detail to separate them. A verified application source is needed."
                    if not q and not reply:
                        applications = [profiles[vid] for vid in dict.fromkeys(p["vehicle_id"] for p in parts)]
                        unknown = [f for f in ("engine", "trim", "drivetrain", "hybrid") if getattr(details, f) is None]
                        result.update(status="candidates", candidates=parts, vehicle=applications[0], applications=applications,
                                      unconfirmed_fields=unknown, fitment_confirmed=False)
                        reply = "I found a catalog application to review. It covers the displayed configuration only; your unconfirmed details stay unknown. Demo parts use simulated fitment."
                if not parts and not reply:
                    result["status"] = "outside_coverage"
                    reply = "I don't have that position or side loaded for this request. Your details are kept; no substitute has been inferred."
    if q:
        count = state.attempts.get(q["field"], 0)
        if count:
            choices = ", ".join(q["options"])
            offer = " A VIN would help confirm it. If you don't have it, we can keep going with the year and vehicle details." if not state.vin_declined else " We can continue manually."
            reply = ((f"Only {choices} applications are loaded; your {q['field'].replace('_', ' ')} remains unconfirmed." if choices else "That detail remains unconfirmed.")
                     + offer + " Or say 'demo vehicles' to try a sample.")
            # Stop the required-question loop; keep pending context for a later answer.
            result["status"] = "unconfirmed"
            return {"details": details.model_dump(), "reply": reply, "question": None, "lookup": result, "pending": q}
        reply = q["label"]
        result["questions"] = [q]
    return {"details": details.model_dump(), "reply": reply, "question": q, "lookup": result, "pending": q}
