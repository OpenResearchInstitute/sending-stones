# PROVENANCE — DEF CON 34 Contributed Captures (public version)

**Status:** Published 2026-09. Collectors are anonymized pending their consent;
this file will be updated with credit as contributors opt in.
**Location of data:** NOT in this repository, at the contributors' request.
This file documents what the captures are, what each instrument can and cannot
see, and integrity fingerprints for verifying a privately-shared copy. The
derived analysis (aggregates only) is `analysis/mahalo-1-dc34/`.

---

## Doctrine

1. **Attribution by consent.** Collectors are named only if they choose to be.
   Roles are used until then. Credit is offered, never imposed.
2. **Field semantics are collector-specific.** No field is interpreted until
   verified against the collecting tool. Two corrected errors in MAHALO-1
   came from this rule (`hop start = 0` ≠ zero hops; `hops_away` = budget
   remaining, not traveled).
3. **Dedup behavior is part of the instrument.** Whether a capture preserves
   duplicate receptions determines which phenomena it can see at all.
4. **Raw data is not republished; fingerprints are.**
5. **No identifiers in derived artifacts.** Node IDs render as rank labels;
   sender names, payloads, and collector file paths are never rendered.

---

## Chain of custody

All artifacts were shared privately with Open Research Institute on 2026-08-26
by a community member acting as intermediary for the collectors. The
intermediary requested that datasets not be republished; that request is
honored here. Collectors have been offered review and credit.

---

## Artifacts

### A. App-level datalog (CSV, 39,837 rows)
- **Instrument:** Meshtastic app/serial datalog export from a single node.
- **Position:** unknown (con-floor class aperture inferred from traffic shape).
- **Coverage:** Aug 5–11 local time; **no timezone recorded**.
- **Dedup behavior:** app-level — one row per unique packet.
  **Structurally blind to duplicate-reception phenomena** (the storm class).
- **Fields:** no packet ID, no destination; SNR on all rows.
- **Fingerprint (SHA-256 prefix):** `071f9b2cb0cf`

### B. Device-trace megalogger database (SQLite, 814,441 records)
- **Instrument:** trace-log tailer with resume-safe cursors and per-line
  SHA-256; every RF reception retained, including encrypted (header-only)
  packets (~97% of records).
- **Position:** high-elevation aperture — upper floor of a north-Strip hotel.
- **Coverage:** 2026-08-03 15:46 → 08-09 17:34 **UTC** (verified via
  human-diurnal TEXT traffic, MAHALO-1 §2.2).
- **Dedup behavior:** ingestion-level only; **RF duplicates preserved** — the
  instrument that made the storm class visible.
- **Verified semantics:** `hops_away` = hop budget remaining; zeroed
  timestamps excluded (`> 1e9`); channel hash 209 = its decodable primary;
  storm traffic rode hashes 14 and 0 (undecrypted at this aperture).
- **Fingerprint:** `c2376cc4e92e`

### C. SDR PHY-layer capture (49 files)
- **Instrument:** `lorarx` demodulator, parallel SF7–SF11 decoders on 500 kHz
  windows; per-frame measured airtime, SNR, level, CRC status, raw LoRa frame.
  Sync-word filter off — captures **all** in-band LoRa; frames require
  classification.
- **Frequencies:** 906.875 MHz (LongFast slot), 917.250 MHz, 910.525 MHz.
- **Position:** a different Strip property from B, ~1 km distant.
- **Coverage:** filenames carry capture-start time only; rows have **no
  absolute time**. Bulk of material Sunday 2026-08-09.
- **Dedup behavior:** none (raw stream); cross-SF double-decodes possible.
- **Pending verification:** CRC field semantics (three-state 0/1/−1 observed).
- **Fingerprints:** per-file prefixes recorded in artifact D's `merge_sources`.

### D. Merged database (SQLite, 2.8 GB)
- **Instrument:** engineered merge of A, B, C, and E. Profile
  `defcon34-conservative-v1`. Not an independent capture.
- **Dedup design:** every observation retained with a disposition
  (1,603,700 observations; 890,601 canonical) — dupes adjudicated, not deleted.
  Per-source clock and identity bases recorded rather than normalized.
- **Limitations:** trace layer ≈ B + C rows (not independent corroboration of
  B-derived findings); C rows lack IDs and absolute time, so the conservative
  matcher joined **zero** keys between B and C — cross-aperture nulls from
  this merge are instrument limitations, not evidence.

### E. Broker-side infrastructure export
- **Instrument:** MQTT broker configuration, MQTT→Postgres collector, packet
  export (58,323 rows), viewer history databases (59,194 / 12,132 rows).
- **Aperture:** server-side view of gateway-connected traffic only. Near-blind
  to the storm class — which made it the decisive falsification instrument
  for the gateway-re-injection hypothesis (MAHALO-1 §4.2).
- **Note:** the export includes operational configuration not suitable for
  redistribution; the operator has been notified through the intermediary.
  Only aggregate row counts are used here.

---

## What these captures cannot provide
A delivery ratio. No offered load was controlled; no denominator exists.
Characterizing what was *heard* is the ceiling of retrospective analysis.
Measuring what is *delivered* is the Sending Stones experiment (`DESIGN.md`).

## Contributors
Anonymized pending consent. To claim credit for any artifact, or to request
changes, open an issue or contact ORI. Credit will be added on request.
