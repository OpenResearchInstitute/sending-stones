import json, time
from pubsub import pub
import meshtastic.serial_interface as msi

def dump(packet, interface):
    print(json.dumps(packet, indent=2, default=str))
    print("=" * 60)

pub.subscribe(dump, "meshtastic.receive")
iface = msi.SerialInterface()
print("listening...")
while True: time.sleep(1)
