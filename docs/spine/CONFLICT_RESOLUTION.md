# Đánh giá & chốt xung đột kỹ thuật (spine ↔ repo) — 2026-06-13

Tài liệu này khép lại phần "đánh giá xung đột kỹ thuật" trước khi merge. Hai
nhánh code:

- **spine** = `Vòng 2/greenflow/` (nền do mình dựng: dữ liệu EnergyPlus thật
  188 zone, schema text-key, lưu time-series bảng rộng theo world_run).
- **repo** = repo này (`green-flow-agentic-building-energy-control`): full-stack
  chạy được, engine synthetic 5 zone archetype, khóa uuid + `entity_key`, lưu
  kết quả mô phỏng kiểu EAV.

Không có xung đột Git (merge additive). "Xung đột" ở đây là khác biệt **thiết
kế**. Dưới đây là 6 quyết định đã chốt + 1 mâu thuẫn còn lại và cách hoá giải.

## Quyết định chốt

| # | Vấn đề | Chốt theo | Lý do |
|---|---|---|---|
| 1 | **Dữ liệu gốc** | **spine** | EnergyPlus thật, 188 zone, đã kiểm chứng (EUI 179, peak 76.6 W/m², surrogate R² 0.95). Số liệu thật là tài sản pitch mạnh nhất. |
| 2 | **Cách đánh số phòng (khóa)** | **repo** | uuid PK + `entity_key` (= IFC GUID). Tách định danh nội bộ khỏi GUID → IFC tái trích không gãy liên kết; frontend/agent vẫn resolve theo `entity_key`. |
| 3 | **Lưu kết quả mô phỏng** | **spine** | Bảng **rộng** theo từng run thay cho EAV (mỗi chỉ số một dòng). Kéo trajectory 188 zone × nghìn mốc nhanh hơn, cùng shape với telemetry. |
| 4 | Backend + data | **spine** | Hướng dữ liệu/xử lý đi theo spine. |
| 5 | Frontend + 3D | **giữ nguyên repo** | UI xeokit 5 zone + 3 tab đã chạy ổn. Không sửa code frontend. |

## Mâu thuẫn còn lại: data 188 zone vs frontend 5 zone

Quyết định #1 (dữ liệu 188 zone thật) **chọi** với #5 (frontend chỉ có 5 khối
3D archetype, hardcode `zone_storey0_*` + building `b0000000-…-001`). Nếu nạp
thẳng 188 zone, frontend không hiện được.

**Cách hoá giải (đã kiểm chứng map sạch):** mỗi zone thật thuộc đúng 1 trong 5
archetype (`tools/idf/out/archetype_zone_map.json`):

```
office 114 · meeting 29 · circulation 20 · amenity 14 · open_office 11  = 188
```

→ **Gộp 188 zone thật → 5 zone archetype** của building demo (cộng điện/năng
lượng, trung bình nhiệt/CO₂ theo diện tích). Frontend **giữ nguyên** vẫn hiển
thị **số thật**. Đây là `scripts/load_real_into_demo.py`. "Data theo spine,
frontend không đụng" được thoả mãn đồng thời.

Bản đầy đủ 188 zone vẫn nạp được làm building thứ hai
(`scripts/load_real_telemetry.py`) cho tương lai khi dựng UI 188 zone — không
phải đường demo chính.

## Đã hợp nhất trong merge này (theo các quyết định trên)

| Hạng mục | File | Theo quyết định |
|---|---|---|
| Bảng rộng lưu sim | `db/schema.sql::sim_zone_15m` | #3 (rộng) + #2 (uuid) |
| Ghi/đọc sim qua bảng rộng | `backend/greenflow/sim/sim_store.py`, sửa `agent/tools/simulation_tool.py`, `scripts/seed_demo.py` | #3 — API JSON giữ nguyên ⇒ #5 frontend không đụng |
| Loader gộp data thật → 5 zone | `scripts/load_real_into_demo.py` | #1 + #5 |
| Loader 188 zone (building 2, dự phòng) | `scripts/load_real_telemetry.py` | #1 + #2 |
| Regret check / ml specs / anomaly | (merge trước) | bổ sung an toàn |

`simulation_results` (EAV) **giữ lại** trong schema để không gãy gì còn tham
chiếu, nhưng **ngừng ghi** — đường ghi/đọc của record giờ là `sim_zone_15m`.

## Đánh giá tổng: bên nào mạnh hơn

- **Repo mạnh hơn** ở: sản phẩm chạy end-to-end, full-stack, tránh được bẫy
  per-zone EnergyPlus (D9) bằng cách chỉ mô phỏng 5 archetype. Giữ làm khung.
- **Spine mạnh hơn** ở: độ thật của dữ liệu (EnergyPlus thật) và cách lưu sim
  rộng dễ truy vấn, cộng cơ chế an toàn `regrettable_substitution_check`.

Bộ đôi đã chốt = **khung repo + dữ liệu & cách lưu spine + keying repo** — đúng
hướng merge này.
