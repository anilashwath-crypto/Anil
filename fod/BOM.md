# FOD Guard — Bill of Materials (one machine cell)

Hardware to run the CCTV foreign-object & orientation gate on a single machine:
camera + kiosk computer + lighting + HTTP relay door lock. Edit quantities/prices in
`FOD_Guard_BOM.xlsx` — this file is the readable copy. Prices are indicative Aug 2026
retail (robu.in / amazon.in / local electrical market), GST included; get quotes before
ordering. The software itself (`fod/index.html`) is free.

## A. Vision — camera & compute

| Item | Spec / example | Qty | Unit ₹ | Total ₹ | Notes |
|---|---|--:|--:|--:|---|
| IP bullet camera 2 MP, fixed 4 mm lens | CP Plus / Hikvision value line with JPEG snapshot URL | 1 | 2,800 | 2,800 | Must expose /snapshot.jpg or ONVIF snapshot; enable CORS or serve the app from the same host |
| Camera mounting arm, articulated + clamp | Rigid mount on machine frame over the die | 1 | 600 | 600 | Rigid + vibration-free mounting = fewer false alarms |
| Raspberry Pi 4B 2 GB | Runs FOD Guard in Chromium kiosk mode | 1 | 4,500 | 4,500 | Any spare PC / Android tablet works instead — see Options |
| microSD 32 GB A1 + reader | Boot + app storage | 1 | 450 | 450 | |
| Official USB-C PSU 5 V 3 A | Pi supply | 1 | 700 | 700 | |
| 7" HDMI touchscreen | Operator display: live view + RUN CYCLE CHECK | 1 | 3,800 | 3,800 | Skip if a monitor/PC already sits at the cell |
| **Subtotal** | | | | **12,850** | |

## B. Lighting

| Item | Spec / example | Qty | Unit ₹ | Total ₹ | Notes |
|---|---|--:|--:|--:|---|
| LED floodlight 20 W, 4000 K neutral white | Constant die illumination, machine-mounted | 1 | 700 | 700 | Biggest single reliability lever — consistent light beats any threshold tuning |
| Floodlight bracket + glare hood | Aim across the die; shade direct glare from the lens | 1 | 300 | 300 | |
| **Subtotal** | | | | **1,000** | |

## C. Door lock, relay & signalling

| Item | Spec / example | Qty | Unit ₹ | Total ₹ | Notes |
|---|---|--:|--:|--:|---|
| ESP32 DevKit V1 | Serves /lock and /unlock HTTP endpoints, drives GPIO | 1 | 450 | 450 | Shelly 1 alternative needs no coding — see Options |
| Relay module 2-ch 5 V, opto-isolated | Ch1 door lock, Ch2 tower light | 1 | 150 | 150 | |
| Solenoid bolt lock 12 V DC | Guard-door bolt, spring-return | 1 | 1,300 | 1,300 | Electromagnetic 180 kg alternative — see Options |
| SMPS 12 V 5 A | Lock + floodlight + tower light supply | 1 | 550 | 550 | |
| DC-DC buck 12 V → 5 V 3 A | ESP32 + relay supply | 1 | 200 | 200 | |
| Tower light 12 V, 3-colour + buzzer | Mirrors verdict at the cell (red fault / green clear) | 1 | 1,400 | 1,400 | Optional but strongly recommended on a noisy floor |
| **Subtotal** | | | | **4,050** | |

## D. Wiring, enclosure & network

| Item | Spec / example | Qty | Unit ₹ | Total ₹ | Notes |
|---|---|--:|--:|--:|---|
| Cat6 patch lead 10 m | Camera and Pi to plant switch/router | 2 | 250 | 500 | |
| PoE injector 48 V (or 12 V camera supply) | Powers the IP camera over the same lead | 1 | 400 | 400 | |
| ABS IP65 enclosure 200×150 + DIN rail | Relay-node box beside the door | 1 | 450 | 450 | |
| Terminal blocks, glands, flyback diode, MOV, wire, ferrules | 1 lot | 1 | 600 | 600 | Flyback diode across the solenoid coil is mandatory |
| Conduit, saddles, fasteners | 1 lot | 1 | 400 | 400 | |
| **Subtotal** | | | | **2,350** | |

## Totals

| | ₹ |
|---|--:|
| Subtotal — one cell | **20,250** |
| Contingency 10% (shipping, damage, retries) | 2,025 |
| **GRAND TOTAL (per machine)** | **22,275** |

## Options / swaps *(not included in totals)*

| Item | Swap | ₹ |
|---|---|--:|
| Logitech C270 USB webcam | Replaces IP camera + PoE injector; short USB runs only | 1,700 |
| USB AV/HDMI capture dongle | Reuse an existing analogue CCTV / DVR spot-monitor feed | 1,200 |
| Shelly 1 smart relay | Replaces ESP32 + relay + buck; ready-made HTTP API | 1,600 |
| Spare PC / Android tablet | Replaces Pi + microSD + PSU + touchscreen (saves ₹9,450) | 0 |
| Electromagnetic lock 180 kg | Instead of solenoid bolt, for flush door faces | 1,500 |

**Adding machines:** subsystems A–D repeat per cell; the plant switch/router and the
software are shared. With the spare-PC and Shelly swaps, an incremental cell can come
in near **₹10,000**.

> ⚠️ **Safety** — FOD Guard is a process-assist check, not a certified safety device.
> The guard-door interlock must still run through the machine's certified safety relay /
> guard switch — this lock is wired **in addition to** it, never instead of it.
