# GreenFlow — Phản biện & Quyết định chốt (SPINE, 2026-06-12)

Tài liệu này là kết quả "suy nghĩ và phản biện" trên bộ docs trong
`project-readme/` trước khi giao code. Mỗi mục: vấn đề → phân tích → **CHỐT**.
Mã D# được tham chiếu từ schema.sql và các module skeleton.

---

## D1. Schema cũ dùng UUID PK — vênh toàn bộ dữ liệu thật

`DATABASE_SCHEMA.sql` cũ: `zones.id uuid DEFAULT gen_random_uuid()`. Nhưng dữ
liệu thật (parquet + zone_equipment_map.json) key bằng **IFC GUID text 22 ký
tự** (`0FmGuf5a54T9pmsaibMAqb`). Nếu giữ UUID phải duy trì bảng crosswalk
uuid↔guid ở MỌI điểm chạm (loader, API, agent, 3D viewer pick theo GUID, E+
mapping) — nguồn bug số 1 trong hackathon.

**CHỐT**: text natural key (IFC GUID) làm PK cho zones/devices/floors.
xeokit pick object → GUID → query API trực tiếp, không dịch khóa.

## D2. Spec cũ gợi ý time-series dạng EAV (metric/value) — sai cho khối lượng này

REPO_BUILD_SPEC_UPDATED §6.4 đề xuất bảng narrow `(entity, metric, value)`.
Với 1,66M dòng zone × ~20 metric → 33M dòng + pivot mỗi query. Parquet đã wide.

**CHỐT**: bảng wide khớp parquet 1:1, COPY thẳng không transform, partition
theo tháng, **không FK** trên bảng TS (validate ở loader). EAV bị bác.

## D3. world_run phải là chiều dữ liệu, không phải metadata

Mọi so sánh baseline-vs-agent là counterfactual "cùng thế giới, khác điều
khiển". Nếu telemetry không key theo world_run thì agent variant phải lưu bảng
riêng/DB riêng → API compare viết 2 lần.

**CHỐT**: `world_run_id` nằm trong PK mọi bảng TS. Compare = self-join 2 run
(đã implement thật trong `api/routers/simulations.py::compare_runs`).
`scenario_kpi` chỉ là cache, không phải nguồn sự thật.

## D4. Timezone là bug âm thầm nguy hiểm nhất

Parquet timestamp naive (local VN). Nếu COPY vào timestamptz với session UTC →
toàn bộ dữ liệu lệch 7 tiếng, peak 14h thành 21h, mọi rule giờ làm việc sai mà
không có lỗi nào ném ra.

**CHỐT**: loader `SET timezone='Asia/Ho_Chi_Minh'` trước COPY; partition bound
khai báo kèm `+07`. Test nạp xong phải check `max(total_power_kw)` rơi vào
9-17h local.

## D5. device_state parquet thiếu scenario_id/world_run_id

zone_state có, device_state không (xem PARQUET_SCHEMA.md). Loader hiện inject
qua CLI; nhưng đây là gap của datagen — khi sinh agent variant mà quên thì
device data của 2 run đè nhau.

**CHỐT**: task cho Opus — thêm 2 cột vào `datagen/pipeline.py` (5 dòng), đồng
thời fix `fault_state` null-type → string.

## D6. "Realtime" phải là replay clock, không phải now()

Dữ liệu là Jun–Aug 2025, demo chạy 2026. Mọi endpoint "latest" mà dùng `now()`
sẽ trả rỗng.

**CHỐT**: tham số `at` (replay clock) trên mọi endpoint state/kpi, mặc định =
`max(timestamp)` của world_run (implement thật trong `state.py::resolve_at`).
Frontend giữ 1 replay tick toàn cục.

## D7. Plan 2 tuần ghi "xeokit", REPO_BUILD_SPEC ghi "Three.js + GLB" — mâu thuẫn

Hai docs chỉ định 2 stack 3D khác nhau, kéo theo asset pipeline khác nhau
(XKT giữ IFC GUID sẵn; GLB cần mesh_entity_map tự build).

**CHỐT theo plan mới nhất (PROJECT_PLAN_2WEEKS §8)**: xeokit + IFC→XKT.
GUID có sẵn trong XKT metadata → pick/highlight không cần bảng mesh map →
schema v2 **bỏ** `geometry_assets/mesh_entity_map` (bớt 2 bảng + 1 pipeline).
Fallback nếu convert XKT trục trặc: 2D floorplan SVG theo floor (đã ghi trong
plan rủi ro).

## D8. "regrettable_substitution_check" chưa từng được định nghĩa

Xuất hiện 4 lần trong docs nhưng không doc nào nói nó check GÌ. Không định
nghĩa được = không code được = mất 1 điểm pitch.

**CHỐT** (implement thật trong `agent/policy.py`, có 11 unit test):
action là "đánh đổi đáng tiếc" nếu cải thiện KPI mục tiêu nhưng:
- R1 comfort: violation tăng > 15 phút trong action window;
- R2 rebound: năng lượng dội lại cửa sổ sau (recool spike) > 50% saving;
- R3 peak: tạo peak mới > 5 kW (pre-cool sai giờ);
- R4 cost-inversion: saving kWh dương nhưng cost VND âm (tariff — tối ưu nhầm mục tiêu).
Regrettable → không bao giờ auto_run, xuống approval kèm flags giải thích.

## D9. BẪY LỚN NHẤT: E+ chạy 5 archetype, action lại ở mức zone

Plan ngày 4–5 viết "action_to_idf → chạy agent E+ variant" như thể nhúng
action 1 zone vào IDF là chuyện hiển nhiên. Không phải: IDF hiện tại chỉ có
**5 zone vật lý (archetype shoebox)**, không có 188 zone. Action trên 1 meeting
room không tồn tại trong E+ model. Nếu Opus không biết điều này sẽ mất 1-2 ngày
đi vòng.

**CHỐT** (spec trong `sim/action_to_idf.py`): area-weighted archetype blending —
sửa `schedules_15m.parquet` per-zone → build_idf aggregate theo diện tích như
nó vẫn làm → E+ validate **building/archetype-level**; phân rã per-zone do
surrogate đảm nhiệm. Honesty khi pitch: "E+ xác nhận tổng saving; per-zone
attribution là surrogate." Tuyệt đối không claim E+ per-zone.

## D10. "Confidence" của forecast cần công thức, không phải vibe

Docs yêu cầu confidence ở mọi nơi (forecast, action, policy gate) nhưng không
định nghĩa. Surrogate R²=0.95 là số GLOBAL — không dùng làm confidence per-prediction được.

**CHỐT** (spec trong `ml/forecast_service.py`): residual-sigma theo bucket
(category, hour) tính lúc train, lưu vào meta; interval = ±1.64σ;
`confidence = 1 − σ/(|yhat|+ε)`. Occupancy: IQR lịch sử của bucket.
Deterministic, giải thích được, không cần train thêm model.

## D11. Surrogate phải NHẠY với setpoint, nếu không agent scoring vô nghĩa

Surrogate hiện train để dự đoán hvac_power từ (weather, time, area, category...).
Agent dùng nó để so sánh setpoint 24°C vs 25.5°C — nếu feature
`cooling_setpoint_c` không có/không nhạy (baseline setpoint gần như constant
trong data!), mọi candidate sẽ score ≈ 0 saving.

Đây là rủi ro thật: **dữ liệu baseline có rất ít variance setpoint** để model
học elasticity. **CHỐT**: (a) khi train phải log partial-dependence của
setpoint vào meta và fail loudly nếu phẳng; (b) nếu phẳng → bổ sung dữ liệu
train bằng 2-3 E+ run với setpoint 23/25/26°C (chạy 1 lần, ~30 phút) để model
học được độ dốc. Ghi thành task T1 riêng — đừng để đến demo mới phát hiện.

## D12. LLM không nằm trên đường ra quyết định

Giữ đúng AGENT_DESIGN: rule sinh candidate, surrogate score, policy gate quyết
auto/approval — tất cả deterministic, test được offline, demo không chết vì
API LLM. LangGraph/LLM chỉ: phân loại intent, lập plan tool-call, sinh giải
thích từ số liệu có sẵn. `reason` của candidate phải đủ tốt TRƯỚC khi LLM
trau chuốt (yêu cầu trong control.py spec).

## D13. Thứ tự build: compare phải chạy được trước khi agent thông minh

Spine đã dựng để **demo M&V chạy được với agent "ngu"**: chỉ cần 1 world_run
thứ hai nạp vào DB (kể cả surrogate-generated) là `/simulations/compare` ra số.
→ T2 có thể demo end-to-end từ ngày đầu với 1 action hardcode, rồi mới làm
rule/scoring tinh vi. Giảm rủi ro tích hợp phút chót.

---

## Những gì spine này ĐÃ LÀM (verify rồi)

- `db/schema.sql` + `seed_core.sql`: áp sạch trên pgvector:pg16 (38 bảng,
  partition checked, 7 scenario seed).
- `contracts/openapi.yaml`: contract đầy đủ cho mọi endpoint trong plan T3.
- `contracts/PARQUET_SCHEMA.md`: đọc từ parquet thật, không chép từ docs.
- `scripts/load_parquet_to_db.py`: loader entities + COPY 3 bảng TS (idempotent).
- API read endpoints (meta/state/kpi/actions/alerts/compare): SQL thật.
- `agent/policy.py` + regrettable check: implement thật, 11/11 test pass.
- `sim/kpi.py`: scenario_kpi aggregate thật.
- Skeleton có spec dày: `agent/control.py`, `ml/forecast_service.py`,
  `ml/occupancy_forecaster.py`, `sim/action_to_idf.py`, `sim/runner.py`,
  `agent/anomaly.py` — mỗi NotImplementedError là 1 task có mã T#.
