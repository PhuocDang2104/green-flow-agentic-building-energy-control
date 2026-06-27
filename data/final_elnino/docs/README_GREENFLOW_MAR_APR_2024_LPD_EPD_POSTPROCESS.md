# GreenFlow Final Mode B+ Mar-Apr 2024 LPD/EPD Dataset

This package postprocesses the Phase 3 Mar-Apr 2024 EnergyPlus run into a queryable
GreenFlow analytics dataset.

## Scope

- Period: 2024-03-01 to 2024-04-30
- Year retained: 2024
- Records per hour: 2
- Timesteps: 2928
- Zones: 308
- Zone-time rows: 901824

## Main Outputs

- DuckDB: `D:\VIN_HACKATHON_DATA\MAR_APR_2024_LPD_EPD_POSTPROCESS\greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd_dataset_20260626_093107\duckdb\greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd.duckdb`
- Preview workbook: `D:\VIN_HACKATHON_DATA\MAR_APR_2024_LPD_EPD_POSTPROCESS\greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd_dataset_20260626_093107\preview\greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd_preview.xlsx`
- Validation: `docs/final_validation_report.json`
- Data dictionary: `docs/final_data_dictionary.csv`

## Core Tables

- `final_weather_timeseries`
- `final_ai_training_timeseries`
- `final_zone_device_power_timeseries`
- `final_device_power_timeseries`
- `final_building_meter_timeseries`
- `final_zone_energy_summary`
- `final_room_type_energy_summary`
- `energy_balance_summary`
- `final_data_dictionary`

## Validation Status

`passed`
