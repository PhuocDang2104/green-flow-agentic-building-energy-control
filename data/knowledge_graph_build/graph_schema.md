# Knowledge Graph Schema

Nodes: **5705**, Edges: **13446**

## Node types
- `CableTray`: 1784
- `LightFixture`: 1408
- `HVACDevice`: 1234
- `ThermalZone`: 308
- `EnergyPlusZone`: 308
- `PTAC`: 305
- `Outlet`: 187
- `Circuit`: 80
- `ElectricalBoard`: 57
- `Alarm`: 12
- `Floor`: 10
- `Meter`: 10
- `Building`: 1
- `WeatherTimeseries`: 1

## Relationship types
- `OBJECT_LOCATED_ON_FLOOR`: 3477
- `OBJECT_ASSIGNED_TO_ZONE`: 3476
- `CIRCUIT_SUPPLIES_LOAD_POINT`: 1607
- `HVAC_DEVICE_SERVES_ZONE`: 1185
- `ZONE_LOAD_ALLOCATED_TO_BOARD`: 1032
- `ZONE_LOAD_ALLOCATED_TO_CIRCUIT`: 1032
- `FLOOR_HAS_ROOM`: 308
- `ZONE_MAPS_TO_EPLUS_ZONE`: 308
- `ZONE_HAS_HVAC_LOAD`: 308
- `WEATHER_CONTEXT_FOR_HVAC_LOAD`: 308
- `ENERGYPLUS_PTAC_REPRESENTS_HVAC_FOR`: 305
- `BOARD_SUPPLIES_CIRCUIT`: 80
- `BUILDING_HAS_FLOOR`: 10
- `METER_MEASURES_ENTITY`: 10

Every node carries source_system/value_class/confidence; every edge carries source/method/confidence/evidence. Confidence ∈ {exact,high,medium,low,manual_review}.
Boards are distribution assets and are never modelled as consuming loads.