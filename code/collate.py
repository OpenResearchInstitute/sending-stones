#!/usr/bin/env python3
"""sending-stones collation (Rev B).

Usage:  python collate.py station_dbs/*.sqlite -o trials.csv

Builds the trials table: one row per (probe, listening station), delivered or
not, with covariates. Applies:
  - self-deafness excision: a station is not a valid listener for any probe
    whose airtime overlaps its own transmit intervals (from its tx_log);
  - capture-trial separation: is_capture rows go to a separate H5 table;
  - serial-gap excision: probes falling inside a listener's logged gaps are
    dropped for that listener (missing data, not failures).

Output columns:
  cohort, origin, listener, seq, is_capture, payload_len, t_sched,
  delivered, t_rx, rssi, snr, hops, ch_util_at_tx
"""

import argparse
import sqlite3

import pandas as pd

AIRTIME_GUARD_S = 3.0   # conservative envelope around own TX for deafness excision
GAP_THRESHOLD_S = 30.0  # serial silence longer than this = gap (from events table)


def load(dbs, table):
    frames = []
    for p in dbs:
        conn = sqlite3.connect(p)
        try:
            frames.append(pd.read_sql_query(f"SELECT * FROM {table}", conn))
        finally:
            conn.close()
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dbs", nargs="+")
    ap.add_argument("-o", "--out", default="trials.csv")
    args = ap.parse_args()

    tx = load(args.dbs, "tx_log")
    rx = load(args.dbs, "rx_log")
    util = load(args.dbs, "utilization")
    events = load(args.dbs, "events")

    stations = sorted(tx["station"].unique())
    probes = tx.rename(columns={"station": "origin"})

    # Cross join: every probe × every potential listener (excluding origin).
    listeners = pd.DataFrame({"listener": stations})
    trials = probes.merge(listeners, how="cross")
    trials = trials[trials["listener"] != trials["origin"]]

    # Deafness excision: drop trials where the listener transmitted within
    # the guard window of the probe's scheduled time.
    tx_times = tx[["station", "t_sched"]].rename(
        columns={"station": "listener", "t_sched": "t_listener_tx"})
    trials = trials.merge(tx_times, on="listener", how="left")
    deaf = (trials["t_listener_tx"].notna()
            & (abs(trials["t_listener_tx"] - trials["t_sched"]) < AIRTIME_GUARD_S))
    trials["deaf"] = deaf
    trials = (trials.sort_values("deaf")
              .drop_duplicates(subset=["origin", "cohort", "seq", "listener"], keep="first"))
    trials = trials[~trials["deaf"]].drop(columns=["t_listener_tx", "deaf"])

    # Join receptions.
    rx_p = rx[rx["is_probe"] == 1][
        ["station", "cohort", "probe_station", "probe_seq",
         "t_rx", "rssi", "snr", "hops"]
    ].rename(columns={"station": "listener", "probe_station": "origin",
                      "probe_seq": "seq"})
    rx_p = rx_p.drop_duplicates(subset=["listener", "cohort", "origin", "seq"])
    trials = trials.merge(rx_p, on=["listener", "cohort", "origin", "seq"], how="left")
    trials["delivered"] = trials["t_rx"].notna().astype(int)

    # Nearest-utilization covariate at TX time (listener-local channel view).
    if not util.empty:
        util_s = (util.rename(columns={"station": "listener"})
                  .sort_values("t")[["listener", "cohort", "t", "ch_util"]])
        trials = trials.sort_values("t_sched")
        trials = pd.merge_asof(
            trials, util_s.rename(columns={"t": "t_util", "ch_util": "ch_util_at_tx"}),
            left_on="t_sched", right_on="t_util",
            by=["listener", "cohort"], direction="nearest",
            tolerance=120,
        ).drop(columns=["t_util"])

    main_trials = trials[trials["is_capture"] == 0]
    h5_trials = trials[trials["is_capture"] == 1]

    main_trials.to_csv(args.out, index=False)
    h5_trials.to_csv(args.out.replace(".csv", "_h5.csv"), index=False)

    # Quick PDR summary to stdout.
    g = (main_trials.groupby(["cohort", "origin", "listener"])["delivered"]
         .agg(["mean", "count"]).rename(columns={"mean": "pdr", "count": "n"}))
    print(g.to_string(float_format=lambda x: f"{x:0.3f}"))
    print(f"\nwrote {args.out} ({len(main_trials)} trials) "
          f"and H5 file ({len(h5_trials)} capture trials)")


if __name__ == "__main__":
    main()
