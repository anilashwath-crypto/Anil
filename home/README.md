# HouseKeeper — The House Of Ommi

**Designed, Initiated & Developed by The House Of Ommi.**

One mobile-first, offline-first app (`home/index.html`, single file, no build
step) for running the whole household: kitchen/toiletries inventory,
housekeeping schedules with photo-verified placement, staff records with
attendance, and the family vehicles.

**Live (once Pages picks up the branch):** https://anilashwath-crypto.github.io/Anil/home/

On first open the app asks each user to pick their language — English, ಕನ್ನಡ or
हिंदी — and the entire UI runs in that language from then on (changeable any
time from the header).

## Modules (bottom tabs)

### 🧺 Stock · 🧾 Purchases · ⏰ Alerts · 🤖 Insights
| Feature | How |
|---|---|
| Opening stock | Add each product once with its starting quantity and unit |
| Packet photos | **Up to 4 photos per item** (front, ingredients label, mfg/expiry panel, MRP), compressed and stored on-device |
| Read from photo (OCR) | **📖 Read details from photos** runs on-device OCR over all the item's photos and fills empty fields: mfg/expiry dates (incl. "best before N months"), MRP, net quantity/unit, ingredients. Purchase and fuel forms have **📖 Read the bill** for date/vendor/total and litres/amount. The reader (Tesseract) downloads from a CDN on first use (~few MB, then cached); results are shown for you to confirm — label prints vary, so treat it as a fast first draft, not gospel |
| Mfg / expiry dates | Recorded per item; updated per batch when you log a new purchase |
| Ingredients | Copied from the label; scanned for flags (palm oil, trans fats, MSG, maida, SLS/parabens, artificial colours, preservatives…) |
| Expiry reminders | Alerts tab + phone notification (once a day when the app is opened) for anything expired or expiring within 7 days; 30-day early-warning list |
| Price tracking | Every purchase logs date, quantity, ₹/unit, store/vendor |
| Invoices | Photograph the bill with each purchase; browsable per month and per item |
| Consumption / live stock | Weighed goods (kg/g/L/ml): tap **⚖ Weigh**, put the packet on a digital kitchen scale and enter the reading — tare is subtracted, live stock is set exactly, the delta is logged, optional photo of the scale display. Countable items use “− Use” |
| Insights | On-device: spend by category, monthly trend, price-watch (first vs latest ₹/unit), money lost to expired stock, and useful / needs-a-change / avoid verdicts |

### 🧹 Keeping (housekeeping)
- **Team** — staff/family with role, phone, **Aadhaar number (shown masked:
  `XXXX XXXX 1234`) and an Aadhaar/ID card photo** for household staff
  records, plus an *is a driver* flag. ID details stay on this phone only —
  collect them with the person's consent.
- **Schedules & assignments** — tasks per area, assigned to a person, daily /
  chosen weekdays / one-time; the **Today** sub-tab shows what's due and open.
- **Attendance** — each person marks **IN** when work starts and **OUT** when
  leaving; a **selfie is captured every time** as photo proof of who marked it,
  with the timestamp. A register shows recent days, with the day's selfies one
  tap away. (True face-*matching* needs an ML model — this is the audit-proof
  photo version; upgradeable later.)
- **Master placement photos & verification** — each area stores a master photo
  of the correct artefact arrangement; after cleaning, the after-photo is
  compared on-device (brightness-normalised region diff), scored, and
  mismatched regions get **red boxes** — a person confirms *Placed correctly*
  or *Needs re-doing*. History logs every check; an approved photo can become
  the new master.

### 🚗 Drive (drivers & vehicles)
- **Vehicles** — name + registration; card shows this month's KM run, fuel
  spend, repair spend, and the latest odometer reading.
- **KM log** — per day: vehicle, driver (staff flagged as drivers), start/end
  odometer (start pre-filled from the last known reading), purpose/route.
- **Fuel** — date, litres, amount, odometer, station, **bill photo**; the list
  computes **km/L between fills** automatically.
- **Repairs** — work done, amount, **bill photo**.
- Driver attendance uses the same selfie IN/OUT in Keeping → Attendance.

## Login (app lock)

Optional password/PIN gate on every open (salted PBKDF2 hash — the password
itself is never stored) plus **face/fingerprint unlock** via WebAuthn, using
the phone's own screen-lock biometrics. Set up under **More → App lock**.
"Forgot?" erases all app data so the lock cannot be bypassed. Note: this gates
access to the app; data on the phone is not additionally encrypted.

## Data & privacy

All data — inventory, photos, invoices, staff IDs, attendance selfies, vehicle
bills — lives in the phone's browser storage (IndexedDB). Nothing is uploaded
anywhere. **More → Export backup** writes everything (all modules) to one JSON
file; import restores it on a new phone. Clearing the browser's site data
deletes everything, so export now and then.

## Local hub (while development continues)

`home/hub.py` turns any computer on your home WiFi into the HouseKeeper hub:

1. Install Python (python.org) if needed.
2. Run `python3 hub.py` (Windows: `py hub.py`) in this folder.
3. It prints two addresses — open the **“On phones”** one
   (e.g. `http://192.168.1.5:8080`) on each phone on the same WiFi and
   *Add to Home screen*.

Notes: each phone keeps its own on-device data (move it with Export/Import
backup); the app lock needs https or localhost, so on the plain hub address
the app runs unlocked and says so under More → App lock.

**Optional — ngrok:** with the hub running, `ngrok http 8080` (free account at
ngrok.com) gives a temporary **https** URL reachable from anywhere — and
because it's https, the app lock and face/fingerprint unlock work on it. The
URL changes each run; it's a development preview, not the final deploy. The
permanent deploy stays GitHub Pages (merge the PR).

## Using it on the phone

1. Open the page in Chrome and **Add to Home screen** — it opens full-screen
   and works offline.
2. Pick your language on first run; set the app lock under More.
3. **Alerts → Enable reminders** once for expiry notifications.
4. **More → Load sample data** fills every module with a demo household to
   explore before real entry.
