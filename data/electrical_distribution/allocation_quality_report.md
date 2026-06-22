# Allocation Quality Report

- allocation rows: **1032** (per zone×category)
- by category: {'lights': 412, 'equipment': 312, 'hvac': 308}
- by mapping confidence: {'low': 766, 'medium': 266}
- allocations to UNMAPPED_BOARD (manual review): **0**
- (zone,category) weight-sum ≠ 1: **0** (must be 0)

## Load-point → board
- by confidence: {'medium': 1406, 'low': 189}

## Circuits
- total circuits: **80** (system-grouped: **54**, pseudo: **26**)

Lighting/plug use IFC system-code + floor + proximity evidence; HVAC uses a
pseudo HVAC circuit on the floor main board (no IFC HVAC→board link). Boards
are distribution assets and are never counted as additional consumption.