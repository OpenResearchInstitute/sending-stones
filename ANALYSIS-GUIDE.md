# How to Analyze the Stations

---

## 0. What do we Have?

Five+ stations (**FB, RFV, HRV, CHILL, SPARE, and COLD on Palmoar**), 
each has a Raspberry Pi 4 with **two** Heltec V3 radios connected.

- **cohort A = LongFast** (BW 250 kHz, SF11)
- **cohort B = ShortTurbo** (BW 500 kHz, SF7)

Every station both **transmits** timed probe packets and **logs** every probe it
hears, into one SQLite DB per station (`mesh_pdr_<NAME>.sqlite`, WAL mode). The
question we're after is packet delivery ratio. 

Specifically, **LongFast vs ShortTurbo packet delivery**, or any A vs. any B 
packet delivery comparison that can be configured on the radios. 

The two presets compute to *different* center frequencies because the channel
slot count depends on the bandwidth (~104 slots at 250 kHz vs ~52 at 500 kHz). 
So cohort A and cohort B in this case are independent and non-interfering 
populations sharing the band.

Measured channel utilization was ~20% on A's frequency and ~0% on B's. 
We can run both at once without them stepping on each other.

---

## 1. How to run the Analysis

- From something like a laptop, in `~/Meshtastic/sending-stones`.
- The Pis are reached over **Tailscale** by ssh aliases: `stone-fb`, `stone-rfv`,
  `stone-hrv`, `stone-chill`, `stone-spare`, `stone-cold`.
- `collate_lab.sh` hardcodes `REMOTE_USER=abraxas3d`. 
- If **nothing** connects then check Tailscale is up (`tailscale status`) before
  blaming the stations.

---

## 2. Everything Still Running?

Before any matrix, confirm all five loggers are up and actually logging. The
one-command check is the health tool:

```bash
./fleet-health.sh
```

Healthy fleet = every row **LOGGER active, WATCHDOG active, CLOCK sync**, and a
small **DB_AGE** (seconds since that stone last wrote its database). Anything
flagged — `*inactive` logger, `NOSYNC` clock, `DB_AGE` with `(!)`, or
`UNREACHABLE` — is the stone to look at.

To dig into one stone:

```bash
ssh abraxas3d@stone-<name>.local 'systemctl status sending-stones --no-pager'
ssh abraxas3d@stone-<name>.local 'journalctl -u sending-stones -f'   # watch it live
```

- **Logger not `active`?** Start it: `sudo systemctl start sending-stones`
  (Section 6). Do NOT launch it by hand with `nohup` — it's a systemd service
  now, and a hand-started copy would fight the service over the serial port.
- **DB_AGE large / `(!)`** (service claims active but isn't writing)? The radios
  may be deaf — wrong region or wrong preset. See Section 5.
- **`UNREACHABLE`?** The stone is off the network (or a slow name path). It keeps
  logging to its local SD regardless; reach it over `.local` or reconnect it.

> The logger is a **systemd service** (`sending-stones`) — it auto-starts on boot
> and auto-restarts on crash. That's the fix for the thing that bit us hard: the
> old hand-started `nohup` logger silently died on a reboot and nobody noticed for
> ~22 hours. **Manage it with `systemctl start/stop`, never `pkill`** — systemd
> respawns a killed process in 5 seconds.

---

## 3. Run the Collation (like collating papers)

```bash
./collate_lab.sh 600        # 600-second (10-minute) window
```

This pulls only the window's probe rows from each station (not the whole DB!) and
prints two delivery matrices, cohort A and cohort B.

A freshly restarted station needs to sit inside a common time window with the others 
before its row means anything. Otherwise its denominator is tiny and the numbers 
look scary for no reason (see Section 4, small-denominator trap). Just wait the 10
minutes and it will be good. 

---

## 4. Enter the Matrix (the whole point of the experiment)

Each cell = **fraction of that sender's probes that that receiver actually logged**,
`|sent ∩ received| / |sent|`, in this window
Rows = sender, columns = receiver.
`--` is self, `.` means the sender sent nothing. The `sent` column is the
**denominator**, which is how many probes that sender put on the air.

**What it should look like on the bench:** ~**1.00** almost everywhere, in
*both* cohorts, as **one coherent block** per cohort.

**The small-denominator trap.** Read the `sent` column *before* reacting to a
low cell. If a station sent only 4 probes, one miss is 0.75 and that is a
quantization, not a bad link. Low cells on a station with a small `sent` count,
especially one just restarted, are almost always quantization artifacts.
Re-run after it has a full window before believing them or getting stressed.

**A genuinely bad link** is a cell that stays low *with a full denominator*,
in a *stable* window, on a *specific* pair. That's when you go chase one radio
and not before.

---

## 5. Failures and Stuff

| Symptom in the data | Cause | Fix |
|---|---|---|
| A station hears **nothing** from anyone (its receive column all `.`/0), logger running | `lora.region` was **UNSET (0)** on that Pi's radios, and therefore radio is deaf/mute | `meshtastic --set lora.region US` on each of its radios (`--port /dev/ttyUSB0` and `/dev/ttyUSB1`) |
| Cohort **B splits into two islands** (two ~1.00 groups, ~0 between) | Some B-radios still on **LongFast** (250/SF11) instead of **ShortTurbo** | `meshtastic --set lora.modem_preset SHORT_TURBO` on the offending B radio (usually `/dev/ttyUSB1`) then verify |
| Delivery cell **> 1.00** (impossible!) | Old bug: count/count division across mis-aligned pull windows | Already fixed, but the join is now probe-level set-intersection. Should not see this again. |
| A station has **two radios but only one cohort logs** | Both radios grabbed the same cohort, or a serial path collided | Check `config.yaml` cohort serials use **`/dev/serial/by-path/`**, not `by-id` (all CP2102 chips report serial `0001`, so `by-id` is ambiguous — `by-path` is stable per physical USB port) |
| Two stations' probes **overwrite each other** which makes a station's numbers look duplicated | Two stations share the same `slot` | `slot` must be **unique per station**: FB=0, RFV=1, HRV=2, CHILL=3, COLD=4, SPARE=5 |
| Everything looks connected but no probes flow | USB cable seated but radio not actually enumerated | A USB cable is power **and** data so reseat, re-check `/dev/serial/by-path/`. |

---

## 6. Operating the fleet safely

Each Stone runs `station.py` as a **systemd service** called `sending-stones`.
It starts automatically on boot and restarts within 5 seconds if it ever exits,
so a reboot or a crash no longer silently stops data collection. It has **no
network dependency** on purpose. A Stone keeps logging to its local SD card
even when it is off the network.

### Day-to-day control

systemd owns the logger now so **do not `pkill` station.py**, or it will respawn
in 5 seconds. Use systemctl:

| Task | Command |
|---|---|
| Stop the logger (e.g. to free the serial ports for `meshtastic` config) | `sudo systemctl stop sending-stones` |
| Start it again | `sudo systemctl start sending-stones` |
| Is it running? | `systemctl is-active sending-stones` |
| Full status | `systemctl status sending-stones` |
| Watch it live! | `journalctl -u sending-stones -f` |

A manual `stop` does work. `Restart=always` only respawns on an *unexpected*
exit, not when you deliberately stop it. It will still auto-start on the next
reboot. For longer maintenance or when you don't want that, also
`sudo systemctl disable sending-stones` (and `enable` when done).

Install (or re-install) the service:

```bash
sudo ./install-resilience.sh
```

`station.py` is restart-safe: it resumes each cohort's seq counter from the DB,
so a restart doesn't reset the experiment. Hard won!

**The golden deletion rule.** While `station.py` is running, a station's live
`mesh_pdr_<THIS>.sqlite` and its `-wal` / `-shm` are **off-limits**. Deleting a
live WAL out from under the writer loses in-flight data. Learned the hard way!

**Don't checkpoint or open a DB with a glob.** `sqlite3 ~/mesh_pdr_*.sqlite "..."`
opens the *wrong* file on a multi-match and fails silently. Always name the one
file. Leanred the hard way!

---

## 7. Shutting Everything Down Safely

`for s in stone-fb stone-rfv stone-hrv stone-chill stone-spare; do
  echo "== $s =="; ssh abraxas3d@$s 'sudo shutdown -h now'
done`

---

## 8. Glossary

- **PDR** — Packet Delivery Ratio: of the probes a sender put on the air, the
  fraction a given receiver logged.
- **cohort A / cohort B** — the two radios per station; A runs LongFast, B runs
  ShortTurbo. Different presets have different center frequencies so they're independent.
- **probe** — a timed packet, payload `PDR|<cohort>|<station>|<seq>|<epoch>|<N|C>`.
  The transmit intent is logged **before** the send, so a failed send is *data*
  (a recorded denominator with an error status), not a missing row.
- **the join key** — `(probe_station, cohort, probe_seq)`. Don't use `probe_seq`
  alone because cohorts A and B share the same seq number space, so seq-only would
  cross-match A's probe #7 with B's probe #7. This is the single most important
  correctness invariant in the whole analysis. Learned the hard way.
- **denominator = intent, not success** — the `sent` count comes from the
  sender's `tx_log` where `api_status='ok'`; the numerator comes from the
  receiver's `rx_log` where `is_probe=1`.

---
