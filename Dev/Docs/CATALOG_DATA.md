# Canonical CSV catalog and generator

The application now reads its catalog through `counterpilot/domain.py` from UTF-8 CSV files in `counterpilot/data/`. The former runtime `counterpilot/catalog.json` is removed. CSV is the editable source; there is no second JSON catalog or workbook import path.

## Generate or validate in one command

From PowerShell:

```powershell
cd C:\Users\chris\Projects\Meta-Hackathon
.\.venv\Scripts\python.exe .\scripts\generate_demo_catalog.py
```

The generator uses only Python's standard library and the project's shared CSV schema/validator. It does not import the web app, read `.env`, contact Meta, or make network calls. No dependencies need to be installed. Neither `openpyxl` nor `xlsxwriter` was available in this environment, so no optional workbook was generated.

The initial output has **6 vehicle configurations, 180 sample part applications (30 per vehicle), 86 aliases and 0 verified applications**. IDs, part numbers and CSV field values are read as strings. The existing runtime converts only vehicle year to an integer.

| File | Ownership and use |
| --- | --- |
| `counterpilot/data/vehicles.csv` | Six fictional scenario profiles, including engine/trim/drivetrain, equipment assumptions and the featured flag. |
| `counterpilot/data/parts.csv` | Sample applications with exactly the requested twelve columns. Every row has brand `CounterPilot Demo`, status `sample`, source `generated_demo`, and simulated-fitment notes. |
| `counterpilot/data/part_aliases.csv` | Shared `alias,part_type` mappings used by offline interpretation and chat lookup. |
| `counterpilot/data/parts_verified.csv` | Manually maintained real records. Same twelve columns plus `source_reference,verification_date`. Initially headers only. |

Existing files are **never overwritten**. Rerunning the command validates the current editable CSVs and creates only missing files. Manual edits remain authoritative. Validation errors are printed, return a nonzero exit code, and prevent new files from being written. Valid runs print vehicle, sample, verified and alias counts plus `Validation errors: 0`.

For a fresh, deterministic sample copy without changing edited source files:

```powershell
.\.venv\Scripts\python.exe .\scripts\generate_demo_catalog.py --output-dir .\artifacts\catalog-preview
```

Use an empty destination. That preview is not consumed by the app. Separate fresh runs with the same profiles produce byte-identical CSVs. Existing edited files are validated and preserved rather than reset. To add an application, edit CSV; do not expect the generator to merge new templates into an existing parts file.

After editing CSV, run the normal generator command to validate, then restart the application with `start.ps1`. The existing catalog layer loads CSV at startup.

## Reused scenarios and assumptions

| vehicle_id | Year / vehicle | Existing configuration |
| --- | --- | --- |
| F150-01 | 2021 Ford F-150 | 3.5L EcoBoost / XLT / 4WD |
| RAV4-01 | 2019 Toyota RAV4 | 2.5L / XLE / AWD; featured homepage example |
| CRV-01 | 2023 Honda CR-V | 1.5T / EX / AWD |
| SIL1500-01 | 2021 Chevrolet Silverado 1500 | 5.3L / LT / 4WD |
| TIGUAN-01 | 2021 Volkswagen Tiguan | 2.0T / SE / FWD |
| SX4-01 | 2007 Suzuki SX4 | 2.0L / trim unknown / AWD; user-requested fictional demo |

The original five scenarios and the appended Suzuki profile are fictional descriptions, not independently verified equipment records. Gasoline is explicitly an unverified demo assumption. Brake and steering equipment start as `unknown`. Disc-brake applications on unknown configurations carry an explicit unverified disc-brake assumption; all applications disclose unverified equipment, mounting and assembly style. Front damper style differs between the pickup and SUV scenarios, and remains an unverified assumption.

The generation rules omit spark plugs/coils for diesel or unknown-fuel profiles, substitute shoes and omit disc applications where a brake position is known to use drums, and never assume a hydraulic steering pump. Conventional starters/alternators are omitted for hybrid/electric profiles. If you change a profile's equipment, also review its existing application rows; the non-overwriting generator does not silently rewrite them to fit new assumptions.

## Part numbering and schema

Sample numbers use a global deterministic sequence starting at 101, formatted as `PREFIX-00101`. Prefixes follow the supplied mapping: FL filters, BR pads/shoes, RT rotors, CL calipers, SP plugs, IC coils, ST starters, AL alternators, SU suspension, SR steering, CO cooling, FP fuel pumps, AX CV axles, HB hubs/bearings, BT belts/tensioners and WP wipers. The sample ID is `DEMO-<part_number>`. Vehicle fitment is joined through `vehicle_id`; numbers contain no vehicle code.

`category` is the broad family, such as `filters` or `brakes`; `part_type` is the specific selector, such as `oil_filter` or `brake_pad`. The existing `/api/search` request field remains named `criteria.category` for compatibility and accepts these specific part types. `/api/catalog` supplies the current selectors and names to the UI. Position is blank, `front` or `rear`; side is blank, `left` or `right`. Blank means not specified by the application, not a fabricated equipment assertion.

The required part columns, in order, are:

```text
part_id,vehicle_id,part_number,brand,category,part_type,name,position,side,fitment_notes,data_status,source
```

The verified file appends `source_reference,verification_date`. Both part files may then append the optional group `price_amount,currency,price_unit` in that order. Original headers remain supported. Keep the exact header order. When importing CSV into Excel, set identifier and part-number columns to **Text** before importing so Excel does not remove leading zeros. Save edits back to UTF-8 CSV. No formulas, OEM numbers, branded demo numbers or fictional interchanges are generated.

### Prices and photos (November 3 polish pass)

The current sample CSV has all three price columns and fictional fixed prices on 180 applications. For example, the featured oil filter is `12.95,USD,each`; pads/shoes use `axle set`, wipers use `pair`, and other parts use `each`. Displayed sample prices are labeled **Demo price**, excluding tax/shipping. They are not supplier quotes, stock or purchase offers.

Price amounts are positive decimal values, at most two decimal places and no more than 999999.99. Currency must be `USD`; units must be `each`, `pair` or `axle set`. Leave all three cells blank when unavailable; partial or invalid pricing is rejected. Verified records do not inherit sample prices. To price your first real part, append the three headers after `verification_date` and enter its actual amount/currency/unit explicitly. A displayed **Listed price** is informational; source-record verification does not imply a current supplier quote. Restart after CSV edits.

The generator adds the fixed table prices only when creating new sample files and never overwrites existing CSVs. Legacy sample files with no price columns load successfully and show **Price unavailable**. This pass applied a one-time addition to the current generated sample file while preserving every original field and the verified file byte-for-byte. Manually maintained prices are not reset on later generator runs.

Part-type photos live locally under `counterpilot/static/parts/` and are attached through the existing catalog loader, not through a second application catalog. See [photo provenance](PART_PHOTOS.md). Retrieved API candidates have additive `price` and `image` metadata; missing prices are null, and old chat snapshots continue to work. Only existing retrieved records can be selected for comparison.

## Add your first real part to the featured vehicle

The featured vehicle is **RAV4-01**, the homepage's 2019 Toyota RAV4 / 2.5L / XLE / AWD example.

1. Obtain an actual manufacturer or licensed application record. Confirm that it supports this exact vehicle configuration and any restrictions. The demo profile itself is not verification evidence.
2. Open `counterpilot/data/parts_verified.csv`. Leave `parts.csv` unchanged. The verified file initially contains only its header.
3. Add one row with the following fields. Replace every placeholder with your actual evidence; do not save placeholders as a verified record.

| Field | What to enter for an actual RAV4 oil-filter application |
| --- | --- |
| part_id | A unique internal ID, for example your own `REAL-0001` identifier. |
| vehicle_id | `RAV4-01` |
| part_number | The exact real part number from your source, kept as text. |
| brand | The actual brand from that source. |
| category | `filters` |
| part_type | `oil_filter` |
| name | The source's actual product name. |
| position | Blank for this filter if the source has no position distinction. |
| side | Blank for this filter if the source has no side distinction. |
| fitment_notes | Exact application scope, restrictions and what you checked; do not claim more than the source supports. |
| data_status | `verified` |
| source | A meaningful source label, such as `manufacturer_catalog`. |
| source_reference | The actual source URL or document/page/catalog reference you checked. |
| verification_date | The actual date you verified it, formatted `YYYY-MM-DD`. |

4. Run the generator command to validate. It must report one verified application and no validation errors, and must preserve the row on another run.
5. Restart the app and search `Oil filter for a 2019 Toyota RAV4`. In chat, also answer `2.5L` when asked. Acknowledge the displayed configuration to inspect the record.
6. For that exact `(vehicle_id, part_type, position, side)` key, the real record replaces the sample result. Other applications remain sample results. The card shows **Verified source record**, the brand, source reference and verification date. Sample cards show **Demo part — simulated fitment**.

If multiple legitimate verified alternatives share that key, all are returned; the loader does not invent a ranking. Missing evidence/date, duplicate IDs, unsupported types, invalid aliases and invalid references are rejected. Validation checks structure and provenance fields; it cannot independently authenticate a manually entered fitment claim.

## Lookup and safety boundaries

Both the main page and chat retrieve from the same CSV-backed catalog. Shared aliases resolve normal part wording. A symptom such as “won't start,” “battery light” or “squealing brakes” asks which part is needed and does not diagnose a failed starter, alternator or brake component. Ambiguous requests naming multiple part types also require clarification.

Meta may extract criteria only. It does not supply candidate numbers, fitment, availability or confidence. Only numbers in retrieved catalog records reach the UI. Record labels and source details remain visible; no confidence percentages are added. Left/right and front/rear questions replace the previous fictional brake-package split, which is not part of the new CSV schema.

The generator does not touch credentials. All verification for this CSV migration was offline: backend tests, deterministic reruns, temporary verified-record tests and browser scenarios with the Meta paths intercepted or bypassed through manual corrections. No live Meta request or real manufacturer lookup was needed for this change.

Verification completed: 58 backend tests passed, including all 150 generated customer-wording searches; nine main-page browser scenarios and seven chat browser scenarios passed. Desktop/mobile rendering was checked, with no horizontal overflow, browser exceptions or external browser asset requests. No verified production rows were added during tests; verified preference was tested in temporary directories only.

## Suzuki SX4 demo addition

`SX4-01` adds a user-requested 2007 Suzuki SX4 / 2.0L / AWD profile with unknown trim and 30 sample applications. Parts use the same generator, `CounterPilot Demo` brand, `sample` status, `generated_demo` source and simulated-fitment disclosures. Existing rows and numbers were preserved; Suzuki samples occupy sequence 00251–00280 (oil filter `FL-00251`, front wipers `WP-00280`). No OEM/verified sources or real fitment claims were added. Restart the server, then try `Oil filter for a 2007 Suzuki SX4 2.0 AWD`, or choose `Demo SX4-01` in chat.
