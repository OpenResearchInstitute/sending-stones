# Sending Stones Station Setup Guide

Complete procedure to turn a blank Raspberry Pi OS card into a deployed,
remotely-reachable Sending Stones monitoring/PDR station. Follow top to bottom
per station. Steps that have to happen while physically on-site are marked
**[ON-SITE]** and like everything else can be done later over Tailscale.

Tested on: Raspberry Pi 4 (2GB) + Geekworm X728 UPS + Heltec V3 (US915),
Raspberry Pi OS Lite (64-bit), meshtastic-python 2.7.11, firmware 2.7.26.

---

## 0. Before you start

You need:
- Pi 4 imaged with Raspberry Pi OS Lite. During imaging (Raspberry Pi Imager
  gear/customize) set: hostname, enable SSH, your **home** WiFi + a known
  user/password. Turn on "verify after write". Eject cleanly.
- The X728 stack assembled (Pi and standoffs  X728  C1 case), or a bench Pi on
  a plain PSU for mules.
- A Heltec V3 flashed with Meshtastic (flasher.meshtastic.org,  Heltec V3, 
  latest stable, **standard install**, US region). NOT full-erase unless
  recovering a brick.
- The station's role name: FB | RFV | HRV | CHILL | COLD | SPARE (or a custom
  name like PALOMAR for a field-deployed unit).

---

## 1. First contact

Power the station. If using an X728, you may need to press its power button.
But I did not have to because I put in the jumper for auto-on. Remember to
remove the charge-control jumper before putting in the batteries.

Give it ~90 s to boot and join a network, then from your Mac or lesser computer:

    ssh <user>@<hostname>.local

If `.local` won't resolve, get grumpy and then find the IP in your router's 
DHCP client list and `ssh <user>@<ip>`. 
Pi MACs start with b8:27:eb / dc:a6:32 / e4:5f:01 / 2c:cf:67 (now I know)

**If it won't connect at all**, it's almost always the network, not the Pi:
- A plain USB-A-to-USB-C cable might be **power only** (ask me how I know) 
  and it might not give a network link and gives no serial console unless 
  USB gadget mode was pre-configured (it wasn't on a standard card). 
  Do not try to SSH "over USB".
- On a new site the Pi only knows your **home** WiFi. It won't join a different
  network. Fixes, easiest first:
  - **Ethernet cable** from the site router's LAN port, instant DHCP lease.
  - **Phone hotspot** named/passworded **identically to your home WiFi** the
    Pi joins it then SSH in then add the site WiFi (step 4).
  - **Monitor + USB keyboard** (Pi 4 = micro-HDMI) console login.

---

## 2. System update + timezone (UTC is mandatory)

    sudo apt update && sudo apt full-upgrade -y
    sudo timedatectl set-timezone UTC
    date                                # confirm UTC

Every timestamp in the data pipeline assumes UTC. 
Do not skip this. 
Ask me how I know.

---

## 3. Packages + I2C (for the X728 fuel gauge/RTC)

    sudo apt install -y python3-venv python3-pip git i2c-tools sqlite3
    sudo raspi-config nonint do_i2c 0   # enable I2C
    # (reboot later; or `sudo reboot` now if i2cdetect shows nothing)

Acceptance check for the X728 stack (after I2C enabled + reboot):

    i2cdetect -y 1
    # want to see 0x36 (MAX17048 fuel gauge) and 0x68 (DS1307 RTC)
    dmesg | grep -i volt                # empty = clean power, no brownouts!

`0x36` present proves the Pi to X728 GPIO stack seated correctly. Bench mules on a
plain PSU won't show these and that is totally ok don't get worried. 

---

## 4. Networking: Ethernet + WiFi + failover

Doctrine: **Ethernet preferred** (robust, survives hostile con WiFi), WiFi as
fallback, home WiFi kept so the station reconnects when it comes back to HQ.
NetworkManager stores multiple profiles and picks whatever is available. Adding
a network does NOT remove the others.

Add the site WiFi (quote SSID/password, use single quotes if they contain
spaces or shell characters like `$`):

    sudo nmcli device wifi connect 'SiteSSID' password 'sitepassword'
    nmcli connection show               # confirm home + site + wired all listed
    nmcli device status                 # wlan0 should say 'connected'

Optional: make Ethernet strongly preferred:

    sudo nmcli connection modify <wired-conn-name> connection.autoconnect-priority 100

**[ON-SITE] Test WiFi failover before you leave:** unplug Ethernet, wait ~15 s,
confirm still reachable (`nmcli device status` should keep wlan0 connected), and
check upstream:

    ping -c 3 1.1.1.1                   # clean = WiFi has real internet! Yay!

Then re-plug Ethernet if leaving it wired.

---

## 5. **[ON-SITE]** Tailscale to give remote access through any NAT

Home 5G/cellular backhaul is almost always CGNAT. Without a tunnel you can only
reach the station from inside its LAN, and lose it the moment you leave. Tailscale
punches through. **Set this up while physically present and TEST it before driving
away because it is miserable to fix remotely.**

On the station:

    curl -fsSL https://tailscale.com/install.sh | sh
    sudo tailscale up                   # follow the auth link; log in (e.g. GitHub)
    tailscale ip -4                     # note this 100.x.y.z address

On your Mac (once, if not already there):

    brew install tailscale && sudo tailscale up
    # log in with the SAME account/tailnet as the station

**Test from the Mac while still on-site:**

    ssh <user>@100.x.y.z                # the station's tailscale ip
    # or, with MagicDNS on:  ssh <user>@<hostname>

That address is now permanent and reachable from anywhere, on Ethernet or WiFi,
at home or at a con. This is the "remote hands" capability the fleet depends on.

---

## 6. Clone the repo + Python venv

    cd ~ && mkdir -p Meshtastic && cd Meshtastic
    git clone https://github.com/OpenResearchInstitute/sending-stones.git
    cd sending-stones
    python3 -m venv ~/mesh
    source ~/mesh/bin/activate
    pip install meshtastic==2.7.11 pyyaml pypubsub
    echo 'source ~/mesh/bin/activate' >> ~/.bashrc   # auto-activate on login

Pin meshtastic to the fleet version (2.7.11) so every station speaks the same
lingo. Later updates are a deliberate migration, not a surprise.

---

## 7. Name the radio + set region

With the Heltec attached:

    meshtastic --set-owner "Stone <Name>" --set-owner-short "<CODE>"
    meshtastic --set lora.region US
    ls /dev/serial/by-id/               # copy the CP2102 by-id path for the config

Use by-id paths, never /dev/ttyUSBn (enumeration order is not stable).

---

## 8. config.yaml

    cd ~/Meshtastic/sending-stones/code
    cp config.example.yaml config.yaml
    nano config.yaml

Per-station edits:
- `station_id:` the role code (e.g. COLD)
- `cohorts:` keep **only the cohorts you have radios for**. A one-radio
  monitoring node has just cohort A — **delete the cohort B block**, or the
  logger will hang/retry forever trying to open a nonexistent `CHANGE_ME_B`
  serial device.
- `cohorts.A.serial:` the by-id path from step 7
- `tx_enabled: false` for a monitoring/RX-only node (no probe transmission).
  `true` only when running probes with a controlled transmitter.
- `capture_trials.enabled: false` for a solo node.
- `db_path:` use a writable path — **`/home/<user>/mesh_pdr_{station_id}.sqlite`**,
  NOT `/data/...` (that root path doesn't exist / needs root and will crash).

Minimal one-radio monitoring config:

    station_id: COLD
    slot: 2
    slot_width_s: 12
    minute_period_s: 60
    cohorts:
      A:
        preset: LongFast
        serial: /dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0
    tx_enabled: false
    jitter_max_s: 3.0
    payload:
      short_len: 20
      long_len: 180
    capture_trials:
      enabled: false
      roster: [FB, RFV, HRV, CHILL, COLD]
      every_min: 10
      cohort_alternate: false
      threeway:
        enabled: false
        every_nth_trial: 7
    census_period_s: 600
    util_period_s: 60
    db_path: /home/abraxas3d/mesh_pdr_{station_id}.sqlite
    log_level: INFO

---

## 9. Verify the code before running

    cd ~/Meshtastic/sending-stones/code
    python3 -m py_compile monitor_rx.py && echo "syntax OK"
    python3 -c "import monitor_rx; print('methods:', \
      hasattr(monitor_rx.Monitor,'on_receive'), \
      hasattr(monitor_rx.Monitor,'on_established'))"

Want `syntax OK` and both methods `True`. `on_established` present = the
NodeDB-replay gate is in this checkout (drops connect-time replay so only live
receptions are logged). py_compile catches syntax and the hasattr check catches a
method accidentally de-indented out of the class.

---

## 10. First-light aperture scan (capture it)

    meshtastic --nodes | tee ~/<name>-firstlight-nodes.txt

Save this becuase the node list + SNR distribution characterizes the site's aperture.
High/clear sites show much stronger SNR (near 0 dB) than low/cluttered ones
(near -20 dB, the decode floor). Commit to `data/bench/` as a site record.

---

## 11. Start the logger (detached, unbuffered)

    cd ~/Meshtastic/sending-stones/code
    nohup python3 -u monitor_rx.py --config config.yaml > ~/<name>-soak.log 2>&1 &
    echo $! > ~/<name>.pid
    sleep 90 && sqlite3 ~/mesh_pdr_<STATION_ID>.sqlite \
      "SELECT COUNT(*) rx FROM rx_log; SELECT COUNT(*) util FROM utilization;"

The `-u` (unbuffered) is mandatory for a backgrounded logger. Without it stdout
buffers and the log looks dead even while it's working. Non-zero counts = it's
logging. Note: on a quiet channel `rx` grows slowly; `util` ticks up ~1/min
regardless (it polls the local radio), so a climbing `util` alone proves the
loop is alive.

Stop it later with `kill $(cat ~/<name>.pid)`.

---

## 12. Leaving / handoff checklist

Before you walk away from an on-site deployment, confirm:
- [ ] Reachable over Tailscale from the Mac (`ssh <user>@100.x.y.z`)
- [ ] wlan0 connected (WiFi fallback proven) AND/OR Ethernet plugged (preferred)
- [ ] `ping 1.1.1.1` clean (upstream exists for the tunnel)
- [ ] logger running (`pgrep -af monitor_rx`) and DB row counts climbing
- [ ] first-light `--nodes` scan saved
- [ ] radio named, region US, OLED shows the station name

Everything after step 5 can be redone remotely over Tailscale, so you can
get power + network + Tailscale working on-site, then finish the
software from home!

---

## Known gotchas (learned the hard way)

- **USB cable might not give you a network.**
- **Wrong-WiFi silence.** A Pi at a new site with only home credentials boots
  fine and joins nothing and is invisible. Ethernet or hotspot-mimic to get in.
- **`db_path: /data/...`** crashes (no such dir / needs root). Use home dir.
- **Leftover `CHANGE_ME_B` cohort** makes the logger retry a dead serial device
  forever. Delete unused cohorts. Put them back in when you get a second radio.
- **`fromId` vs `from_id`**, **SQLite thread ownership**, and **NodeDB replay**
  are all handled in the current `monitor_rx.py`/`db.py` just don't regress
  them. The replay gate (`on_established` → `self.live`) is why the DB doesn't
  fill with stale connect-time replay packets.
- **Bad SD cards** fail imaging randomly ("some work, some don't"). Verify-on-
  write, and retire any card that fails a clean re-image twice then use a spare.
- **X728 power** goes IN via the X728's USB-C, not the Pi's own port, once the
  board is installed.
- **Possibly avoid full-erase** flash the Heltec with the instructions from the
  event because there might be bugs or weirdness. Ask around and research before
  just doing the usual standard firmware updates. 
