"""Small, bounded localhost conversation store and deterministic state transitions."""
from __future__ import annotations

import json
import hashlib
import re
import threading
import time
import uuid
from dataclasses import dataclass, field

from fastapi import HTTPException
from .chat import ChatDetails, ChatMessage, ChatRequest, Conversation, PartRequest, application_facts, detail_progress, engine_matches, lookup_reply, merge_details, question, stated_engine_displacement
from .domain import CATALOG, extract_part_type, resolve_part_type
from .providers import MetaProvider, ProviderError
from counterpilot_vin_lookup import VIN_PATTERN, VinLookupError


@dataclass
class Session:
    state: Conversation = field(default_factory=Conversation)
    lock: threading.RLock = field(default_factory=threading.RLock)
    touched: float = field(default_factory=time.monotonic)
    last_request_id: str | None = None
    last_result: dict | None = None
    last_request_hash: str | None = None
    explanations: dict = field(default_factory=dict)


SESSIONS: dict[str, Session] = {}
STORE_LOCK = threading.RLock()


def respond(request: ChatRequest, decode_vin):
    with STORE_LOCK:
        for key in list(SESSIONS):
            if time.monotonic() - SESSIONS[key].touched > (7200 if SESSIONS[key].state.revision else 60):
                del SESSIONS[key]
        if request.session_id:
            session = SESSIONS.get(request.session_id)
            if session is None:
                raise HTTPException(409, "This chat expired or the server restarted. Start a new conversation.")
            session_id = request.session_id
        else:
            # The client's unique turn ID also finds an initial request whose
            # response was lost, before the browser learned its session ID.
            session_id = request.request_id or uuid.uuid4().hex
            session = SESSIONS.get(session_id)
            if session is None:
                if len(SESSIONS) >= 256:
                    raise HTTPException(503, "Chat is busy. Retry shortly.")
                session = Session(state=Conversation(details=request.details, parts=request.parts, active_part=min(request.active_part, max(0, len(request.parts) - 1))))
                SESSIONS[session_id] = session
    with session.lock:
        fingerprint = hashlib.sha256(request.model_dump_json(exclude={"context"}).encode()).hexdigest()
        if request.request_id and request.request_id == session.last_request_id and session.last_result:
            if fingerprint != session.last_request_hash:
                raise HTTPException(409, "This request changed. Send it as a new message.")
            session.touched = time.monotonic()
            return session.last_result
        if not request.session_id and session.state.revision:
            raise HTTPException(409, "This request is no longer current. Continue in a new session.")
        if request.session_id and request.revision != session.state.revision:
            raise HTTPException(409, "The conversation changed. Reload before sending another message.")
        # Commit only after a successful turn; provider failures cannot destroy facts.
        state = session.state.model_copy(deep=True)
        revision = state.revision
        result = advance(state, request, decode_vin)
        progress = detail_progress(state)
        result["lookup"]["detail_progress"] = progress
        if result["lookup"]["candidates"] and not result.get("question") and not result.get("pending"):
            # A preview remains visible while optional details are clarified.
            for field, label in (("engine", "What engine does your vehicle have?"),
                                 ("trim", "Which trim does your vehicle have?"),
                                 ("drivetrain", "What drivetrain does your vehicle have?")):
                if (field in progress["unconfirmed_fields"] and field not in state.skipped_preview_fields
                        and any(v.get(field) not in (None, "", "unknown")
                                for v in result["lookup"].get("applications", []))):
                    follow_up = {**question(field, label), "optional": True}
                    result.update(question=follow_up, pending=follow_up)
                    result["lookup"]["questions"] = [follow_up]
                    break
        state.revision = revision + 1
        state.pending = result.pop("pending", result.get("question"))
        state.candidate_ids = [p["id"] for p in result["lookup"]["candidates"]]
        state.history.extend([ChatMessage(role="user", content=request.message or "Customer edited lookup details."),
                              ChatMessage(role="assistant", content=result["reply"])])
        state.history = state.history[-16:]
        session.explanations.clear()
        session.state, session.touched = state, time.monotonic()
        with STORE_LOCK:
            SESSIONS[session_id] = session
        response = {**result, "session_id": session_id, "revision": state.revision,
                "parts": [item.model_dump() for item in state.parts], "active_part": state.active_part,
                "state": {"sources": state.sources, "decoded": state.decoded.model_dump() if state.decoded else None,
                          "vin": state.vin, "confirmed": state.confirmed, "overrides": state.overrides,
                          "vin_declined": state.vin_declined, "pending": state.pending,
                          "attempts": state.attempts, "candidate_ids": state.candidate_ids}}
        session.last_request_id, session.last_result = request.request_id, response
        session.last_request_hash = fingerprint
        return response


def message_result(state, text, q=None):
    return {"details": state.details.model_dump(), "reply": text, "question": q, "pending": q,
            "lookup": {"status": "needs_clarification" if q else "unconfirmed", "candidates": [], "questions": [q] if q else []}}


def apply_update(state, update, source="customer"):
    old = state.details
    delta = update.model_dump(exclude_unset=True)
    changed_vehicle = any(f in delta and delta[f] != getattr(old, f) for f in ("year", "make", "model"))
    if changed_vehicle:
        # A manually changed identity must never retain the previous vehicle's VIN.
        state.vin = None
        state.decoded = None
        state.overrides = {}
        state.vin_declined = False
        state.skipped_preview_fields.clear()
        state.item_attempts.clear()
    new = merge_details(old, update)
    if new != old:
        if any(getattr(old, f) != getattr(new, f) for f in ("year", "make", "model", "engine", "trim", "drivetrain", "hybrid")):
            state.confirmed = False
        state.candidate_ids = []
        state.attempts = {}
    for f in ChatDetails.model_fields:
        if getattr(new, f) != getattr(old, f):
            if getattr(new, f) is None:
                state.sources.pop(f, None)
            else:
                state.sources[f] = source
                state.skipped_preview_fields.discard(f)
                if source in {"customer", "customer override"} and getattr(old, f) is not None:
                    state.overrides[f] = getattr(new, f)
                if state.decoded and getattr(state.decoded, f) != getattr(new, f):
                    state.overrides[f] = getattr(new, f)
    state.details = new
    if state.parts:
        state.parts[state.active_part] = PartRequest(part=new.part or state.parts[state.active_part].part,
                                                    position=new.position, side=new.side)
        if changed_vehicle:
            state.parts = [item.model_copy(update={"position": None, "side": None}) for item in state.parts]


def update_requested_parts(state, requested, action):
    incoming = [item if isinstance(item, PartRequest) else PartRequest(**item) for item in requested]
    existing = state.parts or ([PartRequest(part=state.details.part, position=state.details.position,
                                         side=state.details.side)] if state.details.part else [])
    combined = existing + incoming if action == "append" else incoming
    unique = {}
    for item in combined:
        kind = resolve_part_type(item.part)
        key = (kind if kind != "unsupported" else item.part.casefold(), item.position, item.side)
        unique.setdefault(key, item)
    if len(unique) > 20:
        raise HTTPException(422, "Keep a request to 20 separate items or fewer.")
    state.parts = list(unique.values())
    state.active_part = len(existing) if action == "append" and len(state.parts) > len(existing) else 0
    active = state.parts[state.active_part]
    state.details = ChatDetails(**{**state.details.model_dump(), **active.model_dump(), "symptoms": None})
    state.pending, state.proposed, state.attempts, state.item_attempts = None, None, {}, {}


def explicitly_stated(text, field, value):
    """Recognize repeated facts without treating catalog defaults as confirmations."""
    if value in (None, "") or re.search(r"\b(?:not|no|unknown|unsure)\b|don't|do not", text, re.I):
        return False
    words = str(value)
    if field == "engine":
        if re.match(r"\d", words):
            return stated_engine_displacement(text, words)
    if field == "drivetrain":
        aliases = {"AWD": "all[- ]wheel[- ]drive", "4WD": "(?:four|4)[- ]wheel[- ]drive",
                   "FWD": "front[- ]wheel[- ]drive", "RWD": "rear[- ]wheel[- ]drive"}
        words = re.escape(words) + "|" + aliases.get(words.upper(), re.escape(words))
    else:
        words = re.escape(words)
    return bool(re.search(r"(?<!\w)(?:" + words + r")(?!\w)", text, re.I))


def advance(state, request, decode_vin):
    text = request.message.strip()
    lower = text.casefold().replace('’', "'")
    edit_item = re.fullmatch(r"edit item (\d{1,2})", lower)
    if edit_item and state.parts:
        index = int(edit_item[1]) - 1
        if not 0 <= index < len(state.parts):
            return message_result(state, "Choose an item from the current requested-parts list.", state.pending)
        state.item_attempts[state.active_part] = dict(state.attempts)
        state.attempts = dict(state.item_attempts.get(index, {}))
        state.active_part = index
        state.details = ChatDetails(**{**state.details.model_dump(), **state.parts[index].model_dump()})
        result = lookup_reply(state.details, state)
        state.active_part = index
        state.details = ChatDetails(**{**state.details.model_dump(), **state.parts[index].model_dump()})
        q = {**question("part", f"What would you like to change for item {index + 1} ({state.parts[index].part})?"), "item_index": index}
        result.update(details=state.details.model_dump(), reply=f"Editing item {index + 1}: {state.parts[index].part}.", question=q, pending=q)
        result["lookup"].update(questions=[q], active_item=index)
        return result
    if re.fullmatch(r"(?:start over|reset|new conversation)[.!]?", lower):
        clean = Conversation()
        for f in Conversation.model_fields:
            setattr(state, f, getattr(clean, f))
        return message_result(state, "What part do you need?", question("part", "What part do you need?"))
    if re.fullmatch(r"(?:change|switch)(?: the)? vehicle[.!]?", lower):
        part = state.details.part
        clean = Conversation(details=ChatDetails(part=part),
                             parts=[item.model_copy(update={"position": None, "side": None}) for item in state.parts],
                             active_part=state.active_part)
        for f in Conversation.model_fields:
            setattr(state, f, getattr(clean, f))
        return lookup_reply(state.details, state)
    if lower in {"demo vehicles", "show demo vehicles"}:
        choices = [f"Demo {v['id']}" for v in CATALOG["vehicles"]]
        return message_result(state, "Choose a fictional demo profile, or keep describing your own vehicle.", question("demo", "Choose a demo profile", choices))
    demo = re.fullmatch(r"demo\s+([\w-]+)", text, re.I)
    if demo:
        profile = next((v for v in CATALOG["vehicles"] if v["id"].casefold() == demo[1].casefold()), None)
        if profile:
            fuel = profile.get("fuel_type", "").casefold()
            selection = ChatDetails(year=profile["year"], make=profile["make"], model=profile["model"],
                                    engine=profile["engine"], trim=None if profile["trim"] == "unknown" else profile["trim"],
                                    drivetrain=None if profile["drivetrain"] == "unknown" else profile["drivetrain"],
                                    hybrid=True if "hybrid" in fuel else False if fuel in {"gasoline", "diesel"} else None)
            apply_update(state, selection, "demo profile")
            state.vin, state.decoded = None, None
            state.pending, state.proposed, state.confirmed = None, None, False
            state.overrides, state.attempts = {}, {}
            state.sources.update({f: "demo profile" for f in selection.model_fields_set if getattr(selection, f) is not None})
            return lookup_reply(state.details, state)
        return message_result(state, "That demo profile isn't loaded. Say 'demo vehicles' to see the choices.")
    if re.search(r"(?:don't have|do not have|no|without|haven't got).{0,18}\bvin\b", lower):
        state.vin_declined = True
        result = lookup_reply(state.details, state)
        result["reply"] = "No problem—we can continue manually. " + result["reply"]
        return result
    yes = lower.rstrip('.!') in {"yes", "y", "correct", "use it", "use the correction", "that's right", "confirmed"}
    no = lower.rstrip('.!') in {"no", "n", "incorrect"}
    if state.pending and state.pending["field"] in {"override_confirmation", "vin_confirmation"}:
        if yes:
            proposed = state.proposed
            if proposed:
                adopting_decode = state.decoded is not None and proposed == state.decoded
                # Keep decoded source values when accepting a conflicting override.
                decoded, vin = state.decoded, state.vin
                apply_update(state, proposed, "VIN decoded" if adopting_decode else "customer override")
                state.decoded = decoded
                if proposed.model_fields_set & {"year", "make", "model"} and not adopting_decode:
                    state.vin = None
                else:
                    state.vin = vin
                if not adopting_decode:
                    state.overrides.update(proposed.model_dump(exclude_unset=True))
            state.confirmed, state.pending, state.proposed = True, None, None
            if state.proposed_parts:
                update_requested_parts(state, state.proposed_parts, state.proposed_parts_action)
                state.proposed_parts = None
            for field, source in list(state.sources.items()):
                if source == "VIN decoded":
                    state.sources[field] = "VIN confirmed"
            return lookup_reply(state.details, state)
        if no:
            if state.pending["field"] == "vin_confirmation":
                state.decoded, state.vin = None, None
            state.pending, state.proposed = None, None
            if state.proposed_parts:
                update_requested_parts(state, state.proposed_parts, state.proposed_parts_action)
                state.proposed_parts = None
            return lookup_reply(state.details, state)
    elif yes or no:
        return message_result(state, "What would you like to confirm or change?", state.pending)
    token = re.search(r"\b[A-Z0-9]{17}\b", text.upper())
    vin = token[0] if token and re.search(r"\d", token[0]) else None
    vin_requested = bool(re.search(r"\bvin\b", lower) or (state.pending and state.pending["field"] == "vin"))
    if not vin:
        tail = re.split(r"\bvin\b", text, flags=re.I)[-1] if vin_requested else text
        tail = re.sub(r"^[\s:=]*(?:is[\s:=]+)?", "", tail, flags=re.I)
        compact = re.sub(r"[\s-]", "", tail).strip(".,:; ").upper()
        looks_like_vin = vin_requested or (VIN_PATTERN.fullmatch(compact) and re.search(r"[A-Z0-9]{6}", tail.upper()))
        if looks_like_vin and re.fullmatch(r"[A-Z0-9]{17}", compact) and re.search(r"\d", compact):
            vin = compact
    if vin or vin_requested:
        if not vin:
            return message_result(state, "Send the 17-character VIN, or we can continue manually.", question("vin", "What is the VIN?"))
        if not VIN_PATTERN.fullmatch(vin):
            return message_result(state, "A VIN has 17 letters and numbers and does not use I, O or Q. Check it and try again; your details are kept.", question("vin", "What is the corrected VIN?"))
        try:
            raw = decode_vin(vin)
            if raw.get("api_error_code") not in (None, "0"):
                raise VinLookupError("Decode incomplete")
            engine = (raw.get("engine") or {}).get("displacement_l")
            decoded = ChatDetails(year=int(raw["model_year"]) if raw.get("model_year") else None,
                                  make=raw.get("make"), model=raw.get("model"), engine=engine,
                                  trim=raw.get("trim"), drivetrain=raw.get("drivetrain"))
            if not any((decoded.year, decoded.make, decoded.model)):
                raise VinLookupError("Decode has no vehicle identity")
        except (VinLookupError, ValueError, TypeError, KeyError, AttributeError):
            return message_result(state, "VIN decoding is unavailable or incomplete. Your details are kept. Retry the VIN, or continue with the year, make and model.", state.pending if state.pending and state.pending["field"] != "vin" else question("year", "What year is the vehicle?"))
        state.decoded, state.vin, state.confirmed = decoded, vin, False
        state.proposed = None
        delta = decoded.model_dump(exclude_none=True)
        conflicts = {f: v for f, v in delta.items() if getattr(state.details, f) is not None and str(getattr(state.details, f)).casefold() != str(v).casefold()}
        # Decoded nulls remain unknown; no demo fallback, no inferred displacement.
        if conflicts:
            state.proposed = ChatDetails(**delta)
            q = question("override_confirmation", "The VIN details differ from what you gave me. Use the decoded details?", ["Yes", "No"])
        else:
            # Display the proposal in chat; apply only after customer acceptance.
            state.proposed = ChatDetails(**delta)
            for field in delta:
                if state.sources.get(field) == "VIN confirmed":
                    state.sources[field] = "VIN decoded"
            state.decoded, state.vin = decoded, vin
            q = question("vin_confirmation", "Are these decoded details correct?", ["Yes", "No"])
        summary = ", ".join(f"{f}: {v if v is not None else 'unknown'}" for f, v in decoded.model_dump().items() if f in {"year", "make", "model", "engine", "trim", "drivetrain"})
        return message_result(state, f"NHTSA decoded {summary}. VIN identity does not establish part fitment. {q['label']}", q)
    # Every ordinary language turn really calls Meta. No successful-looking fallback.
    request = request.model_copy(update={"details": state.details, "history": state.history or request.history,
        "context": json.dumps({"pending": state.pending, "vin_declined": state.vin_declined,
                               "requested_parts": [item.model_dump() for item in state.parts], "active_item": state.active_part,
                               "sources": state.sources, "decoded": state.decoded.model_dump() if state.decoded else None,
                               "applications": [{f: v.get(f) for f in ("year", "make", "model", "engine", "trim", "drivetrain")} for v in application_facts(state.details)]})})
    update = request.edits if request.edits is not None else MetaProvider().interpret_conversation(request)
    delta = update.model_dump(exclude_unset=True)
    requested_parts = delta.pop("parts", None)
    parts_action = delta.pop("parts_action", "replace")
    item_index = delta.pop("item_index", None)
    if item_index is not None:
        if not 0 <= item_index < len(state.parts):
            raise ProviderError("The requested item could not be identified. Select an item and try again.")
        state.item_attempts[state.active_part] = dict(state.attempts)
        state.attempts = dict(state.item_attempts.get(item_index, {}))
        state.active_part = item_index
        state.details = ChatDetails(**{**state.details.model_dump(), **state.parts[item_index].model_dump()})
    if requested_parts:
        # Item-specific qualifiers must never leak through the shared vehicle patch.
        for field in ("part", "position", "side", "symptoms"):
            delta.pop(field, None)
    if re.search(r"clicking|squealing|rattling|shaking|vibrat|won't start|overheat", lower) and not extract_part_type(lower):
        delta.pop("part", None)
        delta["symptoms"] = text[:300]
    pending_field = state.pending["field"] if state.pending else None
    unsure = re.search(r"don't know|do not know|not sure|no idea|unsure|skip|unknown", lower)
    unresolved_field = None
    unresolved_attempts = 0
    if unsure:
        field = "engine" if "engine" in lower else pending_field
        if field:
            state.attempts[field] = state.attempts.get(field, 0) + 1
            unresolved_field, unresolved_attempts = field, state.attempts[field]
            if state.pending and state.pending.get("optional"):
                state.skipped_preview_fields.add(field)
    # Defend generic requests against accidental model over-specification.
    if not requested_parts and re.search(r"\bfilters?\b", lower) and not re.search(r"\b(oil|air|cabin|fuel|ac|pollen)\b", lower):
        delta["part"] = "filter"
    if not requested_parts and re.search(r"\bbrakes?\b", lower) and not re.search(r"\b(pads?|rotors?|discs?|disks?|calipers?|shoes?)\b", lower):
        delta["part"] = "brakes"
    if pending_field == "part" and state.details.part and "filter" in state.details.part.casefold():
        short = {"oil": "oil filter", "engine air": "engine air filter", "cabin air": "cabin air filter"}
        if lower.rstrip('.!') in short:
            delta["part"] = short[lower.rstrip('.!')]
    # Canonical known model aliases are metadata-derived, not demo profile substitution.
    if delta.get("model"):
        norm = lambda x: re.sub(r"[^a-z0-9]", "", x.casefold())
        matches = {(v["make"], v["model"]) for v in CATALOG["vehicles"] if norm(v["model"]) == norm(delta["model"])}
        if len(matches) == 1:
            make, model = next(iter(matches))
            if delta.get("make") and delta["make"].casefold() != make.casefold():
                return message_result(state, f"{model} is listed under {make}. Which make and model should I use?", question("model", "Which make and model?"))
            delta.update(make=make, model=model)
    # Null patches never erase known values unless explicitly edited or cleared.
    if request.edits is None:
        delta = {f: v for f, v in delta.items() if v is not None
                 or (unsure and f == unresolved_field)
                 or re.search(r"\b(clear|remove|forget)\b", lower)}
        # Catalog context must not become customer-provided equipment.
        for field in ("trim", "drivetrain"):
            if delta.get(field) is not None and not explicitly_stated(text, field, delta[field]):
                delta.pop(field)
    update = ChatDetails(**delta)
    if state.decoded and state.vin:
        conflicts = {f: v for f, v in delta.items() if v is not None and getattr(state.decoded, f) is not None
                     and v != getattr(state.details, f) and
                     not (f == "engine" and engine_matches(v, getattr(state.decoded, f)))
                     and str(v).casefold() != str(getattr(state.decoded, f)).casefold()}
        if conflicts:
            state.proposed = update
            state.proposed_parts = [PartRequest(**item) for item in requested_parts] if requested_parts else None
            state.proposed_parts_action = parts_action
            q = question("override_confirmation", "That differs from the VIN decode. Use your correction instead?", ["Yes", "No"])
            return message_result(state, q["label"], q)
    before = state.details.model_copy()
    apply_update(state, update)
    if requested_parts:
        update_requested_parts(state, requested_parts, parts_action)
    for field in ("year", "make", "model", "engine", "trim", "drivetrain"):
        value = getattr(state.details, field)
        if ((request.edits is not None and field in request.edits.model_fields_set and value is not None)
                or explicitly_stated(text, field, value)):
            state.sources[field] = "customer override" if state.sources.get(field) == "customer override" else "customer"
            state.skipped_preview_fields.discard(field)
    if unresolved_field and getattr(state.details, unresolved_field, None) is None:
        state.attempts[unresolved_field] = unresolved_attempts
    if state.details != before:
        state.pending = None
        state.proposed = None
    elif pending_field and not unsure:
        state.attempts[pending_field] = state.attempts.get(pending_field, 0) + 1
    result = lookup_reply(state.details, state)
    if unsure and unresolved_field == "engine" and state.details.engine is None and state.attempts.get("engine") == 1 and not state.vin_declined and not result["question"]:
        result["reply"] = "A VIN would help confirm it. If you don't have it, we can keep going manually. " + result["reply"]
    return result
