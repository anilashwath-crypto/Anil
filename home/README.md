# Home Stock — household inventory tracker

Mobile-first, offline-first web app (`home/index.html`, single file, no build step)
for tracking everything the house consumes — kitchen groceries, toiletries and
cleaning supplies.

**Live (once Pages picks up the branch):** https://anilashwath-crypto.github.io/Anil/home/

## What it does

| Feature | How |
|---|---|
| Opening stock | Add each product once with its starting quantity and unit |
| Packet photos | Camera capture (front + ingredients label), compressed and stored on-device |
| Mfg / expiry dates | Recorded per item; updated per batch when you log a new purchase |
| Ingredients | Copied from the label; scanned for flags (palm oil, trans fats, MSG, maida, SLS/parabens, artificial colours, preservatives…) |
| Expiry reminders | Alerts tab + phone notification (once a day when the app is opened) for anything expired or expiring within 7 days; 30-day early-warning list |
| Price tracking | Every purchase logs date, quantity, ₹/unit, store/vendor |
| Invoices | Photograph the bill with each purchase; browsable per month and per item |
| Consumption / live stock | Weighed goods (kg/g/L/ml): tap **⚖ Weigh**, put the packet on a digital kitchen scale and enter the reading — tare (empty-container weight) is subtracted, live stock is set exactly, the consumption delta is logged, and you can attach a photo of the scale display. Countable items (pcs/packets/bottles) use the “− Use” button |
| Insights (AI-style analysis) | Runs on-device from your own entries: spend by category, monthly spend trend, price-watch (first vs latest ₹/unit), money lost to expired stock, and verdicts — **useful** (fully consumed, price stable), **needs a change** (price up ≥12% → compare vendors/brands), **avoid / buy smaller** (expired with stock left), **review** (flagged ingredients) |
| App lock (login) | Optional password/PIN gate on every open (salted PBKDF2 hash — the password itself is never stored) plus **face/fingerprint unlock** via WebAuthn, which uses the phone's own screen-lock biometrics (no camera model, no server). Set it up under **More → App lock**. A "Forgot?" reset erases all app data — so nobody can bypass the lock and read your entries. Note: this gates access to the app; the data on the phone is not additionally encrypted |
| Trilingual | English / ಕನ್ನಡ / हिंदी, same convention as the farm dashboard |
| Backup | Export/import a single JSON file (photos included) to move phones or keep a copy |

## Data & privacy

All data lives in the phone's browser storage (IndexedDB) — nothing is uploaded
anywhere. Export a backup from **More → Export backup** now and then; clearing
the browser's site data deletes the inventory.

## Using it on the phone

1. Open the page in Chrome on the phone and choose **Add to Home screen** — it
   then opens full-screen like an app and works offline.
2. Tap **Alerts → Enable reminders** once to allow notifications.
3. Open the app daily (or whenever you cook/shop); the expiry notification
   fires at most once per day.

> Browser pages can't ring the phone while fully closed (that needs a push
> server); the reminder fires whenever the app is opened or left open. For a
> guaranteed daily nudge, add a recurring 8 am phone alarm named "Check Home
> Stock" — the Alerts tab always has the current list.

## Try it

**More → Load sample data** fills a demo pantry (including an expired item and
a price rise) so every tab has something to show. Delete the sample items or
just export/import over them when starting real entry.
