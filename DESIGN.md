# Sending Stones
## Measuring What the Mesh Actually Delivers
## A Delivery-Ratio Experiment for Dense-Event Meshtastic Networks (DC35 target)

By Open Research Institute https://openresearch.institute

**Status:** Rev B is identical stations, all-TX round-robin, capture-effect trials added
**Motivation:** A LongFast vs. ShortTurbo debate at DEF CON 34 was argued from received-message counts observed at single points. This is a quantity confounded by population size, receiver aperture, and survivorship. No stage of any monitoring pipeline is known to have written to disk (will update this document if received). This design specifies the minimal sufficient instrument to measure packet delivery ratio (PDR) directly, at packet layer, with a known denominator.

---

## 1. Domain Model

**Station** This is the physical unit. One Pi 4 host, two Heltec V3 nodes (one per cohort), UPS-buffered AC power, matched antennas, one SQLite database. *All five stations are hardware-identical.* Role (whether/when a station transmits) is configuration, not hardware.

**Slot** Each station owns a fixed 12-second slot within every minute. Station k transmits at seconds [12k, 12k+12]. Slots guarantee our probes never overlap each other *by construction* except when we schedule them to do so, because reasons. (see Capture Trial).

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
- **H2 (preset comparison):** Under matched offered load and matched apertures, ShortTurbo sustains higher PDR than LongFast in the dense regime, or does not.
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
- **Capture trials:** at minutes where epoch_min % 10 == 0, a rotating pair of stations transmits at second 0 exactly, no jitter, same cohort, flagged C. The pair is derived from the clock and the shared station roster. Every station computes the schedule independently, so no coordination traffic rides the channel under test. All 10 pairs cycle every 100 minutes. The other three stations listen.
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

There could be Easter Eggs or a CTF in the probes if we want. If this is done, egg content must live after the flag. It can be in the padding field or additional pipe-delimited fields. Do not put it inside the first six.

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

## 9. Synchronized Multi-Aperture Reception Survey
N identical passive monitoring stations (CLIENT_MUTE, LongFast, UTC-synchronized) 
deployed at geographically-distinct apertures across the San Diego–LA region, 
logging concurrently. Because all stations observe the same channel over the same 
interval, cross-aperture comparison isolates the effect of siting and geography 
on reception. The union of receptions across stations approximates ground-truth 
transmission activity, enabling per-aperture delivery-fraction estimates that a 
single station cannot produce. We did this with one station and it's in mahalo-2.

## 10. San Diego Field Trial, Full-Experiment Dress Rehearsal

**Purpose.** Run the *complete* Sending Stones PDR experiment across San Diego–region
apertures **before DEFCON**, configured identically to the DEFCON deployment, so that the
first time the full system runs is at home, where a failing station is a drive away and not on
a con floor where it will suck to fail.

This is **not** a passive characterization survey (that is MAHALO-2, already done for one
aperture). This is the real experiment setup. Stations transmit scheduled probes, receive each
other's probes, run collision trials, and log to per-station databases that collate into a
delivery-ratio dataset. San Diego is the rehearsal and DEFCON is the performance.

---

## Why a full rehearsal is necessary and what has never run

Everything below is currently **unexercised** and must not debut at DEFCON (Update as we go!)

- **`probe_tx.py` has never transmitted a probe that another station received.** The transmit
  path, the payload format, the slot scheduler, validated only in isolation, never end-to-end
  over the air to a second station.
- **The slot-synchronized rotation has never run across stations.** The clock-derived slot
  assignment (station k transmits in seconds [12k, 12k+12) of each minute) assumes all stations
  share UTC and compute the same schedule independently. Never tested with >1 transmitter.
- **The capture-trial collision machinery (H5) has never fired.** Scheduled simultaneous
  transmission by clock-derived rotating pairs and this is pure theory until two stations 
  actually collide on purpose and a third records it.
- **`collate.py` has never run on real distributed multi-station data.** Cross-joining probes
  against receptions across stations, excising self-deaf intervals, attaching the utilization
  covariate. It has been tested on synthetic 2-station data only.
- **Multi-station Tailscale fleet management has never been exercised.** Reaching, monitoring,
  and pulling data from N stations concurrently. Proven for one (Palomar) and untested at fleet scale.

The field trial exists to make all of these fail *here*, cheaply, before they can fail expensively.

---

## Station configuration is identical to DEFCON

Every field-trial station is a **full experiment participant**, configured exactly as it will be
at DEF CON:

| Setting | Value | Rationale |
|---|---|---|
| Role | **CLIENT** (not CLIENT_MUTE) | Must transmit probes and receive; muting breaks the experiment |
| `tx_enabled` | **true** | Stations run `probe_tx.py` and send scheduled probes |
| Rebroadcast | **decision required - see below** | Whether probe stations also relay ambient traffic |
| Preset (cohort A) | LongFast | Matches the deployed population |
| Preset (cohort B) | ShortTurbo | The comparison arm (H2) needs the second radio per station |
| Timezone | UTC | Slot synchronization depends on shared clock |
| Time source | NTP + on-board RTC | Slot timing must not drift; RTC backs NTP across brief outages |
| `station_id` | per station (FB/RFV/HRV/CHILL/COLD…) | Identity in probe payloads and collation |
| `slot` | 0..N-1, unique per station | Round-robin TX schedule |
| Tailscale | on, tested | Remote management of the whole fleet |
| Logger | `monitor_rx.py` (validated: replay-gated, from_id, threading) | RX side |
| Transmitter | `probe_tx.py` | TX side **first real multi-station run** |

### Open decision: do probe stations also relay?

- **Relay ON** stations behave as normal mesh nodes (participate in flooding). Measures PDR as
  a *real participating node* experiences it; most realistic. Cost: your stations add relay load
  and become part of the ambient traffic you're measuring against.
- **Relay OFF (rebroadcast NONE), probe-TX on** stations inject only their own known probes and
  receive everything, but do not rebroadcast others'. Cleaner isolation of the controlled signal;
  your fleet doesn't amplify the background. Recommended for the *cleanest PDR measurement*.

**Recommendation:** relay OFF for the primary PDR arm (measure delivery of a clean injected
signal), with the option to run a relay-ON block separately to compare "participant PDR" vs
"injected-signal PDR." Decide and record before deployment; do not leave it to per-station default.

---

## Radios are the gating dependency

The full experiment needs **two radios per station** (cohort A LongFast + cohort B ShortTurbo)
to run the H2 preset comparison. With ~10 radios inbound:

- **5 stations × 2 radios = 10** this means the full five-station, two-cohort experiment. This is the target.
- If fewer are usable at trial time: run **single-cohort (LongFast only)** across as many stations
  as radios allow. A 3-station single-cohort trial still exercises probe TX/RX, slot sync, capture
  trials, and collation (the untested machinery) even without the preset-comparison arm. Do not
  wait for all ten to start; a reduced trial de-risks most of the system.

Stone Cold (Palomar) currently holds the one flashed radio as a passive monitor. When the fleet
radios arrive, either reflash/repurpose it into the trial or leave it as an ongoing passive
baseline and build the trial from new radios and decide based on count.

---

## Sites and the aperture geometry

The trial's scientific value is in *aperture diversity*, so sites should span the
range/geography axis, not cluster. Target profile:

- **Palomar Mountain** is high rural, wide aperture (proven: 568 nodes/24h). The long-range anchor.
- **Carmel Valley** is suburban San Diego, mid aperture. The "typical deployment" point.
- **Long Beach** is dense urban, LA basin, ~150 km north. House-hosted (reliable power/network/hands).
  Tests whether the mesh bridges SD to LA at all, and gives a genuinely different urban aperture.
- **1–2 more San Diego points** we need to fill in the geometry (e.g., a coastal site, a central-city site).
  Maybe a library or school would help. 

Each site needs: a willing host, AC power, and network (WiFi or ethernet). The Palomar deployment
proved the bring-up template (power, network, Tailscale, validated code, launch), so each new
site follows the STATION-SETUP.md checklist.

**Note on the SD to LA span:** at ~150 km, Long Beach almost certainly cannot hear San Diego nodes
directly. That distance exceeds even Palomar's reach. That is itself a *measurement*: the trial
quantifies the geographic extent of mutual reception, and likely shows San Diego and LA as
*distinct mesh regions* with limited or no direct bridging. Whether any node is heard by both a
San Diego station and Long Beach is an empirical question the trial answers.

---

## What the trial measures (the science, beyond de-risking)

1. **Per-aperture, per-preset delivery ratio (H2).** For known transmitted probes, what fraction
   does each station receive, on LongFast vs ShortTurbo? The core PDR question, with a real
   denominator (probes are counted at TX).
2. **Cross-aperture reception maps.** Which stations heard each probe gives indication of coverage 
   overlap and gaps between apertures.
3. **Capture-effect under scheduled collisions (H5).** When two stations transmit simultaneously,
   what does a third receive? First real data on LoRa capture in this setting.
4. **The consensus denominator, cross-checked.** The union of receptions across stations vs. the
   known TX ledger validates the "spatial diversity as denominator" method against ground truth
   you actually have (because you control the transmitters).
5. **Aperture geography.** The extent and boundaries of mutual reception across the SD to LA region.

---

## Success criteria for the rehearsal (de-risking checklist)

The trial has done its job when all of these have happened *at least once, in San Diego*:

- [ ] A probe transmitted by one station is logged as received by another (probe TX/RX round-trip).
- [ ] All stations independently compute and transmit in the correct slot (schedule sync holds).
- [ ] A capture trial fires: two stations transmit simultaneously, a third logs both/one/neither.
- [ ] `collate.py` produces a delivery-ratio table from real multi-station databases.
- [ ] The full fleet is reachable and its data pullable over Tailscale concurrently.
- [ ] A station survives a multi-day run unattended (endurance, already shown for one; confirm for fleet).
- [ ] At least one deliberate failure (unplug a station) is detected and recovered/logged cleanly.

Every box checked in San Diego is a box that will not be checked for the first time at DEFCON.

---

## Sequence

1. **Now (radios in transit):** secure sites (hosts, power, network); finalize the relay-on/off
   decision; keep Palomar passive baseline running.
2. **Radios arrive:** flash (region US, cohorts A/B per station), apply STATION-SETUP.md per box.
3. **Deploy** to secured sites; bring each up via Tailscale; verify i2c/power/network/logger.
4. **Bench the probe round-trip first** with two stations on one bench, confirm `probe_tx.py` gives
   `monitor_rx.py` logs a probe, before distributing. (This is the single most important untested
   step; do it before driving anywhere.)
5. **Run the distributed trial** this is a synchronized, multi-day, full experiment.
6. **Collate and analyze** goes to MAHALO-3, and a proven system for DEF CON.


## FINDING
Bench, 14 September 2026: monitor_rx.py and probe_tx.py each work in isolation but CANNOT run simultaneously. Serial ports are exclusive, and each opens its own SerialInterface. Unify into a single per-station process (station.py) that opens each radio once and runs both the RX subscription and the TX scheduler against the shared interface. This is a prerequisite for any real PDR measurement. Issue was opened. 

## Appendix A: Why not IQ?
PHY capture answers *why* packets die, at 100–1000 GB/station + SDR/DSP pipeline. 
Delivery ratio needs a known numerator/denominator at packet layer. The nodes 
provide it directly. H5 recovers the headline capture-effect result at the packet 
layer for free. IQ is the sequel, contingent on these results. 
