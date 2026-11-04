"""Resolve cookie bookmarks against current catalog records; no accounts or writes."""
from __future__ import annotations

import json
import re
from urllib.parse import unquote

COOKIE_NAME = 'counterpilot_garage_v1'
MAX_APPLICATIONS = 20
MAX_COOKIE_BYTES = 3800
IDENTIFIER = re.compile(r'^[A-Za-z0-9._-]{1,80}$')


def read_garage(cookie: str | None, catalog: dict) -> dict:
    selections = []
    invalid = False
    if cookie:
        try:
            if len(cookie.encode('utf-8')) > MAX_COOKIE_BYTES:
                raise ValueError('Cookie too large')
            selections = json.loads(unquote(cookie))
            if not isinstance(selections, list) or len(selections) > MAX_APPLICATIONS:
                raise ValueError('Invalid selections')
            if any(not isinstance(item, list) or len(item) != 2 or
                   any(not isinstance(value, str) or not IDENTIFIER.fullmatch(value) for value in item)
                   for item in selections):
                raise ValueError('Invalid IDs')
        except (ValueError, TypeError, UnicodeError, RecursionError):
            selections, invalid = [], True
    vehicles = {v['id']: v for v in catalog['vehicles']}
    parts = {p['id']: p for p in catalog['parts']}
    applications = []
    seen = set()
    for vehicle_id, part_id in selections:
        key = (vehicle_id, part_id)
        if key in seen:
            continue
        seen.add(key)
        vehicle, part = vehicles.get(vehicle_id), parts.get(part_id)
        available = bool(vehicle and part and part['vehicle_id'] == vehicle_id)
        applications.append({'vehicle_id': vehicle_id, 'part_id': part_id, 'available': available,
                             'vehicle': vehicle if available else None, 'part': part if available else None})
    return {'applications': applications, 'invalid_cookie': invalid, 'limit': MAX_APPLICATIONS}
