# FOD Guard — CCTV Foreign-Object & Orientation Check

Single-file, no-build web app (`fod/index.html`) that turns a simple CCTV camera into a
pre-cycle inspection gate for a machine (press / CNC / forging cell):

1. **Master setup** — for each job, capture a master image of the correctly loaded part
   and drag a box to mark the inspection zone (die / fixture area).
2. **Cycle check** — each time the job is reloaded, press **RUN CYCLE CHECK** (or Space,
   or enable auto mode). The app grabs a frame and, inside the zone:
   - **Orientation** — the live frame is aligned to the master by searching small
     rotations (±12°), the cardinal rotations (90/180/270°) and small shifts, scoring
     each with normalized cross-correlation. Wrong-way-round parts report
     "Misoriented ~N°"; a low score everywhere reports "Job missing / wrong job".
   - **Foreign objects** — after alignment and illumination normalization, the frame is
     differenced against the master; connected regions bigger than the configured
     minimum size are flagged and boxed in red on the snapshot.
3. **Door lock switch** — only when orientation matches **and** no foreign object is
   found does the app fire the *Lock URL* (any HTTP relay: Shelly, Tasmota/Sonoff, or an
   ESP8266/ESP32 sketch) so the door solenoid locks and the cycle is enabled. On any
   fault it fires the *Unlock / inhibit URL*, shows a red banner and beeps. With no URLs
   configured, the on-screen lock indicator alone shows the verdict.

Every check is logged (timestamp, job, verdict, score, FO count, annotated thumbnail);
jobs, settings and history persist in `localStorage` and can be exported/imported as JSON.
Trilingual (EN / ಕನ್ನಡ / हिंदी), light/dark theme, mobile-first — same conventions as the
rest of this repo.

## Field manual

`fod/GUIDE.html` is the full commissioning reference: how the detection works in depth,
hardware + wiring diagrams, software/hosting rules, relay endpoints (Shelly / ESP32
sketch), first-job walkthrough with an acceptance sequence, threshold tuning, central
multi-machine setup (incl. a CORS snapshot proxy), troubleshooting, and safety
boundaries. Open it at `http://localhost:8000/fod/GUIDE.html`.

## Bill of materials

Per-machine hardware (~Rs.22,300 incl. 10% contingency; ~Rs.10,000 incremental with
swaps) is listed in `fod/BOM.md` / `fod/FOD_Guard_BOM.xlsx`.

## Interactive explainer

`fod/explainer.html` is a self-contained walkthrough of how the system decides — a simulated
machine cell running the **same detection algorithm** as the app, with scenario buttons
(correct load, rotated 15°, flipped 180°, nut left behind, no part) and live visuals of each
stage: master + zone, pose search, aligned difference map, and the lock decision. Run it locally:

```sh
cd Anil && python3 -m http.server 8000
# then open http://localhost:8000/fod/explainer.html  (app: /fod/index.html)
```

## Camera options

| Setup | How |
|---|---|
| Analogue/HDMI CCTV | USB capture dongle into the device running the browser → "Device / USB camera" |
| USB webcam | "Device / USB camera" |
| IP camera / DVR | "IP camera snapshot URL" — a JPEG endpoint such as `/snapshot.jpg` or `/cgi-bin/snapshot.cgi`. The endpoint must allow CORS for pixel *reads* (the live view alone can work without it); most cameras don't send CORS headers — run `python3 fod/snapshot_proxy.py` and use `http://localhost:8090/?u=<camera-url>` instead |

Camera access (`getUserMedia`) requires HTTPS or `http://localhost` — open the page from
a local file, localhost server, or an HTTPS host (e.g. GitHub Pages).

## Central mode — one computer, many machines

One PC on the plant network can supervise several machines: each job carries optional
**Central-mode fields** (this machine's camera snapshot URL + its lock/unlock relay
URLs; blank falls back to Settings). Create one job per machine — the part currently
running on it — and:

- pick a machine in the Job selector and RUN CYCLE CHECK (no local camera needed when
  the job has its own snapshot URL), or
- press **CHECK ALL MACHINES** to sweep every job that has a camera URL: each machine's
  own relay is fired, every result is logged, and the banner summarises which machines
  failed.

When a machine changes over to a different part, edit its job (or keep one job per
part per machine) and re-capture the master. Hardware for this topology is priced in
`BOM.md` → *Central option* (PoE switch head-end + per-machine kit).

## Per-job tuning

- **Orientation match required** (default 60%) — minimum correlation to accept the part.
- **Foreign-object sensitivity** (default 45) — gray-level difference threshold; lower
  catches smaller contrast differences but risks false alarms.
- **Minimum object size** (default 0.5% of zone) — blobs smaller than this are ignored
  (dust, glare speckle).

Practical tips: fix the camera rigidly, light the zone consistently (a small LED flood
removes most false alarms), keep the inspection zone tight around the die, and re-capture
the master whenever tooling or lighting changes.

## Relay wiring (door lock)

Any relay board reachable over HTTP works, e.g.:

- **Shelly 1**: lock `http://<ip>/relay/0?turn=on`, unlock `.../turn=off`
- **Tasmota**: `http://<ip>/cm?cmnd=Power%20On` / `...Power%20Off`
- **ESP8266/ESP32**: a 20-line sketch serving `/lock` and `/unlock` driving a GPIO

Wire the relay output through the door solenoid lock / cycle-enable input.

> ⚠️ **Safety** — FOD Guard is a process-assist check, not a certified safety device.
> The guard-door interlock must still run through a proper safety relay / guard switch
> per the machine's applicable safety standard; never use this system as the only thing
> keeping the door shut.
