#!/usr/bin/env python3
"""sending-stones unified station agent (Rev C).

Replaces running monitor_rx.py and probe_tx.py as two processes — which is
IMPOSSIBLE, because a serial port can be held by only one process, and each
script opened its own SerialInterface. This single process opens each cohort
radio ONCE and does both jobs through that one interface:

  RX  (reader thread, pubsub):  logs every received packet's metadata + RF
      stats to rx_log; parses and flags OUR probe payloads. NodeDB replay is
      gated out until connection.established.
  TX  (dedicated scheduler thread): transmits scheduled probes on this
      station's slot, with jitter, alternating short/long by seq parity;
      runs H5 capture-trial deliberate collisions at second 0. Offered load
      is defined by INTENT — the tx_log row is written BEFORE the send.
  Periodics (main thread): census (NodeDB snapshot) and utilization every
      configured period.

All three threads share the SAME open interfaces and write to the SAME sqlite
connection under one LOCK. TX transmits through Monitor.ifaces[cohort] — the
very interface the RX path is subscribed to — so there is no second open and
no port-lock conflict.

Config: unchanged from the two-script version (same keys). tx_enabled=false
runs a pure passive monitor (no TX thread) — the correct config for survey
stations (e.g. Palomar baseline).

Requires: pip install meshtastic pyyaml pypubsub
"""

import argparse
import itertools
import random
import socket
import threading
import time

import yaml
from pubsub import pub

import db

try:
    import meshtastic.serial_interface as msi
except ImportError:
    msi = None

HOST = socket.gethostname()
LOCK = threading.Lock()  # guards the shared sqlite connection across all threads


# --------------------------------------------------------------------------
# helpers (lifted verbatim from monitor_rx.py / probe_tx.py — behavior preserved)
# --------------------------------------------------------------------------
def parse_probe(text):
    """Return (probe_station, seq, is_capture) or None. (from monitor_rx)"""
    try:
        parts = text.split("|")
        if parts[0] != "PDR":
            return None
        return parts[2], int(parts[3]), parts[5].startswith("C")
    except (IndexError, ValueError):
        return None


def build_payload(cohort, station, seq, is_capture, target_len):
    """PDR|<cohort>|<station>|<seq>|<epoch>|<N|C>  padded with x. (from probe_tx)"""
    flag = "C" if is_capture else "N"
    core = f"PDR|{cohort}|{station}|{seq}|{int(time.time())}|{flag}"
    if len(core) < target_len:
        core += "|" + "x" * (target_len - len(core) - 1)
    return core[: max(target_len, len(core))]


def sleep_until(t_target):
    """Sleep in short hops until wall-clock reaches t_target. (from probe_tx)"""
    while True:
        dt = t_target - time.time()
        if dt <= 0:
            return
        time.sleep(min(dt, 0.5))


def capture_participants(cap_cfg, epoch_min):
    """Clock-derived set of stations transmitting in this capture trial, so
    every station computes it independently with no coordination traffic on the
    channel under test. Empty set if this minute is not a trial minute.
    (from probe_tx — unchanged)"""
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


# --------------------------------------------------------------------------
class Station:
    def __init__(self, cfg):
        self.cfg = cfg
        self.station = cfg["station_id"]
        self.conn = db.open_db(cfg["db_path"].format(station_id=self.station))
        self.ifaces = {}          # cohort -> the ONE SerialInterface (RX + TX share it)
        self.by_dev = {}          # devPath -> cohort
        self.live = False         # gate: True only after connection.established
        self.seq = {}             # cohort -> monotonically increasing probe seq
        self._stop = threading.Event()

    # ---- RX path (runs on meshtastic reader thread via pubsub) -----------

    def _resume_seq(self):
        """FIX 1 (durability): continue seq numbering past any tx_log rows already
        in this database, so a restart never reuses a seq from a prior run. Without
        this, seq restarts at 1 and collides with earlier probes. Called once at
        startup, before the TX thread begins."""
        with LOCK:
            for cohort in self.cfg["cohorts"]:
                row = self.conn.execute(
                    "SELECT MAX(seq) FROM tx_log WHERE station=? AND cohort=?",
                    (self.station, cohort),
                ).fetchone()
                self.seq[cohort] = row[0] if row and row[0] is not None else 0
        if any(self.seq.values()):
            with LOCK:
                db.log_event(self.conn, HOST, "note",
                             f"resumed seq from db: {dict(self.seq)}")

    def on_established(self, interface, topic=pub.AUTO_TOPIC):
        self.live = True
        with LOCK:
            db.log_event(self.conn, HOST, "note", "connection established; live logging on")

    def on_receive(self, packet, interface):
        if not self.live:
            return                 # drop NodeDB replay during connect
        print(f"RX from={packet.get('fromId')} port={packet.get('decoded',{}).get('portnum','ENC')}", flush=True)
        cohort = self.by_dev.get(getattr(interface, "devPath", None), "?")
        d = packet.get("decoded", {}) or {}
        port = d.get("portnum", "?")
        text = d.get("text") if port == "TEXT_MESSAGE_APP" else None
        probe = parse_probe(text) if text else None

        hop_start = packet.get("hopStart")
        hop_limit = packet.get("hopLimit")
        hops = (hop_start - hop_limit) if (hop_start is not None
                                           and hop_limit is not None) else None

        payload = d.get("payload")
        plen = len(text) if text else (len(payload) if payload else None)

        fnum = packet.get("from")
        from_id = packet.get("fromId") or (f"!{fnum:08x}" if fnum is not None else None)

        row = (
            self.station, cohort, time.time(),
            from_id, packet.get("toId"), str(port),
            1 if probe else 0,
            1 if (probe and probe[2]) else 0,
            probe[0] if probe else None,
            probe[1] if probe else None,
            plen,
            packet.get("rxRssi"),
            packet.get("rxSnr"),
            hops,
        )
        try:
            with LOCK:
                self.conn.execute(
                    "INSERT INTO rx_log VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row
                )
        except Exception as e:  # noqa: BLE001
            print(f"INSERT FAILED for {packet.get('fromId')}: {e}", flush=True)

    def on_lost(self, interface):
        self.live = False
        dev = getattr(interface, "devPath", "?")
        cohort = self.by_dev.get(dev, "?")
        with LOCK:
            db.log_event(self.conn, HOST, "serial_gap", f"{cohort} {dev} lost; reconnecting")
        try:
            interface.close()
        except Exception:
            pass
        threading.Thread(target=self.connect, args=(cohort, dev), daemon=True).start()

    # ---- TX path (transmits through the SAME interface RX is using) ------
    def send_probe(self, cohort, is_capture, target_len):
        """Write intent to tx_log, transmit via the shared interface, record result.
        (send() logic lifted from probe_tx.CohortRadio, using self.ifaces[cohort].)"""
        self.seq[cohort] = self.seq.get(cohort, 0) + 1
        seq = self.seq[cohort]
        t_sched = time.time()
        # FIX 3 (durability): plain INSERT, not INSERT OR REPLACE. A seq collision
        # (which _resume_seq makes impossible in normal operation) must be LOUD, not
        # a silent clobber of a prior run's probe. If it ever happens, log it and
        # skip this probe rather than overwrite data or crash the TX thread.
        try:
            with LOCK:
                self.conn.execute(
                    "INSERT INTO tx_log VALUES (?,?,?,?,?,?,?,?)",
                    (self.station, cohort, seq, int(is_capture),
                     target_len, t_sched, None, None),
                )
        except Exception as e:  # e.g. sqlite3.IntegrityError on PK collision
            with LOCK:
                db.log_event(self.conn, HOST, "note",
                             f"tx_log collision cohort={cohort} seq={seq}: {e}; probe skipped")
            return f"skip:collision:{type(e).__name__}"
        payload = build_payload(cohort, self.station, seq, is_capture, target_len)
        status, t_sent = "ok", None
        iface = self.ifaces.get(cohort)
        try:
            if iface is None:
                raise RuntimeError(f"cohort {cohort} interface not connected")
            iface.sendText(payload)       # the SAME open interface RX is subscribed to
            t_sent = time.time()
        except Exception as e:  # noqa: BLE001 — any radio failure is data
            status = f"err:{type(e).__name__}:{e}"[:200]
        with LOCK:
            self.conn.execute(
                "UPDATE tx_log SET t_sent=?, api_status=? "
                "WHERE station=? AND cohort=? AND seq=?",
                (t_sent, status, self.station, cohort, seq),
            )
        return status

    def tx_scheduler(self):
        """Precise probe scheduler — its own thread so sleep_until can hit
        sub-second slot / capture-second-0 targets without being coupled to the
        coarse census/util periodics. (main loop lifted from probe_tx.main.)"""
        c = self.cfg
        station = self.station
        slot = int(c["slot"])
        slot_w = float(c["slot_width_s"])
        minute = float(c["minute_period_s"])
        jitter = float(c["jitter_max_s"])
        p_short = int(c["payload"]["short_len"])
        p_long = int(c["payload"]["long_len"])
        cap = c["capture_trials"]
        cap_enabled = bool(cap["enabled"]) and station in cap["roster"]

        with LOCK:
            db.log_event(self.conn, HOST, "start", f"tx scheduler station={station} slot={slot}")

        while not self._stop.is_set():
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
                sleep_until(minute_start)      # no jitter, no slot offset: simultaneity is the point
                self.send_probe(cohort, True, p_short)
                # Normal probe for the OTHER cohort still runs in our slot this minute:
                other = "B" if cohort == "A" else "A"
                t_probe = minute_start + slot * slot_w + random.uniform(0, jitter)
                sleep_until(t_probe)
                tlen = p_short if (self.seq.get(other, 0) + 1) % 2 == 0 else p_long
                self.send_probe(other, False, tlen)
            else:
                t_probe = minute_start + slot * slot_w + random.uniform(0, jitter)
                sleep_until(t_probe)
                for cohort in self.ifaces.keys():
                    tlen = p_short if (self.seq.get(cohort, 0) + 1) % 2 == 0 else p_long
                    self.send_probe(cohort, False, tlen)
                    time.sleep(2.5)  # serialize our own two cohorts; no reason to self-collide

    # ---- periodics (main thread) -----------------------------------------
    def census(self):
        t = time.time()
        with LOCK:
            for cohort, iface in self.ifaces.items():
                for node_id, n in (iface.nodes or {}).items():
                    self.conn.execute(
                        "INSERT INTO census VALUES (?,?,?,?,?,?)",
                        (self.station, cohort, t, node_id,
                         n.get("lastHeard"), n.get("snr")),
                    )

    def utilization(self):
        t = time.time()
        with LOCK:
            for cohort, iface in self.ifaces.items():
                try:
                    m = (iface.nodesByNum.get(iface.localNode.nodeNum, {})
                         .get("deviceMetrics", {}))
                except Exception:  # noqa: BLE001
                    m = {}
                self.conn.execute(
                    "INSERT INTO utilization VALUES (?,?,?,?,?)",
                    (self.station, cohort, t,
                     m.get("channelUtilization"), m.get("airUtilTx")),
                )

    # ---- lifecycle -------------------------------------------------------
    def connect(self, cohort, dev):
        while not self._stop.is_set():
            try:
                iface = msi.SerialInterface(devPath=dev)
                self.ifaces[cohort] = iface
                self.by_dev[dev] = cohort
                with LOCK:
                    db.log_event(self.conn, HOST, "start", f"rx connect {cohort} {dev}")
                return
            except Exception as e:  # noqa: BLE001
                with LOCK:
                    db.log_event(self.conn, HOST, "serial_gap",
                                 f"{cohort} {dev} connect fail: {e}")
                time.sleep(5)

    def run(self):
        if msi is None:
            raise RuntimeError("meshtastic package not installed")
        pub.subscribe(self.on_receive, "meshtastic.receive")
        pub.subscribe(self.on_established, "meshtastic.connection.established")
        pub.subscribe(self.on_lost, "meshtastic.connection.lost")

        for cohort, cc in self.cfg["cohorts"].items():
            self.connect(cohort, cc["serial"])

        self._resume_seq()   # FIX 1: continue seq past existing tx_log rows

        # Start the TX scheduler thread ONLY if this station transmits.
        # tx_enabled=false => pure passive monitor (survey stations, Palomar).
        if self.cfg.get("tx_enabled", True):
            threading.Thread(target=self.tx_scheduler, daemon=True).start()
        else:
            with LOCK:
                db.log_event(self.conn, HOST, "note", "tx_enabled=false; passive monitor, no TX thread")

        # Main thread: census/util periodics (coarse 1s tick is fine for these).
        t_census = t_util = 0.0
        while True:
            now = time.time()
            if now - t_census >= self.cfg["census_period_s"]:
                self.census(); t_census = now
            if now - t_util >= self.cfg["util_period_s"]:
                self.utilization(); t_util = now
            time.sleep(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    Station(cfg).run()


if __name__ == "__main__":
    main()
