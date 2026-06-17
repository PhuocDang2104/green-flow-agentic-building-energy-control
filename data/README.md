# Data

## 3D digital twin source — `enriched_IFC/`

The live 3D building and canonical data come from the **enriched IFC** set
(Nordic LCA office, IFC4, exported from Revit and enriched with a
`Pset_GreenFlow_Metadata` carrying floor/zone/room-type/controllability):

- `ARCH_AsBuilt_enriched.ifc` — architecture: 11 storeys, 308 IfcSpaces,
  walls/slabs/roofs/curtain walls/windows. Source of spaces, storeys, zones.
- `HVAC_enriched.ifc` — air distribution + equipment (ducts, air terminals,
  cooled beams, space heaters).
- `ELE_enriched.ifc` — electrical (light fixtures, outlets).
- `STRUCTURAL_enriched.ifc` — structural frame (columns, beams, slabs).

`python scripts/build_3d_assets_ifc.py` tessellates these with ifcopenshell
(world coordinates, shared recentre) into per-layer XKT for the xeokit viewer
and writes `db/seed/normalized_building.json` (a curated ~14 live thermal
zones; the full 308 spaces still render and are pickable). These IFC files are
large (HVAC ~350 MB) and are **git-ignored** — regenerate assets locally when
present.

## `greenflow_archetype.idf`

The original 5-zone EnergyPlus archetype. Still parsed by the IDF pipeline
(`scripts/build_3d_assets.py`, kept for reference/tests); the live demo now
uses the enriched IFC instead.

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
