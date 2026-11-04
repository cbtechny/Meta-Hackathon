from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from .catalog_io import DATA_DIR, PART_TYPES, read_sources, price_metadata, image_metadata

class Criteria(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    year: int | None = Field(default=None, ge=1980, le=2100)
    make: str | None = Field(default=None, max_length=40)
    model: str | None = Field(default=None, max_length=40)
    # The existing API field remains named category; its selector is a part_type.
    category: str | None = Field(default=None, max_length=60,
                                 json_schema_extra={"enum": [*PART_TYPES, "unsupported", None]})
    position: Literal["front", "rear"] | None = None
    side: Literal["left", "right"] | None = None

    @field_validator("category")
    @classmethod
    def supported_part_type(cls, value):
        if value is not None and value not in PART_TYPES and value != "unsupported":
            raise ValueError("Unknown part type")
        return value


def load_catalog(path: Path | None = None) -> dict:
    vehicles, samples, aliases, verified = read_sources(path or DATA_DIR)
    def key(part):
        return tuple(part[field] for field in ("vehicle_id", "part_type", "position", "side"))
    preferred = {key(part) for part in verified}
    records = [part for part in samples if key(part) not in preferred] + verified
    parts = []
    for raw in records:
        sample = raw["data_status"] == "sample"
        reference = raw.get("source_reference", "")
        parts.append({**raw, "price": price_metadata(raw), "image": image_metadata(raw["part_type"]), "id": raw["part_id"], "position": raw["position"] or None,
                      "side": raw["side"] or None, "fictional": sample, "requires": {}, "interchanges": [],
                      "display_label": "Demo part — simulated fitment" if sample else "Verified source record",
                      "evidence": [{"source": reference or raw["source"], "statement": raw["fitment_notes"]}],
                      "restrictions": ["Confirm the displayed engine, trim and drivetrain before proceeding.",
                                       "Sample record: not for purchasing or installation." if sample else
                                       "Review source restrictions and verification date before use."],
                      "source_reference": reference, "verification_date": raw.get("verification_date", "")})
    return {"vehicles": [{**v, "id": v["vehicle_id"], "year": int(v["year"]),
                           "featured": v["featured"] == "true", "fictional": v["data_status"] == "sample"} for v in vehicles],
            "parts": parts, "aliases": aliases, "sample_count": len(samples), "verified_count": len(verified)}


CATALOG = load_catalog()


def extract_part_type(text: str, catalog: dict = CATALOG) -> str | None:
    """Longest phrase wins; multiple distinct requested parts need clarification."""
    matches = []
    for row in catalog["aliases"]:
        phrase = row["alias"]
        for match in re.finditer(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text, re.I):
            matches.append((match.start(), match.end(), row["part_type"]))
    matches.sort(key=lambda item: item[1] - item[0], reverse=True)
    selected = []
    for match in matches:
        if not any(match[0] >= existing[0] and match[1] <= existing[1] for existing in selected):
            selected.append(match)
    types = {match[2] for match in selected}
    return next(iter(types)) if len(types) == 1 else None


def resolve_part_type(part: str | None, catalog: dict = CATALOG) -> str | None:
    if not part:
        return None
    if part in PART_TYPES:
        return part
    return extract_part_type(part.replace("_", " "), catalog) or "unsupported"


def search(criteria: Criteria, catalog: dict = CATALOG) -> dict:
    base = {"criteria": criteria.model_dump(), "candidates": [], "questions": [],
            "notice": "Sample records have simulated fitment. Verified records include manually maintained source references."}

    def clarify(field: str, label: str, options: list | None = None):
        base["questions"].append({"field": field, "label": label, "options": options or []})

    if criteria.category == "unsupported":
        return {**base, "status": "outside_coverage", "message": "This part category is outside demo coverage."}
    for field, label in [("year", "What model year?"), ("make", "Which make?"),
                         ("model", "Which model?"), ("category", "Which part do you need?")]:
        if getattr(criteria, field) is None:
            clarify(field, label)
    if base["questions"]:
        return {**base, "status": "needs_clarification", "message": "Confirm the missing request details."}
    vehicles = [v for v in catalog["vehicles"] if v["year"] == criteria.year
                and v["make"].casefold() == criteria.make.casefold()
                and v["model"].casefold() == criteria.model.casefold()]
    if not vehicles:
        return {**base, "status": "outside_coverage", "message": "This vehicle configuration is outside demo coverage."}
    vehicle = vehicles[0]
    parts = [p for p in catalog["parts"] if p["vehicle_id"] == vehicle["id"]
             and p["part_type"] == criteria.category]
    positions = sorted({p["position"] for p in parts if p["position"]})
    if positions and criteria.position is None:
        clarify("position", "Which position do you need?", positions)
    if criteria.position is not None and positions:
        parts = [p for p in parts if p["position"] == criteria.position]
    sides = sorted({p["side"] for p in parts if p["side"]})
    if not base["questions"] and sides and criteria.side is None:
        clarify("side", "Do you need the left or right side?", sides)
    if criteria.side is not None and sides:
        parts = [p for p in parts if p["side"] == criteria.side]
    if base["questions"]:
        return {**base, "status": "needs_clarification", "message": "A fitment detail is needed before selecting candidates.",
                "vehicle": vehicle}
    matches = parts
    return {**base, "status": "candidates" if matches else "outside_coverage",
            "vehicle": vehicle, "candidates": matches,
            "message": "Catalog application found. Check each record's status and source; confirm vehicle details."
            if matches else "No application in demo coverage. No substitute has been inferred."}
