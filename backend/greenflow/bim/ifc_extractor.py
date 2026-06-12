"""IFC extractor interface (P1 scaffold).

The MVP demo building is parsed from the EnergyPlus IDF archetype
(`idf_parser.py`). This module defines the extension point for the Nordic
Office IFC dataset in `data/ARCH/IFC`, `data/HVAC/IFC`. Implementing it
requires `ifcopenshell` and must follow the placement rules from
REPO_BUILD_SPEC §5.2:

- recursive IfcLocalPlacement -> 4x4 world matrix (never local placement
  as world coordinate)
- point-in-space footprint spatial join for point devices
- line/intersection mapping for ducts/pipes/cable trays
- floor alias mapping HVAC/ELE <-> ARCH
- reject device-zone mappings when contained_storey != mapped_floor

The output contract is the same normalized dict as
`normalized.build_normalized`, so the rest of the pipeline (seed, 3D assets,
agents) works unchanged once this is implemented.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class IfcExtractorNotImplemented(NotImplementedError):
    pass


def extract_ifc(arch_ifc: str | Path,
                hvac_ifc: str | Path | None = None,
                ele_ifc: str | Path | None = None) -> dict[str, Any]:
    """Extract a normalized building dict from IFC files.

    Raises IfcExtractorNotImplemented until the P1 implementation lands.
    """
    raise IfcExtractorNotImplemented(
        "IFC extraction is a P1 feature. Install ifcopenshell and implement "
        "extract_ifc() following REPO_BUILD_SPEC §5.2. The MVP uses "
        "idf_parser.parse_idf + normalized.build_normalized instead."
    )
