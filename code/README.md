# Sending Stones, a delivery-ratio instrument for dense-event Meshtastic (Rev B)

Five identical stations. Each: Pi 4 + 2x Heltec V3 (cohort A: LongFast,
cohort B: ShortTurbo/event channel) + UPS-buffered AC. Role = config.yaml.

## Install (per station)
    sudo apt install python3-pip
    pip install meshtastic pypubsub pyyaml
    cp config.example.yaml config.yaml   # set station_id, slot, serial by-id paths
    python3 monitor_rx.py &              # always on
    python3 probe_tx.py &                # all stations transmit in Rev B

(systemd units recommended for deployment; run both under Restart=always.)

## Schedule model
- Minute cycle; station k owns seconds [12k, 12k+12).
- Normal probe: slot start + U(0,3) s jitter, per cohort, short/long payload
  alternating by seq parity. Probes never collide with each other by construction.
- H5 capture trial: every 10th minute, a ROTATING PAIR. Derived from the
  clock and the shared roster, no coordination traffic; all 10 pairs cycle
  every 100 min. Transmits at second 0 exactly (deliberate collision),
  alternating cohorts, flagged C. The other three stations listen.
  Optional 3-way trials behind a config flag (default off; Phase 2 gate).

## Post-con
    python3 collate.py stations/*.sqlite -o trials.csv
Produces trials.csv (H1–H4) + trials_h5.csv (capture trials), with
self-deafness excision and utilization covariates. Analyze in Python/MATLAB.

## Validated so far
- Payload build/parse round trip (short + long + capture flag + rejects garbage)
- End-to-end synthetic two-station run through collate.py recovers known
  injected loss rates within binomial error (n=30/path)

## Bench TODO (Phase 0, radio in hand)
- Confirm rx packet dict fields (hopStart/hopLimit, rxRssi) against current
  meshtastic-python version. We should adjust monitor_rx.on_receive if names drift
- deviceMetrics polling path for channelUtilization on local node
- Plug-yank UPS test under live logging
- Verify sendText targets primary channel on event firmware (cohort B)
