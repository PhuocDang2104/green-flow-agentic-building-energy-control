# Phân phối điện toàn tòa nhà — Tổng quan, Lý thuyết, Thống kê & Insight

> Tài liệu giải thích **bức tranh điện của cả tòa nhà GreenFlow**: con số đến từ đâu,
> tính theo logic nào, hiện trạng thống kê thật, **đang thiếu gì**, và các **insight**
> kỹ thuật. Mọi số là số thật của bản build hiện tại (scenario `openmeteo_2025_30min_baseline`,
> 30 phút × cả năm 2025, 308 zone). Đọc kèm [GRAPH_RAG_NGUYEN_LY_VA_AGENT.md](GRAPH_RAG_NGUYEN_LY_VA_AGENT.md).

---

## 1. Tổng quan — lớp này là gì

GreenFlow mô phỏng năng lượng ở **mức zone** (EnergyPlus). Lớp "Electrical Distribution"
**đặt thêm một tầng hạ tầng phân phối** lên trên: tủ phân phối (board) → mạch (circuit)
→ điểm tải (đèn/ổ/báo cháy), lấy hình học + thuộc tính điện từ **IFC**, rồi **phân bổ
ngược** năng lượng zone (E+ mô phỏng) về từng board để trả lời các câu hỏi kỹ sư điện:
*"board nào tải nặng nhất? cấp cho zone nào? dòng bao nhiêu? có nguy cơ quá tải?"*

Nguyên tắc bất biến: **không mô phỏng lại E+, không sửa IDF, board không phải tải tiêu
thụ** (board chỉ **phân phối lại** năng lượng zone) ⇒ Σ năng lượng board = Σ năng lượng
zone (kiểm chứng lệch **0.0%**, không double-count).

---

## 2. Lý thuyết & nguyên lý thống kê — con số tính thế nào

### 2.1. Năng lượng (kWh) — `energyplus_simulated × inferred allocation`

```
board_kwh(b)   = Σ_zone Σ_category  zone_kwh(zone, category) × weight(zone→b, category)
zone_kwh       = ∫ công suất zone (lights/equipment/HVAC) dt   [từ gold E+, 30 phút]
Σ_b weight(zone→b, category) = 1   ∀ (zone, category)   ← bảo toàn năng lượng
```
- `weight` = tỉ lệ tải của một (zone, category) được phân về một board, **suy luận** từ
  mã hệ thống + tầng + board gần nhất (xem §4). Tổng = 1 nên **không tạo/mất năng lượng**.

### 2.2. Nhu cầu đỉnh (peak kW) — **non-coincident**

`peak_total_kw(b)` = max theo thời gian của tổng công suất board (gộp các zone nó cấp).
⚠ Đây là đỉnh **của riêng board**; **tổng các đỉnh board ≠ đỉnh tòa nhà** vì các đỉnh
không xảy ra cùng lúc (chưa áp **hệ số đồng thời/diversity** — xem §5).

### 2.3. Dòng điện (A) — công thức kỹ thuật chuẩn

```
1 pha:  I = P / (V · PF)
3 pha:  I = P / (√3 · V_dây · PF)
```
- `V`, số pha lấy từ IFC; thiếu thì dùng mặc định (230V 1φ / 400V 3φ, PF 0.9) và gắn
  nhãn `assumption_based`.

### 2.4. Tải & quá tải (%) — **chỉ khi có dòng định mức thật**

```
loading_pct = I_peak / rated_current_a × 100      (chỉ khi rated_current_a > 0)
overload_status = normal(<80%) | warning(80–100%) | overload(>100%)
                = rating_missing   nếu KHÔNG có rated_current thật
```
→ Vì IFC để `Nimellisvirta` (dòng định mức) phần lớn = 0 placeholder, **toàn bộ board
hiện ở trạng thái `rating_missing`** (chỉ xếp hạng nhu cầu, **không** kết luận quá tải).

---

## 3. Thống kê thật — toàn tòa nhà

### 3.1. Năng lượng (E+ mô phỏng, cả năm)

| chỉ số | giá trị |
|---|--:|
| **Tổng điện năng** | **3 106,6 MWh/năm** |
| Chiếu sáng (lights) | 1 220,9 MWh — **39%** |
| Thiết bị/ổ cắm (equipment) | 1 038,2 MWh — **33%** |
| HVAC (điện) | 847,6 MWh — **27%** |
| Diện tích sàn (308 zone) | ~76 600 m² |
| **EUI** (cường độ năng lượng) | **40,6 kWh/m²/năm** |
| Σ đỉnh zone (non-coincident) | 1 265 kW · zone lớn nhất 159,2 kW |

**Theo tầng** (MWh/năm): Level_02 **621,8** · Level_04 596,9 · Level_03 595,1 ·
Level_01 441,6 · Foundation **335,4** · Basement 271,0 · Level_05 244,9.

### 3.2. Hạ tầng điện (từ IFC)

| đối tượng | số lượng |
|---|--:|
| Tủ phân phối `IfcElectricDistributionBoard` | **57** (56 có bảng nhu cầu) |
| Điểm tải (load points) | **1 619** — đèn 1 419 · ổ cắm 188 · báo cháy 12 |
| Đoạn/phụ kiện máng cáp | 1 801 |
| Mạch (circuit) | **80** — system-grouped 54 · pseudo 26 |
| Điện áp board | 400V: 37 · 230V: 19 |
| Số pha | 3 pha: 37 · 1 pha: 19 |
| Σ đỉnh board (non-coincident) | **1 275 kW** (≈ Σ đỉnh zone 1 265 kW → bảo toàn ✔) |

**Top board theo đỉnh:** RKE01 (basement) **236,6 kW / 531 MWh** · RKE01 (L04) 142,9 kW ·
RKE01 (L03) 141,7 kW · RKE01 (L02) 140,8 kW · RKE02 (L01) 123,2 kW.

### 3.3. Chất lượng ánh xạ (allocation)

| độ tin cậy | số dòng (trên 1 032) |
|---|--:|
| `medium` (mã hệ thống + tầng + gần nhất) | 266 |
| `low` (fallback theo tầng/loại) | 766 |
| `high` / `exact` | **0** |

**Phương pháp:** load_point_aggregation 470 · pseudo_hvac_floor_main **308** ·
floor_dominant_equipment 178 · floor_lighting_board_proxy 52 · floor_dominant_lights 22 ·
nearest_floor_board 2.

### 3.4. Kiểm định (validation)

`12 checks · 0 fail · 1 warn · 57 manual-review` — quan trọng nhất: **board-vs-zone
năng lượng lệch 0.0% (không double-count)**.

---

## 4. Logic pipeline (tóm tắt)

```
IFC ELE  ──extract──▶ boards/load-points/cables (+psets Phần Lan: V, pha, mã hệ thống)
IFC ARCH ──tessellate─▶ zone centroid + BOUNDING BOX  ─┐
gold E+  ──read───────▶ zone kWh (lights/equip/HVAC) ──┤
                                                       ▼
   ALLOCATION: ghép (zone,category) → board theo (mã hệ thống → tầng → board gần nhất),
   weight chuẩn hoá Σ=1  →  board timeseries (DuckDB)  →  peak/current/loading
                                                       ▼
   GRAPH (5705 node / 13446 edge, mỗi phần tử có provenance) → RAG cards → 3D scene
```
Mỗi giá trị gắn nhãn: `measured | energyplus_simulated | ifc_derived | spatially_inferred
| naming_inferred | assumption_based | manual_review`.

---

## 5. ĐANG THIẾU GÌ (gaps — đọc kỹ trước khi dùng cho kỹ thuật)

| # | Thiếu | Hệ quả | Vì sao |
|---|---|---|---|
| 1 | **Dòng định mức board thật** | **100% board = `rating_missing`** → không đánh giá được quá tải/bảo vệ | IFC `Nimellisvirta` = 0 placeholder |
| 2 | **Cân bằng pha** | 100% `not_available` → không tính được mất cân bằng pha | Chưa phân bổ tải theo từng pha |
| 3 | **Độ tin cậy topology** | 0 quan hệ `exact/high` (766 low / 266 medium) → board↔zone là **ước lượng**, không phải sơ đồ đấu dây | Không có cable đấu nối board→tải trong IFC |
| 4 | **Hệ số đồng thời (diversity)** | Σ đỉnh board (1 275 kW) **cộng dồn**, cao hơn đỉnh tòa nhà thực | Chưa tính coincidence factor / đỉnh đồng thời |
| 5 | **Tiết diện cáp · sụt áp · ngắn mạch** | Không có cable sizing / voltage-drop / Icc | Ngoài phạm vi (cần thông số cáp + chiều dài tuyến) |
| 6 | **Công suất thiết kế điểm tải** | 598 load point `design_power=0`, 200 thiếu → phân bổ trong-zone kém mịn | IFC `Teho` thưa/placeholder |
| 7 | **HVAC → board** | 308/308 HVAC qua **pseudo** floor-main (low) | Không có liên kết IFC HVAC↔board |
| 8 | **Đo thật (metering)** | Mọi số là **mô phỏng**, chỉ đồng hồ tòa nhà là "measured" | Không có submeter từng board |

→ Hệ này là **lớp suy luận + trực quan hoá kỹ thuật**, **KHÔNG** phải nghiên cứu phối
hợp bảo vệ / load-flow đã nghiệm thu.

---

## 6. INSIGHT kỹ thuật

1. **Cơ cấu tải cân đối nhưng nghiêng chiếu sáng** (39% lights / 33% plug / 27% HVAC).
   Với khí hậu mát của scenario, HVAC chỉ 27% → đòn bẩy tiết kiệm lớn nhất nằm ở
   **chiếu sáng + thiết bị** (cộng 72%), không phải HVAC như giả định thường gặp.
2. **EUI 40,6 kWh/m²/năm là THẤP** so với văn phòng điển hình (~100–250). Gợi ý dataset
   mô phỏng thiên về bảo toàn, hoặc diện tích gồm nhiều khu chưa điều hoà → cần đối
   chiếu khi suy luận tuyệt đối; **so sánh tương đối giữa board/zone vẫn hợp lệ**.
3. **Năng lượng tập trung**: một zone duy nhất ~335 MWh (cả "Foundation") trội bất
   thường — ứng viên số 1 để kiểm tra mô hình/sub-meter; foundation thường ít tải.
4. **Cấu trúc 230/400V rõ ràng**: 37 board 3-pha 400V gánh HVAC & tải lớn; 19 board
   1-pha 230V cho chiếu sáng. Phân tầng đúng tập quán LV.
5. **Bảo toàn năng lượng đứng vững**: Σ đỉnh board 1 275 kW ≈ Σ đỉnh zone 1 265 kW và
   lệch năng lượng 0.0% → cơ chế phân bổ đáng tin **về mặt năng lượng** (dù topology
   chỉ ở mức ước lượng).
6. **RKE01 basement = tủ LV chính** (236,6 kW, 531 MWh, gấp ~1,7× tủ kế tiếp) → điểm
   giám sát/đo ưu tiên; mọi chiến lược peak-shaving nên bắt đầu từ đây.
7. **766/1032 ánh xạ ở mức `low`** → khi agent trả lời về board↔zone phải nêu rõ "ước
   lượng, độ tin cậy thấp" (answer policy ép điều này) — đừng dùng cho điều khiển/bảo vệ.

---

## 7. Hướng nâng cấp (nếu muốn tiến tới mức kỹ thuật)

1. **Nạp dòng định mức/cầu chì thật** (bảng board hoặc nhập tay) → mở khoá overload &
   loading-% thật, gỡ `rating_missing`.
2. **Phân bổ theo pha** (gán mạch vào L1/L2/L3) → tính mất cân bằng pha.
3. **Hệ số đồng thời** theo loại tải/khung giờ → đỉnh board/feeder sát thực tế.
4. **Tuyến cáp + sụt áp** từ máng cáp đã có (1 801 đoạn) → kiểm tra ΔU%.
5. **Sub-meter ảo per-board** đối chiếu với phân bổ → nâng độ tin cậy từ low→medium/high.

---

## 8. Tham chiếu nhanh

| dữ liệu | nguồn |
|---|---|
| Năng lượng zone (gold) | `data/final/03. Data_parquet/…`; tổng hợp năm → `data/electrical_distribution/zone_annual_energy.csv` |
| Bảng board | `board_annual_summary.csv`, `electrical_boards.csv` |
| Phân bổ | `zone_load_to_board_allocation.csv` |
| Mạch / pha | `electrical_circuits.csv`, `phase_balance_summary.csv` |
| Kiểm định | `electrical_validation_report.json`, `manual_review_items.csv` |
| Đồ thị | `data/knowledge_graph_build/graph_nodes.csv`, `graph_edges.csv` |
| 3D scene API | `GET /api/electrical/scene` (boards/zones-bbox/links/loads/floors) |
| Build lại | `python scripts/build_electrical_kg.py --all` |

> **Một câu:** Tòa nhà tiêu thụ **~3 107 MWh/năm** (39% chiếu sáng, 33% thiết bị, 27%
> HVAC), phân phối qua **57 tủ** (RKE01 basement là tủ chính 236,6 kW); năng lượng được
> phân bổ **bảo toàn tuyệt đối** về board, nhưng **topology, dòng định mức, cân bằng pha
> và hệ số đồng thời còn là ước lượng/thiếu** — đủ để xếp hạng & trực quan hoá, chưa đủ
> để thay một nghiên cứu bảo vệ điện chính thức.
