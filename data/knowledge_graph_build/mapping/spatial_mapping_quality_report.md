# Spatial Mapping Quality Report

- Canonical floors (ARCH storeys): **10**
- Zones (IfcSpace): **308**, joined to gold EnergyPlus zone_id: **308**
- Electrical objects located: **3477**

## Floor assignment (IFC storey containment)
- with floor (high confidence): **3477**
- floor unresolved: **0**

## Zone assignment (nearest IfcSpace centroid, same floor)
- medium (≤6 m): **3169**
- low (≤16 m): **307**
- manual_review (no nearby space / no coords): **1**

## Coordinate-frame diagnostic
- median |xy| electrical objects: 50.6 m; ARCH space centroids: 51.8 m → **aligned**

Floor is the reliable spatial key (storey containment); zone-per-object is
best-effort and is **not** required for board allocation, which works at
floor + system-code + category level.