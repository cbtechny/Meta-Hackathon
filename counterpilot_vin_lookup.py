"""Free VIN decoding through NHTSA's public vPIC API.

This module decodes basic manufacturer-reported vehicle identity. It does not
confirm aftermarket part fitment or every factory option.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues"
VIN_PATTERN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


class VinLookupError(RuntimeError):
    """Raised for invalid input, service failures, or unusable API responses."""


def _clean(value: Any) -> str | None:
    value = str(value or "").strip()
    if not value or value.lower() in {"not applicable", "0", "null"}:
        return None
    return value


def decode_vin(vin: str, model_year: int | None = None, timeout: float = 12.0) -> dict[str, Any]:
    """Decode a 17-character VIN and return a compact, stable field mapping.

    Args:
        vin: Vehicle identification number. It is normalized to uppercase.
        model_year: Optional year hint supported by NHTSA for VIN decoding.
        timeout: HTTP timeout in seconds.
    """
    normalized = re.sub(r"\s+", "", vin).upper()
    if not VIN_PATTERN.fullmatch(normalized):
        raise VinLookupError("Enter a valid 17-character VIN (letters I, O, and Q are not used).")
    if model_year is not None and not 1980 <= int(model_year) <= 2100:
        raise VinLookupError("Model year hint must be between 1980 and 2100.")

    query = {"format": "json"}
    if model_year is not None:
        query["modelyear"] = str(int(model_year))
    request = Request(
        f"{API_ROOT}/{normalized}?{urlencode(query)}",
        headers={"Accept": "application/json", "User-Agent": "CounterPilot/0.1"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise VinLookupError(f"NHTSA vPIC returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise VinLookupError(f"Could not reach or read NHTSA vPIC: {exc}.") from exc

    rows = payload.get("Results") or []
    if not rows:
        raise VinLookupError("NHTSA vPIC returned no decode result for this VIN.")
    row = rows[0]

    def pick(*names: str) -> str | None:
        for name in names:
            value = _clean(row.get(name))
            if value:
                return value
        return None

    summary = {
        "vin": normalized,
        "model_year": pick("ModelYear") or (str(model_year) if model_year else None),
        "make": pick("Make"),
        "model": pick("Model"),
        "trim": pick("Trim", "Series2", "Series"),
        "body_class": pick("BodyClass"),
        "engine": {
            "model": pick("EngineModel"),
            "displacement_l": pick("DisplacementL"),
            "cylinders": pick("EngineCylinders"),
            "fuel": pick("FuelTypePrimary", "FuelTypeSecondary"),
            "configuration": pick("EngineConfiguration"),
        },
        "drivetrain": pick("DriveType"),
        "transmission": pick("TransmissionStyle"),
        "manufacturer": pick("Manufacturer"),
        "plant_country": pick("PlantCountry"),
        "api_error_code": pick("ErrorCode"),
        "source": "NHTSA vPIC",
        "fitment_note": (
            "Use this as a vehicle identity starting point. Verify catalog fitment and option-sensitive parts separately."
        ),
    }
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Free VIN decode using NHTSA vPIC")
    parser.add_argument("vin", help="17-character VIN")
    parser.add_argument("--year", type=int, help="Optional model-year hint")
    args = parser.parse_args()
    try:
        print(json.dumps(decode_vin(args.vin, args.year), indent=2))
    except VinLookupError as exc:
        parser.error(str(exc))
