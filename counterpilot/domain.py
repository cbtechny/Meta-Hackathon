"""Domain models and deterministic catalog matching for CounterPilot.

Architectural Role:
    This module contains the single source of truth for part compatibility.
    Unlike AI-driven search engines that might hallucinate or guess part fitment,
    CounterPilot strictly separates natural language interpretation from catalog matching:
      1. AI or heuristic parsers translate informal customer text into a structured `Criteria` model.
      2. This module deterministically matches those criteria against curated application fixtures.

    If an application detail is unknown (e.g. front vs. rear rotor, or standard vs. heavy-duty brake package),
    this module returns clarification questions rather than guessing or returning an arbitrary part.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The demo supports four mechanical part categories and an explicit 'unsupported' category.
# Unsupported categories indicate the customer asked for something recognizable (e.g., alternator, pads)
# that this specific catalog fixture does not cover.
Category = Literal["oil_filter", "air_filter", "cabin_filter", "brake_rotor", "unsupported"]


class Criteria(BaseModel):
    """Normalized search parameters used to query the parts catalog.

    Why Pydantic with extra='forbid' is used:
        - Prevents accidental hallucinated fields from AI providers or arbitrary query parameters
          from penetrating domain logic.
        - `str_strip_whitespace=True` prevents whitespace discrepancies from failing exact matches.
        - Values default to None to represent 'unknown / not yet stated', which directly drives
          the clarification generation in `search()`.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    year: int | None = Field(default=None, ge=1980, le=2100)
    make: str | None = Field(default=None, max_length=40)
    model: str | None = Field(default=None, max_length=40)
    category: Category | None = None
    position: Literal["front", "rear"] | None = None
    brake_package: Literal["standard", "heavy-duty"] | None = None


def load_catalog(path: Path | None = None) -> dict:
    """Load and validate the local catalog fixtures JSON file.

    Validation Decisions:
        - Ensures vehicle IDs and part IDs are unique.
        - Ensures every part points to an existing vehicle ID (no orphan applications).
        - Verifies that every part record validates against `Criteria` schema requirements.
        - Enforces that catalog parts are marked fictional and carry application evidence,
          preventing mock fixtures from being confused with real-world certified fitment.

    Returns:
        dict: The loaded catalog data structure containing 'vehicles' and 'parts'.
    """
    data = json.loads((path or Path(__file__).with_name("catalog.json")).read_text(encoding="utf-8"))
    vehicles = data["vehicles"]
    ids = [v["id"] for v in vehicles]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate vehicle IDs")
    part_ids = set()
    for part in data["parts"]:
        if part["id"] in part_ids or part["vehicle_id"] not in ids:
            raise ValueError("Duplicate part ID or orphan application")
        part_ids.add(part["id"])
        Criteria(category=part["category"], position=part.get("position"), **part["requires"])
        if part["category"] == "unsupported" or not part["evidence"] or not part["fictional"]:
            raise ValueError("Demo catalog requires supported categories and fictional evidence")
    return data


# Pre-loaded default catalog instance.
CATALOG = load_catalog()


def search(criteria: Criteria, catalog: dict = CATALOG) -> dict:
    """Deterministically match search criteria against catalog applications or formulate clarification questions.

    State Transitions and Flow:
      1. Category check: If category is explicitly 'unsupported', immediately return 'outside_coverage'.
      2. Baseline vehicle & category completeness: If any of year, make, model, or category is None,
         generate clarification questions for the missing fields and return status='needs_clarification'.
      3. Vehicle lookup: Check if the exact (year, make, model) triplet exists in the catalog.
         If not, return status='outside_coverage'.
      4. Position split: For brake rotors, position (front vs. rear) is required. If None,
         ask for position and return 'needs_clarification'.
      5. Option restrictions: If position is known, check option restrictions required by matching parts
         (e.g., 'brake_package' for rear rotors). Only ask option questions relevant to the narrowed parts.
         If any required option is None, ask and return 'needs_clarification'.
      6. Final candidate filter: Return exact matching parts with status='candidates', or 'outside_coverage'
         if no candidate satisfies all criteria.

    Why this design?
      - Staged clarification ensures front rotor requests aren't asked about rear brake package splits.
      - Never returns a guess or substitute; absence of evidence yields 'outside_coverage'.
      - Cross-reference/interchange data is attached to parts for reference, but is deliberately NOT
        consumed by search matching to avoid unverified fitment claims.
    """
    base = {"criteria": criteria.model_dump(), "candidates": [], "questions": [],
            "notice": "Fictional demonstration catalog. Not for purchasing or installation."}

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
             and p["category"] == criteria.category]
    if criteria.category == "brake_rotor" and criteria.position is None:
        clarify("position", "Are the rotors for the front or rear?", ["front", "rear"])
    if criteria.position is not None and criteria.category == "brake_rotor":
        parts = [p for p in parts if p["position"] == criteria.position]
    # Only ask option questions after position is known, so front results are not
    # blocked by restrictions belonging exclusively to rear applications.
    if not base["questions"]:
        for field in sorted({key for p in parts for key in p["requires"]}):
            if getattr(criteria, field) is None:
                clarify(field, "Which brake package is fitted? Check the vehicle equipment record.",
                        sorted({p["requires"][field] for p in parts if field in p["requires"]}))
    if base["questions"]:
        return {**base, "status": "needs_clarification", "message": "A fitment detail is needed before selecting candidates.",
                "vehicle": vehicle}
    matches = [p for p in parts if all(getattr(criteria, k) == value for k, value in p["requires"].items())]
    return {**base, "status": "candidates" if matches else "outside_coverage",
            "vehicle": vehicle, "candidates": matches,
            "message": "Listed in the fictional demo application data; confirm vehicle details."
            if matches else "No application in demo coverage. No substitute has been inferred."}
