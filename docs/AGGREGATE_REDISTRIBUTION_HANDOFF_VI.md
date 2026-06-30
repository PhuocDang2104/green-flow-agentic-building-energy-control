# Aggregate redistribution handoff

Tài liệu này tóm tắt trạng thái triển khai hiện tại để teammate tiếp tục review và
đánh giá số liệu.

## 1. Trạng thái hiện tại

Production VM đang chạy:

```text
GREENFLOW_ENERGY_SCOPE_MODE=redistribute
GREENFLOW_TELEMETRY_SCOPE_MODE=redistribute
```

Mục tiêu: không cộng trực tiếp các zone aggregate như `VOLUME / OFFICE`, `GFA`,
`Gross Area Placeholder` vào dashboard/KPI. Load, energy, occupancy, cost của
aggregate được phân bổ lại xuống child zones theo weight diện tích.

Kết quả reload telemetry gần nhất:

```text
901,824 raw rows -> 843,264 effective rows
aggregate rows redistributed = 58,560
unmapped aggregates = 0
```

UI/API hiện dùng 288 visible/countable zones:

```text
atomic_energy_zone = 210
review_required = 78
aggregate_context = 0 visible telemetry rows
```

## 2. Code paths chính

- Scope classifier: `backend/greenflow/energy_scope.py`
- Child-zone weighting: `backend/greenflow/zone_redistribution.py`
- Human-readable zone names: `backend/greenflow/zone_naming.py`
- Electrical KG scope phase: `backend/greenflow/electrical/scope.py`
- Telemetry materialization: `scripts/load_real_data.py`
- Dashboard zone API: `backend/greenflow/agent/tools/db_tool.py`
- Run Optimization semantic count: `backend/greenflow/agent/nodes/building_semantic.py`

Generated mapping:

```text
data/knowledge_graph_build/mapping/zone_scope_child_weights.csv
data/knowledge_graph_build/mapping/zone_scope_redistribution_report.json
```

Review list:

```text
docs/ZONE_ENERGY_SCOPE_REVIEW_LIST.csv
docs/ZONE_ENERGY_SCOPE_REVIEW_NOTES.md
```

## 3. Verify nhanh trên VM

```bash
cd /opt/green-flow-agentic-building-energy-control
docker compose exec -T api printenv GREENFLOW_ENERGY_SCOPE_MODE
docker compose exec -T api printenv GREENFLOW_TELEMETRY_SCOPE_MODE
```

Expected:

```text
redistribute
redistribute
```

Verify API state:

```bash
docker compose exec -T api python - <<'PY'
from greenflow.agent.tools.db_tool import get_zones
from greenflow.agent.tools.timeseries_tool import get_building_kpis, get_building_health
from greenflow.api.deps import default_building_id
b = default_building_id()
zones = get_zones(b)
print("visible_zones", len(zones))
print("aggregate_context", sum(1 for z in zones if z.get("energy_scope") == "aggregate_context"))
print("first_zones", [z["name"] for z in zones[:5]])
print("kpis", get_building_kpis(b))
print("health", get_building_health(b))
PY
```

Expected high-level result:

```text
visible_zones 288
aggregate_context 0
```

## 4. UI expectations

- Dashboard `Zone state` shows 288 zones, not 308.
- Rows such as `VOLUME / OFFICE`, `VOLUME / GARAGE`, `GFA`, `Gross Area Placeholder`
  should not appear in Zone state.
- Child zone names should be readable, for example:
  `Basement · ELECT 0302 · 63.8 m2`.
- New Run Optimization logs should say:
  `Loaded semantic graph: 288 zones`.
- Old Run Optimization sessions can still show `308 zones` because logs were
  persisted before the fix.

## 5. What teammate should review next

1. Review 20 `aggregate_context` rows in `ZONE_ENERGY_SCOPE_REVIEW_LIST.csv`.
   Confirm they are truly gross/volume/GFA/net-area context zones.

2. Review `zone_scope_child_weights.csv`.
   Confirm every aggregate is mapped to plausible child zones. Current expected
   summary is:

   ```text
   aggregates = 20
   mapped_aggregates = 20
   child_zones = 210
   weight_rows = 833
   unmapped_aggregates = 0
   ```

3. Review 78 `review_required` rows.
   These are still counted. Pay attention to:
   - `context_space_name`
   - `unusual_height`
   - very large area zones

4. Run one new optimization flow.
   Confirm selected actions target readable child zone names and do not target
   aggregate zones.

5. Compare dashboard vs API:
   - `/api/kpi/current`
   - `/api/kpi/health-score`
   - `/api/electrical/overview`

## 6. Rollback

Backup before telemetry reload:

```text
/root/greenflow_telemetry_zone_15m_before_redistribute_2026-06-30_151153.sql.gz
```

Restore telemetry:

```bash
cd /opt/green-flow-agentic-building-energy-control
gzip -dc /root/greenflow_telemetry_zone_15m_before_redistribute_2026-06-30_151153.sql.gz \
  | docker compose exec -T db psql -U greenflow -d greenflow
```

Set modes back to audit:

```bash
sed -i 's/^GREENFLOW_ENERGY_SCOPE_MODE=.*/GREENFLOW_ENERGY_SCOPE_MODE=audit/' .env
sed -i 's/^GREENFLOW_TELEMETRY_SCOPE_MODE=.*/GREENFLOW_TELEMETRY_SCOPE_MODE=audit/' .env
docker compose up -d --build api
```

## 7. Recent commits related to this work

```text
a26922c Fix telemetry redistribution record key
e8157a3 Hide aggregate zones from zone state API
8dacfd8 Clean repeated child zone name tokens
ab7a944 Report visible zone count in semantic agent
```
