# Generic part photos

Generated November 3, 2026 using the built-in imagegen tool and the imagegen skill, not the CLI or a project API key. These are generated product-style illustrations, not manufacturer photographs or fitment evidence. There are no real product numbers, branding or external image-host dependencies. Each of the 24 registered part types has a local JPEG at `counterpilot/static/parts/<part_type>.jpg`.

The originals were generated separately, one per subject below. All were inspected together as a contact sheet. Local thumbnail encoding preserves the complete image within a 480 x 360 neutral canvas, JPEG quality 84. The 24 thumbnails total 390108 bytes. Original PNGs remain outside the repo; local path mappings are in ignored `artifacts/photo-sources.json`. Encoding helper: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prepare_part_photos.ps1 -Manifest artifacts/photo-sources.json`. Execution policy applies only to that child process.

## Final prompt set

Each subject used this shared prompt: **Use case: product-mockup. One photorealistic studio catalog product photograph of [subject]. Generic and entirely unbranded. Centered three-quarter view, full object visible with generous margin, warm off-white seamless background (#f7f8f4), soft natural shadow, realistic metal and rubber textures, crisp small-thumbnail readability. No text, letters, numbers, labels, logos, packaging, watermark, people or extra tools. Square composition. Illustrative part-type photo, not any actual branded product.**

| Asset stem | Subject |
| --- | --- |
| oil_filter | Plain dark-green metal spin-on oil filter with visible threaded base. |
| air_filter | Rectangular pleated engine air filter with orange rubber surround. |
| cabin_filter | Rectangular white pleated cabin filter with dark thin frame. |
| spark_plug | One metal spark plug with plain white ceramic insulator. |
| ignition_coil | Black pencil ignition coil with connector. |
| brake_pad | Four curved black disc brake pads with friction surfaces visible. |
| brake_shoe | Pair of curved drum brake shoes with brown friction lining. |
| brake_rotor | Silver vented disc brake rotor. |
| brake_caliper | Plain silver brake caliper. |
| starter | Compact starter motor with solenoid. |
| alternator | Silver alternator with black pulley. |
| shock_absorber | Black telescopic shock absorber without coil spring. |
| strut_assembly | Complete black strut assembly with coil spring. |
| control_arm | Black triangular lower control arm with bushings. |
| tie_rod_end | Metal outer tie rod end with ball joint and threaded shaft. |
| radiator | Rectangular aluminum radiator with black side tanks. |
| thermostat | Small metal wax thermostat valve with spring. |
| water_pump | Cast aluminum water pump with visible impeller. |
| fuel_pump | In-tank fuel pump module with white housing. |
| cv_axle | Metal CV axle with two black rubber joint boots. |
| wheel_hub | Silver hub bearing assembly with five wheel studs. |
| serpentine_belt | Looped black multi-rib serpentine belt. |
| belt_tensioner | Metal tensioner arm and black pulley. |
| wiper_blade | Pair of slim black windshield wiper blades. |

Cards and comparison views label all imagery **Illustrative photo**. An unavailable asset renders a neutral text fallback. Image URLs are restricted to the local registered asset path shape; model output never supplies image URLs. Photo style and depicted equipment must not be interpreted as exact fitment, pack contents, brand or stock evidence.
