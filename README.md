# GreenFlow — Agentic Digital Twin for Energy-Efficient Building Operations

GreenFlow là **simulation-first operations layer** cho tòa nhà văn phòng: đọc mô hình
building (IDF/BIM), dựng **3D digital twin** theo zone (xeokit + XKT), chạy baseline
simulation, dự đoán energy/comfort/peak risk, rồi để **LangGraph orchestrator** đề xuất
action có guardrails — mọi action đều được mô phỏng counterfactual, policy-check,
human-approve và audit.

```text
IDF/BIM + Weather + Occupancy + Tariff
→ canonical DB + 3D digital twin (xeokit/XKT)
→ baseline simulation (EnergyPlus | synthetic fallback)
→ Prediction + Control reasoning (LangGraph)
→ candidate action → what-if simulation → policy gate
→ auto-run / approval queue / reject
→ baseline-vs-optimized KPI + report PDF + audit log
```

GreenFlow **không thay thế BMS** — nó là lớp quyết định phía trên (mock execution trong MVP).

## Demo nhanh (5 phút)

Yêu cầu: Docker Desktop, Python 3.11+, Node 20+.

```bash
# 0. Cài dependencies (backend editable + web + tools)
make install            # hoặc: pip install -e ".[dev]" && cd web && npm i && cd ../tools && npm i

# 1. Postgres + schema
docker compose up -d db

# 2. Sinh 3D assets từ IDF (normalized JSON + GLB + XKT + manifest)
python scripts/build_3d_assets.py

# 3. Seed demo building + 7 ngày telemetry 15-phút + baseline run
python scripts/seed_demo.py

# 4. Chạy backend + frontend (2 terminal)
make api                # FastAPI ở :8000  (docs: http://localhost:8000/docs)
make web                # Next.js ở :3000

# Mở http://localhost:3000
```

Hoặc chạy **toàn bộ stack qua Docker + Caddy** (production-style, dùng cho VNPT cloud):

```bash
docker compose up -d --build      # db + api + web + caddy
# rồi seed một lần:
python scripts/build_3d_assets.py && python scripts/seed_demo.py
# Mở http://localhost  (Caddy reverse proxy ở cổng 80)
```

Deploy lên VNPT cloud: trỏ DNS về VM, đặt `DOMAIN=ten-mien-cua-ban.vn` trong `.env`
→ Caddy tự cấp HTTPS.

## Ba trang chính

| Route | Nội dung |
|---|---|
| `/dashboard` | 3D digital twin (xeokit), layer toggle, heatmap energy/comfort/occupancy, click zone → Inspector, KPI cards, zone table, nút Building Semantic Report (PDF) |
| `/agent-actions` | Run Optimization / Run Prediction, agent timeline kiểu CI pipeline, action queue (Recommended/Pending/Executed/Blocked), approve/reject, policy guardrails, audit trail |
| `/simulation-baseline` | Baseline vs optimized chart (đánh dấu peak window), KPI delta (kWh, VND, peak kW, comfort, CO₂), bảng simulation runs, action trace, Simulate Peak-Hour Strategy |

Chatbot **"Ask GreenFlow"** nổi ở mọi trang — câu hỏi đi qua Orchestrator (intent →
plan → agents → answer kèm linked entity chips highlight trên 3D).

## Kiến trúc

```text
greenflow-agentic-building-energy/
  backend/greenflow/
    bim/        IDF parser → normalized JSON; idf_to_gltf (GLB writer); ifc_extractor (P1 stub)
    sim/        synthetic physics-lite engine + EnergyPlus runner + action→schedule + KPI
    agent/      LangGraph: state, graph, policy.yaml, nodes/ (semantic, prediction,
                control, simulation, policy, execution, report, composer), tools/
    api/        FastAPI routers + WebSocket replay ticker (/ws/building/{id}/state)
  db/           schema.sql (Postgres 16 + pgvector), seed/normalized_building.json
  scripts/      build_3d_assets, seed_demo, run_baseline, run_agent_variant, download_epw
  tools/        convert_xkt.mjs (GLB→XKT), verify_viewer.mjs (headless E2E)
  web/          Next.js 14 + Tailwind + zustand + recharts + @xeokit/xeokit-sdk
    public/assets/buildings/greenflow_archetype/   xkt/ glb/ metadata/ mapping/ manifest
  data/         greenflow_archetype.idf (demo building) + bộ IFC Nordic (P1)
  docs/         toàn bộ spec sản phẩm
  Caddyfile / docker-compose.yml   reverse proxy + 4 services
```

### Nguyên tắc cốt lõi (từ REPO_BUILD_SPEC)

1. **Simulation tính số vật lý, AI không bịa số** — action chỉ sửa *schedule*
   (lighting fraction, setpoint); engine tính hậu quả. Có EnergyPlus thì dùng
   (`ENERGYPLUS_BIN` + EPW, xem `scripts/download_epw.py`), không có thì engine
   synthetic deterministic từ schedules trong IDF — cùng format kết quả.
2. **Counterfactual chuẩn** — baseline và optimized chạy cùng weather/occupancy,
   chỉ khác action; KPI delta là bằng chứng.
3. **Geometry tĩnh, state động** — IDF → XKT một lần; runtime chỉ đổi
   colorize/opacity/highlight qua WebSocket + API (object id = `entity_key`).
4. **Không có Anomaly Agent riêng** — mọi bất thường do Building Semantic Agent
   suy ra từ graph + state + schedule.
5. **Policy là code thuần, audit được** — `agent/policy.yaml` + `policy.py`:
   auto_run / approval_required / rejected với lý do tường minh.

### LangGraph flow

```text
START → input_router → intent_classifier → orchestration_planner
      → plan_executor (Building Semantic → Prediction → Control → Simulation
                       → Policy → Execution/Approval | Report | Compare)
      → response_composer → audit_logger → END
```

Mỗi bước ghi `agent_logs` (DB) → UI stream như Codex/CI. LLM **tùy chọn**:
`LLM_PROVIDER=openai|anthropic|none` — mặc định `none`, toàn bộ flow chạy
rule-based deterministic, không cần API key.

## Cấu hình (.env)

Copy `.env.example` → `.env`. Đáng chú ý:

| Biến | Ý nghĩa |
|---|---|
| `LLM_PROVIDER` | `none` (mặc định, không cần key) / `openai` / `anthropic` |
| `ENERGYPLUS_BIN` | đường dẫn binary E+; bỏ trống → synthetic engine |
| `WEATHER_EPW` | EPW Hà Nội (`python scripts/download_epw.py`) |
| `ENABLE_AUTO_ACTIONS`, `MAX_SETPOINT_DELTA_C`, `MIN_OCCUPANCY_CONFIDENCE` | policy guardrails |
| `DOMAIN` | `:80` local / domain thật để Caddy auto-HTTPS |
| `REPLAY_SPEED_SECONDS` | tốc độ replay ticker WebSocket |

## Test

```bash
make test        # 29 tests: IDF parser, sim counterfactual, policy guardrails, agent plans
node tools/verify_viewer.mjs   # E2E headless: viewer load XKT, pick zone, heatmap (cần web+api chạy)
```

## API chính

`GET /docs` có đầy đủ OpenAPI. Nhóm chính: `/api/buildings|zones|devices|entities`,
`/api/state/latest`, `/api/timeseries`, `/api/kpi/current`, `/api/3d/*`,
`/api/agent/run-optimization|predict|chat|runs/{id}/logs`,
`/api/actions`, `/api/approvals/{id}/approve|reject`,
`/api/simulations/compare/series`, `/api/reports`, WS `/ws/building/{id}/state`.

## Mở rộng (P1/P2)

- **IFC Nordic Office**: implement `backend/greenflow/bim/ifc_extractor.py`
  (interface + quy tắc placement đã ghi sẵn) → cùng normalized contract, toàn bộ
  pipeline phía sau dùng lại nguyên vẹn; thêm layer hvac/electrical/structural/terrain
  vào manifest là LayerPanel tự nhận.
- **EnergyPlus thật**: cài E+ 24.x, `download_epw.py`, đặt `ENERGYPLUS_BIN` — runner
  tự chuyển engine.
- **ML forecast** (LightGBM surrogate), **pgvector RAG** cho chatbot docs, **YOLO
  occupancy**: bảng DB + hooks đã có chỗ sẵn.
