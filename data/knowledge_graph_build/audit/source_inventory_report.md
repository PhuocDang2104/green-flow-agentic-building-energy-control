# Source Inventory Report

**Building:** Nordic LCA Office

## IFC files (enriched)
| discipline | exists | role / key content |
|---|---|---|
| ARCH | True | spatial master — storeys + spaces |
| ELE  | True | boards=True, lights=True, outlets=True, cable-trays=True; **Finnish** property sets |
| HVAC | True | HVAC device graph |
| STRUCT | True | structural context |

### ELE product counts
- `IfcLightFixture`: 1419
- `IfcCableCarrierSegment`: 1185
- `IfcCableCarrierFitting`: 616
- `IfcOutlet`: 188
- `IfcElectricDistributionBoard`: 57
- `IfcAlarm`: 12
- `IfcBuildingStorey`: 7
- `IfcBuildingElementProxy`: 1
- `IfcBuilding`: 1
- `IfcSite`: 1

## EnergyPlus / gold dataset (energy source of truth — not re-simulated)
- IDF: `IDF_FILE.idf` (zone-level model, byte-stable)
- DuckDB: `greenflow_final_mode_b_plus_openmeteo_2025_30min_patched-001.duckdb` (present: True)
- Parquet grains: final_ai_training_timeseries, final_building_meter_timeseries, final_device_electricity_timeseries, final_device_power_timeseries, final_weather_timeseries, final_zone_device_power_timeseries
- **Best table for board allocation:** `final_zone_device_power_timeseries`
  (per-zone lights/equipment/HVAC kW + kWh-interval), 308 zones, scenario `openmeteo_2025_30min_baseline`
- Building meters (validation): InteriorEquipment:Electricity, Heating:EnergyTransfer, Cooling:EnergyTransfer, Fans:Electricity, Cooling:Electricity, Electricity:Facility, Electricity:HVAC, Heating:Electricity, Electricity:Building, InteriorLights:Electricity
- `eplusout.sql`: **not present** → using the patched Parquet/DuckDB outputs
- Data dictionary: `final_data_dictionary_patched.csv`

## Mappings
- xeokit object map present: True
- graph/ERD exports present: False (this pipeline creates them)
