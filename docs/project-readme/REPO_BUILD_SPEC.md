# GreenFlow — Repo Build Spec (cho dev)

Tài liệu này là spec để dev dựng repo GreenFlow. Đọc xong là biết: dựng gì, theo thứ tự nào, dữ liệu chảy ra sao, và 3 nguyên tắc bất di bất dịch của hệ thống.

> Đọc kèm: `PROJECT_PROPOSAL.md`, `AGENT_DESIGN.md`, `AGENT_POLICY_PROPOSAL.md`, `DEMO_SCENARIOS.md`, `SEMINAR_IMPROVEMENT_NOTES.md`. Tài liệu này **thay thế** phần kiến trúc DB cũ trong `DATABASE_SCHEMA.md`/`DATABASE_ARCHITECTURE.md` ở những chỗ mâu thuẫn (nêu rõ ở mục 5).

---

## 0. GreenFlow là gì (1 đoạn cho dev)

Lớp phần mềm chạy phía trên một tòa nhà văn phòng: đọc trạng thái (nhiệt độ, người, điện), **mô phỏng** tác động của một hành động trước khi làm, rồi đề xuất/tự động hành động low-risk có kiểm soát, kèm giải thích và lưu vết. Tòa nhà mẫu = `ARK_NordicLCA_Office_Concrete` (10 tầng, 308 phòng). Khung cảnh pitch = văn phòng HCMC nóng ẩm (xem nguyên tắc #2 về giả định khí hậu).

---

## 1. BA NGUYÊN TẮC BẤT DI BẤT DỊCH (đã chốt)

Mọi thiết kế phải tuân thủ. Vi phạm là sai kiến trúc.

**Nguyên tắc 1 — E+ là "tòa nhà ảo" tự tính vật lý. Nhóm KHÔNG bịa số vật lý.**
- EnergyPlus (E+) tự tính: nhiệt độ phòng, điện HVAC, mức vi phạm comfort, peak load.
- Nhóm chỉ tạo **đầu vào**: lịch người ra/vào từng phòng, đèn/ổ cắm theo người, lịch vận hành baseline, thời tiết (lấy số thật từ file EPW).
- KHÔNG được viết rule sinh ra nhiệt độ/điện. Lý do: ML học lại rule của mình → con số vô nghĩa → vỡ trận khi bị hỏi.

**Nguyên tắc 2 — IFC đóng băng; mọi thứ "sống" nằm trong database.**
- Đọc IFC **một lần** → đổ vào DB. Mỗi entity giữ `raw_ifc_guid` làm mỏ neo.
- Trạng thái realtime (nhiệt độ, người, on/off, lệnh AI) **luôn ở DB time-series**, không bao giờ ghi ngược vào IFC.
- Tòa nhà đổi thật (đập phòng, lắp máy) → **re-extract** (đọc lại IFC vào DB), không patch IFC.
- "Digital twin sống" = DB-keyed-by-GUID. IFC chỉ là gốc as-designed.

**Nguyên tắc 3 — Kiểm chứng lệnh AI bằng "diễn lại ngày đó 2 lần rồi so sánh".**
- Mỗi kịch bản chạy E+ 2 (hoặc nhiều) lần trên **cùng thời tiết + cùng lịch người**:
  - `baseline`: vận hành cố định, không AI.
  - `agent`: có áp dụng action của AI (nhúng vào lịch điều khiển).
- Chênh lệch giữa 2 lần = bằng chứng giá trị (điện tiết kiệm, comfort giữ được).
- KHÔNG điều khiển E+ realtime từng phút. Trình bày trung thực: đây là phân tích "nếu… thì…" (what-if counterfactual), không phải controller tự động hoàn toàn.

---

## 2. Stack (giữ gọn — đừng phình)

| Thành phần | Chọn | Ghi chú |
|---|---|---|
| DB | **PostgreSQL + pgvector** (đã có trong `docker-compose.yml`) | 1 DB lo hết: metadata, time-series, graph (recursive query), vector |
| Time-series | Bảng partition trong Postgres | Volume nhỏ (~vài trăm nghìn dòng) → **không cần TimescaleDB** |
| Graph quan hệ | Bảng quan hệ + recursive CTE | **Không Neo4j** |
| Streaming | Vòng tick đọc DB / file | Realtime là replay → **không Redis Streams** |
| Vector/RAG | pgvector | **P2, chỉ làm nếu có chat hỏi tài liệu** (có sẵn PDF chuẩn MEP) |
| Mô phỏng | EnergyPlus (chạy batch) | "Tòa nhà ảo" |
| ML | YOLO pretrained + LightGBM | Xem mục 7 |
| API | FastAPI (Python) | Cùng ngôn ngữ với E+/ML/extractor |
| Web | Next.js | 3 tab (Dashboard / Agent / Simulation) |

---

## 3. Cấu trúc repo

```
greenflow/
  docker-compose.yml          # postgres+pgvector (đã có)
  .env.example
  db/
    schema.sql                # schema mục 5
    seed/                     # dữ liệu seed cho demo (sinh sẵn)
  bim/
    extractor.py              # extractor PIP đã sửa (mục 6)
    out/                      # JSON đã extract (zones, devices, zone_equipment_map...)
  sim/
    idf/                      # model E+ (archetype)
    weather/                  # file EPW (HCMC)
    runner.py                 # chạy 1 trajectory, parse output -> DB
    action_to_idf.py          # dịch action -> chỉnh lịch điều khiển trong IDF
    scenarios.py              # định nghĩa kịch bản (heatwave, after-hours, fault...)
  ml/
    occupancy_yolo.py         # YOLO trên video demo -> occupancy count
    train_surrogate.py        # train LightGBM trên output E+
    forecast_service.py       # bộ "đoán nhanh" cho agent
  agent/
    orchestrator.py           # điều phối + giải thích (LLM)
    policy.py                 # rule engine + regrettable_substitution_check
    tools/                    # state_reader, graph, forecast, simulate, policy
  api/
    main.py                   # FastAPI: states, scenarios, actions, kpi
  web/                        # Next.js: 3 tab
  scripts/
    generate_data.py          # chạy E+ nhiều lần -> sinh dataset + train surrogate
    load_to_db.py             # đổ extractor out + sim output vào DB
```

---

## 4. Hai đồng hồ + vòng lặp (timestep)

**Ba nhịp thời gian — đừng lẫn:**
- **Bước mô phỏng E+**: ~10 phút (E+ tự tính nội bộ).
- **Độ phân giải lưu/hiển thị**: **15 phút** (mọi bảng time-series, dashboard).
- **Nhịp AI ra quyết định (decision tick)**: 15 phút/lần (hoặc theo sự kiện cho demo, ví dụ "phòng vừa trống").
- **Tầm nhìn mỗi quyết định (horizon)**: ~2 giờ tới.

**Vòng lặp của agent tại mỗi tick `t`:**
```
1. Đọc trạng thái lúc t (từ trajectory hiện tại)
2. Bộ đoán nhanh (surrogate) dự báo 2h tới NẾU không làm gì
3. Agent đề xuất 1+ action ứng viên
4. Với mỗi ứng viên: dựng IDF "có áp dụng action từ t" -> chạy E+ -> trajectory phản thực
5. Tính KPI chênh lệch + regrettable_substitution_check
6. Policy quyết: auto / chờ duyệt / từ chối
7. Nếu áp dụng: trajectory "agent" rẽ nhánh từ t
8. Lưu hết: tick, sim ứng viên, action chọn, KPI, audit
```
MVP có thể tiền-tính (pre-bake) phần lớn để demo mượt; chỉ cần 1 zone chạy "live" để show agent phản ứng.

> **Lưu ý comfort:** "số phút vi phạm comfort" không đo được chính xác từ snapshot 15 phút. Cho **E+ xuất thẳng `comfort_violation_min` cho mỗi khoảng 15 phút** (phần của 15 phút bị vi phạm). Tổng lại là chính xác.

---

## 5. Schema cải tiến (cái chính cần build)

Schema cũ (`DATABASE_SCHEMA.md`) ổn ở phần metadata, nhưng **thiếu 6 thứ** khiến không chứng minh được giá trị. Dưới đây là phần thêm/sửa. Giữ nguyên các bảng metadata cũ (`buildings, floors, zones, rooms, devices, device_systems, meters, cameras, tariff_rules`).

### 5.1 THÊM: `scenarios` (thay cho `scenario_id` dạng text)
Mỗi kịch bản demo là 1 dòng.
- `id`, `key` (heatwave_day, after_hours, hvac_fault, high_occupancy, normal_day…)
- `description`
- `weather_file` (EPW dùng)
- `occupancy_profile` (tham chiếu lịch người)
- `fault_injection_json` (vd: device X hỏng từ giờ Y)
- `sim_start`, `sim_end`

### 5.2 THÊM: `world_runs` — mỗi lần chạy E+ = một "trajectory"
Đây là khái niệm còn thiếu hẳn ở schema cũ. Nó cho phép so baseline-vs-agent **trên cùng trục thời gian**.
- `id`, `scenario_id` (FK)
- `variant`: `baseline` | `agent` | `candidate`
- `parent_run_id` (nullable — ứng viên rẽ từ baseline)
- `idf_version`, `created_at`, `status`
- `artifact_path` (file E+ output thô để trên đĩa/object storage, **không** nhét vào DB)

### 5.3 SỬA: các bảng time-series gắn nguồn gốc + trajectory
`telemetry_zone_15m`, `telemetry_device_15m`, `occupancy_zone_15m`: **bỏ** `scenario_id text`, **thêm**:
- `world_run_id` (FK → world_runs)
- `source`: `eplus` | `synthetic_input` | `real`  ← (nguyên tắc #1 & tính trung thực + drift)
- (zone) thêm `comfort_violation_min numeric` do E+ xuất ra.
PK: `(world_run_id, timestamp, zone_id/device_id)`. Partition theo `timestamp`.

### 5.4 THÊM: `decision_ticks` — khi nào AI "thức dậy" và thấy gì
- `id`, `world_run_id`, `tick_time`, `horizon_min`
- `trigger`: schedule | event
- `observed_summary_json` (state lúc đó)
- `status`

### 5.5 SỬA + THÊM: `actions` nối được nhân quả
`actions` thêm:
- `decision_tick_id` (FK)
- `screening_forecast_run_id` (bộ đoán nhanh đã sàng) — nullable
- `validation_world_run_id` (lần E+ kiểm chứng) — nullable
- `tradeoff_summary text`  ← seminar yêu cầu
- `regrettable_check_passed boolean`  ← seminar yêu cầu
Giữ `action_targets` như cũ.

### 5.6 THÊM: `scenario_kpi` — số tiêu đề để pitch (1 dòng / scenario × variant)
Để khỏi phải gom từ EAV mỗi lần lên dashboard.
- `scenario_id`, `world_run_id`, `variant`
- `energy_kwh`, `cost_vnd`, `peak_demand_kw`
- `comfort_violation_min`, `iaq_risk_proxy`, `co2_avoided_kg`
- `unsafe_actions_blocked`, `actions_executed`
- KPI cards ở Tab 3 đọc thẳng bảng này.

### 5.7 THÊM: `comfort_profiles` — cho `comfort_risk` có nghĩa
`comfort_risk` cũ là text rỗng nghĩa. Định nghĩa ngưỡng theo `room_type`:
- `room_type`, `temp_min_c`, `temp_max_c`, `co2_max_ppm`, `rh_max_pct`

Giữ `simulation_runs/results` (giờ là chi tiết của `world_runs`), `forecast_runs/predictions`, `alerts`, `audit_logs`, `documents/document_embeddings` như cũ.

---

## 6. BIM extraction (đã giải quyết, dev áp dụng)

Map thiết bị → phòng **làm được từ IFC gốc** bằng point-in-polygon. Sửa `bim/extractor.py` theo các điểm sau (đã kiểm chứng trên dữ liệu thật):

1. **Lấy hình học phòng bằng `ifcopenshell.geom.iterator`**, KHÔNG dùng `create_shape` lẻ (lẻ trả 0 vertex cho IfcSpace — đây là lý do extractor cũ bỏ geometry và map sai).
2. **Đơn vị**: hình học phòng ra **mét**, toạ độ thiết bị (`placement`) ra **milimét** → chia thiết bị cho 1000. Hai file chung gốc toạ độ.
3. **Loại phòng "đa tầng/kỹ thuật"** trước khi map: bỏ space cao >5m và loại `SHAFT/CHASE/VENT/GFA/HEATED NETAREA` (chúng phình nuốt thiết bị).
4. **Point-in-polygon + ràng buộc cao độ z**: thiết bị rơi vào đa giác phòng nào (cùng khoảng z, đệm ~0.6m) thì thuộc phòng đó; nhiều phòng chứa → chọn phòng **diện tích nhỏ nhất**.
5. **Gắn `scope`** cho mọi thiết bị: `zone` (đã về phòng) | `floor` (chỉ biết tầng) | `plant` (van/coil/quạt thuộc hệ phân phối, không thuộc phòng).

Kết quả mong đợi: ~3346/3358 thiết bị về đúng phòng; ~12 thiết bị mái → `scope=floor/plant`. **Agent chỉ ra lệnh trên thiết bị `scope=zone` + controllable** trong tập demo. File `zone_equipment_map.json` cũ HỎNG (gán 2373 thiết bị tầng 2-4 vào 1 phòng tầng hầm) — phải sinh lại.

---

## 7. Dữ liệu & ML (theo nguyên tắc #1)

**Sinh dữ liệu (`scripts/generate_data.py`):**
1. Dựng model E+ archetype: lấy phòng/diện tích/zoning từ BIM, dùng `HVAC:IdealLoadsAirSystem` per zone (E+ tự tính nhu cầu nhiệt/lạnh, **không** mô hình từng ống/máy). Dùng công suất thiết bị BIM làm **trần**, đổi nhu cầu → điện qua **COP** từ spec. Thời tiết = EPW HCMC. **Ghi rõ giả định "tái dùng hình học, khí hậu HCMC" trong report** (nguyên tắc #2 climate).
2. Nhóm tạo input: lịch người/zone (từ room_type + giờ làm + nhiễu, hoặc YOLO cho zone demo), đèn/ổ cắm theo người, lịch vận hành baseline.
3. Chạy E+ baseline cho từng scenario → đổ vào `telemetry_*` với `source=eplus`, `variant=baseline`.
4. Sweep biến thể (ngày thường/heatwave × occupancy × setpoint) → nhiều run → **tập train cho surrogate**.
5. Hậu xử lý (được phép tính, không phải bịa vật lý): `cost = energy × tariff`; `occupancy_confidence` từ YOLO/mock.

**Mô hình:**
- **Occupancy**: YOLO **pretrained** (person), không train. Output chỉ count/state/confidence, không nhận diện danh tính.
- **Surrogate (bộ đoán nhanh)**: LightGBM train trên **output E+** → dự báo nhanh energy/temp cho vòng lặp agent. Vì học từ E+ nên "khớp dữ liệu theo định nghĩa", không còn vòng lặp khép kín.
- **Anomaly/comfort**: rule trước (HVAC chạy khi phòng trống; temp vượt `comfort_profiles`), nâng cấp sau.

---

## 8. Action → E+ (theo nguyên tắc #3)

`sim/action_to_idf.py` dịch action thành chỉnh lịch điều khiển, rồi `runner.py` chạy E+ batch full-day cho variant `agent`/`candidate`, so với `baseline`.

| action_type | Núm trong E+ |
|---|---|
| hvac_setback / hvac_eco_mode | nâng cooling setpoint zone +Δ trong cửa sổ |
| pre_cooling | hạ setpoint trước cửa sổ |
| lighting_reduction | giảm fraction lịch chiếu sáng |
| early_shutdown | tắt availability HVAC |
| ventilation_adjustment | đổi lưu lượng gió tươi |

Không checkpoint giữa ngày: action = "lịch đổi bắt đầu từ thời điểm quyết định", chạy lại nguyên ngày rồi so. Đơn giản, deterministic, song song được.

---

## 9. Thứ tự dựng (build order)

| Phase | Việc | Ra cái gì |
|---|---|---|
| P0 | docker-compose + `schema.sql` (mục 5) | DB chạy |
| P0 | Sửa `bim/extractor.py` (mục 6) + `load_to_db.py` | metadata + zone_equipment_map đúng trong DB |
| P0 | Dựng IDF archetype + 1 EPW HCMC + `runner.py` chạy 1 baseline | 1 trajectory trong DB |
| P0 | API đọc state/scenario/kpi + Tab 1 Dashboard 3D | thấy tòa nhà |
| P0 | `action_to_idf.py` + chạy `agent` variant + Tab 3 so baseline/optimized | bằng chứng tiết kiệm |
| P0 | `policy.py` (rule + regrettable check) + `actions`/audit + Tab 2 | câu chuyện agentic an toàn |
| P1 | surrogate LightGBM + forecast_service | vòng lặp agent "live" 1 zone |
| P1 | YOLO trên video demo | occupancy trực quan |
| P1 | thêm scenario stress-test (heatwave, fault, after-hours) | resilience story |
| P2 | RAG trên PDF chuẩn MEP (pgvector) | chat hỏi tài liệu |

**Critical path để demo thắng:** Dashboard 3D thuyết phục + 1 so sánh baseline-vs-optimized sạch + agent giải thích + 1 màn chặn action unsafe. Mọi thứ khác là phụ.

---

## 10. Việc còn mở (cần chốt khi làm)

- Δ setpoint tối đa cho auto-action (1 / 1.5 / 2°C) — xem `AGENT_POLICY_PROPOSAL.md`.
- COP/hiệu suất dùng để đổi nhu cầu→điện (lấy từ spec thiết bị BIM hay giá trị chuẩn).
- Chọn EPW HCMC nào (năm/nguồn).
- Số zone demo (đề xuất 6–12 phòng MEETING/OPEN OFFICE/OFFICE trên 2–3 tầng).
- Deploy: ưu tiên seed sẵn dữ liệu, app chạy từ DB seed, không phụ thuộc API ngoài lúc pitch; quay video backup.
```
