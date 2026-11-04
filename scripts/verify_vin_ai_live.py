"""Bounded live verification: five generated labels and one evidence explanation."""
import base64
import io
import json
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from counterpilot.app import app

root = Path(__file__).resolve().parents[1]
output = root / "artifacts" / "vin-ai"
output.mkdir(parents=True, exist_ok=True)
font = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 38)
small = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 20)
vin = "1HGCM82633A004352"
client = TestClient(app)
records = []
for name in ["clear", "rotated", "obscured", "absent", "multiple"]:
    image = Image.new("RGB", (1000, 240), "#f6f5ed")
    draw = ImageDraw.Draw(image)
    draw.text((30, 18), "SYNTHETIC TEST LABEL — NOT A REAL VEHICLE PHOTO", font=small, fill="black")
    draw.text((30, 80), "VIN: " + vin if name != "absent" else "NO VEHICLE IDENTIFIER PRESENT", font=font, fill="black")
    if name == "multiple":
        draw.text((30, 145), "VIN: 1M8GDM9AXKP042788", font=font, fill="black")
    if name == "obscured":
        draw.rectangle((430, 75, 570, 127), fill="black")
    if name == "rotated":
        image = image.rotate(7, expand=True, fillcolor="white")
    # Generated test fixtures only; user uploads are never saved.
    image.save(output / (name + ".png"))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    start = time.perf_counter()
    response = client.post("/api/vin-photo", json={"image": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()})
    elapsed = round(time.perf_counter() - start, 2)
    data = response.json()
    correct = response.status_code == 200 and (data.get("vin") == vin if name in {"clear", "rotated"} else data.get("vin") is None and data.get("status") != "readable")
    record = {"fixture": name, "http_status": response.status_code, "reading_status": data.get("status"), "exact_or_safe": correct, "latency_seconds": elapsed}
    records.append(record)
    print(json.dumps(record), flush=True)

lookup = client.post("/api/chat", json={"edits": {"year": 2019, "make": "Toyota", "model": "RAV4", "part": "oil filter"}}).json()
start = time.perf_counter()
response = client.post("/api/explain", json={"session_id": lookup["session_id"], "revision": lookup["revision"], "part_id": lookup["lookup"]["candidates"][0]["id"]})
result = response.json()
explanation = {"http_status": response.status_code, "mode": result.get("mode"), "latency_seconds": round(time.perf_counter() - start, 2), "sample_disclosed": "simulated" in result.get("disclosure", ""), "focus_fields": [item["field"] for item in result.get("focus", [])]}
print(json.dumps({"explanation": explanation}), flush=True)
(output / "live-results.json").write_text(json.dumps({"synthetic_only": True, "photo_cases": records, "explanation": explanation, "paid_call_limit": 6}, indent=2), encoding="utf-8")
