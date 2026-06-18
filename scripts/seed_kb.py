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
