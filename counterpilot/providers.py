from __future__ import annotations

import json
import os
import re
from typing import Protocol
from urllib.request import Request, urlopen

from pydantic import ValidationError
from .domain import Criteria


class ProviderError(RuntimeError):
    pass


class LanguageProvider(Protocol):
    name: str
    def interpret(self, text: str) -> Criteria: ...


class MockProvider:
    name = "mock"

    def interpret(self, text: str) -> Criteria:
        text = text.casefold()
        if not text.strip():
            return Criteria()
        # Deliberately bounded offline parser, not a general language model.
        aliases = [
            (r"\bf[ -]?150\b", "Ford", "F-150"),
            (r"\brav[ -]?4\b", "Toyota", "RAV4"),
            (r"\bcr[ -]?v\b", "Honda", "CR-V"),
            (r"\bsilverado(?:\s+1500)?\b", "Chevrolet", "Silverado 1500"),
            (r"\btiguan\b", "Volkswagen", "Tiguan"),
        ]
        values = {}
        years = set(re.findall(r"\b(?:19|20)\d{2}\b", text))
        if len(years) == 1:
            values["year"] = int(next(iter(years)))
        vehicles = [(make, model) for pattern, make, model in aliases if re.search(pattern, text)]
        if len(vehicles) == 1:
            values["make"], values["model"] = vehicles[0]
        else:
            makes = [make for pattern, make in [
                (r"\bford\b", "Ford"), (r"\btoyota\b", "Toyota"), (r"\bhonda\b", "Honda"),
                (r"\b(?:chevrolet|chevy)\b", "Chevrolet"), (r"\b(?:vw|volkswagen)\b", "Volkswagen")]
                if re.search(pattern, text)]
            if len(makes) == 1:
                values["make"] = makes[0]
        # A make explicitly contradicting a recognized model is a question,
        # never permission to silently replace the customer's vehicle.
        explicit_makes = [make for pattern, make in [
            (r"\bford\b", "Ford"), (r"\btoyota\b", "Toyota"), (r"\bhonda\b", "Honda"),
            (r"\b(?:chevrolet|chevy)\b", "Chevrolet"), (r"\b(?:vw|volkswagen)\b", "Volkswagen")]
            if re.search(pattern, text)]
        if len(vehicles) == 1 and any(make != vehicles[0][0] for make in explicit_makes):
            values.pop("make", None)
            values.pop("model", None)
        categories = [category for pattern, category in [
            (r"\boil\s+filter\b", "oil_filter"),
            (r"\b(?:engine\s+)?air\s+filter\b", "air_filter"),
            (r"\bcabin\s+(?:air\s+)?filter\b", "cabin_filter"),
            (r"\b(?:rotors?|brake\s+dis[ck]s?)\b", "brake_rotor")]
            if re.search(pattern, text)]
        # Cabin air filter should not also mean engine air filter.
        if "cabin_filter" in categories and re.search(r"cabin\s+air\s+filter", text):
            categories = [c for c in categories if c != "air_filter"]
        unsupported = re.search(r"\b(?:pads?|calipers?|alternators?|spark\s+plugs?|belts?|pumps?|wipers?)\b", text)
        if unsupported:
            values["category"] = "unsupported"
        elif len(categories) == 1:
            values["category"] = categories[0]
        elif not categories and not re.search(r"\b(?:filter|brake|part)s?\b", text):
            values["category"] = "unsupported"
        positions = [p for p in ["front", "rear"] if re.search(rf"\b{p}\b", text)]
        if len(positions) == 1:
            values["position"] = positions[0]
        packages = [value for pattern, value in [
            (r"\bstandard\b", "standard"), (r"\bheavy[ -]duty\b", "heavy-duty")]
            if re.search(pattern, text)]
        if len(packages) == 1:
            values["brake_package"] = packages[0]
        return Criteria(**values)


class MetaProvider:
    name = "meta"

    def interpret(self, text: str) -> Criteria:
        key = os.environ.get("MODEL_API_KEY")
        if not key:
            raise ProviderError("Meta is not configured. Use offline or manual mode.")
        payload = {
            "model": os.environ.get("META_MODEL", "muse-spark-1.3"),
            "messages": [
                {"role": "system", "content": (
                    "Extract vehicle and part criteria only. Never infer compatibility, options, or missing fields. "
                    "Return only a JSON object using this schema: " + json.dumps(Criteria.model_json_schema()) +
                    ". Use null for unknowns. Supported models use canonical names F-150, RAV4, CR-V, Silverado 1500, Tiguan. "
                    "Use unsupported for other part categories. For multiple conflicting values return null.")},
                {"role": "user", "content": text}],
            "max_tokens": 800,
        }
        request = Request("https://api.meta.ai/v1/chat/completions",
                          data=json.dumps(payload).encode(),
                          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=25) as response:
                data = json.load(response)
            content = data["choices"][0]["message"]["content"]
            return Criteria.model_validate(json.loads(content))
        except (OSError, ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
            # Do not expose upstream response bodies, keys, or the user's request.
            raise ProviderError("Meta could not return valid criteria. Retry or use offline/manual mode.") from exc


def get_provider(name: str) -> LanguageProvider:
    return MetaProvider() if name == "meta" else MockProvider()
