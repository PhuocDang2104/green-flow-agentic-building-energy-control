# Claude Agent Prompt: Predictive MPC + What-if Precompute Cache

Copy toàn bộ prompt này cho Claude/code agent. Agent phải đọc kỹ repo trước khi
code, đặc biệt là spec:

```text
C:/Users/ADMIN/Desktop/greenflow-agentic-building-energy/docs/GREENFLOW_PREDICTIVE_MPC_AGENT_SYNC_SUGGESTIONS_VI.md
```

## Prompt cho Claude

Bạn là coding agent làm việc trong repo GreenFlow:

```text
C:/Users/ADMIN/Desktop/greenflow-agentic-building-energy
```

Hãy đọc kỹ tài liệu:

```text
docs/GREENFLOW_PREDICTIVE_MPC_AGENT_SYNC_SUGGESTIONS_VI.md
```

Sau đó implement phần **Predictive MPC What-if precompute cache** để tab
`/What-if Analysis` không phải chạy full replay runtime khi user mở trang.

### Mục tiêu kỹ thuật

Hiện repo có:

- `POST /api/simulations/campaign`: fixed-policy what-if, chạy trực tiếp khi UI mở tab.
- `POST /api/simulations/predictive-control`: receding-horizon/MPC scaffold.
- `POST /api/simulations/predictive-replay`: chạy từng timestep và compare baseline E+ telemetry vs AI surrogate branch.

Yêu cầu mới:

```text
Cloud batch job
  -> chạy predictive replay từng ngày / từng timestep
  -> ghi cache vào Postgres và artifact storage
  -> UI What-if Analysis chỉ đọc cache đã precompute
  -> không tự chạy full replay nặng trong request web
```

### Phạm vi code cần làm

#### 1. Thêm DB/cache layer idempotent

Repo hiện chưa có migration framework riêng, chỉ có `db/schema.sql`. Vì cloud DB
đã tồn tại, không được phụ thuộc vào init DB lại.

Tạo module hoặc script idempotent để tự tạo bảng nếu thiếu:

```text
whatif_cache_runs
whatif_cache_daily
whatif_cache_timestep
```

Schema theo spec trong doc:

```text
docs/GREENFLOW_PREDICTIVE_MPC_AGENT_SYNC_SUGGESTIONS_VI.md
Section 5.3
```

Yêu cầu:

- Dùng `CREATE TABLE IF NOT EXISTS`.
- Dùng unique key/cache key để rerun an toàn.
- Không phá bảng cũ.
- Có thể gọi từ script precompute và API.

#### 2. Tạo script precompute

Tạo script:

```text
scripts/precompute_predictive_whatif.py
```

CLI bắt buộc:

```bash
python scripts/precompute_predictive_whatif.py \
  --date-from 2024-03-01 \
  --date-to 2024-05-01 \
  --scenario-id elnino_2024_mar_apr_baseline \
  --horizon-steps 8 \
  --top-k 4 \
  --chunk-days 1 \
  --write postgres,parquet \
  --resume
```

Flags cần có:

```text
--building-id
--date-from
--date-to
--scenario-id
--horizon-steps
--top-k
--chunk-days
--write postgres|parquet|postgres,parquet
--resume
--force
--dry-run
--continue-on-error
--allow-local-fallback
```

Logic:

```text
1. Resolve active_dataset().
2. Load model metadata/model-info where possible.
3. Build deterministic cache_key:
   dataset_key, scenario_id, control_mode, horizon_steps, top_k,
   objective_version, controller_version, model metadata/version.
4. Split date range into daily chunks.
5. For each day:
   - skip if completed and --resume
   - delete/recompute if --force
   - call run_predictive_replay(day, day+1, max_steps=48, horizon_steps, top_k)
   - validate steps=48, errors=0 unless --continue-on-error
   - write whatif_cache_daily
   - write whatif_cache_timestep
   - write Parquet/JSON artifact under /app/storage/whatif_cache/{cache_key}/...
   - mark run complete/failed
6. Print final JSON summary.
```

Storage path:

```text
{STORAGE_DIR or /app/storage}/whatif_cache/{cache_key}/
  manifest.json
  daily.parquet
  series/date=YYYY-MM-DD/*.parquet
  actions/date=YYYY-MM-DD/*.jsonl
```

Chấp nhận dùng JSONL nếu Parquet write phức tạp, nhưng ưu tiên Parquet vì repo đã có
`pyarrow`.

#### 3. Tạo validation script

Tạo script:

```text
scripts/validate_whatif_cache.py
```

CLI:

```bash
python scripts/validate_whatif_cache.py \
  --date-from 2024-03-01 \
  --date-to 2024-05-01 \
  --horizon-steps 8 \
  --top-k 4
```

Check tối thiểu:

```text
dataset_key = elnino_2024_mar_apr
scenario_id = elnino_2024_mar_apr_baseline
days_complete = 61
missing_days = 0
total_steps = 2928
errors = 0
daily rows exist
timestep rows exist
cache source = precomputed_cache
```

In JSON summary, exit code `0` nếu pass, `1` nếu fail.

#### 4. Thêm API đọc cache

Thêm endpoint:

```text
GET /api/simulations/whatif-cache
```

Query:

```text
mode=predictive_replay
date_from=2024-03-01
date_to=2024-05-01
horizon_steps=8
top_k=4
scenario_id=elnino_2024_mar_apr_baseline
```

Response shape tương thích với `CampaignWhatIf`:

```json
{
  "metadata": {
    "source": "precomputed_cache",
    "status": "complete",
    "control_mode": "predictive_replay",
    "cache_key": "...",
    "dataset": {}
  },
  "policy": {
    "engine": "predictive_mpc_replay",
    "peak_window": "receding-horizon",
    "setpoint_delta_c": null
  },
  "kpi": {
    "baseline_kwh": 0,
    "optimized_kwh": 0,
    "saving_kwh": 0,
    "saving_percent": 0,
    "cost_saving_vnd": 0,
    "peak_reduction_kw": 0,
    "comfort_violation_delta_min": 0,
    "co2_avoided_kg": 0,
    "days": 0
  },
  "daily": [
    {
      "date": "2024-04-25",
      "baseline_kwh": 9040.2,
      "optimized_kwh": 8990.0,
      "peak_baseline_kw": 1045.4,
      "peak_optimized_kw": 1000.0
    }
  ]
}
```

Nếu cache thiếu:

```text
404 hoặc 409
message rõ: precomputed what-if cache missing for cache_key/date range
```

Không được fallback sang chạy `run_predictive_replay()` full-period trong request
API.

#### 5. Nâng UI What-if Analysis

File chính:

```text
web/src/components/simulation/CampaignWhatIf.tsx
web/src/lib/api.ts
```

Yêu cầu UI:

- Giữ mode cũ: `Campaign fixed policy`.
- Thêm mode mới: `Predictive MPC replay`.
- Với mode campaign, vẫn gọi `api.campaign()`.
- Với mode predictive replay, gọi `api.whatifCache()`.
- Nếu cache missing, hiển thị message rõ:

```text
Predictive replay cache is not available for this range. Run the cloud
precompute job first.
```

- Không trigger precompute job từ browser.
- Chart dùng dữ liệu cache đã có.

#### 6. Không phá logic hiện tại

Không được làm các việc sau:

- Không đổi ý nghĩa `POST /api/simulations/campaign`.
- Không xóa `predictive-control` hoặc `predictive-replay`.
- Không chạy replay full range trong UI request.
- Không ghi vào `/app/data` vì compose mount read-only.
- Không phụ thuộc vào DuckDB file nếu cloud chỉ có parquet fallback.

### Code style

- Dùng helper hiện có:

```text
backend/greenflow/db.py
backend/greenflow/datasets.py
backend/greenflow/config.py
backend/greenflow/control/replay.py
```

- Scripts cần thêm:

```python
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
```

- Dùng `docker compose exec -T` khi command có heredoc trên cloud.
- Output scripts nên là JSON summary dễ copy vào log.

### Tests/smoke local sau khi code

Chạy tối thiểu:

```bash
python -m py_compile \
  scripts/precompute_predictive_whatif.py \
  scripts/validate_whatif_cache.py \
  backend/greenflow/api/routers/simulations.py
```

Nếu có backend deps:

```bash
python scripts/precompute_predictive_whatif.py \
  --date-from 2024-04-25 \
  --date-to 2024-04-26 \
  --horizon-steps 8 \
  --top-k 4 \
  --chunk-days 1 \
  --write postgres \
  --force

python scripts/validate_whatif_cache.py \
  --date-from 2024-04-25 \
  --date-to 2024-04-26 \
  --horizon-steps 8 \
  --top-k 4
```

## VNPT runbook sau khi code xong

Các lệnh dưới đây chạy trên VM VNPT.

### 1. SSH và vào repo

```bash
ssh root@14.225.168.28
cd /opt/green-flow-agentic-building-energy-control
```

Nếu IP khác, dùng host đang chạy Caddy/API hiện tại.

### 2. Pull code và kiểm tra env

```bash
git status --short
git pull

grep -n "GREENFLOW_ELECTRICAL_OUT\\|GREENFLOW_DATASET\\|MLFLOW_TRACKING_URI\\|GREENFLOW_MODEL" .env docker-compose.yml || true
```

`.env` nên có tối thiểu:

```bash
GREENFLOW_DATASET=elnino_2024_mar_apr
GREENFLOW_ELECTRICAL_OUT=/app/storage/electrical_distribution_elnino
MLFLOW_TRACKING_URI=http://mlflow:5000
GREENFLOW_MODEL_SOURCE=mlflow
```

Nếu thiếu thì thêm:

```bash
cat >> .env <<'EOF'
GREENFLOW_DATASET=elnino_2024_mar_apr
GREENFLOW_ELECTRICAL_OUT=/app/storage/electrical_distribution_elnino
MLFLOW_TRACKING_URI=http://mlflow:5000
GREENFLOW_MODEL_SOURCE=mlflow
EOF
```

### 3. Rebuild API

```bash
docker compose build api
docker compose up -d --force-recreate api
docker compose ps
```

Nếu web self-hosted trên VM cũng cần rebuild:

```bash
docker compose build web
docker compose up -d --force-recreate web
```

Nếu frontend lấy từ Vercel, không cần rebuild web trên VM; deploy lại Vercel từ
Git và set env:

```text
NEXT_PUBLIC_API_BASE=https://greenflow-api.duckdns.org/api
```

### 4. Kiểm tra true-building data trước khi precompute

```bash
docker compose exec api python scripts/validate_true_building_sync.py --require-postgres
```

Expected quan trọng:

```text
duckdb/parquet zones = 308
telemetry rows = 901824
telemetry zones = 308
March ~= 157737 kWh
April ~= 192847 kWh
```

Nếu weather rows còn dư từ dataset cũ, cleanup và load lại:

```bash
docker compose exec -T api python - <<'PY'
from sqlalchemy import text
from greenflow.db import db_conn
with db_conn() as conn:
    before = conn.execute(text("SELECT count(*) FROM weather_15m")).scalar()
    conn.execute(text("DELETE FROM weather_15m"))
    after = conn.execute(text("SELECT count(*) FROM weather_15m")).scalar()
print({"weather_rows_before": before, "weather_rows_after": after})
PY

docker compose exec api python scripts/load_weather.py
```

### 5. Smoke test predictive endpoints

```bash
docker compose exec -T api python - <<'PY'
from fastapi.testclient import TestClient
from greenflow.api.main import app

c = TestClient(app)
tests = [
    ("model-info", "get", "/api/ml/model-info", None),
    ("predictive-control", "post", "/api/simulations/predictive-control", {
        "timestamp": "2024-04-25T13:00:00+07:00",
        "horizon_steps": 8,
        "top_k": 4
    }),
    ("predictive-replay-1day", "post", "/api/simulations/predictive-replay", {
        "date_from": "2024-04-25",
        "date_to": "2024-04-26",
        "max_steps": 48,
        "horizon_steps": 8,
        "top_k": 4
    }),
]
for name, method, path, payload in tests:
    r = getattr(c, method)(path, json=payload) if method == "post" else c.get(path)
    print("\\n==", name, r.status_code)
    print(r.text[:1500])
PY
```

Expected:

```text
model-info = 200
predictive-control = 200, metadata.zone_count = 308
predictive-replay-1day = 200, summary.steps = 48, errors = 0
```

### 6. Precompute thử 1 ngày

```bash
docker compose exec api python scripts/precompute_predictive_whatif.py \
  --date-from 2024-04-25 \
  --date-to 2024-04-26 \
  --scenario-id elnino_2024_mar_apr_baseline \
  --horizon-steps 8 \
  --top-k 4 \
  --chunk-days 1 \
  --write postgres,parquet \
  --force
```

Validate 1 ngày:

```bash
docker compose exec api python scripts/validate_whatif_cache.py \
  --date-from 2024-04-25 \
  --date-to 2024-04-26 \
  --horizon-steps 8 \
  --top-k 4
```

Test API cache:

```bash
docker compose exec -T api python - <<'PY'
from fastapi.testclient import TestClient
from greenflow.api.main import app

c = TestClient(app)
r = c.get("/api/simulations/whatif-cache?mode=predictive_replay&date_from=2024-04-25&date_to=2024-04-26&horizon_steps=8&top_k=4")
print(r.status_code)
print(r.text[:3000])
PY
```

Expected:

```text
status = 200
metadata.source = precomputed_cache
kpi.days = 1
daily length = 1
```

### 7. Precompute full March-April 2024

Chỉ chạy sau khi 1 ngày pass.

```bash
docker compose exec api python scripts/precompute_predictive_whatif.py \
  --date-from 2024-03-01 \
  --date-to 2024-05-01 \
  --scenario-id elnino_2024_mar_apr_baseline \
  --horizon-steps 8 \
  --top-k 4 \
  --chunk-days 1 \
  --write postgres,parquet \
  --resume
```

Nếu process bị ngắt, chạy lại y chang với `--resume`.

Validate full:

```bash
docker compose exec api python scripts/validate_whatif_cache.py \
  --date-from 2024-03-01 \
  --date-to 2024-05-01 \
  --horizon-steps 8 \
  --top-k 4
```

Expected:

```text
days_complete = 61
missing_days = 0
total_steps = 2928
errors = 0
```

### 8. Test qua public API domain

Không dùng `http://localhost` nếu Caddy đang redirect theo domain TLS. Dùng domain thật:

```bash
curl -sS https://greenflow-api.duckdns.org/api/health

curl -sS "https://greenflow-api.duckdns.org/api/simulations/whatif-cache?mode=predictive_replay&date_from=2024-04-25&date_to=2024-04-26&horizon_steps=8&top_k=4" | head -c 2000
```

Nếu test từ chính VM nhưng muốn hit Caddy domain về local:

```bash
curl -sS --resolve greenflow-api.duckdns.org:443:127.0.0.1 \
  "https://greenflow-api.duckdns.org/api/simulations/whatif-cache?mode=predictive_replay&date_from=2024-04-25&date_to=2024-04-26&horizon_steps=8&top_k=4" | head -c 2000
```

### 9. Kiểm tra UI

Nếu frontend Vercel:

```text
Vercel env:
NEXT_PUBLIC_API_BASE=https://greenflow-api.duckdns.org/api
Redeploy web from latest Git commit.
```

Mở:

```text
/simulation-baseline hoặc tab What-if Analysis
```

Expected:

```text
Campaign fixed policy vẫn chạy như cũ.
Predictive MPC replay đọc cache, không loading lâu.
Nếu chọn range chưa precompute, UI báo thiếu cache.
```

### 10. Cron daily sau này

Chỉ dùng khi muốn tự precompute ngày mới:

```bash
crontab -e
```

Thêm:

```cron
0 2 * * * cd /opt/green-flow-agentic-building-energy-control && docker compose exec -T api python scripts/precompute_predictive_whatif.py --date-from $(date -d yesterday +\%F) --date-to $(date +\%F) --horizon-steps 8 --top-k 4 --chunk-days 1 --write postgres,parquet --resume >> /var/log/greenflow_whatif_precompute.log 2>&1
```

## Acceptance checklist

Claude phải báo lại kết quả theo checklist này:

```text
[ ] Added idempotent cache table creation
[ ] Added scripts/precompute_predictive_whatif.py
[ ] Added scripts/validate_whatif_cache.py
[ ] Added GET /api/simulations/whatif-cache
[ ] Added frontend API client method
[ ] Updated What-if UI with Predictive MPC replay cache mode
[ ] Runtime request does not run full replay when cache missing
[ ] 1-day precompute passes
[ ] Full Mar-Apr precompute command documented
[ ] Public API cache endpoint returns 200 on precomputed range
```

