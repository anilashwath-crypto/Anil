# Smart Farm — DIY Bill of Materials

DIY electronics for the *Smart Farm AI System Design* blueprint (10-acre mixed farm,
rural Karnataka). Edit quantities/prices in `Smart_Farm_DIY_BOM.xlsx` — this file is the
readable copy. Prices are indicative July 2026 retail (robu.in / amazon.in / local market).

## A. Edge gateway & connectivity  *(Phase 1)*

| Item | Spec / example | Qty | Unit ₹ | Total ₹ | Notes |
|---|---|--:|--:|--:|---|
| Raspberry Pi 4B 4GB | Farm brain — Home Assistant + Node-RED + Frigate | 1 | 5,500 | 5,500 | Pi 5 4GB also fine (~Rs.6,500) |
| microSD 64GB (high-endurance) | SanDisk High Endurance class | 1 | 700 | 700 | NVR/logging wears cheap cards out |
| LoRa module SX1278 Ra-02 433 MHz | Gateway radio | 1 | 350 | 350 | Single-channel is enough for ~10 nodes |
| ESP32 DevKit V1 | LoRa-to-Pi serial bridge | 1 | 450 | 450 |  |
| 4G router, dual-SIM, ext. antenna port | Tenda 4G03 Pro / TP-Link MR110 class | 1 | 6,500 | 6,500 | Jio + Airtel SIMs per blueprint |
| Outdoor high-gain 4G antenna + SMA lead | 10–12 dBi panel/yagi | 1 | 1,200 | 1,200 | Mount high at pump house |
| SIM800L GSM module + antenna | SMS fallback commands/alarms | 1 | 350 | 350 | Own SIM, Rs.20/mo SMS pack |
| DS3231 RTC module | Keeps schedules through reboots | 1 | 150 | 150 |  |
| IP65 enclosure + DIN rail + glands | 300x200 ABS, gateway box | 1 | 1,200 | 1,200 |  |
| **Subtotal** | | | | **16,400** | |

## B. Solar power — control layer  *(Phase 1)*

| Item | Spec / example | Qty | Unit ₹ | Total ₹ | Notes |
|---|---|--:|--:|--:|---|
| Solar panel 200 W 12 V | Poly/mono, control system only | 1 | 6,000 | 6,000 | Pump stays on grid/diesel |
| LiFePO4 battery 12.8 V 50 Ah | 3+ days autonomy for controls | 1 | 11,000 | 11,000 | Lead-acid 100 Ah alt: Rs.9,500, 1/3 the life |
| MPPT charge controller 20 A | 12/24 V auto | 1 | 2,500 | 2,500 |  |
| DC-DC buck 12->5 V 3 A | Per node / Pi supply | 4 | 200 | 800 |  |
| Fuses, MC4 pairs, 6 mm2 solar cable set |  | 1 | 1,500 | 1,500 |  |
| **Subtotal** | | | | **21,800** | |

## C. Irrigation control & water monitoring  *(Phase 1)*

| Item | Spec / example | Qty | Unit ₹ | Total ₹ | Notes |
|---|---|--:|--:|--:|---|
| Solenoid valve 1" 12 V DC, normally-closed | Plastic body, drip-rated | 6 | 1,400 | 8,400 | One per zone; NC = fails shut |
| Valve-controller node (ESP32 + 4-ch relay + box) | Each drives 3 valves | 2 | 1,600 | 3,200 |  |
| Flow meter YF-B10 1" brass, pulse | Main line + fertigation line | 2 | 1,000 | 2,000 |  |
| Pressure transducer 0–10 bar 1/4" | Leak / burst / clog detection | 2 | 1,400 | 2,800 |  |
| Borewell level sensor 0–50 m, 4–20 mA | Submersible hydrostatic | 1 | 4,500 | 4,500 | Blueprint 4.1: watch falling yield |
| 4–20 mA receiver board | For borewell sensor | 1 | 400 | 400 |  |
| Ultrasonic level sensor JSN-SR04T | Overhead tank % | 1 | 450 | 450 | Waterproof probe |
| Phase-failure relay | Single-phasing protection | 1 | 1,200 | 1,200 | Pairs with existing starter |
| PZEM-004T 100 A + CT | Pump energy metering (kWh) | 1 | 900 | 900 |  |
| Pump-house node (ESP32 + SIM800 + box) | GSM start/stop + dry-run logic | 1 | 1,500 | 1,500 | DIY 'Kisan Raja' |
| 30 A relay/contactor driver module | Drives pump contactor coil | 1 | 600 | 600 |  |
| **Subtotal** | | | | **25,950** | |

## D. Soil monitoring — 6 zone nodes + 2 field stations  *(Phase 1–2)*

| Item | Spec / example | Qty | Unit ₹ | Total ₹ | Notes |
|---|---|--:|--:|--:|---|
| Soil node kit (ESP32 + Ra-02 LoRa) | One per zone | 6 | 750 | 4,500 |  |
| Capacitive soil moisture probe v2 | 2 depths per zone; seal with epoxy | 12 | 120 | 1,440 | Never use resistive probes — they corrode |
| DS18B20 waterproof soil temperature | One per zone | 6 | 150 | 900 |  |
| 2x 18650 + TP4056 + holder | Per node battery pack | 6 | 350 | 2,100 |  |
| 6 V 2 W solar top-up panel | Per node | 6 | 250 | 1,500 |  |
| IP65 node enclosure + mounting pole |  | 6 | 500 | 3,000 |  |
| pH kit: E-201 probe + driver board | Field stations A & B | 2 | 1,800 | 3,600 | Recalibrate monthly (pH 4/7 buffers) |
| Analog EC kit, K=1 probe | Field stations A & B + dose feedback | 2 | 2,000 | 4,000 | DFRobot-class; generic TDS boards drift |
| ADS1115 16-bit ADC | Clean analog reads for pH/EC | 2 | 250 | 500 |  |
| **Subtotal** | | | | **21,540** | |

## E. Weather station  *(Phase 2)*

| Item | Spec / example | Qty | Unit ₹ | Total ₹ | Notes |
|---|---|--:|--:|--:|---|
| Cup anemometer, pulse output | Wind speed (spray windows) | 1 | 2,500 | 2,500 |  |
| Wind vane, analog | Wind direction | 1 | 1,800 | 1,800 | Optional but helps drift calls |
| Tipping-bucket rain gauge | Auto rain-skip input | 1 | 1,500 | 1,500 |  |
| SHT31 temp/RH sensor |  | 1 | 400 | 400 |  |
| BMP280 barometric pressure |  | 1 | 150 | 150 |  |
| Leaf-wetness sensor | DIY interdigitated PCB | 1 | 200 | 200 | Disease-risk input |
| ESP32 + Ra-02 LoRa node |  | 1 | 750 | 750 |  |
| Radiation shield + 3 m mast | DIY plate-stack shield | 1 | 1,500 | 1,500 |  |
| Node solar + battery pack |  | 1 | 600 | 600 |  |
| **Subtotal** | | | | **9,400** | |

## F. Fertigation & venturi diffuser  *(Phase 2)*

| Item | Spec / example | Qty | Unit ₹ | Total ₹ | Notes |
|---|---|--:|--:|--:|---|
| Venturi injector 3/4" + assembly | The diffuser — suction dosing | 1 | 1,800 | 1,800 |  |
| Peristaltic dosing pump 12 V | Metered jeevamrutha injection | 1 | 2,800 | 2,800 | Gives true L/h control for auto-dosing |
| Dosing solenoid 1/2" 12 V | Opens diffuser suction line | 1 | 1,400 | 1,400 |  |
| Disc filter 120 mesh 1" | Two stages — jeevamrutha clogs drip | 2 | 1,200 | 2,400 | Filter to 120 mesh minimum |
| Inline EC probe + board | Dose feedback / EC guard | 1 | 2,000 | 2,000 |  |
| Barrel stirrer: 12 V wiper motor + paddle | Daily jeevamrutha stir | 1 | 1,500 | 1,500 | Automates task tT2 |
| Float switch (barrel level) |  | 2 | 250 | 500 |  |
| Dosing node (ESP32 + 4-ch relay + box) | Runs the auto-dosing logic | 1 | 1,600 | 1,600 |  |
| **Subtotal** | | | | **14,000** | |

## G. Livestock shed  *(Phase 2)*

| Item | Spec / example | Qty | Unit ₹ | Total ₹ | Notes |
|---|---|--:|--:|--:|---|
| Shed node: ESP32 + SHT31 + 2-ch relay | Temp/RH + fan/fogger auto | 1 | 1,600 | 1,600 |  |
| Contactor 25 A (fan, fogger) |  | 2 | 450 | 900 |  |
| Fogger kit: 10 nozzles + 60 psi pump | Heat-stress control >=30 C | 1 | 3,500 | 3,500 |  |
| Platform scale: 4x 50 kg load cells + HX711 + frame | Goat-kid weigh-bands -> records | 1 | 4,500 | 4,500 | Growth data = breeding premium |
| RFID EID stick reader + 40 ear tags | Animal identity for records | 1 | 5,400 | 5,400 | ISO 11784/85 FDX-B |
| Coop door: linear actuator + LDR + ESP32 | Auto open/close for Giriraja | 1 | 2,500 | 2,500 | Biggest predator-loss saver |
| **Subtotal** | | | | **18,400** | |

## H. Cameras & security  *(Phase 1–2)*

| Item | Spec / example | Qty | Unit ₹ | Total ₹ | Notes |
|---|---|--:|--:|--:|---|
| Outdoor 3 MP ONVIF/RTSP camera | Gate, pump house, shed, store | 4 | 3,200 | 12,800 | 2 in Phase 1, 2 in Phase 2; local RTSP, no cloud fee |
| 1 TB surveillance HDD (USB) | Frigate NVR on the Pi | 1 | 4,000 | 4,000 |  |
| PoE switch / 12 V camera PSU |  | 1 | 1,500 | 1,500 |  |
| PIR + siren node (store room) | ESP32 + PIR + 12 V siren | 1 | 800 | 800 |  |
| **Subtotal** | | | | **19,100** | |

## I. Pest & weed monitoring  *(Phase 2–3)*

| Item | Spec / example | Qty | Unit ₹ | Total ₹ | Notes |
|---|---|--:|--:|--:|---|
| Termite bait station (DIY: PVC + wood bait) | Grid of 10 around orchard | 10 | 120 | 1,200 | Check weekly, log hits in dashboard |
| Pheromone trap (funnel type) | FAW / fruit-fly | 10 | 180 | 1,800 |  |
| Lure refills (per season) |  | 20 | 60 | 1,200 | Replace every 3–4 weeks |
| Yellow/blue sticky traps | 10 per acre on crop block | 50 | 15 | 750 |  |
| ESP32-CAM trap camera | Daily photo of trap for counting | 2 | 700 | 1,400 |  |
| Pi NoIR camera + red filter | DIY NDVI from a pole/kite | 1 | 2,500 | 2,500 | Or hire drone NDVI (Rs.400–600/acre) |
| **Subtotal** | | | | **8,850** | |

## J. Wiring, protection & mounting  *(Phase all)*

| Item | Spec / example | Qty | Unit ₹ | Total ₹ | Notes |
|---|---|--:|--:|--:|---|
| 1.5 mm2 2-core outdoor cable, 200 m | Valve and power runs | 1 | 3,000 | 3,000 |  |
| HDPE conduit 16 mm, 100 m | Rodent protection for cable | 1 | 1,500 | 1,500 |  |
| Surge protection: MOVs, TVS, earth rod + wire | Lightning is the #1 killer | 1 | 2,500 | 2,500 | Earth every mast and the gateway |
| Spare IP65 boxes, glands, terminals, fuses |  | 1 | 2,500 | 2,500 |  |
| Silica gel, epoxy, heatshrink, UV ties | Monsoon-proofing | 1 | 800 | 800 |  |
| GI poles & brackets | Sensor and antenna mounts | 6 | 250 | 1,500 |  |
| **Subtotal** | | | | **11,800** | |

## Totals

| | ₹ |
|---|--:|
| All subsystems | 167,240 |
| Contingency 10% | 16,724 |
| **Grand total (DIY electronics)** | **183,964** |

## Buy, don't build

| Item | Source | Cost | Why not DIY |
|---|---|---|---|
| Cattle activity collars | Cowfit / Stellapps mooOn | Rs.6,000–9,000 per animal x 12 | Heat-detection algorithms need vendor data; DIY misses heats — one missed cycle costs more than the collar |
| Drip system + main filtration | Netafim / Jain / Finolex dealer | ~Rs.2.7 lakh for 6 acres before subsidy | PMKSY-PDMC 45–55% subsidy requires an empanelled vendor install |
| Drone spraying & NDVI survey | Local operator / IFFCO Kisan | Rs.400–600 per acre per pass | Hire as a service — owning costs Rs.3–5 lakh |
| Milk analyzer | Everest / Stellapps | Rs.35,000–45,000 | Calibrated fat/SNF needed for A2 pricing credibility |
| Sexed semen + AI service | KLDB / govt semen stations | Rs.250–1,000 per dose | Service, not equipment |

## Tools (one-time)

Soldering iron + solder (₹800), Crimping tool + lugs/ferrules (₹900), Multimeter (₹700), Wire stripper (₹300), Cordless drill + bits (₹2,500), PTFE tape, spanners for plumbing (₹500) — about ₹5,700 if starting from zero.

## Free software stack

- **ESPHome / Arduino** on every ESP32 node (sensors, valves, dosing)
- **Home Assistant + Node-RED** on the Pi — automations, offline schedules, this dashboard's data API
- **Frigate** on the Pi — camera NVR with person/vehicle detection
- **Telegram/WhatsApp webhook + SIM800L SMS** for alerts

*Vendor comparison: the blueprint's Phase 1+2 vendor-installed automation is ~₹9.6 lakh gross.
This DIY build covers the monitoring/control electronics for a fraction of that — the trade-off
is your build time, no AMC, and no vendor crop-AI subscription (Fasal/Fyllo can be added later).*
