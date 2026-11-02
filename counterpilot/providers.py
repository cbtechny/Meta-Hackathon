"""Language interpretation providers for CounterPilot.

Architectural Role:
    This module defines the `LanguageProvider` protocol and its implementations.
    The provider translates messy, unstructured human text into a clean, structured `Criteria` object.
    Crucially:
      - Providers ONLY translate customer statements into search parameters.
      - Providers NEVER access catalog inventory, check stock, or decide fitment.
      - Providers NEVER invent or guess missing information (e.g., if the user didn't mention year,
        the provider leaves year as None so domain logic can trigger an explicit clarification).

Implementations:
    - MockProvider: Fast, bounded offline regex heuristic parser. Works without any network access or keys.
    - MetaProvider: Remote LLM adapter using Meta's Chat Completions API with strict JSON schema validation.
    - Manual mode (in app.py) bypasses providers entirely and builds `Criteria` directly from UI controls.
"""

from __future__ import annotations

import json
import os
import re
from typing import Protocol
from urllib.request import Request, urlopen

from pydantic import ValidationError
from .domain import Criteria


class ProviderError(RuntimeError):
    """Raised when an interpretation provider encounters a configuration, network, or parsing failure.

    This exception is caught by the API layer (`app.py`) and translated to an HTTP 503 Service Unavailable,
    preserving application integrity without crashing the process or silently falling back to a different provider.
    """
    pass


class LanguageProvider(Protocol):
    """Protocol defining the language interpretation interface.

    Any provider (mock, local model, cloud LLM) must implement `interpret(text: str) -> Criteria`.
    This decouples language parsing technology from the catalog lookup engine.
    """
    name: str

    def interpret(self, text: str) -> Criteria:
        """Parse natural language request text into structured vehicle and part criteria."""
        ...


class MockProvider:
    """Offline, deterministic regex-based interpreter.

    Why this exists:
        - Allows the demo, tests, and local workflows to operate with zero network dependencies or API keys.
        - Provides predictable parsing for supported vehicle families and categories.

    Key Non-Obvious Decisions:
        - Bounded vocabulary: Only recognizes supported models and categories. Unknown words trigger 'unsupported'.
        - Ambiguity protection:
            * Multiple years (e.g. "2019 or 2023") yields None, triggering clarification rather than picking one.
            * Explicit contradictions (e.g. "Ford RAV4") clear both make and model so the user must clarify.
            * "Cabin air filter" is disambiguated so it doesn't trigger "air filter" (engine).
        - Conservative by design: Better to ask than guess wrong.
    """
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
    """External LLM adapter connecting to Meta's Chat Completions endpoint.

    Architecture & Privacy Boundaries:
        - Only the customer request text is transmitted over the wire.
        - Catalog inventory, fitment rules, vehicle VINs, and explicit manual overrides are NEVER sent.
        - Requires the `MODEL_API_KEY` environment variable.
        - System prompt forces the model to emit strictly validated JSON matching `Criteria.model_json_schema()`.

    Failure & Safety Handling:
        - Output is rigorously validated against `Criteria.model_validate()`. Malformed JSON, hallucinated
          fields (blocked by extra='forbid'), or invalid types raise a `ProviderError`.
        - Raw upstream responses, HTTP error traces, and user text are kept out of customer-facing error messages
          to prevent token/secret leakage.
    """
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
    """Factory function returning the configured LanguageProvider instance.

    Args:
        name: Provider identifier ('meta' or 'mock'). Any value other than 'meta' defaults to MockProvider.
    """
    return MetaProvider() if name == "meta" else MockProvider()
