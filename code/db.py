"""sending-stones: SQLite schema + minimal writer helpers.

WAL mode so probe_tx.py and monitor_rx.py can share one DB file per station
without stepping on each other. All timestamps are UTC epoch seconds (float).
"""

import sqlite3
import time
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS tx_log (
  station     TEXT NOT NULL,
  cohort      TEXT NOT NULL,          -- 'A' | 'B'
  seq         INTEGER NOT NULL,
  is_capture  INTEGER NOT NULL DEFAULT 0,
  payload_len INTEGER NOT NULL,
  t_sched     REAL NOT NULL,          -- when the scheduler intended to send
  t_sent      REAL,                   -- just after API send call returned
  api_status  TEXT,                   -- 'ok' | error string
  PRIMARY KEY (station, cohort, seq)
);

CREATE TABLE IF NOT EXISTS rx_log (
  station     TEXT NOT NULL,
  cohort      TEXT NOT NULL,          -- which local radio heard it
  t_rx        REAL NOT NULL,
  from_id     TEXT,
  to_id       TEXT,
  portnum     TEXT,
  is_probe    INTEGER NOT NULL DEFAULT 0,
  is_capture  INTEGER NOT NULL DEFAULT 0,
  probe_station TEXT,                 -- parsed from probe payload
  probe_seq   INTEGER,
  payload_len INTEGER,
  rssi        REAL,
  snr         REAL,
  hops        INTEGER                 -- hop_start - hop_limit when available
);
CREATE INDEX IF NOT EXISTS rx_probe_idx
  ON rx_log (probe_station, cohort, probe_seq) WHERE is_probe = 1;

CREATE TABLE IF NOT EXISTS census (
  station    TEXT NOT NULL,
  cohort     TEXT NOT NULL,
  t          REAL NOT NULL,
  node_id    TEXT NOT NULL,
  last_heard REAL,
  snr        REAL
);

CREATE TABLE IF NOT EXISTS utilization (
  station     TEXT NOT NULL,
  cohort      TEXT NOT NULL,
  t           REAL NOT NULL,
  ch_util     REAL,                   -- channelUtilization (%)
  air_util_tx REAL                    -- airUtilTx (%)
);

CREATE TABLE IF NOT EXISTS events (
  host   TEXT NOT NULL,
  t      REAL NOT NULL,
  kind   TEXT NOT NULL,               -- power|timesync|serial_gap|start|stop|note
  detail TEXT
);
"""


def open_db(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0, isolation_level=None)  # autocommit
    conn.executescript(SCHEMA)
    return conn


def log_event(conn, host: str, kind: str, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO events VALUES (?,?,?,?)",
        (host, time.time(), kind, detail),
    )
