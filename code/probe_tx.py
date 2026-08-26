#!/usr/bin/env python3
"""sending-stones probe transmitter (Rev B).

Every station runs this. Behavior per minute, per cohort:
  - Normal minute: transmit one probe at slot_start + U(0, jitter_max), payload
    length alternating short/long by seq parity.
  - Capture-trial minute (epoch_min % every_min == 0, station in partners):
    transmit at slot-second 0 of the MINUTE (i.e. second 0, both partners
    simultaneously), no jitter, flagged 'C'. Cohort alternates by trial index.

Offered load is defined by INTENT: tx_log row is written BEFORE the send call.
A failed send is data (api_status records it), not a missing denominator entry.

Payload format:  PDR|<cohort>|<station>|<seq>|<epoch>|<N or C>  padded with 'x'
to the target length. Announce this format on the con channels.

Requires: pip install meshtastic pyyaml
"""

import argparse
import itertools
import random
import socket
import time

import yaml

import db

try:
    import meshtastic.serial_interface as msi
except ImportError:  # allow bench work on machines without radios attached
    msi = None

HOST = socket.gethostname()


def build_payload(cohort, station, seq, is_capture, target_len):
    flag = "C" if is_capture else "N"
    core = f"PDR|{cohort}|{station}|{seq}|{int(time.time())}|{flag}"
    if len(core) < target_len:
        core += "|" + "x" * (target_len - len(core) - 1)
    return core[: max(target_len, len(core))]


class CohortRadio:
    """One serial-attached node dedicated to one cohort/preset."""

    def __init__(self, cohort, serial_path):
        self.cohort = cohort
        self.serial_path = serial_path
        self.iface = None
        self.seq = 0

    def connect(self, conn):
        if msi is None:
            raise RuntimeError("meshtastic package not installed")
        self.iface = msi.SerialInterface(devPath=self.serial_path)
        db.log_event(conn, HOST, "start", f"tx connect {self.cohort} {self.serial_path}")

    def send(self, conn, station, is_capture, target_len):
        self.seq += 1
        t_sched = time.time()
        conn.execute(
            "INSERT OR REPLACE INTO tx_log VALUES (?,?,?,?,?,?,?,?)",
            (station, self.cohort, self.seq, int(is_capture),
             target_len, t_sched, None, None),
        )
        payload = build_payload(self.cohort, station, self.seq, is_capture, target_len)
        status, t_sent = "ok", None
        try:
            # Broadcast on the primary channel of this radio's configured preset.
            self.iface.sendText(payload)
            t_sent = time.time()
        except Exception as e:  # noqa: BLE001 — any radio failure is data
            status = f"err:{type(e).__name__}:{e}"[:200]
        conn.execute(
            "UPDATE tx_log SET t_sent=?, api_status=? "
            "WHERE station=? AND cohort=? AND seq=?",
            (t_sent, status, station, self.cohort, self.seq),
        )
        return status


def sleep_until(t_target):
    while True:
        dt = t_target - time.time()
        if dt <= 0:
            return
        time.sleep(min(dt, 0.5))


def capture_participants(cap_cfg, epoch_min):
    """Return the set of stations transmitting in this capture trial, derived
    from the clock alone so every station computes it independently (no
    coordination traffic on the channel under test). Returns empty set if
    this minute is not a trial minute."""
    every = int(cap_cfg["every_min"])
    if epoch_min % every != 0:
        return set(), -1
    roster = sorted(cap_cfg["roster"])
    trial_index = epoch_min // every
    pairs = list(itertools.combinations(roster, 2))
    tw = cap_cfg.get("threeway", {})
    if tw.get("enabled", False) and trial_index % int(tw["every_nth_trial"]) == 0:
        triples = list(itertools.combinations(roster, 3))
        return set(triples[trial_index % len(triples)]), trial_index
    return set(pairs[trial_index % len(pairs)]), trial_index


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))

    station = cfg["station_id"]
    slot = int(cfg["slot"])
    slot_w = float(cfg["slot_width_s"])
    minute = float(cfg["minute_period_s"])
    jitter = float(cfg["jitter_max_s"])
    p_short = int(cfg["payload"]["short_len"])
    p_long = int(cfg["payload"]["long_len"])
    cap = cfg["capture_trials"]
    cap_enabled = bool(cap["enabled"]) and station in cap["roster"]

    conn = db.open_db(cfg["db_path"].format(station_id=station))
    radios = {}
    for cohort, c in cfg["cohorts"].items():
        r = CohortRadio(cohort, c["serial"])
        r.connect(conn)
        radios[cohort] = r

    if not cfg.get("tx_enabled", True):
        db.log_event(conn, HOST, "note", "tx_enabled=false; probe_tx idle")
        return

    db.log_event(conn, HOST, "start", f"probe_tx station={station} slot={slot}")

    while True:
        now = time.time()
        minute_start = (int(now // minute) + 1) * minute  # next minute boundary
        epoch_min = int(minute_start // 60)
        participants, trial_index = (
            capture_participants(cap, epoch_min) if cap_enabled else (set(), -1)
        )

        if station in participants:
            # H5: all participants fire at second 0 exactly — deliberate collision.
            cohort = "A" if (not cap.get("cohort_alternate", True)
                             or trial_index % 2 == 0) else "B"
            sleep_until(minute_start)  # no jitter, no slot offset: simultaneity is the point
            radios[cohort].send(conn, station, True, p_short)
            # Normal probe for the OTHER cohort still runs in our slot this minute:
            other = "B" if cohort == "A" else "A"
            t_probe = minute_start + slot * slot_w + random.uniform(0, jitter)
            sleep_until(t_probe)
            r = radios[other]
            tlen = p_short if (r.seq + 1) % 2 == 0 else p_long
            r.send(conn, station, False, tlen)
        else:
            t_probe = minute_start + slot * slot_w + random.uniform(0, jitter)
            sleep_until(t_probe)
            for r in radios.values():
                tlen = p_short if (r.seq + 1) % 2 == 0 else p_long
                r.send(conn, station, False, tlen)
                time.sleep(2.5)  # serialize our own two cohorts; cross-preset
                # collision is physically possible (different BW/SF share the band)
                # and there is no reason to self-collide across cohorts.


if __name__ == "__main__":
    main()
