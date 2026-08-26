# Sending Stones Bill of Materials (Rev B.1)

Six identical station kits (5 deploy + 1 Stone of Reserve) + bench devices.
Philosophy: one SKU per role, one lot where possible, boring known-good parts.
The station host is a **Raspberry Pi 4**. See DESIGN.md §4.1 for why (and for
the roads not taken: USB hub + Pi Zero, GPIO UARTs, WiFi/TCP, ESP32 host,
custom radio firmware).

## Radios
| Qty | Item | Source | Notes |
|---|---|---|---|
| 14 | Heltec V3, **US915** | Rokland (single order/lot) or Heltec direct | 12 deploy + 2 bench mules (permanent San Diego pair). Deliberately V3, not V4 — matches deployed population (DESIGN §4). **Verify 915 MHz variant on every unit at intake.** |

## Station hosts
| Qty | Item | Source | Notes |
|---|---|---|---|
| 7 | Raspberry Pi 4 Model B, 2 GB | CanaKit / PiShop / Adafruit | 6 kits + 1 bench. Four native USB-A ports — both radios direct, no hub. Ethernet for NTP/remote at Stone-FB. |
| 7 | Official Pi 4 USB-C PSU, 5.1 V/3 A | same | One SKU × 7. Underpowered adapters cause brownouts that masquerade as software bugs. |
| 6 | Pi-4-class UPS HAT (Geekworm X728-class or Waveshare equiv.) + specified 18650 cells | Amazon / vendor direct | Target: bridge blips and brief outages (hours, not days). Must pass plug-yank test. I2C battery telemetry → events table where supported. |
| 8 | High-endurance 32 GB microSD (SanDisk High Endurance / Samsung PRO Endurance) | Amazon / B&H | 6 + 2 spares + imaging reader. Endurance rating matters more than capacity for logging. |

## RF
| Qty | Item | Source | Notes |
|---|---|---|---|
| 14 | **TE/Linx ANT-916-CW-HW-SMA** (Digi-Key `ANT-916-CW-HW-SMA-ND`) | Digi-Key | 12 deploy + 2 spare. ½-wave center-fed dipole, 916 MHz center / 30 MHz BW (covers both channels), 1.2 dBi, VSWR 1.9, 50 Ω, SMA **male**, 4.72 in. Half-wave chosen deliberately: no ground-plane dependence, so aperture matching lives in the antenna, not in six subtly different installations. ⚠️ **Suffix trap:** `ANT-916-CW-HW` (no -SMA) is the RP-SMA variant — wrong connector, near-identical listing. |
| 6 | Spare IPEX→SMA-female bulkhead pigtails (V3 conversion package incl. nut/washer) | Rokland (add to radio order) | U.FL/IPEX is good for ~30 mating cycles — treat as consumable. Bench rule: seat IPEX **once** at intake, mount SMA bulkhead to enclosure, all subsequent cycles happen at the SMA. |

## Cables & power contingency
| Qty | Item | Notes |
|---|---|---|
| 14 | Short USB-**A**-to-C data cables | V3 has a documented C-to-C charging quirk; short = less station spaghetti |
| 1–2 | Pass-through-rated power bank | Outletless-station contingency only; subject to plug-yank test |

## Field kit
Gaffer tape, velcro, zip ties, label maker (label every Stone, radio, SD, PSU 
**cohort A/B mixups are a silent data poisoner**), small ventilated enclosures
(Printables has V3 cases to remix), spare fuses for optimism. Go team optimism!

## Intake checklist (receiving = Phase 0 step 1)
- [ ] Every Heltec: confirm US915 silkscreen/label; flash stock firmware; label A/B + Stone ID
- [ ] Every antenna: ANT-916-CW-HW-SMA marking check (NOT the RP-SMA sibling); thread onto an SMA-female pigtail
- [ ] Every pigtail: seat IPEX once, mount bulkhead, mark radio as antenna-committed
- [ ] Every Pi: boot golden image; both radios enumerate under /dev/serial/by-id/ with stable names
- [ ] Every UPS HAT: plug-yank test under live logging — any reboot = fail/return
- [ ] Every PSU: check for undervoltage warnings in dmesg under full station load
- [ ] Bench mules set aside and never packed for Vegas

Estimated total: ~$1,000–1,100 all-in with bench devices and field kit.
