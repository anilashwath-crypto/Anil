# App structure — Smart Farm dashboard

One self-contained `index.html` — no build step, no dependencies. Three layers: HTML
skeleton → CSS design tokens/components → a single vanilla-JS IIFE holding all logic.
The data feed is simulated and designed to be swapped for the edge-gateway API
(same state shapes; see README "Connecting the real farm").

## 1. HTML skeleton

- `header.topbar` — farm name, day/night toggle `#theme-btn`, language `select#lang`, live clock
- `.statusrow` — gateway / LoRa / 4G / SMS-fallback / solar chips
- Tab sections (shown/hidden by the bottom nav):
  - `#tab-home` — alerts, KPI grid, 24 h chart, 5-day forecast + spray window, pest & weed watch, AI insights
  - `#tab-water` — pump & borewell, 6 irrigation zones, soil field stations, soil-nutrient NPK probe, fertigation + auto-dosing diffuser
  - `#tab-stock` — herd summary, collar alerts, 7-day milk chart, shed climate
  - `#tab-ops` — worker tasks, power, cameras, month P&L ledger
- `nav.bottom` — 4-tab navigation

## 2. CSS

- Design tokens as custom properties on `:root`; dark values declared under **both**
  `@media (prefers-color-scheme: dark)` and `:root[data-theme="dark"]` so the manual
  day/night toggle overrides the OS in either direction.
- Component classes: `.card .kpi .seg .chart-wrap .tooltip .zone .switch .stat .pill
  .chip .badge .param .task .cam .alert .herd .forecast .insights` plus the NPK meter
  set `.npk-grid .npk-m .npk-track .npk-needle .npk-scale .npk-band .npk-verdict
  .npk-caveat .npk-link`.

## 3. JavaScript (single IIFE)

### i18n
| Function | Role |
|---|---|
| `L` | en / kn / hi dictionaries (~130 keys each) |
| `t(key)` | lookup with English fallback |
| `tpl(key, vars)` | fills `{placeholder}` templates (alerts, dosing status) |
| `applyLang()` | stamps every `[data-i18n]` / `[data-i18n-html]` node, sets `<html lang>`, re-renders |

### State
- `state` — single source of truth: `lang`, `metric`, `series{moisture,temp,humidity,wind}`
  (49 points = 24 h at 30 min), `soil[2]` (pH/EC/soil-temp stations),
  `npk` (selected station, `demo` flag, Modbus link params), `diffuser`, `tank`,
  `zones[6]` (acres, trigger, moisture, valve), `fert` (auto, rate L/acre, days, inj L/h,
  ec guard, per-zone progress), `pump`, `solar`, `shed`, `milk[7]`, `eggs`, `animals[4]`,
  `tasks[4]`, `pest` (termite stations/hits, trap counts, weed cover per block), `cams[4]`,
  `dismissed`.
- `METRICS` — per-metric chart config (label key, unit, palette slot, y-domain).
- `NPK_BANDS` — per-channel low/optimal/high bands, meter scale and unit for the soil
  NPK probe; `NPK_ADVICE` maps each out-of-range grade to an i18n key.
- `NPK_RATIO` — the factory curve this probe class actually uses. It does not measure
  N, P and K chemically: all three are fixed multiples of the conductivity reading
  (measured ×0.429–0.442 across four channels, spread 0.014). `npkRead()` derives them
  from the station's EC for exactly that reason, and `npkGrade()` bands the result.

### Simulation engine (replace with gateway API)
| Function | Role |
|---|---|
| `seedSeries()` | backfills 24 h of sensor history on load |
| `tick()` | 4-second loop: sensor drift; open valves raise zone moisture, drain tank, run pump; **auto-dosing engine** — picks the irrigating zone still short of its computed dose (acres × rate), injects at `inj` L/h (30× demo speed), pauses on EC > guard; shed climate; milk creep |
| `push()` `noise()` `clamp()` `last()` | series and math helpers |

### Rendering (idempotent; `render()` is the root)
| Function | Renders |
|---|---|
| `renderKpis()` / `setKpi()` | six KPI tiles + trend deltas |
| `renderChart()` | 24 h SVG line chart (grid, axis, area, endpoint dot) |
| `chartHover()` / `chartLeave()` | crosshair + tooltip (pointer events) |
| `renderAlerts()` | derives the alert list from state each pass: standing heat, zone below trigger, tank low, pH out of range, EC-guard pause, salt build-up (probe EC above band), termite activity, weed pressure, high wind, shed heat stress; per-alert dismiss |
| `renderSpray()` | wind-aware neemastra spray window |
| `renderPest()` | termite bait stations, trap counts, weed-cover bars |
| `renderWater()` | pump card, zone rows + valves, soil stations, diffuser status, dosing progress bar, per-zone dose plan |
| `renderNpk()` | NPK banded meters + needles, per-channel grade chips, out-of-range assessment, accuracy caveat, Modbus link line with `SIMULATED` badge |
| `renderStock()` | herd tiles, collar alert rows, shed climate |
| `renderMilkChart()` + `milkHover()`/`milkLeave()` | 7-day SVG bar chart with ₹ tooltip |
| `renderOps()` | task board, power card, camera tiles |
| `renderForecast()` / `renderInsights()` | language-dependent; called on load and language change |

### Theme (manual day/night)
- `effectiveTheme()` — explicit `data-theme` if set, else OS preference
- `updateThemeBtn()` — sun/moon icon shows the mode you'd switch to
- Click stamps `data-theme` on `<html>` and persists to `localStorage("farm-theme")`;
  a `MutationObserver` on `data-theme` re-renders so SVG charts pick up new token values.

### Events
- One delegated `document` click handler: bottom-nav tabs → segmented groups (chart metric,
  NPK station; pressed state is scoped to the clicked group) →
  switches (`#fert-auto`, `#diffuser-switch` manual valve, zone valves) → task checks →
  alert dismiss.
- `input` on `.fert-param` — clamps and stores dose rate / cycle / injection / EC guard,
  recalculates the dosing plan (inputs are static DOM, so typing survives re-renders).
- `change` on `#lang` — persists to `localStorage("farm-lang")`, calls `applyLang()`.
- Pointer events on both chart SVGs.

## Data flow

```
tick() ──mutates──▶ state ──▶ render() ──▶ DOM/SVG
  ▲                                          │
  └── user actions (valves, params, tabs) ───┘
```

Going live = replacing `seedSeries()`/`tick()` with `fetch()` calls to the edge gateway
returning the same shapes, and pointing valve/diffuser/task toggles at gateway commands
(single code paths in the click handler).
