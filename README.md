# Smart Farm Monitor

Mobile-first control dashboard for the farm described in
*Smart_Farm_AI_System_Design* — a 10-acre mixed farm (6 acres crops/vegetables,
2.5-acre orchard, Gir dairy + Boer goats + Giriraja poultry) in rural
Karnataka. This is the "one dashboard" from Section 1 of the blueprint: water,
power, crops, cattle, tasks and expenses on a single phone screen.

Everything lives in one `index.html` — no build step, no dependencies — so it
can be opened directly in a browser, hosted on GitHub Pages, or added to a
phone home screen.

> **Also in this repo:** [`home/`](home/) — **Home Stock**, a mobile
> household-inventory app for kitchen groceries and toiletries (opening stock,
> packet photos, mfg/expiry dates, ingredient flags, expiry reminders, price
> and invoice tracking, on-device spend/wastage analysis). See
> [`home/README.md`](home/README.md).

## Tabs

**Overview** — system status chips (edge gateway, LoRa sensor count, 4G, SMS
fallback, solar battery); live KPIs (field soil moisture, air temp, wind, soil
pH, today's milk, water tank); 24-hour history chart (moisture / temp /
humidity / wind) with touch crosshair; 5-day forecast with a neemastra spray
window that reacts to live wind; a pest & weed watch card (termite bait
stations, sticky/pheromone trap counts, per-block weed cover from drone NDVI)
with automatic alerts; and AI insight cards.

**Language & theme** — a header selector switches the whole UI between
English, ಕನ್ನಡ, and हिंदी (the blueprint calls for Kannada UI for staff
adoption), and a day/night toggle forces light or dark mode regardless of the
phone setting — useful when the light theme washes out in field sunlight.
Both choices persist across visits.

**Water** — pump & borewell card (GSM starter state, flow, water level, energy,
dry-run protection); six irrigation zones matching the blueprint's valve plan
(tomato, beans & chilli, leafy greens, napier, mango, sapota) with per-zone
moisture triggers and valve toggles; soil-health card per IoT field station
(pH, EC, soil temperature); a **soil-nutrient card** reading the RS-485 NPK
probe on each station's LoRa node (banded meters for nitrogen, phosphorus,
potassium and conductivity, with a plain-language assessment that names only
what is out of range); and a parameter-driven fertigation card. The
venturi diffuser doses automatically: set the dose rate (L/acre), cycle
interval (days), injection rate (L/h) and an EC guard (mS/cm), and it
computes each zone's dose from its acreage (e.g. 1.5 ac × 200 L/acre =
300 L ≈ 7.5 h at 40 L/h), injects while that zone irrigates with live
progress, and pauses itself if soil EC exceeds the guard. Switching
auto-dosing off enables the manual dosing valve instead.

**Livestock** — herd summary (Gir / Boer / Giriraja), collar alerts (standing
heat, rumination drop), 7-day milk bar chart with ₹ value at farm-gate A2
pricing, shed climate with the auto fan/fogger threshold.

**Farm ops** — worker task board with done-check, power card (grid, solar
control battery, pump energy, diesel), the four cameras (gate, pump house,
shed, store) with last events, and a month-to-date P&L per enterprise from
the digital ledger.

Alert logic runs continuously: zone below its moisture trigger, tank below
20%, soil pH outside 6.0–7.5, salt build-up (conductivity above 1200 µS/cm),
wind too high to spray, shed heat stress, and collar heat detection.

### About the NPK reading

Low-cost RS-485 NPK probes **do not measure N, P and K chemically.** They
measure bulk electrical conductivity and derive all three numbers from that one
signal through a fixed factory curve. Moving a single probe between two soils
shifts every channel by the same factor — ×0.429, ×0.433, ×0.442 for N, P, K
against ×0.439 for EC, a spread of 1.4% across four supposedly independent
nutrients. The dashboard simulates them the same way, from one EC signal, rather
than as four independent series that would flatter the hardware.

So: conductivity and soil temperature are directly measured and trustworthy;
N, P and K are indicative, useful for tracking change over time in one block,
and are deliberately not allowed to raise alerts on their own. Before a
fertiliser decision, get a lab test with Olsen-P and ammonium-acetate K. The
card says all of this on screen, and carries a `SIMULATED` badge whenever it is
not reading a real probe, so demo data can never be mistaken for a measurement.

Interpretation bands live in `NPK_BANDS` in `index.html` — they default to
general horticultural guidance and should be tuned per crop, since leafy greens
want more nitrogen and fruiting blocks more potassium.

## Running it

Open `index.html` in any browser, or serve the folder:

```sh
python3 -m http.server 8000
# then visit http://localhost:8000 on your phone (same Wi-Fi network)
```

### Publishing it

The dashboard is a single static file, so **GitHub Pages** serves it as-is —
no build step, no workflow. One-time setup, in this repository:

**Settings → Pages → Build and deployment → Source: _Deploy from a branch_ →
Branch: `claude/farm-monitoring-dashboard-iorey1` / `/ (root)` → Save.**

A minute or so later the dashboard is live for anyone with the link at

> **https://anilashwath-crypto.github.io/Anil/**

Every later push to that branch redeploys automatically. On a phone, open the
URL and "Add to Home Screen" for an app-like experience. The `.nojekyll` file
at the repo root tells Pages to serve the file untouched rather than running it
through Jekyll.

Note that the page is public once Pages is on — it carries no credentials and
talks to nothing, since the feed is simulated, but keep that in mind when the
real gateway URL goes in.

## Connecting the real farm

The dashboard currently runs on a simulated feed (see `seedSeries`/`tick` in
`index.html`). Per the blueprint's architecture, the real data source is the
**edge gateway** (Layer 2): replace the simulation with `fetch()` calls to the
gateway/vendor API returning the same shapes —

- time series per metric: `[{ t: <epoch ms>, v: <number> }, …]`
- zones: `[{ id, name, crop, trigger, moisture, valve }, …]`
- soil stations: `[{ name, ph, ec, stemp }, …]`
- NPK probe: `{ n, p, k, ec }` in mg/kg and µS/cm — the gateway polls the probe
  over Modbus RTU (9600 8N1, slave address 1, function `0x03`, base `0x0000`,
  **quantity 10**) and relays the frame over LoRa. Two traps worth carrying into
  the gateway firmware: values are IEEE-754 32-bit floats spread across register
  *pairs*, not the 16-bit scaled integers most soil sensors use, so an **odd
  register quantity silently reads back as zero** — indistinguishable from a
  probe in dry sand; and a Modbus **exception frame is proof of life**, not
  silence, so never discard one as a failed read. Set `state.npk.demo = false`
  once the feed is real; the `SIMULATED` badge clears itself.
- pump/tank/shed/solar: plain numbers as in the `state` object

Valve, diffuser, and task toggles already route through single code paths in
the click handler, so wiring them to gateway commands (`POST /zones/:id/valve`
etc.) is a small change. The dashboard is deliberately read-mostly: per the
design's offline-first principle, schedules always run locally on the gateway
even when this page can't reach the farm.
