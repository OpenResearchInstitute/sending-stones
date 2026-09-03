# MAHALO-1 — What the DEF CON 34 Captures Actually Contained

*Mesh Assessment of Heard And Lost Offerings · Notebook 1 · Sending Stones project · Open Research Institute*

**Abstract.** Five privately-shared captures of the DEF CON 34 Meshtastic mesh — an
app-level datalog, a duplicates-preserving device-trace database at a high-elevation
aperture (Fontainebleau 31st floor), a PHY-layer SDR capture at the Sahara, a broker-side
export, and an engineered merge of all four — were joined to characterize the RF
environment in which the LongFast-vs-ShortTurbo preset debate was argued. Census brackets
the claimed 2,500+ nodes (2,123 / 2,782 unique senders at two apertures). At the
high-elevation aperture, a pathological traffic class — packets re-originated at machine
rate by ~10 node identities with elevated hop budgets on an undecrypted channel —
accounted for ≥62% of channel bytes. Two mechanism hypotheses (immortal TTL-stripped
packets; MQTT gateway re-injection) were proposed and disconfirmed by the data; the storm
was RF-side, node-specific, and audible across the Strip. Every app-level logging method
at the con was structurally blind to it. **No capture contains a delivery ratio; none can.**

**Files.**
- `MAHALO-1-dc34-captures.ipynb` — the analysis, outputs stripped. Fully reproducible
  against local copies of the captures (see `../../data/dc34/PROVENANCE.md` for what they
  are). All storm-node and storm-packet identifiers are **derived from the source database
  at runtime** — nothing is hardcoded, and no side-files are required.
- `MAHALO-1-dc34-captures.pdf` — the executed, citable artifact.

**Data.** Not included, at the contributors' request. Node identifiers render as rank
labels (S1–S10); the raw-ID mapping exists only in memory during a run. Collectors are
credited by handle where known.

**Reproduce.** Place the captures locally, edit the paths in the parameters cell, then
Kernel → Restart & Run All. The notebook derives storm identities from the data; there is
no hidden dependency to satisfy.

**Consequences for Sending Stones** — the experiment these findings motivate — are in
notebook §5 and the top-level `DESIGN.md`.
