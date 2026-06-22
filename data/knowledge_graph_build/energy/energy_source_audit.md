# Energy Source Audit

**Energy source of truth:** the existing patched dataset under `data/final`
(`final_zone_device_power_timeseries`), scenario `openmeteo_2025_30min_baseline`,
30-minute timestep (0.5 h), full-year 2025. EnergyPlus is **not**
re-run; the IDF (`IDF_FILE.idf`) is parsed for object names + provenance only
and is left byte-stable. No `eplusout.sql` is present.

## IDF object inventory (top classes)
- IDF Timestep: `2` per hour
- `BuildingSurface:Detailed`: 1848
- `Zone`: 308
- `People`: 308
- `Lights`: 308
- `ElectricEquipment`: 308
- `DesignSpecification:OutdoorAir`: 308
- `ZoneInfiltration:DesignFlowRate`: 308
- `Sizing:Zone`: 308
- `ThermostatSetpoint:DualSetpoint`: 305
- `ZoneControl:Thermostat`: 305
- `OutdoorAir:Node`: 305
- `OutdoorAir:Mixer`: 305
- `Coil:Cooling:DX:SingleSpeed`: 305
- `Coil:Heating:Electric`: 305
- `Fan:OnOff`: 305
- `ZoneHVAC:PackagedTerminalAirConditioner`: 305
- `ZoneHVAC:EquipmentList`: 305
- `ZoneHVAC:EquipmentConnections`: 305
- `Output:Variable`: 23
- `Schedule:Compact`: 10

## Per-category source columns (zone-level, EnergyPlus simulated)
- lights → `lights_electricity_kw` / `lights_electricity_kwh_interval`
- equipment (plug) → `equipment_electricity_kw` / `equipment_electricity_kwh_interval`
- hvac → `final_hvac_electricity_kw` / `final_hvac_electricity_kwh_interval`
  (composed from fan + cooling/heating coil + PTAC columns by the postprocess)
- total (validation only) → `final_total_zone_electricity_kw`

Zone↔EnergyPlus identity is already carried in the gold table
(`zone_id` ↔ `eplus_zone_name`); 308 zones.

## Building meters (validation)
- `InteriorEquipment:Electricity`
- `Heating:EnergyTransfer`
- `Cooling:EnergyTransfer`
- `Fans:Electricity`
- `Cooling:Electricity`
- `Electricity:Facility`
- `Electricity:HVAC`
- `Heating:Electricity`
- `Electricity:Building`
- `InteriorLights:Electricity`
