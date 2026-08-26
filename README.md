# Sending Stones

*The spell always works during a long rest. We measured whether it works in the tavern.*

Sending Stones is a delivery-ratio experiment for dense-event Meshtastic networks
such as found at amateur radio and computer security conferences. DC35 is the modeled
target for this implementation, but the experiment can be run at any dense event. 

Five identical matched-pair stations ("Stones") measure packet delivery ratio
with a known denominator. 

- `DESIGN.md` the experiment design (Rev B): domain model, hypotheses H1–H5,
  schedule, confound table, build plan
- `code/` station software: probe TX (slot scheduler + capture trials),
  RX monitor, collation
- `analysis/` **MAHALO** (*Mesh Assessment of Heard And Lost Offerings*),
  the analysis notebook
- `hardware/` BOM, station build details, bench/field notes (Phase 0–2)
- `data/` published trial datasets (post-con; node IDs salted-hashed per DESIGN §7)

Stations: Stone-FB Stone-RFV Stone-HRV Stone-CHILL Stone-COLD Stone of Reserve (spare)

License: GPL-3 
