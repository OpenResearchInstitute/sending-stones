#!/usr/bin/env bash
# install-resilience.sh (v2) — harden a Sending Stones node.
#   1) run station.py as a systemd service (auto-start on boot, auto-restart on crash)
#   2) a SAFE connectivity watchdog that self-heals a truly isolated node
#
# v2 rewrites the watchdog after v1 catastrophically rebooted a dual-homed FB.
# The watchdog now does as little as possible and NEVER touches networking or
# reboots a node that still has a wired link or working internet.
#
# Idempotent. Run once per Stone:   sudo ./install-resilience.sh
# Re-running replaces the watchdog with this safe version and re-arms its timer.
# Assumes Raspberry Pi OS Bookworm (NetworkManager) and the mesh venv layout.
set -euo pipefail

[ "$(uname -s)" = Linux ] || { echo "Run this ON a Stone (a Raspberry Pi), not on the Mac."; exit 1; }

USER_NAME="${SUDO_USER:-abraxas3d}"
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
CODE_DIR="$HOME_DIR/Meshtastic/sending-stones/code"
PY="$HOME_DIR/mesh/bin/python3"
IFACE="${WIFI_IFACE:-wlan0}"

[ "$(id -u)" -eq 0 ] || { echo "run with sudo: sudo ./install-resilience.sh"; exit 1; }
[ -x "$PY" ]                 || { echo "venv python not found at $PY"; exit 1; }
[ -f "$CODE_DIR/station.py" ] || { echo "station.py not found in $CODE_DIR"; exit 1; }

echo "== 1/4  stop any existing logger (service or hand-started nohup) =="
systemctl stop sending-stones.service 2>/dev/null || true
pkill -f 'station.py --config' 2>/dev/null || true
sleep 2

echo "== 2/4  install the logger service =="
cat > /etc/systemd/system/sending-stones.service <<EOF
[Unit]
Description=Sending Stones station agent
# No network dependency on purpose — a station must keep logging to its local
# SD even when it is off the network.
After=multi-user.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$CODE_DIR
ExecStart=$PY -u station.py --config config.yaml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "== 3/4  install the SAFE connectivity watchdog =="
cat > /usr/local/sbin/wifi-watchdog.sh <<'EOF'
#!/usr/bin/env bash
# Sending Stones connectivity watchdog (safe revision).
#
# Rule: do as little as possible, and NEVER make a reachable node worse.
#   - Healthy (internet reachable by ANY route) -> touch nothing.
#   - No internet but eth0 has carrier -> node is still reachable to us over
#     LAN/Tailscale; take NO action (this is the dual-homed case v1 got wrong).
#   - Truly isolated (no internet AND no wired link) -> nudge ONLY wlan0, and
#     reboot only as a last resort with a loop guard.
# It never runs `nmcli networking off` and never reboots a wired node.
set -u
IFACE="${WIFI_IFACE:-wlan0}"
LOG=/var/log/wifi-watchdog.log
log(){ echo "$(date -Is) $*" >> "$LOG"; }

alive(){
  ping -c2 -W2 1.1.1.1 >/dev/null 2>&1 && return 0
  ping -c2 -W2 9.9.9.9 >/dev/null 2>&1 && return 0
  timeout 3 bash -c "echo > /dev/tcp/1.1.1.1/443" 2>/dev/null && return 0   # ICMP-blocked nets
  return 1
}

alive && exit 0

carrier=$(cat /sys/class/net/eth0/carrier 2>/dev/null || echo 0)
if [ "$carrier" = 1 ]; then
  log "no internet, but eth0 has carrier — node is wired/reachable; no action"
  exit 0
fi

log "isolated (no internet, no eth0 carrier) — recovering $IFACE"
nmcli radio wifi on            >/dev/null 2>&1 || true
nmcli device connect "$IFACE"  >/dev/null 2>&1 || true
sleep 25
alive && { log "recovered via $IFACE"; exit 0; }

up=$(cut -d. -f1 /proc/uptime 2>/dev/null || echo 0)
if [ "$up" -gt 900 ]; then
  log "still isolated after $IFACE recovery; rebooting (uptime ${up}s)"
  /sbin/reboot
else
  log "still isolated but uptime ${up}s < 900s; deferring reboot"
fi
EOF
chmod +x /usr/local/sbin/wifi-watchdog.sh

cat > /etc/systemd/system/wifi-watchdog.service <<EOF
[Unit]
Description=Sending Stones connectivity watchdog (one-shot)

[Service]
Type=oneshot
Environment=WIFI_IFACE=$IFACE
ExecStart=/usr/local/sbin/wifi-watchdog.sh
EOF

cat > /etc/systemd/system/wifi-watchdog.timer <<EOF
[Unit]
Description=Run the Sending Stones connectivity watchdog every 5 minutes

[Timer]
OnBootSec=3min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF

echo "== 4/4  enable everything =="
systemctl daemon-reload
systemctl enable --now sending-stones.service
systemctl enable --now wifi-watchdog.timer

echo
echo "---- result ----"
systemctl --no-pager --property=ActiveState,SubState show sending-stones.service | sed 's/^/sending-stones /'
systemctl --no-pager list-timers wifi-watchdog.timer | sed -n '1,2p'
echo "logger:        journalctl -u sending-stones -f"
echo "watchdog log:  /var/log/wifi-watchdog.log"
