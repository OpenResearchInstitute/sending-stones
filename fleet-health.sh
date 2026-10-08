#!/usr/bin/env bash
# fleet-health.sh — one-glance health of every Sending Stones node.
# Run from Blue-Palace anytime. Read-only; uses your SSH key (no sudo).
# A healthy stone shows LOGGER=active, CLOCK=sync, and a small DB_AGE
# (seconds since it last wrote its database). WATCHDOG reflects the timer
# state (inactive is fine while the watchdog is parked).
set -u

STONES=(stone-fb stone-rfv stone-hrv stone-chill stone-spare)
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o BatchMode=yes)

# remote probe: prints exactly one line  logger|watchdog|clock|db_age_seconds
# NOTE: `systemctl is-active` prints a word AND exits non-zero when inactive,
# so capture it plainly (no `|| echo`, which would add a second line and break
# the parse) and force a single line with head -n1.
REMOTE='
  N=$(hostname | sed "s/^stone-//" | tr a-z A-Z)
  db="$HOME/mesh_pdr_$N.sqlite"
  svc=$(systemctl is-active sending-stones 2>/dev/null | head -n1)
  wd=$(systemctl is-active wifi-watchdog.timer 2>/dev/null | head -n1)
  clk=$(timedatectl show -p NTPSynchronized --value 2>/dev/null)
  [ "$clk" = "yes" ] && clk=sync || clk=NOSYNC
  if   [ -e "$db-wal" ]; then m=$(stat -c %Y "$db-wal")
  elif [ -e "$db" ];     then m=$(stat -c %Y "$db")
  else m=0; fi
  if [ "$m" -gt 0 ]; then age=$(( $(date +%s) - m )); else age=noDB; fi
  printf "%s|%s|%s|%s\n" "$svc" "$wd" "$clk" "$age"
'

probe(){ ssh "${SSH_OPTS[@]}" "abraxas3d@$1" "$REMOTE" 2>/dev/null | head -n1; }

printf '%-13s %-9s %-9s %-7s %-10s\n' STONE LOGGER WATCHDOG CLOCK DB_AGE
printf '%-13s %-9s %-9s %-7s %-10s\n' ------------- --------- --------- ------- ----------
for s in "${STONES[@]}"; do
  out=$(probe "$s")                       # try Tailscale name (direct)
  [ -n "$out" ] || out=$(probe "$s.local")  # fall back to mDNS on the LAN
  [ -n "$out" ] || out="UNREACHABLE|||"
  IFS='|' read -r svc wd clk age <<<"$out"
  [ "$svc" = active ] || svc="*${svc:-?}"
  if   [ -z "$age" ];                    then age="-"
  elif [ "$age" = noDB ];                then :
  elif [ "$age" -gt 120 ] 2>/dev/null;   then age="${age}s(!)"
  else age="${age}s"; fi
  printf '%-13s %-9s %-9s %-7s %-10s\n' "$s" "${svc:-?}" "${wd:-?}" "${clk:-?}" "${age:-?}"
done

echo
echo "healthy = LOGGER active, CLOCK sync, DB_AGE small (< ~90s)."
echo "WATCHDOG inactive is expected while the watchdog is parked."
echo "'*' on LOGGER, NOSYNC clock, or DB_AGE (!) = that stone needs a look."
