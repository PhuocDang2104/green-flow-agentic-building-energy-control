# Data

## Tracked in git

- `greenflow_archetype.idf` — the demo building (5 thermal zones, EnergyPlus IDF).
  This is the **only** model the runnable app needs. The whole pipeline
  (3D assets, seed, simulation, agents) is driven from it.

## NOT in git (excluded via .gitignore)

The Nordic LCA reference BIM dataset is large CAD/BIM binary source
(`.ifc`, `.rvt`, `.pla`) totalling ~3.7 GB across:

- `ARCH/` — architecture (Revit / ArchiCAD / IFC, specifications)
- `HVAC/` — MEP / HVAC / electrical (MagiCAD-for-Revit / IFC, schedules)
- `STRUCTURAL/` — structural models

These exceed GitHub's 100 MB/file limit and are **not required to run
GreenFlow**. They are reference material for the **P1 IFC extractor**
(`backend/greenflow/bim/ifc_extractor.py`).

To work on IFC extraction, place the dataset back under `data/ARCH`,
`data/HVAC`, `data/STRUCTURAL` (kept out of version control) or store it in
object storage / Git LFS / a release asset and point the extractor at it.
