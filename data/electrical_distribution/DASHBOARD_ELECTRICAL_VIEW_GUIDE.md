# Dashboard Electrical View Guide

`dashboard_electrical_manifest.json` drives the frontend: layers (boards, load points,
cable trays, zones, HVAC), metrics (peak kW, annual kWh, loading %), colour scales
(loading/overload), entity types, click→API actions, and badges (warning, low-confidence,
manual-review, rating-missing).

Views: building overview, floor electrical, zone energy, board, circuit, graph-RAG.
Board/zone/floor payloads come from `backend/greenflow/electrical/dashboard.py` `build_*`
functions, served by `api/routers/electrical.py`.
