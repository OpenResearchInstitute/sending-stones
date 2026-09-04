#!/usr/bin/env python3
"""sending-stones receive monitor (Rev B).

Runs on every station, always. For each cohort radio:
  - subscribes to all received packets; logs metadata + RF stats for everything,
    parses and fully logs OUR probe payloads (third-party payloads are NOT
    retained — metadata only, per design §7);
  - every census_period_s: snapshots the NodeDB (population lower bound);
  - every util_period_s: records local channelUtilization / airUtilTx;
  - watchdog: serial drop -> reconnect loop, gap logged to events.

Requires: pip install meshtastic pyyaml pypubsub
"""

import argparse
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
LOCK = threading.Lock()  # sqlite conn shared across pubsub callbacks


def parse_probe(text):
    """Return (probe_station, seq, is_capture) or None."""
    try:
        parts = text.split("|")
        if parts[0] != "PDR":
            return None
        return parts[2], int(parts[3]), parts[5].startswith("C")
    except (IndexError, ValueError):
        return None


class Monitor:
    def __init__(self, cfg):
        self.cfg = cfg
        self.station = cfg["station_id"]
        self.conn = db.open_db(cfg["db_path"].format(station_id=self.station))
        self.ifaces = {}   # cohort -> interface
        self.by_dev = {}   # devPath -> cohort

    # ---- packet path -----------------------------------------------------
    def on_receive(self, packet, interface):
        cohort = self.by_dev.get(getattr(interface, "devPath", None), "?")
        d = packet.get("decoded", {}) or {}
        port = d.get("portnum", "?")
        text = d.get("text") if port == "TEXT_MESSAGE_APP" else None
        probe = parse_probe(text) if text else None

        # RF metadata is present ONLY on over-the-air receptions — absent on
        # self-heard packets and ACKs. All optional; hops unknown unless both
        # hop fields present (a5fe "hop_start=0 means unknown" doctrine).
        hop_start = packet.get("hopStart")
        hop_limit = packet.get("hopLimit")
        hops = (hop_start - hop_limit) if (hop_start is not None
                                           and hop_limit is not None) else None

        payload = d.get("payload")
        plen = len(text) if text else (len(payload) if payload else None)

        # from_id: prefer the library's !hex string; fall back to building it
        # from the integer 'from' (present even when fromId is absent — ~15% of
        # relayed packets omit the string form).
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
        with LOCK:
            self.conn.execute(
                "INSERT INTO rx_log VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row
            )

    # ---- periodic tasks --------------------------------------------------
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

    # ---- lifecycle ---------------------------------------------------------
    def connect(self, cohort, dev):
        while True:
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
        # meshtastic pubsub also emits connection-lost:
        pub.subscribe(self.on_lost, "meshtastic.connection.lost")

        for cohort, c in self.cfg["cohorts"].items():
            self.connect(cohort, c["serial"])

        t_census = t_util = 0.0
        while True:
            now = time.time()
            if now - t_census >= self.cfg["census_period_s"]:
                self.census(); t_census = now
            if now - t_util >= self.cfg["util_period_s"]:
                self.utilization(); t_util = now
            time.sleep(1)


    def on_lost(self, interface):
        dev = getattr(interface, "devPath", "?")
        cohort = self.by_dev.get(dev, "?")
        with LOCK:
            db.log_event(self.conn, HOST, "serial_gap", f"{cohort} {dev} lost; reconnecting")
        try:
            interface.close()          # release old interface before reopening
        except Exception:
            pass
        threading.Thread(target=self.connect, args=(cohort, dev), daemon=True).start()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    Monitor(cfg).run()


if __name__ == "__main__":
    main()
