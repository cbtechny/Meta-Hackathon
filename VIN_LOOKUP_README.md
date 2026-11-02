# CounterPilot VIN lookup (free NHTSA vPIC)

This small Python module calls the public NHTSA vPIC VIN decoder. It requires Python 3.10+ and uses only the standard library: no account, API key, or paid service is needed.

## Try it

```powershell
python counterpilot_vin_lookup.py 1HGCM82633A004352
```

If the decoder needs a model-year hint:

```powershell
python counterpilot_vin_lookup.py 1HGCM82633A004352 --year 2003
```

Use it from Python:

```python
from counterpilot_vin_lookup import decode_vin

vehicle = decode_vin("1HGCM82633A004352")
print(vehicle["make"], vehicle["model"], vehicle["engine"])
```

The endpoint is `https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues`. NHTSA documents the API and confirms it is free for public use. It has quotas/rate limits and is not intended for bulk VIN lookups; for a small interactive demo, request one decode when the user submits a VIN and avoid repeatedly polling it.

## Fitment boundary

VIN decode is a vehicle-identity aid, not a parts-fitment authority. Manufacturer-reported fields may be missing or broad, and the result may not identify brake package, production split, or other option-sensitive detail needed by a parts catalog. CounterPilot should retain the decoded fields as a proposed vehicle configuration, show unknowns, and then use deterministic catalog applications and clarification/physical measurement where required.

Treat VINs as sensitive vehicle identifiers: do not log them unnecessarily or commit real customer VINs to Git. The code contains no credentials. The module is integrated into CounterPilot's backend via `POST /api/vin` and exposed in the web interface behind an explicit user confirmation step, remaining separate from language interpretation providers.

Source: [NHTSA vPIC API](https://vpic.nhtsa.dot.gov/api/); [vPIC FAQ](https://vpic.nhtsa.dot.gov/api/Home/Index/FAQ).
