# Sending Stones
## Measuring What the Mesh Actually Delivers
## A Delivery-Ratio Experiment for Dense-Event Meshtastic Networks (DC35 target)

By Open Research Institute https://openresearch.institute

**Status:** Rev B — identical stations, all-TX round-robin, capture-effect trials added
**Motivation:** A LongFast vs. ShortTurbo debate at DEF CON 34 was argued from received-message counts observed at single points. This is a quantity confounded by population size, receiver aperture, and survivorship. No stage of any monitoring pipeline is known to have written to disk (will update this document if received). This design specifies the minimal sufficient instrument to measure packet delivery ratio (PDR) directly, at packet layer, with a known denominator.

---

## 1. Domain Model

**Station** This is the physical unit. One Pi 4 host, two Heltec V3 nodes (one per cohort), UPS-buffered AC power, matched antennas, one SQLite database. *All five stations are hardware-identical.* Role (whether/when a station transmits) is configuration, not hardware.

**Slot** Each station owns a fixed 12-second slot within every minute. Station k transmits at seconds [12k, 12k+12)). Slots guarantee our probes never overlap each other *by construction* except when we schedule them to do so, because reasons. (see Capture Trial).

**Probe** This is a packet we originate, identity is known before transmission. The packet communicates cohort, origin station, sequence number, and TX epoch. The set of all probes is the denominator. Probes transmit at slot start + U(0,3) seconds jitter. This jitter breaks any phase-lock with the population's periodic beacons. We do this because nodeinfo/position/telemetry fire on fixed intervals, and we want to avoid this. Slot boundaries keep probes from colliding with each other.

**Capture Trial (H5)** Hypothesis 5 is a *scheduled, deliberate* collision. Once every 10 minutes, two designated stations transmit simultaneously. This is on the same second, no jitter, same cohort. Which transmission each listening station decodes, versus the RSSI delta, measures LoRa capture behavior in the real world at the venue. This is the mechanism behind observations of surprisingly high utilization. We can run this experiment and get results without IQ capture. Capture-trial probes are flagged in the TX log and excluded from H1–H4 analysis. 

**Ambient load** This is the con's organic traffic. It is the independent variable the venue supplies. Characterized via device metrics (`channelUtilization`, `airUtilTx`) and logged continuously.

**Census** This is a 10-minute NodeDB snapshot per node. It is the lower-bound active-population estimate per preset over time.

**Trial** This is one (probe, listening station) outcome. We need to know whether a transmission was delivered or not. With 5 origins and 4 listeners, each cohort yields a 20-cell directed-path matrix. PDR for any slice = delivered/total in slice.

**Deafness accounting** A Meshtastic radio cannot hear during its own transmission. TX logs + slot table let `collate.py` excise each station's own transmit intervals from its listening record exactly. We can account for this. 

**Excluded by design:** IQ/PHY capture (Appendix A) and MQTT-side logging (samples only opted-in nodes)

---

## 2. Hypotheses

- **H1 (congestion regime):** PDR degrades as measured channel utilization rises and we should see a knee in the 25–50% region.
- **H2 (preset comparison):** Under matched offered load and matched apertures, ShortTurbo sustains higher PDR than LongFast in the dense regime.
- **H3 (aperture bias):** LongFast probes are received over longer paths than ShortTurbo probes. This quantifies how much single-point received-counts overstate LongFast.
- **H4 (multi-hop dies first):** PDR for hops ≥ 1 degrades faster with utilization than hops = 0. The capture-effect prediction is that relayed weak traffic starves out first.
- **H5 (capture effect, direct):** In scheduled simultaneous transmissions, decode outcome at each listener is predicted by RSSI delta. We can estimate the capture threshold (dB) per preset in-venue.

H3/H4/H5 are science and H2, in addition to being an engineering test, settles the questions raised on RF Village discord.

---

## 3. Experiment Design

### 3.1 Cohorts
| Cohort | Preset | Channel |
|---|---|---|
| A | LongFast | Default public primary (rides default-firmware population) |
| B | ShortTurbo | DC35 event channel (rides event-firmware population) |

Probes ride the **public** channels deliberately. PDR under ambient flood-rebroadcast load is the quantity in dispute. A private channel would share the RF but not the flooding behavior. Any event-specific firmware can be used in this experiment design for comparison. This experiment is not limited to the DEFCON-specific firmware build. The experiment works for any two firmware builds, as long as they are distinct enough, and the congestion or environment is differentiating enough, to enable an analysis of differences in the data.

### 3.2 Stations & geometry (DC35, LVCC + Fontainebleau as case study)
| # | Station | Location | Why |
|---|---|---|---|
| 0 | FB | Fontainebleau (off-site anchor) | "Reach my buddy across town" |
| 1 | RFV | RF Village, back of Hall 1, floor 1 | Dense, co-located with collaborators |
| 2 | HRV | Ham Radio Village, floor 3 | Vertical diversity — floor-to-floor paths force relaying |
| 3 | CHILL | Chill-out, floor 1 far end | Long same-floor path |
| 4 | COLD | TBD (Vendor area?) | Congestion epicenter; worst-case aperture |

Spare kit = slot 5, dormant; inherits a dead station's slot without schedule disruption.

### 3.3 Probe schedule (round-robin, aggregate-constant)
- Global minute cycle; station k transmits in its slot each minute, per cohort. Aggregate offered load: ~1 probe/min/cohort **per station**, 5/min/cohort network-wide, held constant regardless of station count by slot design. Airtime share verified post hoc against logged utilization (thermometer, not heat source).
- Payloads alternate short (~20 B) / long (~180 B) by seq parity. This means collision cross-section scales with airtime.
- Broadcast text (exercises flood routing). Optional low-rate DM probes for protocol-ACK cross-check.
- **Capture trials:** at minutes where `epoch_min % 10 == 0`, two designated partner stations (for example, HRV + CHILL) transmit at slot-second 0 exactly, no jitter, same cohort, flagged `C` in payload and TX log.
- Duration: Thu 10:00 to Sun 14:00, continuous.

### 3.4 Timing
Pi hosts NTP-synced (GPS/PPS optional). Required resolution is modest. Slot alignment needs hosts within ±1 seconds. Drift is logged.

### 3.5 Power
AC-primary, battery-buffered at every station. We use a quality 5.1 V wall brick, a UPS layer (Pi UPS HAT w/ 18650s, or empirically verified pass-through bank), and this supports the Pi. Bench acceptance test is yank wall power under live logging and any reboot results in a fail. Battery voltage logged to `events` where HAT writes I2C telemetry. Village staff at DEFCON reports hall power stays on overnight and we treat this as a planning assumption to be verified on site. Your site may duck power at night. There can be outages. This design ensures data collection continues during power outages.

### 3.6 Confound table
| Confound | Response |
|---|---|
| Population differs per preset | Census; PDR is population-independent for probes |
| Aperture differs per preset | Co-located matched RX per station; H3 measures it |
| Probes perturb network | Slot budget + post-hoc airtime share check |
| Probe–probe interference | Slots (never overlap except scheduled H5 trials) |
| Phase-lock with ambient beacons | In-slot jitter U(0,3) s |
| Self-deafness | TX-log-driven excision in collate |
| Node/antenna variance | Identical SKUs, pre-con common-TX calibration hour, per-node RSSI offsets recorded |
| Hop-limit differences per firmware | Hop count recorded per RX and PDR conditioned on hops |

---

## 4. Hardware is Five Identical Station Kits (+1 spare)

### 4.1 Station host: Raspberry Pi 4 (decision record)

The host has four jobs. First, speak the Meshtastic serial protocol. Second,
make durable timestamped writes for four days. Third, keep true time 
(±1 s slot alignment), and finally, allow remote login (SSH), so a wedged 
station can be diagnosed and restarted from anywhere in the venue instead of 
requiring a physical visit.

**Pi 4 Model B (2 GB)** does all four with zero custom engineering. 
The official `meshtastic` Python library (project-maintained against
firmware protobuf drift), SQLite/WAL on a journaling filesystem, chrony over
Ethernet or GPS, and SSH. Four native USB-A ports take both radios directly.

Roads considered and not taken:
- **Pi Zero 2 W + USB hub** It has one port and a hub adds a fourth vendor's 
  firmware to the serial path and an enumeration-order failure class. 
  Rejected: buys $27/station at the cost of the most annoying bug family in 
  embedded Linux. Really don't want to deal with this. YMMV.
- **GPIO hardware UARTs** This is deceptively elegant, but trades the hub for 
  soldered harnesses and loses reflash-over-cable. Complexity relocated, not 
  removed.
- **WiFi/TCP to the radios** This puts the instrument's control plane on 2.4 GHz
  at DEFCON. Hm. It adds RF activity, attack surface, and dependency on the most
  hostile network environment in North America. Serial cables don't suffer as much.
  Wired is indoor plumbing. Wireless is an outhouse. Let's go with indoor plumbing.
- **ESP32 as host** So this requires reimplementing the protocol client, crash-safe
  logging on FatFS/SD which is not easy, and it means timekeeping without
  RTC/NTP. Converts ~$30/station into a firmware subproject on the least interesting 
  layer. YMMV. Correct platform for a *future* low-power rural derivative.
- **Custom logging firmware on the Heltecs themselves** So very disqualifying. This
  is not just expensive. It changes the device under test. Stock radio firmware is
  a design invariant. This is really important. Logging intelligence must
  therefore live in a separate host. Don't modify the device under test.

### 4.2 Kit contents

Per kit we have 

1× **Pi 4 Model B (2 GB)** + official 5.1 V/3 A USB-C PSU
2× **Heltec V3** (deliberately V3, not V4: the V3 *is* the deployed population at the most popular, and 28 dBm V4 beacons would punch through collisions that eat everyone else's packets, biasing PDR optimistic. V4 firmware also currently disables RX preamp in sleep which doesn't work for us)
1× Pi-4-class UPS HAT + 18650s (plug-yank tested)
1× high-endurance 32 GB microSD
2× TE/Linx ANT-916-CW-HW-SMA half-wave dipoles

Sourcing: 

Radios from Rokland (single controlled lot) or Heltec direct; **confirm US915 variant per unit at bench**. 
Pi 4s from CanaKit/PiShop/Adafruit. Full parts list, sources, and intake checklist: **hardware/BOM.md**. 
Antennas/pigtails from Digi-Key
SD/power from B&H.

Firmware: stock Meshtastic release (cohort A), stock DC35/event firmware (cohort B). All nodes get fixed position on, GPS off, MQTT off, BT off after config, telemetry intervals left at that firmware's defaults (matching the measured population).

Budget: ~$1,000–1,100 all-in (6 kits + bench mules + field kit). See BOM for final budget.

---

## 5. Software

One golden SD image set to role = YAML. Every Pi runs `monitor_rx.py` always; `probe_tx.py` runs everywhere too (all stations transmit), parameterized by slot. 

Code layout:

```
code/
  config.example.yaml   station id, slot, serial ports, schedule, capture-trial config
  db.py                 schema + writer helpers (WAL mode)
  probe_tx.py           slot scheduler, probe + capture-trial TX, tx_log
  monitor_rx.py         RX logging, probe parsing, census, utilization, events
  collate.py            multi-station join → trials table (CSV/Parquet) + PDR summary
```

Schema additions vs. Rev A: `tx_log.is_capture`, `rx_log.is_capture`, slot table embedded in config, `events.kind` includes `power`, `timesync`, `serial_gap`. This gets us everything we need.

Probe payload: `PDR|<cohort>|<station>|<seq>|<epoch>|<N/C>` padded to target length. Announced on con channels (etiquette + free decode documentation).

There could be Easter Eggs or a CTF in the probes if we want.

---

## 6. Analysis Plan (pre-registered)

Primary: PDR(cohort, path, hour), Wilson 95% confidence intervals. Round-robin note: per-origin rate is 1/min, so per-path trials ≈ 60/hr before exclusions; pool 2–4 h windows narrows it down to ±4–6% confidence intervals.

1. H1: PDR vs. binned `ch_util`, per cohort. Find the knee.
2. H2: paired PDR difference (B − A) per station-hour, with intervals.
3. H3: delivery vs. path class (same-floor / cross-floor / off-site) per cohort; ambient RX-distance distributions.
4. H4: PDR × hops(0, ≥1) × utilization, per cohort.
5. H5: logistic fit of decode outcome vs. RSSI delta per listener leads to capture threshold estimate (dB) per preset.
6. Descriptives: census curves, our airtime share (honesty check), gap/annotation audit.

Deliverables: A QEX-shaped write-up + raw trials + code, open-licensed. DC34's negative space (largest known mesh, no or limited logs) is the introduction.

---

## 7. Ethics, Legality, Etiquette
ISM band, stock power, budgeted duty cycle, reported airtime share. Third-party payloads **not retained** (metadata only: port, size, from-id, RF stats); node IDs salted-hashed in the published set. Village coordination in advance. Live PDR readout offered as village display. Probe format announced on-mesh.

## 8. Build Plan
| Phase | What |
|---|---|
| 0. Bench (San Diego) | 1 full kit; TX/RX round-trip; plug-yank UPS test; schema locked |
| 1. Field (San Diego) | 3 kits across town. This incidentally yields a sparse-rural baseline (the "range matters more" home regime) as published contrast data |
| 2. Load rehearsal | Club event / hamfest; census + utilization capture verified (let us know if you want to have this at your event)|
| 3. Freeze | Code freeze; event-firmware flash/recover drill; pack list |
| 4. Deploy | DC35 Thu AM; daily SD swap + timesync check |
| 5. Analyze | collate then go to notebook then go to write-up then publish|

## Appendix A: Why not IQ?
PHY capture answers *why* packets die, at 100–1000 GB/station + SDR/DSP pipeline. Delivery ratio needs a known numerator/denominator at packet layer. The nodes provide it directly. H5 recovers the headline capture-effect result at the packet layer for free. IQ is the sequel, contingent on these results. 
