# Graph-RAG Example Questions

| question | answered from |
|---|---|
| Which board likely supplies this zone? | `ZONE_LOAD_ALLOCATED_TO_BOARD` edges + zone card |
| Which zones contribute most to a board's peak demand? | board timeseries + allocation weights |
| Which board has the highest estimated load? | `board_annual_summary.csv` (peak_total_kw) |
| Which load categories dominate this board? | `board_load_category_timeseries.parquet` |
| Which zones have high HVAC electricity during hot weather? | gold zone table × `final_weather_timeseries` |
| Which boards have missing ratings? | `board_annual_summary` overload_status=rating_missing |
| Which mappings are low confidence? | edges with confidence low/manual_review |
| Which electrical objects are unmapped? | `manual_review_items.csv` |
| Which HVAC devices serve a high-energy zone? | `HVAC_DEVICE_SERVES_ZONE` edges |
| Which IFC evidence supports this board→zone mapping? | edge `evidence_json` + system code |
| Is this overload warning measured, simulated, or estimated? | answer policy → estimated/rating_missing |
| What must be reviewed before using this for control? | `manual_review_items.csv` |
