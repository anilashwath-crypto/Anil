# shopkeeper — vendored source

Copied from https://github.com/Piyushmishra29/shopkeeper (MIT licence, see `LICENSE`)
at upstream commit `63261a9ad2a460de90fdf763f554d3658db5bbaa` (2026-09-15) so the
programme can be modified here.

## What is included

| folder | what it is |
|---|---|
| `firmware/` | MicroPython 1.28 firmware for the ESP32-S3 (`main.py`, `server.py`, `servo.py`, `hud.py`, `store.py`, `config.py`, `sh1106.py`), the browser UI served from flash (`www/index.html`), and `mock_server.py` for running the UI on a laptop without the board |
| `cad/` | Parametric Python CAD — `nano.py` is the shipped machine; every dimension is a named entry in its `P` dict |
| `tools/` | Bench harness (`bay2_endurance.py`), render pipeline (`render.py`, `make_assets.py`), STL measurement, OLED test |
| `site/` | Project site source (`src/`) and its build script |
| `docs/` | Build guide, design spec, lineage notes |
| `print_profiles/` | Slicer profiles |

## What was left out (regenerable or binary)

- All meshes and plates: `MODELS/`, `nano/`, `out/`, `out2/`, `mini/` (`.stl`, `.3mf`, `.obj`, `.dxf`) —
  rebuild with `python cad/export_cam.py`
- Rendered images and GIFs under `docs/img/` — rebuild with `python tools/make_assets.py`
- Built site `site/dist/` and the 3D viewer `nano/viewer/` — rebuild with `python site/build.py`
- `__pycache__/`

Fetch any of these directly from the upstream repository if needed.

## Not committed

`firmware/secrets.py` (Wi-Fi / hotspot credentials) is gitignored upstream and here; copy
`firmware/secrets_example.py` to `firmware/secrets.py` and fill it in locally.
