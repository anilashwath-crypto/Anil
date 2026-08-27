# Smart Farm Monitor

Mobile-first control dashboard for the farm described in
*Smart_Farm_AI_System_Design* — a 10-acre mixed farm (6 acres crops/vegetables,
2.5-acre orchard, Gir dairy + Boer goats + Giriraja poultry) in rural
Karnataka. This is the "one dashboard" from Section 1 of the blueprint: water,
power, crops, cattle, tasks and expenses on a single phone screen.

Everything lives in one `index.html` — no build step, no dependencies — so it
can be opened directly in a browser, hosted on GitHub Pages, or added to a
phone home screen.

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
(pH, EC, soil temperature); and a parameter-driven fertigation card. The
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
20%, soil pH outside 6.0–7.5, wind too high to spray, shed heat stress, and
collar heat detection.

## Running it

Open `index.html` in any browser, or serve the folder:

```sh
python3 -m http.server 8000
# then visit http://localhost:8000 on your phone (same Wi-Fi network)
```

To publish it at a permanent URL, enable **GitHub Pages** for this repository
(Settings → Pages → deploy from the branch) and open the page on your phone,
then "Add to Home Screen" for an app-like experience.

## Connecting the real farm

The dashboard currently runs on a simulated feed (see `seedSeries`/`tick` in
`index.html`). Per the blueprint's architecture, the real data source is the
**edge gateway** (Layer 2): replace the simulation with `fetch()` calls to the
gateway/vendor API returning the same shapes —

- time series per metric: `[{ t: <epoch ms>, v: <number> }, …]`
- zones: `[{ id, name, crop, trigger, moisture, valve }, …]`
- soil stations: `[{ name, ph, ec, stemp }, …]`
- pump/tank/shed/solar: plain numbers as in the `state` object

Valve, diffuser, and task toggles already route through single code paths in
the click handler, so wiring them to gateway commands (`POST /zones/:id/valve`
etc.) is a small change. The dashboard is deliberately read-mostly: per the
design's offline-first principle, schedules always run locally on the gateway
even when this page can't reach the farm.

## Related: `npk-live/`

`npk-live/` holds the mobile dashboard for the FST100-2006E1111 soil NPK probe —
a self-contained `npk-live.html` that polls the probe's own `server.py`, plus the
server patch (`server.py.diff`) that adds a `/live` route, a CORS header and an
`NPK_BIND` env var for LAN access. That is a separate project from the farm
dashboard above; see `npk-live/README.md` for how to run and install it.
