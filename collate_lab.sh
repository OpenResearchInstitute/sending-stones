#!/usr/bin/env bash
# collate_lab.sh — sending-stones lab delivery matrix (slice-pull edition, v2)
#
# WHAT THIS DOES:
#   Runs two window-scoped SELECTs on each station over SSH and pulls back only
#   the matching rows as CSV. Bandwidth scales with the WINDOW, not with DB
#   history. No file copy, no checkpoint — a SELECT-only read under WAL never
#   blocks or touches the live writer.
#
# JOIN SEMANTICS (identical to the old full-copy script, so numbers match):
#   probe-level set-intersection,  delivery = |sent ∩ received| / |sent|,
#   keyed on (probe_station, cohort, probe_seq).  seq ALONE is never the key.
#
# v2 fixes vs v1:
#   - DB referenced by BARE filename, resolved against the remote login home
#     (exactly like the old `scp host:mesh_pdr_X.sqlite`). No hardcoded
#     /home/<user> assumption — that was why v1 failed on every station.
#   - Each remote call is ONE line (legible quoting).
#   - stderr is NOT suppressed: a failed slice prints sqlite's real error.
#
# Usage:  ./collate_lab.sh [window_seconds]     (default 600)

set -uo pipefail

WIN="${1:-600}"
CUT=$(( $(date +%s) - WIN ))          # epoch cutoff; UTC-agnostic, needs NTP-synced Pis

# fleet: NAME  ssh-alias   — THE ONE LIST TO EDIT. Add a station here and it is
# both pulled AND shown in the matrix (order below = matrix row/column order).
# To add Palomar later, drop in a line: "COLD   stone-cold"  (single-cohort until
# it gets a 2nd radio — its cohort B row will just read '.', which is correct).
FLEET=(
  "FB     stone-fb"
  "RFV    stone-rfv"
  "HRV    stone-hrv"
  "CHILL  stone-chill"
  "SPARE  stone-spare"
)
# derive the ordered station-name list from FLEET (single source of truth)
NAMES=""
for row in "${FLEET[@]}"; do read -r n _ <<<"$row"; NAMES="$NAMES $n"; done
NAMES="${NAMES# }"
# Remote login user. These stations authenticate as abraxas3d (where the DBs
# live); without this, ssh falls back to your LOCAL Mac username and hits a
# password wall. Override with REMOTE_USER=... if a station differs.
REMOTE_USER="${REMOTE_USER:-abraxas3d}"
# If a station keeps its db somewhere other than the login home, set DBDIR to
# that absolute dir WITH a trailing slash, e.g. DBDIR="/home/abraxas3d/".
# Default empty = bare filename in the remote home (the proven scp behavior).
DBDIR="${DBDIR:-}"
OUTDIR="$HOME/Meshtastic/lab-collate"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10)

mkdir -p "$OUTDIR"
SENT="$OUTDIR/_sent.csv"; RECV="$OUTDIR/_recv.csv"
: > "$SENT"; : > "$RECV"

echo "== pulling slices (window=${WIN}s, cutoff epoch=${CUT}) =="
for row in "${FLEET[@]}"; do
  read -r NAME HOST <<<"$row"
  DBFILE="${DBDIR}mesh_pdr_${NAME}.sqlite"
  printf '  %-6s <- %s\n' "$NAME" "$HOST"

  # what this station SENT (denominators): station,cohort,seq
  ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${HOST}" \
    "sqlite3 -batch -noheader -csv \"$DBFILE\" \"SELECT station,cohort,seq FROM tx_log WHERE api_status='ok' AND t_sched >= $CUT;\"" \
    >> "$SENT" || echo "    ! sent-slice failed for $NAME (error above)"

  # what this station RECEIVED (numerators): recv,probe_station,cohort,probe_seq
  ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${HOST}" \
    "sqlite3 -batch -noheader -csv \"$DBFILE\" \"SELECT DISTINCT '$NAME',probe_station,cohort,probe_seq FROM rx_log WHERE is_probe=1 AND t_rx >= $CUT;\"" \
    >> "$RECV" || echo "    ! recv-slice failed for $NAME (error above)"
done

echo
python3 - "$SENT" "$RECV" "$NAMES" <<'PY'
import csv, sys
from collections import defaultdict

sent_csv, recv_csv = sys.argv[1], sys.argv[2]
stations = sys.argv[3].split()          # order + membership come from FLEET

# sent[(station,cohort)] = set(seq)
sent = defaultdict(set)
with open(sent_csv) as f:
    for r in csv.reader(f):
        if len(r) != 3: continue
        st, co, seq = r[0].strip(), r[1].strip(), r[2].strip()
        if seq == "": continue
        sent[(st, co)].add(int(seq))

# recv[receiver] = set((probe_station, cohort, probe_seq))
recv = defaultdict(set)
with open(recv_csv) as f:
    for r in csv.reader(f):
        if len(r) != 4: continue
        rx, ps, co, seq = (x.strip() for x in r)
        if seq == "": continue
        recv[rx].add((ps, co, int(seq)))

def matrix(cohort):
    print(f"--- cohort {cohort} : delivery = |sent ∩ received| / |sent| ---")
    hdr = "sender\\recv |" + "".join(f"{s:>8}" for s in stations) + "   | sent"
    print(hdr)
    print("-" * (len(hdr)))
    for X in stations:
        denomset = sent.get((X, cohort), set())
        n = len(denomset)
        cells = []
        for Y in stations:
            if Y == X:
                cells.append(f"{'--':>8}")
            elif n == 0:
                cells.append(f"{'.':>8}")
            else:
                want = {(X, cohort, s) for s in denomset}
                frac = len(want & recv.get(Y, set())) / n
                cells.append(f"{frac:>8.2f}")
        print(f"{X:>10} |" + "".join(cells) + f"   | {n}")
    print("  cells = fraction of sender's probes that receiver actually logged (0..1).")
    print("  lab (0-hop): expect ~1.00.  '--' self,  '.' sender sent nothing.\n")

print("== delivery matrix (probe-level join) ==\n")
matrix("A")
matrix("B")
PY

echo "== done.  slices + output in $OUTDIR =="
