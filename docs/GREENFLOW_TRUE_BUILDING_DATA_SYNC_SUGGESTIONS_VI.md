# GreenFlow True Building Data Sync Implementation Blueprint

Mục tiêu của tài liệu này là chốt lại data chuẩn để triển khai tiếp theo hướng
**true building**: Control & Simulation và Electrical Graph phải cùng dùng toàn bộ
308 zones từ `data/final_elnino`, thay vì Control dùng 14 zones demo còn Electrical
Graph dùng artifact 2025 từ `data/final`.

Tài liệu này dùng để giao việc cho coding agent. Scope chuẩn là:

- **Analytics true building**: chart/KPI/API tính đủ 308 zones.
- **Electrical true building**: board/circuit estimated demand rebuild từ cùng 308-zone El Nino dataset.
- **3D true building**: viewer/inspect/click zone hiểu đủ 308 spaces/zones, không chỉ 14 highlighted zones.

Nếu chỉ làm analytics + electrical thì data đã đồng bộ, nhưng 3D vẫn có thể chưa
inspect đủ 308 zones. Nếu yêu cầu "hiển thị hết tòa nhà" theo nghĩa tương tác 3D
đầy đủ, phải làm thêm phần seed/entity/mesh-map 308 zones ở mục 4.3 và 4.10.

## 0. Readiness để agent code

Doc này đã đủ để bắt đầu code theo phase, nhưng không nên làm một patch lớn duy
nhất. Triển khai nên có validation gate sau từng phase để tránh trạng thái nửa
đúng nửa sai.

### Quyết định bắt buộc trước khi code

| Quyết định | Chốt đề xuất |
|---|---|
| Dataset production cho demo | `elnino_2024_mar_apr` |
| Scenario production | `elnino_2024_mar_apr_baseline` |
| Timezone | `Asia/Ho_Chi_Minh` |
| Timestep thực tế | 30 minutes |
| Analytics scope | 308 zones |
| Electrical output | versioned output `data/electrical_distribution_elnino` |
| Model inference | MLflow Registry primary, local model fallback |
| Control architecture target | predictive control / receding horizon control |
| Prediction horizon | configurable `H` timesteps, không hard-code 60 phút |
| Candidate action selection | top-k action trajectories over horizon |
| Execution semantics | chỉ execute bước `t+1`, sau đó re-plan ở timestep tiếp theo |
| 3D viewer scope phase đầu | giữ viewer hiện tại, nhưng seed DB đủ 308 zones cho data/API |
| 3D viewer scope phase sau | map mesh/entity đủ 308 zones để click/inspect đầy đủ |

### Definition of Done tối thiểu

Một implementation được coi là đúng phase data sync khi các điều kiện này pass:

- `telemetry_zone_15m` có 901,824 rows cho scenario `elnino_2024_mar_apr_baseline`.
- `telemetry_zone_15m` có 308 distinct zones cho scenario đó.
- `weather_15m` có 2,928 rows cùng timestamp range.
- `Control & Simulation` March 2024 baseline khoảng `157,737.0 kWh`.
- `Control & Simulation` April 2024 baseline khoảng `192,847.0 kWh`.
- Tooltip ngày `25 Apr 2024` baseline khoảng `9,040.2 kWh`.
- `/electrical` không còn đọc artifact 2025 cho El Nino view.
- Electrical board total reconcile với zone category total trong tolerance `<= 0.5%`.
- `/api/ml/model-info` báo được model source là `mlflow` khi MLflow reachable.
- Predictive control validation replay tạo được AI trajectory từng timestep.
- AI trajectory metadata ghi rõ horizon, top-k candidates, objective score và action `t+1`.

### Không được coi là done nếu

- Chart vẫn ra `25 Apr 2024 - Without AI: 435.3 kWh`.
- API không filter `scenario_id`, dẫn đến nguy cơ lẫn 2025 và 2024.
- Electrical artifact vẫn có range `2025-01-01` đến `2026-01-01`.
- `zones` trong Postgres vẫn chỉ có 14 live zones cho building.
- UI gọi "Annual energy" cho dataset chỉ có March-April 2024.
- Luồng AI vẫn chỉ là một fixed policy `13:00-16:00 +3C` nhưng được gọi là
  predictive control.
- Validation chỉ tính một lần `measured - surrogate reduction`, không replay từng timestep.

## 1. Kết luận đã kiểm chứng

### Control & Simulation hiện tại đang hiển thị gì?

Tab `Control & Simulation` render component:

- `web/src/app/(app)/simulation-baseline/page.tsx`
- `web/src/components/simulation/CampaignWhatIf.tsx`

Component gọi:

- `POST /api/simulations/campaign`
- backend route: `backend/greenflow/api/routers/simulations.py`
- model tính what-if: `backend/greenflow/ml/campaign_whatif.py`

Chart hiện tại hiển thị campaign what-if:

- `Without AI` = measured baseline từ `telemetry_zone_15m.total_power_kw`
- `With AI` = measured baseline trừ phần giảm tải do surrogate dự đoán khi tăng cooling setpoint
- policy mặc định trên UI: setpoint `+1/+2/+3 C`, active vào weekday `13:00-16:00`
- daily energy = tổng `total_power_kw * 0.5h` theo ngày
- daily peak = tổng kW theo timestamp rồi lấy max theo ngày

### Chart có thật sự chỉ lấy 14 zones không?

Có. Loader hiện tại hard-code 14 zones tại `scripts/load_real_data.py`:

- biến `REPO_ENTITY_KEYS` có 14 `zone_*`
- script đổi `zone_*` sang `tz_*`
- query DuckDB có `WHERE zone_id IN (...)`
- chỉ những rows này được ghi vào `telemetry_zone_15m`

Proof bằng số từ `data/final_elnino`:

| Mốc | 14 zones hiện tại | True building 308 zones |
|---|---:|---:|
| 25 Apr 2024 baseline | 435.3 kWh | 9,040.2 kWh |
| Mar 2024 baseline | 6,615.6 kWh | 157,737.0 kWh |
| Apr 2024 baseline | 8,992.8 kWh | 192,847.0 kWh |
| Terminal 01 May 2024 00:00 | 0.7 kWh | 13.0 kWh |

Tooltip user gửi `25 Apr 2024 - Without AI: 435.3 kWh` khớp tuyệt đối với slice
14 zones. Vì vậy chart hiện tại không phải toàn bộ building.

`With AI: 408.5 kWh` là kết quả runtime của `campaign_whatif.py`, không phải cột
có sẵn trong DuckDB. Nó được tính từ baseline 14 zones + LightGBM surrogate
`zone_surrogate_r2_0.92`. Hiện các model đã được post lên MLflow Registry, nên
hướng nâng cấp đúng là backend inference từ MLflow model registry thay vì phụ
thuộc file local trong `backend/greenflow/ml/models`.

Registered models hiện có trên MLflow:

| Purpose | MLflow registered model |
|---|---|
| Building-level surrogate | `greenflow_surrogate_building` |
| Zone total-power surrogate | `greenflow_surrogate_zone` |
| HVAC surrogate | `greenflow_surrogate_hvac` |

MLflow UI/proxy hiện có tại `greenflow-api.duckdns.org/mlflow/`, backend proxy qua
`backend/greenflow/api/main.py`.

### Electrical Graph hiện tại có đồng bộ không?

Không.

Electrical pipeline hiện đang lấy source tại:

- `backend/greenflow/electrical/config.py`
- `FINAL = data/final`
- `PARQUET_ROOT = data/final/03. Data_parquet`
- `SCENARIO_ID = openmeteo_2025_30min_baseline`

Artifact hiện có:

- `data/electrical_distribution/board_estimated_timeseries.parquet`
- 981,120 rows
- range: `2025-01-01 00:30` đến `2026-01-01 00:00`

Trong khi `final_elnino` là:

- range: `2024-03-01 00:30` đến `2024-05-01 00:00`
- business period: `2024-03-01` đến `2024-04-30`
- 308 zones
- 2 records/hour
- 901,824 zone-time rows

Vì vậy `/electrical` digital twin và `Control & Simulation` hiện không cùng nền data.

## 2. Data chuẩn nên chốt

Source of truth cho phase tiếp theo nên là:

```text
data/final_elnino/1. Dạng duckdb/greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd_SELF_CONTAINED.duckdb
data/final_elnino/3. Dạng parquet/
```

Dataset identity đề xuất:

```text
dataset_key: elnino_2024_mar_apr
scenario_id: elnino_2024_mar_apr_baseline
timezone: Asia/Ho_Chi_Minh
timestep_minutes: 30
business_period_start: 2024-03-01
business_period_end: 2024-04-30
raw_timestamp_min: 2024-03-01 00:30
raw_timestamp_max: 2024-05-01 00:00
zone_count: 308
expected_timesteps: 2928
expected_zone_rows: 901824
```

Lưu ý: user nói "3 tháng", nhưng artifact hiện tại chỉ có March-April 2024 cộng
1 timestamp terminal `2024-05-01 00:00`. Không có full month thứ ba trong
`data/final_elnino`.

Column mapping chuẩn cho El Nino:

| Semantic | Column |
|---|---|
| timestamp local | `datetime` |
| zone id | `zone_id` dạng `tz_*` |
| app entity key | đổi prefix `tz_` -> `zone_` |
| zone temperature | `zone_air_temperature_c` |
| occupancy | `zone_people_occupant_count` |
| cooling setpoint | `cooling_setpoint_c` |
| lighting kW/kWh | `lights_electricity_kw`, `lights_electricity_kwh` |
| equipment kW/kWh | `equipment_electricity_kw`, `equipment_electricity_kwh` |
| HVAC kW/kWh | `hvac_power_kw`, `hvac_electricity_kwh` |
| total đúng gồm HVAC | `target_total_zone_power_kw` |
| interval total kWh | `target_total_zone_power_kw * 0.5` |

Không dùng `zone_total_electricity_kw` làm total building, vì column này chỉ là
lights + equipment, không gồm HVAC.

Category totals toàn bộ 308 zones:

| Period | Lights | Equipment | HVAC | Total |
|---|---:|---:|---:|---:|
| Mar 2024 | 71,905.7 kWh | 76,533.7 kWh | 9,297.6 kWh | 157,737.0 kWh |
| Apr 2024 | 71,299.2 kWh | 75,641.8 kWh | 45,906.0 kWh | 192,847.0 kWh |
| Terminal May row | 3.2 kWh | 9.8 kWh | 0.0 kWh | 13.0 kWh |
| Full package | 143,208.1 kWh | 152,185.3 kWh | 55,203.6 kWh | 350,597.1 kWh |

## 3. Kiến trúc target

Target nên là một data spine duy nhất:

```text
final_elnino 308 zones
  -> canonical zone dimension 308 zones in Postgres
  -> telemetry_zone_15m all 308 zones
  -> weather_15m same timestamps
  -> Control & Simulation campaign from same telemetry
  -> electrical_distribution artifacts rebuilt from same zone power data
  -> /electrical reads rebuilt artifacts
```

Khi đó:

- Control & Simulation March 2024 `Without AI` phải khoảng `157,737 kWh`
- Control & Simulation April 2024 `Without AI` phải khoảng `192,847 kWh`
- tooltip 25 Apr 2024 `Without AI` phải khoảng `9,040.2 kWh`
- Electrical board totals phải reconcile về category totals của cùng dataset
- UI label "building" mới đúng nghĩa true building

### Ranh giới dữ liệu chuẩn

Không trộn các nguồn sau trong cùng một view production:

| Layer | Hiện tại | Target |
|---|---|---|
| Control chart | Postgres telemetry 14 zones | Postgres telemetry 308 zones từ `final_elnino` |
| Electrical board graph | `data/final` 2025 artifact | `data/final_elnino` 2024 artifact |
| Model inference | local LightGBM files | MLflow Registry primary |
| Weather | tùy loader hiện tại | `final_weather_timeseries` cùng timestamp |
| 3D live zones | 14 selected zones | 308 canonical zones nếu làm full 3D phase |

### Contract giữa các layer

Mỗi response chính nên trả metadata dataset để debug:

```json
{
  "dataset_key": "elnino_2024_mar_apr",
  "scenario_id": "elnino_2024_mar_apr_baseline",
  "timezone": "Asia/Ho_Chi_Minh",
  "timestep_minutes": 30,
  "zone_count": 308,
  "row_count": 901824,
  "source": "final_elnino"
}
```

Các API đọc time-series phải filter `scenario_id`. Không nên chỉ filter
`building_id`, vì bảng có thể chứa nhiều scenario hoặc reload từ dataset khác.

Đề xuất default:

- nếu request không truyền `scenario_id`, backend dùng `GREENFLOW_SCENARIO_ID`
- response luôn echo lại `scenario_id`
- validation endpoint báo lỗi nếu row count khác expected

### Target predictive control flow

Luồng AI target không nên là fixed what-if policy đơn giản. Target đúng kỹ thuật
là **predictive control / receding horizon control**:

```text
At timestep t:
  1. Semantic building state
     - toàn bộ 308 spaces/zones
     - devices, systems, floor/zone relations
     - latest telemetry at t
     - weather/occupancy/tariff context
     - comfort and operational constraints

  2. Prediction over horizon H timesteps
     - dùng MLflow surrogate models
     - dự đoán baseline trajectory nếu không can thiệp
     - dự đoán temperature, HVAC, total power, comfort risk, peak risk
     - H là configurable, ví dụ 8/16/24 timesteps, không hard-code 60 phút

  3. Control optimization
     - feed toàn bộ predicted trajectory vào Control Agent
     - sinh top-k candidate action trajectories
     - mỗi trajectory là chuỗi action từ t+1 đến t+H
     - mục tiêu là giảm energy/cost/peak nhưng giữ comfort và tránh ramp tải quá cao

  4. Fast surrogate evaluation
     - chạy surrogate nhanh cho từng candidate trajectory
     - chấm objective score
     - chọn trajectory tốt nhất

  5. Receding horizon execution
     - chỉ execute hoặc schedule bước t+1
     - sang timestep tiếp theo, đọc state mới và re-plan lại
```

Điểm quan trọng: AI không chọn một action rời rạc cho một giờ đơn lẻ. AI chọn một
**trajectory** tốt nhất trong horizon, nhưng chỉ thực hiện bước kế tiếp. Đây là
nguyên lý predictive control: điều khiển từ từ, tránh tăng tải đột ngột, giữ comfort
và cho phép hệ thống tự sửa khi state thực tế thay đổi.

### Predictive objective đề xuất

Mỗi candidate trajectory nên được chấm bằng objective rõ ràng:

```text
score = energy_cost
      + peak_penalty
      + comfort_penalty
      + ramp_penalty
      + action_change_penalty
      + policy_risk_penalty
```

Trong đó:

- `energy_cost`: kWh hoặc VND trong horizon.
- `peak_penalty`: phạt khi vượt peak threshold hoặc tạo peak mới.
- `comfort_penalty`: phạt zone occupied vượt comfort band.
- `ramp_penalty`: phạt thay đổi tải/setpoint quá nhanh giữa các timestep.
- `action_change_penalty`: phạt bật/tắt hoặc đổi setpoint liên tục.
- `policy_risk_penalty`: phạt action high-risk hoặc zone critical.

Constraints tối thiểu:

- cooling setpoint nằm trong range an toàn, ví dụ `22-27 C`.
- mỗi timestep không đổi setpoint quá ngưỡng, ví dụ `<= 0.5-1.0 C`.
- không tăng setpoint ở zone đang comfort high risk.
- không shutdown HVAC toàn nhà nếu không có approval.
- action phải có provenance và reason.

### Candidate trajectory schema

Control Agent nên sinh top-k candidate trajectories, không chỉ top-k action đơn lẻ:

```json
{
  "trajectory_id": "traj_001",
  "horizon_start": "2024-04-25T13:00:00+07:00",
  "horizon_steps": 8,
  "step_minutes": 30,
  "actions": [
    {
      "step": 1,
      "start": "2024-04-25T13:30:00+07:00",
      "end": "2024-04-25T14:00:00+07:00",
      "action_type": "hvac_setpoint_delta",
      "target_zone_keys": ["zone_..."],
      "setpoint_delta_c": 0.5,
      "lighting_factor": null
    }
  ],
  "predicted": {
    "energy_kwh": 123.4,
    "peak_kw": 456.7,
    "comfort_violation_min": 0,
    "cost_vnd": 123456
  },
  "objective": {
    "score": 123.45,
    "energy_cost": 80.0,
    "peak_penalty": 20.0,
    "comfort_penalty": 0.0,
    "ramp_penalty": 5.0,
    "action_change_penalty": 2.0,
    "policy_risk_penalty": 0.0
  },
  "execute_step": 1
}
```

Persisted AI result nên lưu:

- selected trajectory
- top-k rejected trajectories với scores
- actual executed `t+1` action
- model version
- dataset/scenario metadata
- prediction horizon
- constraints version

### Target validation/replay flow

Validation đúng cho AI predictive control không phải tính một lần
`measured - surrogate reduction`. Target validation phải replay từng timestep:

```text
baseline 308-zone E+ telemetry
  -> for t = start .. end:
       read baseline state at t
       build semantic building state for all 308 zones
       predict horizon H using surrogate
       generate top-k action trajectories
       surrogate-evaluate each trajectory
       choose best trajectory
       apply only t+1 action to AI simulated state
       persist AI state/action/score for t+1
  -> compare full baseline trajectory vs AI trajectory
```

Vai trò surrogate trong validation:

- thay thế việc rerun EnergyPlus cho mỗi AI action timestep
- update counterfactual AI state tại `t+1`
- cho phép replay toàn period nhanh hơn E+

Baseline vẫn là 308-zone E+ telemetry có sẵn. AI result là counterfactual trajectory
được tạo bằng control loop + surrogate. Đây mới là validation đúng với ý nghĩa:

```text
Without AI = E+ baseline telemetry
With AI = predictive-control trajectory simulated by surrogate timestep-by-timestep
```

Compare output:

- total baseline kWh vs AI kWh
- daily baseline vs AI
- peak baseline vs AI
- comfort violation baseline vs AI
- ramp/load-shift impact
- action count and action stability
- metadata: model versions, horizon, objective weights, constraints, zone coverage

## 4. Suggestions nâng cấp

### 4.1. Tạo dataset config dùng chung

Hiện mỗi subsystem tự biết path riêng. Nên tạo một config/data-source layer dùng
chung cho backend:

```text
GREENFLOW_DATASET=elnino_2024_mar_apr
GREENFLOW_DUCKDB_PATH=...
GREENFLOW_PARQUET_ROOT=...
GREENFLOW_SCENARIO_ID=elnino_2024_mar_apr_baseline
GREENFLOW_TIMESTEP_MINUTES=30
```

Mục tiêu là `Control`, `Forecast`, `Electrical`, `Chat/RAG`, dashboard analytics
cùng đọc một dataset identity.

File/code nên thêm:

- `backend/greenflow/datasets.py`
- hoặc mở rộng `backend/greenflow/config.py`

Contract đề xuất:

```python
@dataclass(frozen=True)
class DatasetConfig:
    key: str
    scenario_id: str
    timezone: str
    timestep_minutes: int
    duckdb_path: Path
    parquet_root: Path
    expected_zones: int
    expected_timesteps: int
    expected_zone_rows: int
```

Default production config:

```python
DatasetConfig(
    key="elnino_2024_mar_apr",
    scenario_id="elnino_2024_mar_apr_baseline",
    timezone="Asia/Ho_Chi_Minh",
    timestep_minutes=30,
    duckdb_path=DATA / "final_elnino" / "1. Dạng duckdb" / "...SELF_CONTAINED.duckdb",
    parquet_root=DATA / "final_elnino" / "3. Dạng parquet",
    expected_zones=308,
    expected_timesteps=2928,
    expected_zone_rows=901824,
)
```

Không hard-code path trong từng router/pipeline nữa. Electrical config, loader,
simulation router và validation script đều phải lấy cùng config này.

### 4.2. Dùng MLflow Registry làm nguồn model inference

Repo đã có script post model lên MLflow:

- `scripts/log_models_to_mlflow.py`
- experiment: `greenflow-surrogate`
- registered models:
  - `greenflow_surrogate_building`
  - `greenflow_surrogate_zone`
  - `greenflow_surrogate_hvac`

Hiện inference code vẫn load file local:

- `backend/greenflow/ml/realforecast.py::_load_zone()`
- `backend/greenflow/ml/realforecast.py::_load_hvac()`
- model local path: `backend/greenflow/ml/models/surrogate_real_*.txt`

Nên nâng cấp thành model provider có thứ tự ưu tiên:

```text
1. MLflow Registry alias/production version
2. local committed model files fallback
3. heuristic fallback chỉ khi model unavailable
```

Config đề xuất:

```text
MLFLOW_TRACKING_URI=http://mlflow:5000
GREENFLOW_MODEL_SOURCE=mlflow
GREENFLOW_MODEL_STAGE_OR_ALIAS=production
GREENFLOW_MODEL_BUILDING=models:/greenflow_surrogate_building/1
GREENFLOW_MODEL_ZONE=models:/greenflow_surrogate_zone/1
GREENFLOW_MODEL_HVAC=models:/greenflow_surrogate_hvac/1
```

Nếu dùng alias trong MLflow, nên chuyển sang:

```text
GREENFLOW_MODEL_BUILDING=models:/greenflow_surrogate_building@production
GREENFLOW_MODEL_ZONE=models:/greenflow_surrogate_zone@production
GREENFLOW_MODEL_HVAC=models:/greenflow_surrogate_hvac@production
```

Nâng cấp dependency:

- `pyproject.toml` optional extra `ml` hiện có `lightgbm`, `numpy`, `pandas`
- cần thêm `mlflow` vào runtime ML extra hoặc tạo extra riêng `mlflow`
- backend container production phải cài extra này nếu muốn infer trực tiếp từ registry

API/code suggestion:

- tạo module mới `backend/greenflow/ml/model_registry.py`
- expose `load_model(name)` trả về `(model, features, source_metadata)`
- cache model bằng `lru_cache`
- đọc features từ MLflow model signature nếu đã log đủ, hoặc fallback từ
  `surrogate_real_meta.json`
- response `/api/ml/model-info` nên trả thêm:
  - `tracking_uri`
  - `registered_model`
  - `version`
  - `run_id`
  - `source = mlflow | local_file`

`campaign_whatif.py` nên dùng model provider mới, không import trực tiếp
`_load_zone()` từ `realforecast.py`. Như vậy Control & Simulation sẽ infer bằng
model registry đã post, và local file chỉ còn là fallback/offline mode.

Model provider API đề xuất:

```python
model = load_model("zone")
pred = model.predict(frame)
```

`load_model("zone")` trả:

```python
{
    "model": booster_or_pyfunc,
    "features": [...],
    "source": "mlflow",
    "registered_model": "greenflow_surrogate_zone",
    "version": "1",
    "run_id": "...",
}
```

Nếu dùng `mlflow.pyfunc.load_model`, input DataFrame có thể đi qua pyfunc. Nếu
cần LightGBM Booster trực tiếp để giữ code hiện tại, có thể dùng
`mlflow.lightgbm.load_model`.

Lưu ý về feature order:

- model LightGBM cần đúng thứ tự features
- features hiện nằm trong `surrogate_real_meta.json`
- khi log model lên MLflow nên log thêm artifact `features.json` hoặc model signature
- nếu MLflow model chưa có signature, provider phải fallback đọc local meta file

Acceptance check:

```text
GET /api/ml/model-info
```

phải trả được 3 model registry:

- `greenflow_surrogate_building`
- `greenflow_surrogate_zone`
- `greenflow_surrogate_hvac`

và `source` phải là `mlflow` khi backend chạy trong docker network có service
`mlflow`.

### 4.3. Nâng cấp canonical zones từ 14 lên 308

`db/seed/normalized_building.json` hiện có:

- `zone_count: 14`
- `space_count: 308`

Tức là 3D/BIM có 308 spaces, nhưng app DB chỉ seed 14 live zones.

Cần thêm script seed/update zones 308:

- lấy canonical zones từ `backend/greenflow/electrical/spatial_map.py::build_zones()`
- hoặc lấy `final_zone_metadata` + ARCH `IfcSpace`
- `zone_id` DuckDB dạng `tz_*`
- `entity_key` trong app nên là `zone_*` để giữ convention hiện tại
- upsert vào bảng `zones`
- giữ `raw_ifc_guid`, `source_space_name`, `area_m2`, `volume_m3`, `floor_id`, `room_type`

Nếu vẫn cần 14 zones nổi bật cho UI/camera/demo, nên đánh dấu bằng metadata riêng,
không dùng 14 zones làm source telemetry chính.

Implementation detail:

- tạo script mới `scripts/sync_true_building_zones.py`
- script đọc `final_zone_metadata` hoặc `backend/greenflow/electrical/spatial_map.py`
- upsert `floors` trước, rồi `zones`
- giữ UUID stable bằng `uuid5(namespace, entity_key)` để reload không đổi IDs
- `entity_key = "zone_" + zone_id.removeprefix("tz_")`
- `raw_ifc_guid` lấy từ ARCH space nếu map được
- nếu không map được floor, vẫn insert zone nhưng `floor_id = NULL` và ghi warning

Validation:

```sql
SELECT count(*) FROM zones
WHERE building_id = 'b0000000-0000-0000-0000-000000000001';
-- expected >= 308

SELECT count(*) FROM zones
WHERE building_id = 'b0000000-0000-0000-0000-000000000001'
  AND entity_key LIKE 'zone_%';
-- expected: 308 nếu chỉ tính EnergyPlus/IfcSpace zones
```

Không xóa 14 zones cũ nếu đang được viewer/camera dùng. Nếu entity_key trùng thì
upsert; nếu 14 zones là subset của 308 thì chúng sẽ trở thành cùng canonical row.

### 4.4. Nâng cấp `scripts/load_real_data.py`

Hiện script chỉ load 14 zones. Cần đổi thành loader true building:

- bỏ filter `REPO_ENTITY_KEYS`
- load toàn bộ `final_ai_training_timeseries`
- map `tz_*` -> `zone_*`
- auto-create hoặc validate đủ 308 `zones` trong Postgres trước khi ghi telemetry
- ghi `scenario_id = elnino_2024_mar_apr_baseline`
- dùng `COPY`/bulk insert thay vì insert loop nhỏ nếu muốn nhanh
- giữ bảng `telemetry_zone_15m` nhưng ghi rõ data là 30-minute, không phải 15-minute

Column quan trọng:

- `total_power_kw = target_total_zone_power_kw`
- `energy_kwh = target_total_zone_power_kw * 0.5`
- `hvac_power_kw = hvac_power_kw`
- `lighting_power_kw = lights_electricity_kw`
- `plug_power_kw = equipment_electricity_kw`

Sau load, validation bắt buộc:

```sql
SELECT count(*) FROM telemetry_zone_15m
WHERE scenario_id = 'elnino_2024_mar_apr_baseline';
-- expected: 901824

SELECT count(DISTINCT zone_id) FROM telemetry_zone_15m
WHERE scenario_id = 'elnino_2024_mar_apr_baseline';
-- expected: 308
```

Implementation detail:

- đổi `DATASET_SCHEMA=elnino2024` thành default khi `GREENFLOW_DATASET=elnino_2024_mar_apr`
- bỏ `REPO_ENTITY_KEYS` khỏi code path true-building
- query DuckDB không có `WHERE zone_id IN (...)`
- join zone UUID bằng `entity_key`
- delete theo `(building_id, scenario_id)` thay vì delete toàn bộ building nếu muốn giữ dataset khác
- nếu schema hiện chưa có scenario dimension trong primary key, cần cẩn thận:
  `telemetry_zone_15m` primary key là `(timestamp, zone_id)`, nên cùng một zone không
  thể giữ nhiều scenario cùng timestamp trong bảng này

Vì primary key hiện không có `scenario_id`, có 2 lựa chọn:

1. **Replace mode, recommended cho demo hiện tại**
   - xóa telemetry của building trước khi load El Nino
   - chỉ giữ một active scenario trong `telemetry_zone_15m`

2. **Multi-scenario mode**
   - cần migration đổi primary key thành `(timestamp, zone_id, scenario_id)`
   - blast radius lớn hơn vì nhiều query đang assume một row mỗi zone/timestamp

Cho phase này nên dùng Replace mode để giảm rủi ro.

### 4.5. Đồng bộ `weather_15m`

`/api/simulations/campaign` join `weather_15m` theo timestamp. Cần đảm bảo weather
cũng từ `final_elnino/final_weather_timeseries`, không dùng weather cũ.

Mapping:

- `timestamp = datetime`
- `outdoor_temp_c = outdoor_temp_c`
- `humidity_pct = outdoor_rh_pct`
- `wind_speed_mps = wind_speed_m_s`
- `solar_w_m2 = global_horizontal_radiation_w_m2`
- `cloud_cover_pct = total_sky_cover_tenths * 10`

Validation:

```sql
SELECT count(*), min(timestamp), max(timestamp)
FROM weather_15m;
-- expected: 2928, 2024-03-01 00:30, 2024-05-01 00:00
```

### 4.6. Cập nhật Control & Simulation API

Sau khi DB có 308 zones, API campaign có thể giữ nguyên logic tổng hợp vì query
đang lấy toàn bộ `telemetry_zone_15m` theo building. Nhưng nên nâng cấp thêm:

- filter rõ `scenario_id`
- response trả metadata: `dataset_key`, `scenario_id`, `zone_count`, `row_count`,
  `timestep_minutes`, `source`
- chart subtitle không hard-code "building" nếu `zone_count < expected`
- validation endpoint để check baseline totals trước khi hiển thị

Acceptance numbers:

| View | Expected `Without AI` |
|---|---:|
| March 2024 month | 157,737.0 kWh |
| April 2024 month | 192,847.0 kWh |
| 25 Apr 2024 tooltip | 9,040.2 kWh |

API response đề xuất:

```json
{
  "metadata": {
    "dataset_key": "elnino_2024_mar_apr",
    "scenario_id": "elnino_2024_mar_apr_baseline",
    "zone_count": 308,
    "row_count": 901824,
    "model_source": "mlflow",
    "model_name": "greenflow_surrogate_zone",
    "model_version": "1"
  },
  "policy": {},
  "kpi": {},
  "daily": []
}
```

Frontend `CampaignWhatIf.tsx` nên:

- hiển thị dataset/scenario nhỏ trong panel
- nếu `metadata.zone_count < 308`, hiện warning nhỏ `Partial zone coverage`
- không dùng wording "building" khi zone coverage partial
- nếu full 308 zones thì title có thể giữ `building with AI vs without AI`

### 4.7. Thêm predictive control engine

Hiện `Campaign What-if` chỉ apply fixed setpoint policy. Cần thêm engine riêng cho
predictive control, không nhét vào `campaign_whatif.py`.

Module đề xuất:

```text
backend/greenflow/control/predictive.py
backend/greenflow/control/objective.py
backend/greenflow/control/trajectory.py
backend/greenflow/control/replay.py
```

API nội bộ đề xuất:

```python
def build_semantic_state(building_id, ts, *, scenario_id) -> SemanticState:
    ...

def predict_horizon(state, horizon_steps, *, model_provider) -> PredictedTrajectory:
    ...

def generate_candidate_trajectories(state, prediction, *, top_k) -> list[ActionTrajectory]:
    ...

def evaluate_trajectory(state, candidate, *, model_provider, objective) -> TrajectoryScore:
    ...

def select_best(candidates) -> ActionTrajectory:
    ...

def execute_receding_step(best_trajectory) -> ActionStep:
    ...
```

`build_semantic_state` phải dùng đủ 308 spaces/zones:

- `zones`
- `floors`
- `devices`
- `mesh_entity_map` nếu có
- latest telemetry at timestep `t`
- weather at `t` và weather forecast trong horizon
- occupancy/current comfort state
- tariff and peak window

`predict_horizon` không được chỉ dự đoán `horizon_minutes=60`. Horizon nên là:

```text
GREENFLOW_CONTROL_HORIZON_STEPS=8|16|24
GREENFLOW_CONTROL_STEP_MINUTES=30
```

`generate_candidate_trajectories` nên sinh top-k theo nhiều strategy:

- conservative comfort-first
- peak shaving
- energy saving
- load smoothing
- minimal action change

Mỗi trajectory gồm chuỗi actions cho từng timestep trong horizon. Ví dụ:

```text
t+1: zone group A +0.5C, lights 0.9
t+2: giữ +0.5C
t+3: zone group B +0.5C nếu comfort vẫn safe
t+4: release dần về baseline
```

`evaluate_trajectory` dùng surrogate để rollout toàn horizon:

- input = state tại `t`
- apply candidate actions theo từng step
- predict next state/power/comfort
- accumulate objective

`execute_receding_step` chỉ trả action của step đầu tiên. Không execute cả horizon.

Persistence đề xuất:

- bảng mới `control_trajectories`
- bảng mới `control_trajectory_steps`
- hoặc trước mắt lưu JSON vào `agent_runs.state_json` / `simulation_runs.actions_json`

Schema tối thiểu nếu tạo bảng:

```sql
control_trajectories:
  id, building_id, scenario_id, issued_at, horizon_steps, step_minutes,
  selected boolean, score numeric, metadata jsonb

control_trajectory_steps:
  trajectory_id, step_index, start_ts, end_ts, action_json, predicted_json
```

### 4.8. Thêm validation replay engine cho AI trajectory

Validation target phải chạy qua toàn bộ period hoặc selected period, từng timestep.

Module đề xuất:

```text
backend/greenflow/validation/predictive_replay.py
scripts/run_predictive_control_replay.py
```

Input:

- baseline telemetry 308 zones từ `telemetry_zone_15m`
- weather 30-min từ `weather_15m`
- model provider MLflow
- horizon `H`
- objective weights
- constraints
- replay date range

Pseudo-code:

```python
for ts in replay_index:
    semantic = build_semantic_state(building_id, ts, scenario_id=scenario)
    prediction = predict_horizon(semantic, H, model_provider=models)
    candidates = generate_candidate_trajectories(semantic, prediction, top_k=K)
    scored = [evaluate_trajectory(semantic, c, models, objective) for c in candidates]
    best = select_best(scored)
    step_action = execute_receding_step(best)
    ai_state_next = apply_action_and_predict_next(semantic, step_action, models)
    persist_step(ts, semantic, prediction, scored, best, step_action, ai_state_next)
```

Important:

- baseline state at `t` comes from E+ telemetry
- AI state at `t+1` is surrogate-predicted counterfactual
- for a closed replay, later timesteps should use previous AI state where relevant,
  not blindly reset everything to baseline each step
- exogenous variables như weather/occupancy có thể lấy từ baseline dataset để so
  cùng điều kiện

Output artifact đề xuất:

```text
data/validation/predictive_control_replay/
  ai_zone_timeseries.parquet
  ai_building_timeseries.parquet
  selected_actions.parquet
  candidate_trajectories.parquet
  replay_summary.json
```

Compare metrics:

- baseline total kWh vs AI total kWh
- daily kWh baseline vs AI
- peak kW baseline vs AI
- peak hour shift
- comfort violation minutes baseline vs AI
- load ramp max and average
- number of action changes
- accepted/rejected candidate scores
- model versions and objective weights

API endpoint đề xuất:

```text
POST /api/simulations/predictive-replay
GET  /api/simulations/predictive-replay/latest
GET  /api/simulations/predictive-replay/series
```

Frontend `Control & Simulation` nên tách rõ:

- `Period what-if`: simple policy/surrogate estimate, optional legacy panel
- `Predictive control replay`: full AI validation trajectory

Khi predictive replay đã có, KPI chính nên dùng replay result, không dùng campaign
what-if đơn giản làm claim chính.

### 4.9. Rebuild Electrical Graph từ El Nino

Không nên dùng artifact hiện tại trong `data/electrical_distribution` nếu mục tiêu
là true building El Nino.

Có 2 hướng:

1. **Versioned outputs, recommended**
   - output mới: `data/electrical_distribution_elnino`
   - tránh ghi đè artifact 2025
   - frontend/backend chọn artifact theo dataset config

2. **Replace current outputs**
   - ghi đè `data/electrical_distribution`
   - đơn giản hơn nhưng dễ mất khả năng so sánh 2025

Pipeline hiện tại mong schema 2025:

- `timestamp_local`
- `scenario_id`
- `lights_electricity_kwh_interval`
- `equipment_electricity_kwh_interval`
- `final_hvac_electricity_kw`
- `final_hvac_electricity_kwh_interval`
- `final_total_zone_electricity_kwh_interval`

El Nino dùng schema khác. Nên thêm một normalized projection thay vì sửa rải rác:

```sql
SELECT
  row_number() OVER (ORDER BY datetime) AS timestep_index,
  datetime AS timestamp_local,
  'elnino_2024_mar_apr_baseline' AS scenario_id,
  zone_id,
  eplus_zone_name,
  area_m2_final AS area_m2,
  volume_m3_final AS volume_m3,
  height_m_final AS ceiling_height_m,
  lights_electricity_kw,
  lights_electricity_kwh AS lights_electricity_kwh_interval,
  equipment_electricity_kw,
  equipment_electricity_kwh AS equipment_electricity_kwh_interval,
  hvac_power_kw AS final_hvac_electricity_kw,
  hvac_electricity_kwh AS final_hvac_electricity_kwh_interval,
  target_total_zone_power_kw AS final_total_zone_electricity_kw,
  target_total_zone_power_kw * 0.5 AS final_total_zone_electricity_kwh_interval
FROM final_zone_device_power_timeseries
```

Sau đó `board_timeseries.py`, `validate.py`, `energy_map.py` có thể chạy gần như
logic cũ nhưng đọc projection mới.

Implementation detail:

- tạo dataset-aware electrical config:
  - `OUT_ELEC = data/electrical_distribution_elnino`
  - `SCENARIO_ID = elnino_2024_mar_apr_baseline`
  - `ZONE_TS` trỏ vào normalized projection hoặc direct El Nino parquet
- tránh sửa global `data/electrical_distribution` trong phase đầu
- thêm env/config `GREENFLOW_ELECTRICAL_OUT=data/electrical_distribution_elnino`
- router `/api/electrical/*` nên đọc output theo active dataset config
- dashboard manifest phải ghi `dataset_key`, `scenario_id`, `period_start`, `period_end`

Acceptance numbers cho Electrical rebuild:

- board timeseries range phải là `2024-03-01 00:30` đến `2024-05-01 00:00`
- board category total phải bằng zone category total trong `final_elnino`
- full package total phải reconcile khoảng `350,597.1 kWh`
- March board total khoảng `157,737.0 kWh`
- April board total khoảng `192,847.0 kWh`
- không còn xuất hiện `openmeteo_2025_30min_baseline` trong manifest/dashboard payload

### 4.10. Cập nhật UI `/electrical`

Sau rebuild, UI `/electrical` cần đổi wording:

- "Annual energy" không đúng với dataset Mar-Apr 2024, nên đổi thành "Period energy"
- subtitle nên hiển thị scenario/date range
- board register nên có badge `El Nino Mar-Apr 2024`
- nếu có scenario switch sau này, `/electrical` phải gọi API kèm dataset/scenario

### 4.11. Test và validation tự động

Nên thêm test/check script:

```text
scripts/validate_true_building_sync.py
```

Check tối thiểu:

- DuckDB final_elnino có 308 zones, 901,824 rows
- Postgres `zones` có 308 zones cho building
- Postgres `telemetry_zone_15m` có 901,824 rows cho scenario
- March/April/25-Apr totals khớp expected
- `weather_15m` có 2,928 rows cùng timestamp range
- electrical artifact range là 2024, không phải 2025
- electrical board total reconcile với zone category total trong tolerance <= 0.5%
- predictive replay có AI trajectory đủ timestep trong date range
- mỗi replay step có selected trajectory, top-k candidates và executed `t+1` action

### 4.12. Full 3D building scope

Nếu yêu cầu là "hiển thị hết tòa nhà" ở mức chart/KPI thì 308-zone telemetry là đủ.
Nếu yêu cầu là viewer 3D click/inspect đủ tất cả spaces/zones, cần thêm phase 3D.

Hiện trạng:

- `db/seed/normalized_building.json` có `zone_count: 14`
- cùng file có `space_count: 308`
- `scripts/build_3d_assets_ifc.py` đã có logic spaces/thermal zones từ IFC
- electrical `spatial_map.py` cũng biết 308 IfcSpaces

Nâng cấp 3D cần:

- build/seed `mesh_entity_map` cho 308 zones/spaces
- đảm bảo `entity_key` của mesh map khớp `zones.entity_key`
- viewer khi click zone phải resolve được zone UUID trong Postgres
- inspector panel phải query đúng zone telemetry theo selected zone
- các 14 zones highlighted có thể giữ như curated default view, nhưng không được là
  toàn bộ data coverage

Acceptance check 3D:

- chọn bất kỳ space thuộc 308 zones trên viewer thì inspector có `zone_id/entity_key`
- zone đó query được telemetry trong `telemetry_zone_15m`
- layer Spaces/Zones không chỉ highlight 14 zones nếu user bật full building mode
- chart vẫn aggregate 308 zones dù viewer đang focus một subset

## 5. Thứ tự triển khai đề xuất

### Phase 1. Data spine + MLflow inference

Mục tiêu: Control & Simulation dùng đúng model registry và chuẩn bị config chung.

Việc cần làm:

1. Tạo dataset config chung cho `elnino_2024_mar_apr`.
2. Thêm `mlflow` dependency vào ML/runtime extra.
3. Tạo `backend/greenflow/ml/model_registry.py`.
4. Chuyển `realforecast.py` và `campaign_whatif.py` sang dùng model provider.
5. Cập nhật `/api/ml/model-info` để báo model source/version.

Validation gate:

- `/api/ml/model-info` trả đủ 3 registered models.
- Khi MLflow reachable, `source = mlflow`.
- Khi MLflow down, fallback local file vẫn chạy.

### Phase 2. True-building telemetry 308 zones

Mục tiêu: Control chart/KPI không còn 14 zones.

Việc cần làm:

1. Seed/upsert đủ 308 zones vào Postgres.
2. Nâng `load_real_data.py` thành true-building loader.
3. Load lại `telemetry_zone_15m` từ `final_elnino`.
4. Load lại `weather_15m` từ `final_weather_timeseries`.
5. Cập nhật `/api/simulations/campaign` trả metadata dataset/zone coverage.
6. Cập nhật `CampaignWhatIf.tsx` hiển thị metadata/warning partial coverage.

Validation gate:

- `zones` có 308 canonical `zone_*`.
- `telemetry_zone_15m` có 901,824 rows.
- `weather_15m` có 2,928 rows.
- March baseline khoảng `157,737.0 kWh`.
- April baseline khoảng `192,847.0 kWh`.
- Tooltip `25 Apr 2024` baseline khoảng `9,040.2 kWh`.

### Phase 3. Predictive control engine

Mục tiêu: thay thế logic "fixed +3C what-if" bằng receding horizon predictive
control đúng kỹ thuật.

Việc cần làm:

1. Tạo control modules: predictive, trajectory, objective.
2. Build semantic state đủ 308 zones tại timestep `t`.
3. Dự đoán horizon `H` timesteps bằng MLflow surrogate.
4. Sinh top-k candidate action trajectories.
5. Evaluate top-k bằng surrogate rollout.
6. Chọn best trajectory nhưng chỉ expose/execute action `t+1`.
7. Persist trajectory, score, objective breakdown và model metadata.

Validation gate:

- một request control tại timestamp bất kỳ trả đủ top-k trajectories.
- response có selected best trajectory và action `t+1`.
- horizon không bị hard-code 60 phút.
- objective breakdown có energy/peak/comfort/ramp/action-change penalty.

### Phase 4. Predictive validation replay

Mục tiêu: validate AI bằng cách replay toàn period timestep-by-timestep.

Việc cần làm:

1. Tạo `predictive_replay.py`.
2. Tạo script `scripts/run_predictive_control_replay.py`.
3. Với mỗi timestep, chạy semantic -> predict -> control -> surrogate evaluate -> apply `t+1`.
4. Persist AI counterfactual trajectory.
5. Compare baseline 308-zone E+ telemetry vs AI trajectory.
6. Frontend đọc replay result làm KPI chính cho `With AI vs Without AI`.

Validation gate:

- replay có đủ timestep trong selected period.
- mỗi timestep có selected trajectory và executed action.
- baseline series lấy từ E+ telemetry 308 zones.
- AI series lấy từ surrogate counterfactual rollout.
- KPI trả metadata model/horizon/objective/constraints.

### Phase 5. Electrical El Nino rebuild

Mục tiêu: `/electrical` đọc artifact cùng dataset 2024, không đọc 2025.

Việc cần làm:

1. Thêm normalized projection cho El Nino schema.
2. Tạo output versioned `data/electrical_distribution_elnino`.
3. Rebuild board timeseries, category timeseries, summaries, manifest, validation.
4. Cập nhật electrical API đọc artifact theo active dataset.
5. Cập nhật UI wording `Annual energy` -> `Period energy`.

Validation gate:

- board artifact range là `2024-03-01 00:30` đến `2024-05-01 00:00`.
- full board total reconcile khoảng `350,597.1 kWh`.
- March board total khoảng `157,737.0 kWh`.
- April board total khoảng `192,847.0 kWh`.
- manifest không còn `openmeteo_2025_30min_baseline`.

### Phase 6. Full 3D zone interactivity

Mục tiêu: viewer không chỉ có data 308 zones, mà còn inspect/click đủ 308 zones.

Việc cần làm:

1. Build/seed `mesh_entity_map` cho 308 spaces/zones.
2. Đồng bộ `entity_key` giữa viewer mesh, Postgres `zones`, telemetry và electrical mapping.
3. Cập nhật zone inspector để query telemetry theo selected 308-zone entity.
4. Thêm mode hoặc filter phân biệt curated 14 highlighted zones và full 308 zones.

Validation gate:

- click một non-curated zone vẫn inspect được.
- inspector đọc được telemetry của zone đó.
- aggregate chart vẫn là full 308 zones, không phụ thuộc viewer filter.

### Phase 7. Regression validation

Mục tiêu: không regress về 14 zones hoặc artifact 2025.

Việc cần làm:

1. Thêm `scripts/validate_true_building_sync.py`.
2. Thêm test smoke cho `/api/simulations/campaign`.
3. Thêm test artifact electrical range/reconciliation.
4. Thêm test predictive replay output shape và metadata.

Validation gate:

- script fail nếu `25 Apr 2024` baseline là `435.3 kWh`.
- script fail nếu electrical range là 2025.
- script fail nếu `zone_count < 308`.
- script fail nếu predictive replay thiếu timestep/action trajectory metadata.

## 6. Rủi ro cần xử lý trước khi code

- Surrogate trong MLflow hiện vẫn là model đã train/log từ pipeline hiện tại. Nếu
  model train trên 2025 nhưng infer cho El Nino 2024 thì phải ghi rõ là transfer
  surrogate, hoặc train/log version mới từ `final_elnino` nếu muốn claim chính
  xác hơn.
- MLflow Registry phải có alias/stage ổn định. Nếu chỉ gọi `Version 1` hard-code,
  deploy sau này dễ infer nhầm version. Nên dùng alias `production` hoặc config
  explicit model URI.
- 308 zones sẽ làm chart và API nặng hơn 14 zones. Cần index tốt và có thể cần
  aggregate cache theo ngày.
- `telemetry_zone_15m` primary key hiện là `(timestamp, zone_id)`, không gồm
  `scenario_id`. Vì vậy phase đầu nên dùng Replace mode, không cố giữ song song
  2025 và 2024 trong cùng bảng này nếu chưa migration.
- Bảng tên `telemetry_zone_15m` đang chứa 30-minute data. Không nên upsample giả;
  tốt hơn là ghi rõ metadata `timestep_minutes = 30`.
- 3D viewer hiện chỉ có 14 live zones trong normalized seed. Muốn click/inspect đủ
  308 zones thì cần đồng bộ mesh/entity map với 308 zones, không chỉ telemetry.
- Electrical allocation là estimated layer, không phải measured panel data. Sau
  rebuild vẫn phải giữ provenance `spatially_inferred`.
- Không nên ghi đè `data/electrical_distribution` trong lần đầu nếu vẫn cần
  artifact 2025 để so sánh/debug. Dùng `data/electrical_distribution_elnino`.
- Nếu MLflow model URI dùng hard-code `/1`, việc register model mới sẽ không tự
  cập nhật inference. Dùng alias `production` tốt hơn khi registry đã set alias.
- Nếu build 3D full 308 zones ngay trong cùng phase với data sync, blast radius sẽ
  lớn. Nên hoàn thành analytics/electrical trước, rồi mở rộng viewer.
- Predictive replay dùng surrogate thay E+ cho AI trajectory, nên không được claim
  là EnergyPlus rerun. Claim đúng là `surrogate-simulated AI counterfactual`.
- Closed-loop replay phải cẩn thận trạng thái `t+1`: nếu mỗi timestep reset về
  baseline thì đó là open-loop what-if, không phải predictive control replay.
- Objective weights cần versioning. Nếu đổi weight mà không ghi metadata, kết quả
  validation không reproducible.
- Surrogate rollout nhiều timestep có nguy cơ drift. Cần cap/range constraints và
  sanity checks cho temperature, setpoint, HVAC power.
- Top-k trajectory generation có thể rất nặng với 308 zones. Phase đầu nên dùng
  zone grouping hoặc action templates, không brute-force per-zone action space.
