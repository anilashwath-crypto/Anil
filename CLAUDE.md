# Project memory — Anil's Smart Farm

## What this repo is

Mobile-first smart-farm monitoring dashboard (single-file `index.html`, vanilla JS/SVG,
no build step) implementing the "one dashboard" from the *Smart_Farm_AI_System_Design*
blueprint: a 10-acre mixed farm in rural Karnataka (6 ac crops, 2.5 ac orchard, Gir
dairy + Boer goats + Giriraja poultry), 100% organic/ZBNF, offline-first edge gateway
with LoRa sensors, GSM/SMS fallback, and solar-backed controls.

- `index.html` — the app (see `ARCHITECTURE.md` for structure and function map)
- `home/index.html` — **Home Stock**, a second single-file app: mobile household
  inventory for kitchen groceries/toiletries (opening stock, packet photos,
  mfg/expiry dates + reminders, ingredient flags, price/invoice tracking,
  on-device insights). Same conventions (trilingual `L` dict, theme tokens,
  no build step); data in IndexedDB on the phone. Docs in `home/README.md`.
  Branch: `claude/household-inventory-tracker-qje7gi`.
- `BOM.md` / `Smart_Farm_DIY_BOM.xlsx` — DIY electronics bill of materials (~₹1.67 lakh + 10%)
- Working branch: `claude/farm-monitoring-dashboard-iorey1`
- Published artifact: https://claude.ai/code/artifact/9d7580d8-d8bd-4c5d-b23d-61c88dc8a27d

## Conventions

- Dashboard is fully trilingual (EN / ಕನ್ನಡ / हिंदी) via the `L` dictionary in `index.html`;
  every new user-facing string needs all three translations.
- Theme tokens: CSS custom properties with dark values under both the OS media query and
  `:root[data-theme]` (manual day/night toggle must win).
- Data layer is simulated (`seedSeries()`/`tick()`); real integration replaces those with
  `fetch()` to the edge gateway, keeping the same state shapes (documented in README).

## Reference links (user asked to memorise)

- **NITI Aayog Frontier Tech Hub — Agriculture sector:**
  https://frontiertech.niti.gov.in/sector/agriculture/
  Government of India catalogue of frontier-tech (AI/IoT/drones/geospatial) applications
  and initiatives in Indian agriculture. Use it when aligning this project with national
  programs, vendor/tech choices, or subsidy/policy references.
  Note (Jul 2026): the site is not reachable from the Claude Code cloud sandbox
  (proxy/host block) — fetch it from a local machine when its content is needed.
