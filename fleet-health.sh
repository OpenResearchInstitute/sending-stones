#!/usr/bin/env bash
# fleet-health.sh — one-glance health of every Sending Stones node.
# Run from Blue-Palace anytime. Uses Tailscale names + your SSH key; needs no
# sudo (every check is read-only). A station that's alive and logging shows
# LOGGER=active, WATCHDOG=active, CLOCK=sync, and a small DB_AGE (seconds since
# its database was last written — i.e. since it last logged a packet).
set -u

STONES=(stone-fb stone-rfv stone-hrv stone-chill stone-spare)
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=6 -o BatchMode=yes)

# remote probe: prints  logger|watchdog|clock|db_age_seconds
REMOTE='
  N=$(hostname | sed "s/^stone-//" | tr a-z A-Z)
  db="$HOME/mesh_pdr_$N.sqlite"
  svc=$(systemctl is-active sending-stones 2>/dev/null || echo "?")
  wd=$(systemctl is-active wifi-watchdog.timer 2>/dev/null || echo "?")
  clk=$(timedatectl show -p NTPSynchronized --value 2>/dev/null)
  [ "$clk" = "yes" ] && clk=sync || clk=NOSYNC
  if   [ -e "$db-wal" ]; then m=$(stat -c %Y "$db-wal")
  elif [ -e "$db" ];     then m=$(stat -c %Y "$db")
  else m=0; fi
  if [ "$m" -gt 0 ]; then age=$(( $(date +%s) - m )); else age=noDB; fi
  echo "$svc|$wd|$clk|$age"
'

printf '%-13s %-9s %-9s %-7s %-10s\n' STONE LOGGER WATCHDOG CLOCK DB_AGE
printf '%-13s %-9s %-9s %-7s %-10s\n' ------------- --------- --------- ------- ----------
for s in "${STONES[@]}"; do
  out=$(ssh "${SSH_OPTS[@]}" "abraxas3d@$s" "$REMOTE" 2>/dev/null) || out="UNREACHABLE|||"
  IFS='|' read -r svc wd clk age <<<"$out"
  # flag anything that isn't healthy
  [ "$svc" = active ] || svc="*${svc:-?}"
  if   [ -z "$age" ];        then age="-"
  elif [ "$age" = noDB ];    then :
  elif [ "$age" -gt 120 ] 2>/dev/null; then age="${age}s(!)"
  else age="${age}s"; fi
  printf '%-13s %-9s %-9s %-7s %-10s\n' "$s" "${svc:-?}" "${wd:-?}" "${clk:-?}" "${age:-?}"
done

echo
echo "healthy row = LOGGER active, WATCHDOG active, CLOCK sync, DB_AGE small (< ~90s)."
echo "'*inactive' logger, NOSYNC clock, or DB_AGE with (!) = that stone needs a look."
