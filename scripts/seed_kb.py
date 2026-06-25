"""Seed the chatbot knowledge base (kb_chunks) + build the hybrid-RAG index.

Hybrid RAG cần kho tri thức thật: trước đây kb_chunks RỖNG nên RAG là no-op (chat
chỉ chạy function-calling SQL). Script này nạp tri thức vận hành tòa nhà (chính
sách comfort/peak, biểu giá EVN, định nghĩa metric, loại action, policy gate, từ
điển room-type) — viết SONG NGỮ Việt+Anh để cả query tiếng Việt lẫn thuật ngữ
tiếng Anh đều khớp (lexical) và bge-m3 nhúng tốt (dense).

Sau khi nạp:
  - tạo GIN index full-text ('simple') cho nhánh lexical của hybrid search;
  - xoá index vector cũ (đổi embedder => đổi dim => phải dựng lại);
  - embed toàn bộ chunk vào turbovec qua reindex_kb (cần bge-m3 -> chạy trong
    container api đã pre-warm model).

Usage (trong container):  python scripts/seed_kb.py
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import text  # noqa: E402

from greenflow.chat.service import ChatRuntime, reindex_kb  # noqa: E402
from greenflow.config import get_settings  # noqa: E402
from greenflow.db import db_conn  # noqa: E402

BUILDING_ID = uuid.UUID("b0000000-0000-0000-0000-000000000001")

# (doc_type, title, content) — song ngữ, ngắn gọn, đúng số liệu trong repo.
CHUNKS: list[tuple[str, str, str]] = [
    ("overview", "Tổng quan tòa nhà (building overview)",
     "GreenFlow quản lý một tòa văn phòng kiểu Nordic gồm 14 zone (khu vực) và 44 "
     "thiết bị (device), khí hậu Hà Nội. Đây là digital twin: dữ liệu telemetry là "
     "quá khứ được phát lại (replay). 'Bây giờ' (now) = mốc thời gian mới nhất trong "
     "telemetry, không phải giờ thực."),
    ("policy", "Chính sách tiện nghi nhiệt (comfort policy)",
     "Ngưỡng vi phạm tiện nghi (comfort violation) là nhiệt độ vùng > 26.5°C khi có "
     "người. comfort_risk có 3 mức: normal (bình thường), watch (theo dõi), high (cao, "
     "cần xử lý). Mục tiêu là giảm điện mà KHÔNG tăng số phút vi phạm tiện nghi "
     "(comfort_violation_minutes)."),
    ("policy", "Giờ cao điểm và biểu giá điện EVN (peak hours, tariff)",
     "Biểu giá điện kinh doanh EVN (VND/kWh): thấp điểm (off-peak) 1184 khi giờ < 4 "
     "hoặc >= 22; cao điểm (peak) 3314 trong 09:30–11:30 và 17:00–20:00; còn lại là "
     "giờ bình thường (normal) 1839. Cửa sổ cao điểm chiều để cắt đỉnh công suất "
     "(peak shaving) mặc định là 13:00–16:00; peak_risk đánh dấu nguy cơ chạm đỉnh."),
    ("definition", "Định nghĩa các chỉ số (metric definitions)",
     "total_power_kw = tổng công suất tức thời của zone. hvac_power_kw = phần điều hòa "
     "(HVAC); lighting_power_kw = chiếu sáng; plug_power_kw = ổ cắm/thiết bị. "
     "occupancy_count = số người ước lượng. co2_ppm = nồng độ CO2. setpoint_c = nhiệt "
     "độ đặt của điều hòa. energy_kwh = điện năng; cost_vnd = chi phí."),
    ("definition", "Hệ số phát thải CO2 và COP (emission factor, COP)",
     "Hệ số phát thải lưới điện Việt Nam = 0.6766 kg CO2/kWh, dùng để quy đổi điện "
     "tiết kiệm sang CO2 tránh phát thải (co2_avoided_kg). Hệ số hiệu suất làm lạnh "
     "COP = 3.2 (điện tiêu thụ = nhiệt lạnh / COP)."),
    ("action", "Các loại hành động tối ưu (action types)",
     "Agent có thể đề xuất: setpoint_adjust (nâng nhiệt độ đặt để giảm tải lạnh), "
     "lighting_dim (giảm độ sáng), hvac_off / eco mode (tắt hoặc chạy tiết kiệm khi "
     "zone trống), pre-cool (làm mát sớm trước cao điểm để tích 'coolth' vào khối "
     "nhiệt rồi nhả ra, cắt đỉnh 13:00–16:00)."),
    ("policy", "Policy gate: tự động hay cần duyệt (auto vs approval)",
     "Mỗi action sau mô phỏng phải qua policy gate. Hành động rủi ro thấp, tiết kiệm "
     "rõ, không tăng vi phạm tiện nghi -> auto-execute. Rủi ro trung bình/cao hoặc ảnh "
     "hưởng tiện nghi -> approval_required (chờ người duyệt). Vi phạm chính sách -> "
     "rejected. Chat KHÔNG bypass: action thật vẫn qua simulation + policy + audit."),
    ("workflow", "Quy trình tối ưu (run optimization workflow)",
     "Nút Run Optimization chạy chuỗi: Building Semantic -> Prediction (dự báo tải/peak "
     "60 phút tới) -> Control (sinh action ứng viên) -> Simulation (mô phỏng KPI) -> "
     "Policy Engine (duyệt) -> Execution/Approval. Kết quả gồm tiết kiệm kWh/ngày, "
     "giảm đỉnh kW và thay đổi phút vi phạm tiện nghi."),
    ("workflow", "Dự báo ngày trước và pre-cool (day-ahead demand forecast)",
     "Surrogate LightGBM (huấn luyện từ EnergyPlus DoE) dự báo nhu cầu HVAC 24 giờ tới "
     "và đỉnh (peak_hvac_kw). Nếu dự báo đỉnh cao, hệ thống khuyến nghị pre-cool từ sáng "
     "(precool_window) để giảm đỉnh chiều. weather_shift mô phỏng kịch bản nắng nóng."),
    ("workflow", "Mô phỏng đối chứng và kiểm định (simulation validation)",
     "So sánh baseline (lịch cố định, không action) với optimized (có action agent) trên "
     "CÙNG thời tiết/occupancy -> chênh lệch là do action. Model validation backtest "
     "baseline so với telemetry thật một ngày đã trôi qua, báo MAPE/RMSE để chứng minh "
     "engine đã hiệu chỉnh, không phải số bịa."),
    ("glossary", "Từ điển loại phòng (room-type glossary)",
     "room_type gồm: open_office (văn phòng mở), office (văn phòng riêng), meeting_room "
     "(phòng họp), circulation (hành lang/cầu thang), lobby (sảnh), amenity (khu tiện ích "
     "như bếp/kitchen), auditorium (hội trường), parking (bãi đỗ). Mỗi zone có loại phòng "
     "quyết định lịch dùng và mật độ người."),
    ("feature", "Camera CCTV và occupancy trên 3D (cameras, occupancy dots)",
     "13/14 zone có camera CCTV demo; click zone hiển thị feed của zone đó. Chế độ xem "
     "Occupancy hiển thị các chấm đỏ rải trong zone theo số người (occupancy_count). "
     "Privacy mode 'count_only' = chỉ đếm người, không lưu nhận dạng."),
    ("feature", "Trợ lý chat làm được gì (assistant capabilities)",
     "Chatbot trả lời dữ liệu lịch sử (điện, chi phí, đỉnh công suất, tiện nghi, cảnh "
     "báo, danh sách zone) qua truy vấn SQL tham số hoá, và có thể KHỞI CHẠY run thật "
     "(run_optimization, peak_strategy, run_prediction) hiển thị tiến trình từng bước. "
     "Số liệu luôn lấy từ công cụ, không bịa."),
    ("definition", "Cảnh báo và bất thường (alerts, anomaly)",
     "alerts là các cảnh báo đang mở (resolved_at NULL) hoặc đã xử lý. Bất thường ví dụ: "
     "thiết bị HVAC chạy khi zone không có người (lãng phí), tải vượt ngưỡng, lệch nhiệt "
     "độ. anomaly_label gắn nhãn điểm dữ liệu bất thường."),

    # --- system docs (doc_type='system') — how GreenFlow is built and how every
    #     metric/index is computed, for explaining the system to judges. English,
    #     public-safe: concepts and formulas only, no secrets/credentials. ---
    ("system", "System architecture (how GreenFlow is built)",
     "GreenFlow is an agentic digital twin for building energy operations. Stack: a "
     "FastAPI Python backend, a Next.js/React frontend, PostgreSQL for telemetry and "
     "state, a turbovec vector store for retrieval, and MinIO object storage for reports "
     "and media. The agent is a deterministic LangGraph workflow (rule-based decisions, "
     "no LLM in the control path); a separate chat assistant uses an LLM only to route "
     "tools and explain. Telemetry is a recorded simulation year replayed as a live twin."),
    ("system", "Digital twin and the replay clock (what 'now' means)",
     "The building's telemetry is a full recorded year (from an EnergyPlus building-physics "
     "simulation) that the platform replays, so 'now' is a replay anchor, not wall-clock "
     "time. In streaming mode the virtual clock advances fast so dashboards animate; every "
     "metric is read at that anchor. This is why the assistant always queries by the replay "
     "clock, not the real date."),
    ("system", "How the Building Health Score is computed",
     "The Building Health Score is a composite 0–100 built from four transparent sub-scores, "
     "each 0–100, measured at the current replay anchor: Thermal comfort (weight 0.30), Air "
     "quality (0.20), Energy/demand (0.25) and Equipment reliability (0.25). Overall = the "
     "weighted sum, rounded. Grades: ≥85 Excellent, ≥70 Good, ≥50 Fair, else Poor. Each "
     "sub-score penalises the share of zones currently affected, so the headline also "
     "pinpoints which dimension is dragging the building down."),
    ("system", "How the Air Quality score is computed",
     "Air quality is a 0–100 sub-score of the Building Health Score (weight 0.20), driven by "
     "CO2 (co2_ppm) across zones at the replay anchor. Formula: score = 100 × (1 − penalty), "
     "clamped to 0–100, where penalty = (zones with CO2 > 1000 ppm + 0.5 × zones with CO2 "
     "between 800 and 1000 ppm) ÷ total zones. So a zone above 1000 ppm counts fully and an "
     "elevated zone (800–1000) counts half. 1000 ppm is the comfort/ventilation limit; the "
     "co2_high anomaly rule also fires when CO2 stays above 1000 ppm for 30+ minutes. There "
     "is no separate pollutant index — air quality is CO2-based by design."),
    ("system", "How the Thermal Comfort score is computed",
     "Thermal comfort is a 0–100 sub-score (weight 0.30). penalty = (zones at comfort_risk "
     "'high' + 0.5 × zones at 'watch') ÷ total zones; score = 100 × (1 − penalty). comfort_risk "
     "is 'high' when a zone's temperature exceeds 26.5°C while occupied, 'watch' when it is "
     "approaching the limit, else 'normal'. The optimiser must cut energy without increasing "
     "comfort-violation minutes."),
    ("system", "How the Energy/demand and reliability scores are computed",
     "Energy/demand (weight 0.25): penalty = 0.6 × (zones flagged peak_risk 'high' ÷ total "
     "zones); the 0.6 softening keeps a single afternoon peak hour from zeroing the score. "
     "Equipment reliability (weight 0.25): penalty = 0.34 per open device fault + 0.15 per "
     "open sensor-stuck fault. Both use score = 100 × (1 − penalty), clamped."),
    ("system", "How energy cost and intensity (EUI) are computed",
     "Energy uses EVN commercial tariff (VND/kWh): off-peak 1184, normal 1839, peak 3314, "
     "with peak windows 09:30–11:30 and 17:00–20:00. Energy intensity (EUI) = daily energy "
     "(kWh) ÷ total floor area (m²); annual EUI ≈ daily × 365. The energy-performance gauge "
     "maps EUI to 0–100: ≤90 kWh/m²/yr → 100 (efficient), ≥250 → 0 (poor), linear between. "
     "Avoided CO2 = saved kWh × 0.6766 kg/kWh (Vietnam grid factor); HVAC COP is 3.2."),
    ("system", "How anomaly detection works (rules catalog)",
     "Anomalies are found by deterministic batch rules over the replay window, writing to the "
     "alerts table. Rules: hvac_on_empty (HVAC > 0.5 kW in an empty zone for 30+ min, warning); "
     "lighting_after_hours (> 0.2 kW outside 07:00–19:00 for 30+ min, warning); co2_high (CO2 > "
     "1000 ppm for 30+ min, warning); comfort_violation_sustained (comfort breach 45+ min, "
     "critical); sensor_stuck (flat reading 120+ min, info); device_fault (equipment fault "
     "state, critical). Sustained rules group consecutive 30-min rows into episodes."),
    ("system", "How the agent works (the control loop)",
     "A run flows through deterministic LangGraph nodes: input router → intent → planner → "
     "plan executor (prediction, control, simulation) → policy engine → execution or approval "
     "→ composer → audit. Decisions are rule-based, not LLM. The loop is self-correcting: "
     "read-only nodes retry and fall back (forecast→persistence, simulation→quick estimate), "
     "and step/time budgets stop runaway runs with a recorded stop_reason."),
    ("system", "How the policy gate and action lifecycle work",
     "Every proposed action is simulated, then checked by the policy gate: low-risk, clearly "
     "saving, no added comfort violation → auto-execute; medium/high risk or comfort impact → "
     "approval_required (a human must approve); policy breach → rejected. A pending action "
     "auto-expires after 5 minutes if not approved, because a stale control action executed "
     "late is meaningless. Every decision is written to an audit log; chat cannot bypass this."),
    ("system", "How forecasting and optimization work",
     "A LightGBM surrogate model trained on an EnergyPlus design-of-experiments dataset "
     "forecasts HVAC demand and the peak for the next 60 minutes to 24 hours. If a high "
     "afternoon peak is predicted, the system recommends pre-cooling earlier to store 'coolth' "
     "in the building mass and shave the 13:00–16:00 peak. Optimization compares a baseline "
     "(fixed schedule) against the agent's optimized plan and reports kWh saved, kW peak cut "
     "and the change in comfort-violation minutes."),
    ("system", "How the assistant answers (RAG + tools)",
     "The assistant answers two kinds of questions. For the live building's data (energy, cost, "
     "comfort, occupancy, alerts) it calls parameterised SQL tools so numbers are real, never "
     "invented. For how the system works or how a metric is computed it searches this "
     "documentation (search_system_docs) via hybrid retrieval: dense embeddings (bge) plus "
     "lexical full-text, fused with Reciprocal Rank Fusion and re-ranked. After each agent run "
     "it also posts a plain-language report of notable findings into the conversation."),
    ("system", "What GreenFlow can do (product capabilities)",
     "GreenFlow can: monitor a building live as a digital twin (energy, cost, peak power, "
     "comfort, CO2/air quality, occupancy) with a composite health score; detect faults and "
     "anomalies (HVAC in empty zones, after-hours lighting, high CO2, comfort violations, stuck "
     "sensors, device faults) and surface them on dashboards and in 3D; forecast HVAC demand and "
     "the peak; run an agentic optimization that proposes control actions (raise setpoint, dim "
     "lighting, eco/off in empty zones, pre-cool for peak shaving), simulates them, and routes "
     "each through a policy gate to auto-execute or request human approval; generate building and "
     "HVAC/electrical reports; and answer questions in chat (by voice too) about both the live "
     "building and how the system itself works. Every real action is simulated, policy-checked "
     "and audited — chat never bypasses that."),
    ("system", "Main functions and screens (what each part does)",
     "Dashboard: building health score, energy/cost/peak KPIs, energy mix and 24-hour load. 3D "
     "Digital Twin: zones colour-coded by a chosen metric, a Faults view overlaying alert "
     "severity, and CCTV/occupancy overlays. Electrical map: the building's electrical network "
     "(boards, circuits, phase balance). Agents & Actions: an IDE-style workspace with a session "
     "list, live building state, a chat copilot, and the action queue where you approve or reject "
     "proposed actions (pending ones auto-cancel after 5 minutes). Live mode ('Go live') advances "
     "the replay clock so dashboards animate during a demo. Reports: generated PDFs/markdown."),
]


def main() -> None:
    settings = get_settings()
    with db_conn() as conn:
        conn.execute(text("DELETE FROM kb_chunks WHERE building_id = :b OR building_id IS NULL"),
                     {"b": BUILDING_ID})
        for doc_type, title, content in CHUNKS:
            conn.execute(text("""
                INSERT INTO kb_chunks (doc_type, title, content, building_id)
                VALUES (:t, :ti, :c, :b)
            """), {"t": doc_type, "ti": title, "c": content, "b": BUILDING_ID})
        # GIN index cho nhánh lexical của hybrid search (config 'simple' = đa ngôn ngữ)
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS kb_chunks_fts_idx ON kb_chunks
            USING gin (to_tsvector('simple', coalesce(title,'') || ' ' || content))
        """))
        n_rows = conn.execute(text("SELECT count(*) FROM kb_chunks")).scalar()
        print(f"kb_chunks seeded: {n_rows} rows")

    # đổi embedder (bge-m3, dim 1024) => xoá index vector cũ để dựng lại sạch
    idx = settings.vector_index_path
    if idx.exists():
        idx.unlink()
        print(f"removed stale vector index: {idx}")

    with db_conn() as conn:
        runtime = ChatRuntime.build(conn, settings)
        n = reindex_kb(conn, runtime)
        print(f"reindexed into turbovec: {n} chunks @ dim {runtime.embedder.dim}")


if __name__ == "__main__":
    main()
