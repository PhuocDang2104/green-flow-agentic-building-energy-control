# Electrical Graph Schema

See `knowledge_graph_build/graph_schema.md` for live node/edge type counts.

Node types: Building, Floor, ThermalZone, EnergyPlusZone, ElectricalBoard, Circuit,
LightFixture, Outlet, Alarm, CableTray, HVACDevice, PTAC, Meter, WeatherTimeseries.

Edge types: BUILDING_HAS_FLOOR, FLOOR_HAS_ROOM, ZONE_MAPS_TO_EPLUS_ZONE,
OBJECT_LOCATED_ON_FLOOR, OBJECT_ASSIGNED_TO_ZONE, BOARD_SUPPLIES_CIRCUIT,
CIRCUIT_SUPPLIES_LOAD_POINT, ZONE_LOAD_ALLOCATED_TO_BOARD, ZONE_LOAD_ALLOCATED_TO_CIRCUIT,
HVAC_DEVICE_SERVES_ZONE, ENERGYPLUS_PTAC_REPRESENTS_HVAC_FOR, ZONE_HAS_HVAC_LOAD,
WEATHER_CONTEXT_FOR_HVAC_LOAD, METER_MEASURES_ENTITY.

Every node carries `source_system`, `value_class`, `confidence`; every edge carries
`source`, `method`, `confidence`, `evidence_json`.
