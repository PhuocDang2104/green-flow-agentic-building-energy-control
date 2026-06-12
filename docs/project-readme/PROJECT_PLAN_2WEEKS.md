# GreenFlow — Kế hoạch xây dựng hoàn thiện trong 2 tuần (Hackathon "peak")

> Mục tiêu: sản phẩm **hoàn thiện end-to-end + đỉnh nhất** trong 14 ngày, tận dụng Codex + Claude chạy **nhiều track song song**. Đã có sẵn nền vững (BIM map, E+ pipeline, surrogate verified) → 2 tuần là dư để lên "peak".

---

## 0. "Peak" nghĩa là gì (định nghĩa thắng)

Sản phẩm phải demo trọn 7 khoảnh khắc "wow", mỗi cái đều **chạy thật, có số**:
1. **3D digital twin sống** — bấm zone thấy state/occupancy/thiết bị (BIM thật).
2. **Hỏi tiếng Việt → agent lập kế hoạch + giải thích** (LLM reasoning).
3. **Baseline vs Agent (E+ thật)** — saving chứng minh bằng M&V.
4. **Đón đầu**: heatwave/sự kiện → **pre-cool lên lịch trước (lead time)**.
5. **Resilience**: nguồn (chiller/FCU) chết → **phân bổ lại live, bảo vệ zone ưu tiên**.
6. **Safe-to-fail**: action unsafe bị chặn + approval queue + audit + regrettable-check.
7. **Report PDF** (semantic + HVAC/ELE + M&V) tải về.

---

## 1. Đã có (nền — không phải làm lại)
- BIM extract + **device→zone PIP map** (`bim_extractor.py`, `zone_equipment_map.json`).
- **datagen** đầy đủ: schedules, devices, sensors, CO2, fault injection.
- **EnergyPlus pipeline** verified (E+ 26.1): `build_idf.py` (envelope QCVN) → run → `expand_eplus.py`.
- **Surrogate** train được R² 0.95; verify data có nghĩa (EUI 179, peak 76.6 W/m²).
- EPW Hà Nội, config QCVN, bộ doc thiết kế.

## 2. Còn phải build
Semantic graph · forecast_service + occupancy forecaster · agent/control (action) · action_to_idf + agent E+ variant · capacity allocation (fault/peak) · anomaly→alerts · DB schema + load · FastAPI · LangGraph orchestrator + chat · Frontend 3 tab + xeokit 3D · scenarios · reports/PDF · polish + pitch.

---

## 3. Nguyên tắc thực thi (để song song không vỡ)
- **Spine-first (Ngày 1):** chốt **DB schema + API contract (OpenAPI) + data format** trước → các track bám interface, không đụng nhau.
- **Headless-first:** logic (graph/forecast/agent/sim) chạy + test **không cần UI** xong trước, UI gắn sau.
- **Test-as-you-go:** mỗi module có test + 1 script demo CLI.
- **Seed demo sớm:** mọi thứ chạy từ DB đã seed → demo không phụ thuộc service ngoài.

## 4. Phân công Codex × Claude
| | Mạnh ở | Giao việc |
|---|---|---|
| **Claude** | kiến trúc, reasoning, glue khó | spine/contract, semantic graph, agent control logic, LangGraph, E+/BIM glue, integration, review/debug |
| **Codex** | codegen khối lượng lớn từ spec | API routers/services/schemas, frontend components, datagen month-batch, tests, report templates |
- Hai bên **review chéo**; Claude giữ "spine" + tích hợp, Codex cày module độc lập.

---

## 5. Timeline 14 ngày (5 track song song)

Track: **T1** Data/Sim/ML · **T2** Agent/Graph/Policy · **T3** Backend API · **T4** Frontend · **T5** Integration/Demo

### Ngày 1 — SPINE
- Chốt `db/schema.sql` (cải tiến: scenarios/world_runs/decision_ticks/actions/scenario_kpi/comfort_profiles/entity_relations/alerts/audit).
- Chốt **API contract** (OpenAPI) + **parquet schema**.
- Scaffold monorepo (`bim/ sim/ ml/ agent/ api/ web/ db/ scripts/`), `.env`, docker-compose, CI.
- IFC → **XKT** (xeokit) conversion pipeline.

### Ngày 2–3 — FOUNDATION
- **T1**: DB up; sinh **full 3 tháng** (month-batch) → COPY parquet vào Postgres partition.
- **T2**: **Semantic graph** — `entity_relations` từ zone_equipment_map (quan hệ Brick `feeds/isPartOf/hasLocation`) + recursive CTE.
- **T3**: FastAPI skeleton + read endpoints (buildings/floors/zones/devices/state/kpi).
- **T4**: Next.js shell + 3 route + xeokit load building + **pick/highlight zone** theo GUID.
- **T5**: seed demo; pipeline glue.

### Ngày 4–5 — INTELLIGENCE CORE (headless)
- **T1**: `forecast_service` (bọc surrogate) + **occupancy/demand forecaster** (train lịch sử) + confidence.
- **T2**: `agent/control.py` — rule cơ hội (empty-zone, pre-cool, after-hours) → candidate → **surrogate scoring** → policy gate + **regrettable_substitution_check** → action plan; `action_to_idf`; chạy **agent E+ variant**; **baseline-vs-agent** → `scenario_kpi`.
- **T3**: endpoints forecast/actions/simulations/compare.
- **T4**: Dashboard tab gắn live state + KPI cards + charts.
- **T5**: `anomaly_rules` → alerts; fault scenarios.

### Ngày 6–7 — AGENT SURFACE + RESILIENCE
- **T2**: **LangGraph orchestrator** (intent → plan → tools → compose) + **chat** + sinh giải thích.
- **T1**: **capacity-constrained allocation** (nguồn chết/peak) + reallocation sim.
- **T3**: endpoints agent/chat, alerts, reports.
- **T4**: **Agent & Actions tab** (chat, action plan, approval queue, policy badge, audit, alerts).
- **T5**: **kịch bản đón đầu** (forecast lead-time → pre-cool có lịch).

### Ngày 8–9 — SIMULATION TAB + SCENARIOS
- **T4**: **Simulation tab** — baseline vs optimized, scenario selector, KPI delta, **timeline/Gantt action đã lên lịch**, peak/comfort charts.
- **T1/T5**: 6 scenario end-to-end: normal-optimize, heatwave pre-cool, event, after-hours, **fault reallocation**, sensor-missing.
- **T2**: report agent + **PDF** (semantic, HVAC/ELE, baseline-vs-optimized, **M&V**).

### Ngày 10–11 — INTEGRATION + POLISH
- Wiring end-to-end; LLM giải thích khắp nơi; **resilience demo** (chiller chết → reallocate, zone ưu tiên giữ comfort).
- KPI đầy đủ: energy/cost/peak/comfort/CO2-avoided/unsafe-blocked/recovery-time/resilience-score.
- UI polish (design-taste, dark, premium).

### Ngày 12 — HARDENING
- Seed toàn bộ demo data; app chạy từ DB seed (**không phụ thuộc API ngoài lúc pitch**).
- Error/empty states; performance; **quay video backup** từng kịch bản.

### Ngày 13 — PITCH ASSETS
- Slides: **value prop + moat + systems thinking + safe-to-fail + M&V + roadmap** (mở đầu bằng climate-resilient operation, không mở bằng dashboard).
- Demo script (thứ tự 7 wow). **Dry run #1**.

### Ngày 14 — DRY RUN + BUFFER
- Dry run #2/#3, fix, buffer, bản backup cuối.

---

## 6. Định nghĩa Hoàn Thành (DoD)
1. `docker compose up` + `make seed-demo` → DB đầy dữ liệu 3 tháng.
2. 3 tab chạy; 3D viewer pick/highlight zone.
3. Hỏi NL → agent lập plan + giải thích.
4. Baseline-vs-agent (E+ thật) ra KPI + saving.
5. Đón đầu: forecast cảnh báo sớm → action lên lịch trên timeline.
6. Resilience: nguồn chết → reallocate, zone ưu tiên giữ comfort.
7. Policy auto/approval/reject + regrettable-check + audit.
8. Anomaly → alert (đèn/máy lạnh hỏng) có severity/resolve.
9. Report PDF (semantic + HVAC/ELE + M&V) tải được.
10. Mọi action/sim/alert vào audit log.

## 7. Rủi ro & buffer
| Rủi ro | Giảm thiểu |
|---|---|
| E+ tích hợp | **ĐÃ xong** (rủi ro lớn nhất đã loại) |
| Frontend 3D | xeokit (giữ GUID sẵn) thay vì tự GLB; có fallback 2D floorplan |
| LLM/LangGraph | giữ graph gọn; agent quyết bằng rule/optimizer, LLM chỉ điều phối/giải thích → ít rủi ro |
| Scope phình | DoD cố định; buffer ngày 13–14; mọi tính năng có bản "đủ để demo" |
| Data device-all nặng | month-batch (đã có plan); zone-level luôn full |

## 8. Stack chốt
PostgreSQL+pgvector · FastAPI · LangGraph · EnergyPlus 26.1 · LightGBM (surrogate + forecaster) · YOLO pretrained · Next.js + xeokit · Brick vocabulary cho graph. (Không Neo4j/Timescale/Redis ở P0.)

---

## 9. Thứ tự khởi động ngay (hôm nay)
1. `db/schema.sql` + API contract (spine).
2. **Semantic graph** (`entity_relations`) — nền cho action + resilience.
3. `forecast_service` (bọc surrogate) + occupancy forecaster.
4. `agent/control.py` → **baseline-vs-agent** chạy headless trên local.

→ Xong 4 cái này là có "bộ não" hoàn chỉnh; phần còn lại là API + UI + scenarios + polish.
