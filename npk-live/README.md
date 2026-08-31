<!-- Kept as README.md here so the folder self-documents; it is README-live.md
     once copied next to the probe server. -->

# npk-live.html — mobile dashboard for the FST100 soil probe

One self-contained HTML file that polls a running `server.py` and shows live
probe readings on a phone. No build step, no CDN, no dependencies — inline SVG
charts and the same meters as the probe server's desktop `index.html`. Installs
to a home screen.

> These files belong to the **FST100-2006E1111 probe server** project, not to the
> smart-farm dashboard at the root of this repository. They are checked in here so
> the source has a home: copy `npk-live.html` next to `server.py` in that project,
> apply `server.py.diff`, and this file becomes its `README-live.md`. Every
> `index.html`, `chart.js` and `server.py` mentioned below is the probe server's,
> not the root `index.html` of this repo.

## Put it on your phone

On the machine with the probe attached:

```bash
NPK_BIND=0.0.0.0 ./.venv/bin/python server.py
```

It prints its LAN address on startup:

```
NPK dashboard  ->  http://localhost:8090
  mobile app    ->  http://localhost:8090/live
  on this LAN   ->  http://192.168.1.42:8090/live
```

Open that last URL on the phone — same Wi-Fi — then **Add to Home Screen**
(Safari: Share ▸ Add to Home Screen; Chrome: ⋮ ▸ Add to Home screen). It launches
full-screen with no browser chrome, its own icon, and remembers the server
address.

`NPK_BIND` defaults to `127.0.0.1`, so the server stays off the network until you
ask for it. Only bind wider on a network you trust — the API is unauthenticated.

## Other ways to open it

- **On the host machine** — <http://localhost:8090/live>.
- **From disk** — double-click `npk-live.html` and type the server address into
  the header field. It's remembered in `localStorage`.
- **Pinned by URL** — `npk-live.html?host=http://192.168.1.42:8090`.

## What's mobile about it

- **Layout** — one column of meters on a phone, two on a tablet, three across in
  landscape. Sticky header keeps the connection status visible while scrolling.
  Safe-area insets for notches and home indicators.
- **Charts size to the container.** The upstream 900-unit viewBox squashed onto a
  390px phone rendered 9px axis text at under 4px; geometry now follows the
  container width, with tighter gutters and start/end timestamps only.
- **Touch crosshair** — tap and drag any chart to scrub; the tooltip flips sides
  near an edge and releases on lift. Vertical page scrolling still works.
- **16px input font**, so iOS Safari doesn't zoom the page when you focus the
  server field.
- **Polling pauses when the phone is backgrounded** and resumes on return —
  no radio traffic from a dashboard in your pocket.
- **Keep screen on** button (Screen Wake Lock API) for a phone propped next to
  the plant. Hidden on browsers that don't support it.
- **Redraws on rotate**, debounced against iOS firing resize through the animation.

## Changes to server.py

- `Access-Control-Allow-Origin: *` — lets the page read the API when it isn't
  same-origin (opened from disk, or installed to a home screen). Read-only GET.
- `/live` route serving `npk-live.html`.
- `NPK_BIND` env var (default `127.0.0.1`) and a startup line printing the LAN URL.

## Unchanged

The `DEMO DATA` badge still keys off the server's own `demo` flag, so simulated
readings can't be mistaken for measurements. Bands still live in `SPEC` at the
top of the script block. The accuracy caveat still applies — these probes derive
N, P and K from one conductivity signal.
