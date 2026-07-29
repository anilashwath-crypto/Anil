# Farm Monitor

A mobile-first, interactive dashboard for monitoring a smart farm from your phone.
Everything lives in a single `index.html` — no build step, no dependencies — so it
can be opened directly in a browser, hosted on GitHub Pages, or added to a phone
home screen.

## Features

- **Live readings** — soil moisture, air temperature, humidity, and water tank
  level, with 3-hour trend deltas.
- **24-hour history chart** — switch between moisture, temperature, and humidity;
  tap or drag on the chart for a crosshair tooltip at any point in time.
- **Irrigation zones** — per-zone moisture bars and valve toggles. Opening a
  valve raises that zone's moisture over time and draws down the tank.
- **Alerts** — automatic warnings when a zone drops below 30% moisture and a
  critical alert when the tank falls below 20%. Dismissible per alert.
- **5-day forecast** and an **AI insights** feed with irrigation recommendations.
- **Light and dark themes** — follows the phone's system setting.

## Running it

Open `index.html` in any browser, or serve the folder:

```sh
python3 -m http.server 8000
# then visit http://localhost:8000 on your phone (same Wi-Fi network)
```

To publish it at a permanent URL, enable **GitHub Pages** for this repository
(Settings → Pages → deploy from the main branch) and open the page on your
phone, then "Add to Home Screen" for an app-like experience.

## Connecting real sensors

The dashboard currently runs on a simulated sensor feed (see the
`seedSeries`/`tick` functions in `index.html`). To go live, replace those with
`fetch()` calls to your field gateway or IoT platform API that return the same
shapes:

- time series: `[{ t: <epoch ms>, v: <number> }, …]` per metric
- zones: `[{ id, name, crop, moisture, valve }, …]`
- tank level: a number 0–100

Valve toggles call the same code path as the simulation, so wiring them to a
`POST /zones/:id/valve` endpoint is a one-line change in the click handler.
