from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["oil_filter", "air_filter", "cabin_filter", "brake_rotor", "unsupported"]


class Criteria(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    year: int | None = Field(default=None, ge=1980, le=2100)
    make: str | None = Field(default=None, max_length=40)
    model: str | None = Field(default=None, max_length=40)
    category: Category | None = None
    position: Literal["front", "rear"] | None = None
    brake_package: Literal["standard", "heavy-duty"] | None = None


def load_catalog(path: Path | None = None) -> dict:
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


CATALOG = load_catalog()


def search(criteria: Criteria, catalog: dict = CATALOG) -> dict:
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
