# Query The Full GreenFlow Mar-Apr 2024 LPD/EPD Dataset

Open the DuckDB database:

```sql
SELECT COUNT(*) FROM final_ai_training_timeseries;
SELECT * FROM final_weather_timeseries LIMIT 10;
SELECT zone_id, SUM(lights_electricity_kwh), SUM(equipment_electricity_kwh), SUM(hvac_electricity_kwh)
FROM final_ai_training_timeseries
GROUP BY zone_id;
```

Main database:

`D:\VIN_HACKATHON_DATA\MAR_APR_2024_LPD_EPD_POSTPROCESS\greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd_dataset_20260626_093107\duckdb\greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd.duckdb`

Preview workbook:

`D:\VIN_HACKATHON_DATA\MAR_APR_2024_LPD_EPD_POSTPROCESS\greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd_dataset_20260626_093107\preview\greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd_preview.xlsx`
