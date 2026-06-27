# GreenFlow True Building Implementation Summary

## 1. Mục tiêu kỹ thuật

Phase này chuyển GreenFlow từ demo slice 14 zones sang nền **true building**
El Nino Mar-Apr 2024:

- Control & Simulation dùng toàn bộ 308 zones từ `data/final_elnino`.
- Electrical Graph dùng cùng dataset El Nino thay vì artifact 2025 cũ.
- Model inference ưu tiên MLflow Registry, local file chỉ là fallback.
- Control logic mới đi theo hướng predictive/receding-horizon control:
  build semantic state -> predict horizon -> score candidate trajectories ->
  chọn best trajectory -> chỉ execute action bước `t+1`.

## 2. Data spine đã chốt

Dataset mặc định hiện tại:

```text
dataset_key: elnino_2024_mar_apr
scenario_id: elnino_2024_mar_apr_baseline
timezone: Asia/Ho_Chi_Minh
timestep_minutes: 30
expected_zones: 308
expected_timesteps: 2928
expected_zone_rows: 901824
```

Source:

```text
data/final_elnino/1. Dạng duckdb/*.duckdb
data/final_elnino/3. Dạng parquet/
```

Validation DuckDB đã pass:

| Check | Result |
|---|---:|
| zones | 308 |
| zone-time rows | 901,824 |
| timesteps | 2,928 |
| March 2024 baseline | 157,737.046 kWh |
| April 2024 baseline | 192,847.014 kWh |
| 25 Apr 2024 baseline | 9,040.184 kWh |
| full package total | 350,597.069 kWh |

## 3. Backend changes

### Dataset config

Added shared dataset config:

- `backend/greenflow/datasets.py`
- `backend/greenflow/config.py`

All new true-building paths read:

```text
GREENFLOW_DATASET
GREENFLOW_SCENARIO_ID
GREENFLOW_DUCKDB_PATH
GREENFLOW_PARQUET_ROOT
GREENFLOW_ELECTRICAL_OUT
```

### MLflow model provider

Added:

- `backend/greenflow/ml/model_registry.py`

Runtime priority:

```text
1. MLflow Registry model URI
2. local LightGBM model file fallback
3. unavailable metadata, no silent fake model
```

Registered model names expected:

```text
greenflow_surrogate_building
greenflow_surrogate_zone
greenflow_surrogate_hvac
```

Updated users:

- `backend/greenflow/ml/realforecast.py`
- `backend/greenflow/ml/campaign_whatif.py`
- `GET /api/ml/model-info`

Docker API image now installs:

```text
.[ml,electrical,embeddings]
```

so cloud backend should include `mlflow`, `lightgbm`, `duckdb`, `pyarrow`.

## 4. Control & Simulation changes

### Existing Campaign What-if

`POST /api/simulations/campaign` remains a fixed-policy what-if:

```text
Without AI = measured telemetry
With AI = measured telemetry - surrogate-predicted reduction
```

It is still not MPC. It now supports `scenario_id` and returns dataset/model
metadata.

### New predictive control API

Added:

```text
POST /api/simulations/predictive-control
POST /api/simulations/predictive-replay
```

Files:

- `backend/greenflow/control/predictive.py`
- `backend/greenflow/control/trajectory.py`
- `backend/greenflow/control/objective.py`
- `backend/greenflow/control/replay.py`

Current predictive flow:

```text
semantic state from telemetry_zone_15m all zones
-> generate candidate trajectories
-> predict zone/building load over horizon using surrogate provider
-> score energy, peak, comfort, ramp, action churn
-> select best trajectory
-> expose only t+1 action for execution
```

Replay validation flow:

```text
baseline 308-zone E+ telemetry
-> iterate timestep by timestep
-> run predictive control at each timestamp
-> feed AI t+1 state into next step as override
-> compare baseline_kwh vs ai_kwh with metadata
```

CLI artifact runner:

```text
python scripts/run_predictive_control_replay.py
```

## 5. Data loading changes

### Zone sync

Added:

```text
scripts/sync_true_building_zones.py
```

It upserts all zones from `final_zone_metadata`:

```text
DuckDB zone_id: tz_*
App entity_key: zone_*
```

It also upserts floors and keeps stable UUIDs.

### Telemetry loader

Updated:

```text
scripts/load_real_data.py
```

Default is now:

```text
DATASET_SCHEMA=elnino2024
GREENFLOW_LOAD_ALL_ZONES=1
```

So it loads 308 zones by default for El Nino. It no longer defaults to the old
14-zone repo list.

Important column mapping:

```text
total_power_kw = target_total_zone_power_kw
energy_kwh = target_total_zone_power_kw * 0.5
hvac_power_kw = hvac_power_kw
lighting_power_kw = lights_electricity_kw
plug_power_kw = equipment_electricity_kw
```

### Weather loader

Updated:

```text
scripts/load_weather.py
```

It now uses shared dataset config instead of a hard-coded `/data/elnino_2024`
path.

## 6. Electrical Graph changes

Electrical pipeline now reads active dataset config:

- `backend/greenflow/electrical/config.py`
- `backend/greenflow/electrical/gold.py`
- `backend/greenflow/electrical/board_timeseries.py`
- `backend/greenflow/electrical/validate.py`

For El Nino, `board_timeseries.py` creates a normalized projection from raw
El Nino parquet to the old electrical pipeline schema:

```text
datetime -> timestamp_local
hvac_power_kw -> final_hvac_electricity_kw
hvac_electricity_kwh -> final_hvac_electricity_kwh_interval
target_total_zone_power_kw * 0.5 -> final_total_zone_electricity_kwh_interval
scenario_id -> elnino_2024_mar_apr_baseline
```

Output now targets:

```text
data/electrical_distribution_elnino
```

instead of overwriting `data/electrical_distribution`.

Electrical projection local check passed:

```text
zones: 308
rows: 901824
total: 350597.069 kWh
```

## 7. Frontend API client

Updated:

```text
web/src/lib/api.ts
```

Added:

```text
api.predictiveControl(...)
api.predictiveReplay(...)
campaign(... scenario_id ...)
```

No major UI wiring was done in this phase; cloud/web testing can call the new
APIs directly first.

## 8. Validation scripts

Added:

```text
scripts/validate_true_building_sync.py
```

Default check is local DuckDB/electrical artifact only. Postgres is opt-in:

```bash
python scripts/validate_true_building_sync.py
python scripts/validate_true_building_sync.py --check-postgres
python scripts/validate_true_building_sync.py --require-postgres
```

## 9. Minimal code checks completed

Completed locally:

```text
python -m compileall backend/greenflow/control backend/greenflow/ml backend/greenflow/api/routers/simulations.py backend/greenflow/electrical scripts/...
```

Result: compile pass.

Also checked:

- route imports pass
- model provider metadata path works
- campaign what-if handles unavailable model safely
- electrical El Nino projection returns correct 308-zone total
- DuckDB true-building validation passes exact expected counts/totals

## 10. Cloud test order

Run this order on the cloud VM. The first step is mandatory because the API
container reads `./data` from the host through this compose volume:

```yaml
./data:/app/data:ro
```

### 10.1. Preflight host data

On the host, before running loaders:

```bash
pwd
ls -lah data/final_elnino
find data/final_elnino -maxdepth 4 -type f \( -name "*.duckdb" -o -name "final_zone_metadata.parquet" -o -name "final_weather_timeseries.parquet" \)
```

Expected files. The `.duckdb` file is preferred, but after the latest patch the
loaders can run with parquet-only data as long as the three parquet files below
exist:

```text
data/final_elnino/1. Dạng duckdb/greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd_SELF_CONTAINED.duckdb
data/final_elnino/3. Dạng parquet/final_zone_metadata.parquet
data/final_elnino/3. Dạng parquet/final_zone_device_power_timeseries.parquet
data/final_elnino/3. Dạng parquet/final_weather_timeseries.parquet
data/final_elnino/3. Dạng parquet/final_ai_training_timeseries.parquet
```

If `.duckdb` is missing but the parquet files exist, this is OK. The loaders now
fallback to parquet. If the parquet files are missing, copy `data/final_elnino`
to the repo root first, then recreate the API container.

### 10.2. Rebuild API image

The full electrical build needs `ifcopenshell`, so rebuild after the Dockerfile
change:

```bash
docker compose build --no-cache api
docker compose up -d db minio api
```

If MLflow is used on this stack, create its DB once before starting `mlflow`:

```bash
docker compose exec db psql -U greenflow -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='mlflow'" | grep -q 1 \
  || docker compose exec db psql -U greenflow -d postgres -c "CREATE DATABASE mlflow OWNER greenflow;"

docker compose up -d mlflow
```

### 10.3. Preflight data inside API container

Run this before `sync_true_building_zones.py`:

```bash
docker compose exec api sh -lc '
python - <<PY
from greenflow.datasets import active_dataset
ds = active_dataset()
print("duckdb_path =", ds.duckdb_path, "exists =", ds.duckdb_path.exists())
print("parquet_root =", ds.parquet_root, "exists =", ds.parquet_root.exists())
print("duckdb files =", [str(p) for p in ds.duckdb_path.parent.rglob("*.duckdb")][:5])
PY
find /app/data/final_elnino -maxdepth 4 -type f \( -name "*.duckdb" -o -name "final_zone_metadata.parquet" \)
'
```

Expected. `duckdb_path exists = False` is acceptable when parquet exists:

```text
parquet_root exists = True
.../final_zone_metadata.parquet
.../final_ai_training_timeseries.parquet
.../final_weather_timeseries.parquet
```

If both `.duckdb` and required parquet files are missing, do not run the loaders
yet. Fix the host `./data` mount or set explicit paths in `.env`:

```bash
GREENFLOW_DUCKDB_PATH=/app/data/final_elnino/1. Dạng duckdb/greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd_SELF_CONTAINED.duckdb
GREENFLOW_PARQUET_ROOT=/app/data/final_elnino/3. Dạng parquet
GREENFLOW_ELECTRICAL_OUT=/app/data/electrical_distribution_elnino
```

Then recreate API:

```bash
docker compose up -d --force-recreate api
```

### 10.4. Load true-building data

```bash
docker compose exec api python scripts/sync_true_building_zones.py
docker compose exec api python scripts/load_real_data.py
docker compose exec api python scripts/load_weather.py
docker compose exec api python scripts/validate_true_building_sync.py --require-postgres
```

Expected:

```text
synced true-building zones ... upserted=308
pulled 901,824 rows (308 zones, mode=all-zones)
weather_15m: upserted 2928 rows
telemetry rows = 901824
distinct telemetry zones = 308
```

### 10.5. Build electrical artifacts

Full build:

```bash
docker compose exec api python scripts/build_electrical_kg.py --all
docker compose exec api python scripts/validate_true_building_sync.py --require-postgres
```

If you only need to smoke-test the El Nino timeseries projection after a previous
electrical mapping build already exists, run the lighter phases:

```bash
docker compose exec api python scripts/build_electrical_kg.py --phase timeseries --phase validate --phase dashboard
```

### 10.6. API smoke tests

Use `/api/...` only when Caddy/web proxy is up. If only the API container is up
and no port is published, run curls through the container:

```bash
docker compose exec api python - <<'PY'
from fastapi.testclient import TestClient
from greenflow.api.main import app
c = TestClient(app)
print(c.get("/api/ml/model-info").json())
print(c.post("/api/simulations/campaign", json={
    "date_from": "2024-03-01",
    "date_to": "2024-04-01",
    "setpoint_delta": 3,
}).json()["kpi"])
print(c.post("/api/simulations/predictive-control", json={
    "timestamp": "2024-04-25T13:00:00+07:00",
    "horizon_steps": 8,
    "top_k": 4,
}).json()["metadata"])
print(c.post("/api/simulations/predictive-replay", json={
    "date_from": "2024-04-25",
    "date_to": "2024-04-26",
    "max_steps": 48,
    "horizon_steps": 8,
    "top_k": 4,
}).json()["summary"])
PY
```

If Caddy/web is up:

```bash
curl http://localhost/api/ml/model-info
curl -X POST http://localhost/api/simulations/campaign \
  -H "Content-Type: application/json" \
  -d "{\"date_from\":\"2024-03-01\",\"date_to\":\"2024-04-01\",\"setpoint_delta\":3}"

curl -X POST http://localhost/api/simulations/predictive-control \
  -H "Content-Type: application/json" \
  -d "{\"timestamp\":\"2024-04-25T13:00:00+07:00\",\"horizon_steps\":8,\"top_k\":4}"

curl -X POST http://localhost/api/simulations/predictive-replay \
  -H "Content-Type: application/json" \
  -d "{\"date_from\":\"2024-04-25\",\"date_to\":\"2024-04-26\",\"max_steps\":48,\"horizon_steps\":8,\"top_k\":4}"
```

Expected loaded DB numbers:

```text
zones >= 308
telemetry_zone_15m rows for scenario = 901824
distinct telemetry zones = 308
weather_15m rows = 2928
March baseline ~= 157737 kWh
April baseline ~= 192847 kWh
25 Apr baseline ~= 9040.2 kWh
```

## 11. Known notes

- Campaign What-if is still fixed policy, not MPC.
- Predictive Control API is the MPC-style path.
- The surrogate is used as counterfactual engine, not EnergyPlus rerun.
- Electrical artifacts must be rebuilt on cloud to create
  `data/electrical_distribution_elnino`.
- MLflow models must be reachable from API container. If aliases are added later,
  switch model URI from `models:/name/1` to `models:/name@production`.
