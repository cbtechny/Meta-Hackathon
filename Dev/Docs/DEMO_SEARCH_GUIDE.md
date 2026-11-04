# CounterPilot demo search guide

Current CSV-backed catalog: five configurations, 150 sample applications and 86 shared aliases. Generated fitment is simulated and must not be used for purchasing or installation. Verified records, when you add them, are kept separately and show their source and date.

## Run the demo

1. Run `.\start.ps1` and open http://127.0.0.1:8000. Choose **Offline demo parser** for repeatable searches without network calls.
2. Clear the request and details before each example. Paste a request and choose **Find candidates**.
3. Answer position/side questions if needed, acknowledge the exact displayed vehicle configuration, and inspect the result status and source.
4. Chat uses the same CSV-backed lookup. It additionally asks for the engine before displaying a candidate. Real chat interpretation uses Meta; direct panel corrections do not.

## Supported vehicle profiles

| ID | Vehicle | Existing scenario |
| --- | --- | --- |
| F150-01 | 2021 Ford F-150 | 3.5L EcoBoost / XLT / 4WD |
| RAV4-01 | 2019 Toyota RAV4 | 2.5L / XLE / AWD |
| CRV-01 | 2023 Honda CR-V | 1.5T / EX / AWD |
| SIL1500-01 | 2021 Chevrolet Silverado 1500 | 5.3L / LT / 4WD |
| TIGUAN-01 | 2021 Volkswagen Tiguan | 2.0T / SE / FWD |

## Searchable part types

The detailed applications, positions and sides are in [parts.csv](../../counterpilot/data/parts.csv). Equipment-specific applications are unverified demo assumptions, not specifications for these real models.

| Part type | Shared wording examples |
| --- | --- |
| Engine air filter | air cleaner, air filter, air filters |
| Alternator | alternator, alternators |
| Belt tensioner | belt tensioner, serpentine belt tensioner, tensioner |
| Brake caliper | brake caliper, brake calipers, caliper |
| Brake pads | brake pad, brake pads, disc brake pads |
| Brake rotor | brake disc, brake discs, brake disk |
| Cabin air filter | ac filter, cabin air filter, cabin filter |
| Control arm | control arm, control arms, lower control arm |
| CV axle | cv axle, cv axles, cv shaft |
| Fuel pump | fuel pump, fuel pump module |
| Ignition coil | coil pack, coil packs, ignition coil |
| Oil filter | engine oil filter, oil filter, oil filters |
| Radiator | radiator |
| Serpentine belt | accessory belt, drive belt, fan belt |
| Shock absorber | shock, shock absorber, shock absorbers |
| Spark plug | plugs, spark plug, spark plugs |
| Starter motor | starter, starter motor |
| Strut assembly | strut, strut assemblies, strut assembly |
| Thermostat | thermostat |
| Outer tie rod end | outer tie rod, outer tie rod end, tie rod |
| Water pump | coolant pump, water pump |
| Wheel hub / bearing assembly | hub assembly, hub bearing, wheel bearing |
| Wiper blade pair | windshield wipers, wiper, wiper blade |

## Copy-and-paste searches

| Request | Expected sample number |
| --- | --- |
| `Oil filter for a 2021 Ford F-150` | `FL-00101` |
| `Rear Brake pads for a 2021 Ford F-150` | `BR-00108` |
| `Front Left CV axle for a 2021 Ford F-150` | `AX-00124` |
| `Oil filter for a 2019 Toyota RAV4` | `FL-00131` |
| `Rear Brake pads for a 2019 Toyota RAV4` | `BR-00138` |
| `Front Left CV axle for a 2019 Toyota RAV4` | `AX-00154` |
| `Oil filter for a 2023 Honda CR-V` | `FL-00161` |
| `Rear Brake pads for a 2023 Honda CR-V` | `BR-00168` |
| `Front Left CV axle for a 2023 Honda CR-V` | `AX-00184` |
| `Oil filter for a 2021 Chevrolet Silverado 1500` | `FL-00191` |
| `Rear Brake pads for a 2021 Chevrolet Silverado 1500` | `BR-00198` |
| `Front Left CV axle for a 2021 Chevrolet Silverado 1500` | `AX-00214` |
| `Oil filter for a 2021 Volkswagen Tiguan` | `FL-00221` |
| `Rear Brake pads for a 2021 Volkswagen Tiguan` | `BR-00228` |
| `Front Left CV axle for a 2021 Volkswagen Tiguan` | `AX-00244` |

## Questions and limits to demonstrate

| Request | Expected behavior |
| --- | --- |
| `Front caliper for a 2021 Ford F-150` | Asks left or right before selecting an application. |
| `Brake rotors for a 2021 Volkswagen Tiguan` | Asks front or rear. |
| `2019 Toyota RAV4 battery light is on` | Asks which part is needed; does not diagnose an alternator. |
| `2021 Ford F-150 squealing brakes` | Asks which brake part; does not diagnose pads or rotors. |
| `Pads and rotors for a 2019 RAV4` | Asks for one part type rather than silently choosing. |
| `Turbocharger for a 2021 Ford F-150` | Outside demo coverage. |
| `Front pads for a 2018 Toyota Camry` | Recognizes the part but cannot verify the unsupported vehicle. |

## Featured RAV4 chat

1. Send `Oil filter`, then `2019 Toyota RAV4`, then `2.5L`.
2. Acknowledge the configuration and inspect sample `FL-00131`, labeled **Demo part ? simulated fitment**.
3. Send `Actually, the model year is 2018.` The old engine is cleared, and the lookup explains that the vehicle is outside coverage.

For the one-command generator, CSV editing, verified-record preference and first real part, see [Catalog data](CATALOG_DATA.md). Restart the app after CSV edits. Once a verified RAV4 oil-filter row is added, its real number replaces sample `FL-00131` for that exact application key.

The previous fictional brake-package split and vehicle-encoded sample numbers have been retired. No invented interchanges or confidence scores are included.
