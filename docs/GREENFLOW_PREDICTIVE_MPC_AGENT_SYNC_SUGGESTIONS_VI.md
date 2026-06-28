# GreenFlow Predictive MPC, Agent Flow và Validation Sync Suggestions

Mục tiêu của tài liệu này là chốt lại nguyên lý đúng giữa:

- model dự đoán/surrogate
- predictive control/MPC
- LangGraph agent
- validation replay
- tab `/What-if Analysis`

Kết luận chính: **surrogate model không phải là control agent**. Surrogate là
plant model/counterfactual simulator: cho biết nếu building đang ở state `x_t`,
weather/occupancy/schedule là `d_t`, và action là `u_t`, thì tải/comfort sẽ ra
sao. **MPC/control mới là phần thử nhiều action trajectory, chấm objective, chọn
trajectory tốt nhất, rồi chỉ thực hiện bước kế tiếp `t+1`.**

## 1. Nguyên lý chuẩn cần chốt

### 1.1. Model dự đoán timestep `n+1` là gì?

Một model dự đoán timestep kế tiếp thường có dạng:

```text
x_{t+1}, y_{t+1} = f(x_t, d_t, u_t)
```

Trong đó:

| Ký hiệu | Ý nghĩa |
|---|---|
| `x_t` | trạng thái hiện tại của building/zone: temperature, setpoint, load, occupancy... |
| `d_t` | disturbance/exogenous inputs: weather, calendar, solar, occupancy forecast... |
| `u_t` | action/control: tăng setpoint, dim lighting, eco mode... |
| `y_{t+1}` | output dự đoán: total kW, HVAC kW, comfort violation... |

Nếu model chỉ dự đoán được `n+1`, muốn nhìn xa `N` bước thì phải rollout:

```text
for k = 1..H:
  y_{t+k}, x_{t+k} = f(x_{t+k-1}, d_{t+k}, u_{t+k})
```

Tức là model chỉ là engine dự đoán. Nó không tự quyết định action.

### 1.2. Surrogate model trong GreenFlow nên đóng vai trò gì?

Surrogate nên đóng vai trò **fast EnergyPlus replacement** cho control/validation:

```text
EnergyPlus baseline telemetry = no-AI ground truth
Surrogate = fast counterfactual engine cho scenario có AI action
```

Với dữ liệu El Nino:

```text
baseline branch:
  308-zone E+ telemetry từ final_elnino

AI branch:
  semantic state 308 zones
  + weather/occupancy/calendar horizon
  + candidate actions
  -> surrogate rollout nhanh
  -> predicted energy/comfort/peak
```

Không nên hiểu là "surrogate dự đoán tương lai xong control cứ đi theo". Đúng hơn:

```text
control đề xuất nhiều trajectory
surrogate đánh giá từng trajectory
objective chọn trajectory tốt nhất
controller chỉ execute action ở t+1
vòng sau quan sát lại state thật/simulated rồi tối ưu lại
```

### 1.3. MPC/Receding Horizon đúng nghĩa

MPC chuẩn trong GreenFlow nên là:

```text
At time t:
  1. Read semantic building state: all 308 zones + devices + telemetry + weather.
  2. Build horizon t+1 ... t+H.
  3. Generate candidate action trajectories U_1..U_K.
  4. For each trajectory:
       rollout surrogate across H timesteps
       compute energy, peak, comfort, ramp, policy risk
       score objective
  5. Select best trajectory.
  6. Execute only first action u_t.
  7. At t+1, read new state and repeat.
```

Objective nên rõ ràng:

```text
minimize:
  energy_cost
  + peak_penalty
  + comfort_penalty
  + ramp_penalty
  + action_change_penalty
  + policy_risk_penalty
```

Constraints nên rõ ràng:

```text
comfort: occupied zones should not exceed comfort limit
rate limit: setpoint changes must be gradual
equipment: action only if controllable device/zone supports it
policy: human approval if action scope/risk exceeds policy
```

## 2. Code hiện tại đang chạy gì?

### 2.1. Predictive-control endpoint mới

Code path:

```text
POST /api/simulations/predictive-control
backend/greenflow/api/routers/simulations.py
backend/greenflow/control/predictive.py
```

Luồng hiện tại:

```text
build_semantic_state()
  -> lấy telemetry tại timestamp
  -> lấy zones 308 từ DB
  -> lấy weather gần nhất

generate_candidate_trajectories()
  -> sinh fixed template trajectories:
     baseline_hold
     smooth_peak_shave
     empty_zone_saver
     gradual_comfort_safe
     lighting_peak_trim

evaluate_trajectory()
  -> chạy từng step trong horizon
  -> gọi surrogate zone model để predict total kW
  -> apply lighting_factor bằng delta thủ công
  -> tính energy, peak, comfort, ramp
  -> score objective

select_best()
  -> chọn objective score thấp nhất
  -> chỉ trả execute_action ở step 1
```

Điểm đúng:

- Đã có receding-horizon scaffold.
- Đã dùng semantic state 308 zones từ DB.
- Đã dùng MLflow/local model provider.
- Đã evaluate nhiều trajectory qua horizon.
- Đã chọn best trajectory và chỉ execute bước `t+1`.
- `predictive-replay` đã feed first-step zone state sang timestep tiếp theo.

Điểm chưa đủ:

- Candidate trajectories vẫn là rule/template cố định, chưa do control agent
  sinh động từ semantic graph + forecast.
- `top_k` hiện chủ yếu là số candidate trả về, chưa phải search/optimization top-k thật.
- Weather trong horizon hiện giữ weather hiện tại, chưa lấy forecast/weather theo từng future step.
- Model zone surrogate hiện là conditional static model theo time/weather/setpoint/geometry,
  chưa phải state-transition model đầy đủ có `x_t -> x_{t+1}`.
- Comfort transition còn đơn giản:

```text
temperature_next = baseline_temp + 0.4 * setpoint_delta
```

- Trong `evaluate_trajectory`, baseline power cho future horizon lấy từ current state
  của zone, không query/load future baseline telemetry theo từng step khi replay.
- Execution/approval chưa persist action từ predictive-control vào action queue/BMS flow.

### 2.2. LangGraph agent hiện tại

Code path:

```text
backend/greenflow/agent/graph.py
backend/greenflow/agent/nodes/prediction.py
backend/greenflow/agent/nodes/control.py
backend/greenflow/agent/nodes/simulation.py
```

Prediction Agent hiện tại:

- forecast short horizon mặc định 60 phút
- dùng schedule-aware persistence
- có lag model best-effort nếu available
- có day-ahead HVAC demand best-effort
- không gọi `control/predictive.py`
- không rollout candidate trajectories bằng surrogate

Control Agent hiện tại:

- sinh action bằng rules từ abnormal findings, comfort risk, peak risk
- rank bằng `quick_estimate()`
- chọn top 3 actions
- không chạy MPC objective qua horizon
- không chọn trajectory rồi execute `t+1`

Simulation Agent hiện tại:

- `simulate_actions()` so baseline measured day với optimized counterfactual rule-based
- optimized effect dùng:

```text
HVAC_PCT_PER_C = 0.06
lighting_factor
hvac_off
temp += setpoint_delta * 0.4
```

Kết luận:

```text
LangGraph agent cũ chưa nối vào predictive-control v2.
Predictive-control v2 đang là endpoint riêng.
```

### 2.3. What-if Analysis tab hiện tại

UI:

```text
web/src/components/simulation/CampaignWhatIf.tsx
```

API:

```text
POST /api/simulations/campaign
backend/greenflow/ml/campaign_whatif.py
```

Khi vào tab, component chạy:

```text
useEffect(() => { run(); }, [run])
```

Nghĩa là **vừa vào tab là nó gọi API campaign**. Mỗi lần đổi `+1/+2/+3 C`,
month/date range/full period, nó gọi lại.

Logic hiện tại:

```text
Without AI = measured telemetry / E+ baseline
With AI = measured - surrogate predicted reduction
```

Cụ thể:

```text
pred_base = surrogate(base setpoint)
pred_act  = surrogate(base setpoint + delta)
reduction = pred_base - pred_act
optimized = measured - reduction
```

Đây là fixed-policy campaign:

```text
weekday 13:00-16:00
raise cooling setpoint +N C
roll across selected period
```

Nó **không phải MPC validation** vì không có:

- semantic state each timestep
- generate candidate trajectories
- score objective
- execute only `t+1`
- feed state to next timestep

### 2.4. Predictive replay validation hiện tại

Code path:

```text
POST /api/simulations/predictive-replay
backend/greenflow/control/replay.py
```

Luồng hiện tại:

```text
timestamps from telemetry
for each timestamp:
  run_predictive_control(timestamp, state_overrides)
  get selected trajectory
  use selected first step prediction as AI result
  save execute_action
  convert first-step zone states into overrides
  feed overrides into next timestamp
```

Đây là phần gần nhất với validation đúng:

```text
baseline = 308-zone E+ telemetry
AI = surrogate-based receding-horizon counterfactual
compare baseline_kwh vs ai_kwh, peak, comfort, actions, errors
```

Nhưng còn cần nâng cấp như mục 4.

## 3. Kiến trúc target nên sửa thành một flow thống nhất

### 3.1. Tách rõ 4 service/layer

Đề xuất phân lớp:

```text
SemanticStateService
  -> load 308-zone building state
  -> load devices/control capabilities
  -> load weather/occupancy/calendar horizon

PredictionService
  -> exogenous forecast: weather, occupancy, baseline load hints
  -> optional one-step/horizon forecast

SurrogatePlantService
  -> predict_next(state, action, disturbance)
  -> rollout(state, trajectory, horizon)
  -> backed by MLflow models

MPCController
  -> generate candidate trajectories
  -> evaluate via SurrogatePlantService
  -> score objective/constraints
  -> select best
  -> return execute_step=t+1
```

LangGraph nên orchestrate, explain, request approval, log audit. Nó không nên duplicate
plant physics hoặc quick-estimate rule ở nhiều nơi.

### 3.2. Target backend flow

Target API:

```text
POST /api/control/predictive/decide
POST /api/control/predictive/replay
GET  /api/control/predictive/runs/{id}
```

Hoặc giữ route cũ nhưng đổi nội dung:

```text
POST /api/simulations/predictive-control
POST /api/simulations/predictive-replay
```

Payload nên có:

```json
{
  "building_id": "...",
  "timestamp": "2024-04-25T13:00:00+07:00",
  "scenario_id": "elnino_2024_mar_apr_baseline",
  "horizon_steps": 8,
  "top_k": 4,
  "objective": "energy_peak_comfort_v1",
  "mode": "advisory"
}
```

Response nên có:

```json
{
  "metadata": {
    "control_mode": "predictive_receding_horizon",
    "zone_count": 308,
    "model_source": "mlflow",
    "dataset_key": "elnino_2024_mar_apr"
  },
  "selected": {
    "trajectory_id": "...",
    "actions": ["all horizon actions"],
    "step_predictions": ["H-step predicted result"],
    "objective": {}
  },
  "execute_action": {
    "step": 1,
    "action_type": "...",
    "target_zone_keys": [],
    "reason": "..."
  },
  "candidates": ["top-k scored trajectories"]
}
```

### 3.3. Target LangGraph flow

Thay vì:

```text
building_semantic -> prediction -> control -> simulation -> policy -> execution
```

Nên chuyển thành:

```text
building_semantic
  -> prediction_context
  -> predictive_mpc
  -> policy
  -> execution/approval
  -> report/composer
```

Trong đó:

```text
prediction_context:
  load weather/occupancy/baseline forecast horizon
  không tự chọn action

predictive_mpc:
  gọi MPCController
  nhận selected trajectory + top-k candidates
  xuất execute_action t+1

policy:
  kiểm tra scope, comfort risk, affected zones, approval threshold

execution:
  advisory hoặc queue action
```

Agent answer nên nói:

```text
I evaluated 4 trajectories across 8 future 30-min steps.
Best trajectory reduces predicted energy by X kWh while keeping comfort violation at Y min.
Only the first 30-min action is recommended now; the controller will replan next step.
```

## 4. Suggestions sửa code cụ thể

### 4.1. Tạo `PredictionContextService`

File đề xuất:

```text
backend/greenflow/control/context.py
```

Nhiệm vụ:

- lấy semantic state tại `t`
- lấy horizon timestamps `t+1..t+H`
- lấy weather theo từng timestamp nếu có trong `weather_15m`
- lấy occupancy forecast hoặc occupancy baseline từ telemetry/profile
- lấy baseline future telemetry khi chạy replay validation
- lấy control capabilities từ devices/zones

Output:

```python
{
  "state_t": {...},
  "horizon": [
    {"timestamp": t1, "weather": {...}, "occupancy": {...}, "baseline_hint": {...}},
    ...
  ],
  "capabilities": {...}
}
```

### 4.2. Sửa `predictive.py` để không dùng current baseline cho toàn horizon

Hiện `_rows_for_step()` dùng `state["zones"]` cho mọi future step. Nên đổi sang:

```text
rows_for_step(state, horizon_step_context, current_rollout_state, action_mods)
```

Trong replay:

- baseline for step `k` nên lấy từ E+ telemetry tại timestamp `t+k`
- AI branch nên lấy state rollout từ timestep trước

Trong online/live:

- nếu chưa có future baseline telemetry, dùng forecast baseline từ PredictionContextService
- weather lấy theo forecast hoặc nearest known weather

### 4.3. Chuẩn hóa SurrogatePlantService

File đề xuất:

```text
backend/greenflow/control/surrogate_plant.py
```

API nội bộ:

```python
predict_step(state, action, context) -> StepPrediction
rollout(initial_state, trajectory, horizon_context) -> RolloutResult
```

Nên dùng MLflow provider hiện có:

```text
greenflow_surrogate_zone
greenflow_surrogate_hvac
greenflow_surrogate_building
```

Nếu model hiện tại là static conditional model, metadata phải ghi rõ:

```text
model_type = conditional_static_surrogate
state_transition = approximated
```

Nếu sau này train model tốt hơn:

```text
model_type = one_step_transition_surrogate
inputs include lag/load/temp/setpoint/occupancy
outputs include next total_kw, hvac_kw, temperature_c
```

### 4.4. Nâng candidate generation thành top-k trajectory thật hơn

Hiện trajectory là 5 template cố định. Nên thêm generator theo action space:

```text
action dimensions:
  setpoint_delta: [0, +0.25, +0.5, +1.0]
  lighting_factor: [1.0, 0.92, 0.85]
  target groups: safe zones, empty zones, large zones, high-load zones
  duration: 1..H steps
```

Search strategy ban đầu đủ pragmatic:

```text
template candidates
+ sampled combinations
+ prune by comfort/policy constraints
+ score top_k
```

Không cần tối ưu nonlinear phức tạp ngay, nhưng top-k phải thật sự là các
trajectory có objective score tốt nhất sau khi surrogate rollout.

### 4.5. Nối LangGraph Control Agent sang predictive v2

Sửa:

```text
backend/greenflow/agent/nodes/prediction.py
backend/greenflow/agent/nodes/control.py
backend/greenflow/agent/nodes/simulation.py
```

Đề xuất:

- `prediction.py` chỉ tạo `prediction_context`/forecast horizon.
- `control.py` gọi `run_predictive_control()` hoặc `MPCController.decide()`.
- `simulation.py` không chạy `simulate_actions()` rule-based cho predictive mode,
  mà lấy result từ selected trajectory/replay.

Backward compatibility:

```text
scenario_config.control_engine = "predictive_mpc" | "legacy_rules"
default = "predictive_mpc"
```

### 4.6. Sửa policy/execution để hiểu execute step

Hiện policy xử lý action list cũ. Cần thêm schema:

```text
selected_trajectory
execute_action
replan_at = timestamp + timestep_minutes
```

Policy check nên dùng:

- affected zone count
- occupied zone count
- comfort violation risk
- setpoint delta magnitude
- action duration
- automation allowed or approval required

Execution chỉ queue/execute:

```text
execute_action at step 1
```

Không execute toàn bộ trajectory, vì MPC phải replan ở timestep sau.

### 4.7. Sửa What-if Analysis thành 2 hoặc 3 chế độ rõ nghĩa

Hiện tab tên "What-if Analysis" nhưng logic là fixed campaign. Nên đổi UI thành:

1. **Campaign What-if**
   - hiện logic cũ
   - label rõ:

```text
Fixed setpoint policy, not receding-horizon control
```

2. **Predictive Replay Validation**
   - gọi:

```text
POST /api/simulations/predictive-replay
```

   - hiển thị:

```text
Baseline E+ telemetry vs AI MPC surrogate replay
steps, errors, baseline kWh, AI kWh, saving %, peak, comfort minutes
action timeline
selected trajectory per timestep
```

3. **Single Decision Preview**
   - gọi:

```text
POST /api/simulations/predictive-control
```

   - hiển thị:

```text
top-k trajectories
objective score breakdown
execute_action t+1
horizon prediction chart
```

Như vậy user không nhầm campaign fixed-policy với MPC validation.

## 5. Precompute What-if/MPC replay cache trên cloud

Sau khi logic MPC đã đúng, không nên để tab `/What-if Analysis` tự chạy replay
toàn bộ giai đoạn March-April mỗi lần user mở trang. Với 308 zones, 30-minute
timestep, horizon 8 bước, top-k trajectory, giai đoạn hơn 2 tháng sẽ nặng và làm
UI chờ lâu.

Target đúng nên là:

```text
cloud batch job
  -> chạy từng ngày
  -> trong mỗi ngày chạy từng timestep theo receding horizon
  -> ghi kết quả vào cache/table/artifact
  -> UI What-if Analysis chỉ đọc cache đã materialize
```

### 5.1. Nguyên lý cache

Tách rõ 2 loại dữ liệu:

```text
Campaign fixed policy cache
  = +1/+2/+3C fixed policy
  = nhẹ hơn, dùng cho high-level campaign chart

Predictive MPC replay cache
  = receding-horizon validation từng timestep
  = nặng hơn, cần precompute
```

Với UI, response nên thống nhất shape gần giống campaign hiện tại:

```json
{
  "metadata": {
    "source": "precomputed_cache",
    "control_mode": "predictive_replay",
    "dataset_key": "elnino_2024_mar_apr",
    "scenario_id": "elnino_2024_mar_apr_baseline",
    "horizon_steps": 8,
    "top_k": 4,
    "model_versions": {}
  },
  "kpi": {},
  "daily": [],
  "series": [],
  "actions": []
}
```

UI không nên gọi `POST /simulations/predictive-replay` trực tiếp cho full period.
UI nên gọi cache endpoint:

```text
GET /api/simulations/whatif-cache?mode=predictive_replay&date_from=2024-03-01&date_to=2024-05-01&horizon_steps=8&top_k=4
```

Nếu cache thiếu:

```text
HTTP 404/409
message = "precomputed what-if cache missing"
```

Không tự chạy replay dài trong request web.

### 5.2. Cache key bắt buộc

Cache không được chỉ key theo date range. Phải key theo toàn bộ điều kiện làm kết
quả thay đổi:

```text
dataset_key
scenario_id
control_mode
policy_key
horizon_steps
top_k
objective_version
controller_version
model_source
model_uri/version/alias
code_git_sha
date_from
date_to
timestep_minutes
```

Ví dụ:

```text
elnino_2024_mar_apr/
  predictive_replay/
    h8_top4_objv1_model-zone-v1_controller-v1/
      2024-03-01.parquet
      2024-03-02.parquet
      ...
      manifest.json
```

Khi model MLflow đổi version hoặc objective đổi, cache cũ phải được coi là stale
và chạy lại dưới cache key mới.

### 5.3. Storage đề xuất

Có thể dùng Postgres, Parquet, hoặc cả hai.

Đề xuất pragmatic:

```text
Postgres
  -> metadata, daily KPI, API query nhanh

Parquet under /app/storage
  -> timestep series/actions chi tiết, debug/audit, export
```

Tables đề xuất:

```sql
CREATE TABLE whatif_cache_runs (
  id uuid PRIMARY KEY,
  dataset_key text NOT NULL,
  scenario_id text NOT NULL,
  control_mode text NOT NULL,
  policy_key text NOT NULL,
  date_from timestamptz NOT NULL,
  date_to timestamptz NOT NULL,
  horizon_steps int,
  top_k int,
  objective_version text,
  controller_version text,
  model_metadata jsonb,
  cache_key text NOT NULL,
  status text NOT NULL,
  started_at timestamptz DEFAULT now(),
  completed_at timestamptz,
  error text,
  metadata jsonb DEFAULT '{}'::jsonb,
  UNIQUE (cache_key, date_from, date_to)
);

CREATE TABLE whatif_cache_daily (
  run_id uuid REFERENCES whatif_cache_runs(id) ON DELETE CASCADE,
  date date NOT NULL,
  baseline_kwh numeric,
  ai_kwh numeric,
  saving_kwh numeric,
  saving_percent numeric,
  baseline_peak_kw numeric,
  ai_peak_kw numeric,
  comfort_violation_min numeric,
  action_count int,
  PRIMARY KEY (run_id, date)
);

CREATE TABLE whatif_cache_timestep (
  run_id uuid REFERENCES whatif_cache_runs(id) ON DELETE CASCADE,
  timestamp timestamptz NOT NULL,
  baseline_kw numeric,
  ai_kw numeric,
  baseline_kwh numeric,
  ai_kwh numeric,
  saving_kwh numeric,
  comfort_violation_min numeric,
  selected_trajectory text,
  objective_score numeric,
  action_json jsonb,
  PRIMARY KEY (run_id, timestamp)
);
```

Nếu muốn giảm DB size, có thể chỉ lưu `daily` trong Postgres và lưu `timestep`
ở Parquet:

```text
/app/storage/whatif_cache/{cache_key}/series/date=2024-04-25/*.parquet
/app/storage/whatif_cache/{cache_key}/actions/date=2024-04-25/*.jsonl
/app/storage/whatif_cache/{cache_key}/manifest.json
```

### 5.4. Script precompute đề xuất

Tạo script:

```text
scripts/precompute_predictive_whatif.py
```

CLI:

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

Algorithm:

```text
1. Resolve active dataset and model metadata.
2. Build deterministic cache_key.
3. Split date range into daily chunks.
4. For each day:
   a. If day is already complete and --resume, skip.
   b. Insert/update whatif_cache_runs status=running.
   c. Call run_predictive_replay(date_from=day, date_to=day+1, max_steps=48).
   d. Validate steps=48 and errors=0.
   e. Write timestep rows/actions to Postgres/Parquet.
   f. Write daily summary.
   g. Mark chunk complete.
5. Build/refresh manifest and period aggregate.
```

Script phải idempotent:

```text
--resume
  skip completed chunks

--force
  delete and recompute matching cache_key/date chunk

--dry-run
  print chunks and cache key, do not write
```

Không nên parallel mạnh ngay từ đầu. Với cloud VM hiện tại:

```text
--parallel-days 1
```

Sau khi ổn mới tăng lên `2` nếu RAM/CPU cho phép.

### 5.5. API đọc cache cho What-if Analysis

Thêm endpoint:

```text
GET /api/simulations/whatif-cache
```

Query:

```text
mode=predictive_replay | fixed_campaign
date_from=2024-03-01
date_to=2024-05-01
horizon_steps=8
top_k=4
policy_key=default
metric=daily_energy | daily_peak
```

Response cho daily chart:

```json
{
  "metadata": {
    "source": "precomputed_cache",
    "status": "complete",
    "cache_key": "...",
    "control_mode": "predictive_replay"
  },
  "kpi": {
    "baseline_kwh": 350597.1,
    "ai_kwh": 0,
    "saving_kwh": 0,
    "saving_percent": 0,
    "baseline_peak_kw": 0,
    "ai_peak_kw": 0,
    "comfort_violation_min": 0
  },
  "daily": [
    {
      "date": "2024-04-25",
      "baseline_kwh": 9040.2,
      "optimized_kwh": 0,
      "peak_baseline_kw": 0,
      "peak_optimized_kw": 0
    }
  ]
}
```

`optimized_kwh` có thể map từ `ai_kwh` để giữ compatibility với component
campaign hiện tại.

### 5.6. UI What-if Analysis sau khi có cache

UI nên đổi flow:

```text
On mount:
  GET /api/simulations/whatif-cache for default range/mode

If cache exists:
  render immediately

If cache missing:
  show "Precomputed cache not available for this range"
  do not auto-run long replay
```

Nên có mode selector:

```text
Campaign fixed policy
Predictive MPC replay
Single decision preview
```

Với `Predictive MPC replay`, default chỉ đọc cache. Admin/operator có thể có nút
"Run precompute" riêng sau này, nhưng không nên để user page load tự trigger job
nặng.

### 5.7. Cloud run order đề xuất

Một lần full backfill cho El Nino:

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

Validate:

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
dataset_key = elnino_2024_mar_apr
zone_count = 308
source = precomputed_cache
```

Sau này nếu live rolling daily:

```text
cron daily after midnight:
  precompute yesterday
```

Ví dụ:

```bash
0 2 * * * cd /opt/green-flow-agentic-building-energy-control && \
docker compose exec -T api python scripts/precompute_predictive_whatif.py \
  --date-from $(date -d yesterday +\%F) \
  --date-to $(date +\%F) \
  --horizon-steps 8 \
  --top-k 4 \
  --chunk-days 1 \
  --write postgres,parquet \
  --resume
```

### 5.8. Guardrails

Script phải có guardrails:

- Không chạy full range nếu Postgres telemetry chưa đủ `308 zones`.
- Không chạy nếu MLflow model-info unavailable, trừ khi explicit `--allow-local-fallback`.
- Mỗi daily chunk phải validate `48 timesteps` với 30-minute dataset.
- Nếu một ngày lỗi, mark failed và tiếp tục ngày sau khi `--continue-on-error`.
- Ghi `model_metadata`, `objective_version`, `controller_version`.
- Không ghi đè cache complete nếu không có `--force`.
- API không silently fallback sang runtime heavy compute khi cache thiếu.

## 6. Data và model acceptance checks

### 6.1. Predictive decision check

Lệnh:

```bash
curl -X POST https://greenflow-api.duckdns.org/api/simulations/predictive-control \
  -H "Content-Type: application/json" \
  -d '{"timestamp":"2024-04-25T13:00:00+07:00","horizon_steps":8,"top_k":4}'
```

Expected:

```text
metadata.zone_count = 308
metadata.control_mode = predictive_receding_horizon
selected.step_predictions length = 8
candidates length <= 4
execute_action.step = 1 or null if selected baseline_hold
selected.model.source = mlflow when MLflow is reachable
```

### 6.2. Replay validation check

Lệnh:

```bash
curl -X POST https://greenflow-api.duckdns.org/api/simulations/predictive-replay \
  -H "Content-Type: application/json" \
  -d '{"date_from":"2024-04-25","date_to":"2024-04-26","max_steps":48,"horizon_steps":8,"top_k":4}'
```

Expected:

```text
metadata.validation_mode = baseline_eplus_vs_ai_surrogate_receding_horizon
summary.steps = 48
summary.errors = 0
series[*].selected_trajectory is not null when action selected
actions[] contains only first-step actions per timestep
```

### 6.3. What-if campaign check

Lệnh:

```bash
curl -X POST https://greenflow-api.duckdns.org/api/simulations/campaign \
  -H "Content-Type: application/json" \
  -d '{"date_from":"2024-03-01","date_to":"2024-04-01","setpoint_delta":3}'
```

Expected:

```text
metadata.control_mode = fixed_policy_campaign
kpi.baseline_kwh ~= 157,737 kWh for March true-building
daily date range should not include shifted extra UTC day
```

## 7. Thứ tự triển khai đề xuất

1. Giữ `campaign` như fixed-policy campaign nhưng đổi wording UI cho rõ.
2. Thêm Predictive Replay panel vào What-if tab.
3. Thêm precompute script + cache schema cho Predictive Replay.
4. Đổi What-if tab sang đọc cache cho full-period replay.
5. Tách `PredictionContextService` để horizon có weather/baseline/occupancy đúng từng step.
6. Tách `SurrogatePlantService` khỏi `predictive.py`.
7. Sửa rollout để dùng `horizon_context` thay vì current baseline cho mọi future step.
8. Nâng candidate generator thành top-k trajectory thật hơn.
9. Nối `agent/nodes/control.py` sang predictive MPC khi `control_engine=predictive_mpc`.
10. Sửa `policy_node` và `execution` để xử lý `execute_action` step 1.
11. Thêm run logs cho MPC:

```text
Loaded semantic state: 308 zones
Built horizon: 8 x 30-min steps
Evaluated K trajectories
Selected trajectory X
Queued execute_action step 1
```

12. Thêm tests cho campaign, predictive-control, predictive-replay, what-if cache.

## 8. Chốt nguyên lý để triển khai tiếp

Flow chuẩn cuối cùng nên là:

```text
308-zone semantic state
  -> prediction context over horizon
  -> candidate action trajectories
  -> surrogate rollout for each trajectory
  -> objective scoring
  -> select best trajectory
  -> execute only t+1
  -> re-read/replay next state
  -> repeat
```

Và phân biệt rõ:

```text
Campaign What-if
  = fixed setpoint policy rolled across a period
  = useful for high-level what-if
  != MPC

Predictive MPC
  = receding-horizon decision engine
  = semantic + forecast + surrogate + objective
  = execute t+1 only

Predictive Replay Validation
  = E+ baseline telemetry vs AI surrogate MPC branch
  = technical validation of control logic
```
