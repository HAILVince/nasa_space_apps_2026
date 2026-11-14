# Raw PSI experiment tables - Combustion Science

Unprocessed source data (intake folder: the knowledge store does not read it as records).

- `tables/PSI-<id>_<name>.csv` - the "Experimental table" of each investigation, bytes exactly as
  downloaded from NASA PSI on 2026-11-14 (22 files, 2,870 data rows). Only the file names were
  simplified; `manifest.json` maps each file to its original PSI name, SHA-256, row count and columns.
- `psi_combustion_index.csv` - one row per investigation (title, objectives, keywords, data volume).
- `psi_tables_overview.csv` - what one row of each table means and whether it holds results or only test settings.
- `psi_publications.csv` - publications PSI lists for the solid-fuel and smoke investigations, with open NTRS PDFs where found.

The tables are messy on purpose (this is the raw layer): free-text cells such as `~ 22.1`,
`037 mm` (= 0.37 mm), `3400%` (= 34 %), `Complete`, `Acceleratory`. Cleaned values with provenance
live in `flame/data/envelopes.json`; never edit these files - add a cleaning step instead.

Source and citation: NASA Physical Sciences Informatics, https://psi.nasa.gov - cite each
investigation's dataset DOI (in `flame/data/investigations.json`).
