# GreenFlow — Nguyên lý Knowledge Graph, Graph-RAG & cách Agent gọi

> Tài liệu giải thích **toàn bộ nguyên lý** của lớp tri thức điện (electrical knowledge
> graph) trong GreenFlow: cấu trúc **node/edge**, **database** lưu ở đâu, cơ chế
> **Graph-RAG** (truy hồi + trả lời có provenance), và **agent gọi như thế nào**.
> Mọi con số trong tài liệu là số thật của lần build hiện tại (commit `22d74df`+).

---

## 0. Bức tranh tổng thể

GreenFlow có **2 lớp dữ liệu** và **2 bề mặt agent** tách bạch:

```
                 ┌─────────────────────────────────────────────────────────┐
                 │  LỚP NĂNG LƯỢNG (gold)  —  EnergyPlus mô phỏng           │
                 │  data/final/*.parquet : 308 zone × 30 phút × cả năm 2025 │
                 │  lights/equipment/HVAC kW, kWh — KHÔNG bao giờ mô phỏng lại│
                 └───────────────┬─────────────────────────────────────────┘
                                 │  (đọc, không sửa)
                 ┌───────────────▼─────────────────────────────────────────┐
                 │  LỚP TRI THỨC (knowledge graph điện)                     │
                 │  backend/greenflow/electrical/  →  data/knowledge_graph_*│
                 │  NODES (5705) + EDGES (13446) + RAG CARDS (375+9)        │
                 └───────────────┬─────────────────────────────────────────┘
                                 │
        ┌────────────────────────┼─────────────────────────┐
        ▼                        ▼                          ▼
  FastAPI /api/electrical   turbovec vector index    (tùy chọn) Postgres
  /api/graph/...            electrical_kg.tv          el_graph_nodes/edges…
        │                        │                          │
        └──────────┬─────────────┴──────────────────────────┘
                   ▼
        AGENT gọi (2 cách): ① HTTP endpoint   ② Python tool (electrical_graph_tool)
```

Nguyên tắc bất biến của lớp tri thức (đã được kiểm chứng bằng test + validation):
- **Không sửa IDF, không mô phỏng lại EnergyPlus.** Chỉ đọc kết quả gold.
- **Board KHÔNG phải là tải tiêu thụ.** Nhu cầu của board = năng lượng zone (E+ mô
  phỏng) được **phân bổ lại** → Σ năng lượng board = Σ năng lượng zone (lệch 0.0%,
  không double-count).
- **Mọi node/edge đều mang provenance**: `source_system`, `value_class`, `confidence`.
- **Không "bịa" topology chính xác**: quan hệ board↔zone là **ước lượng có nhãn tin
  cậy**, không phải sơ đồ đấu dây thực, trừ khi `confidence = exact`.

---

## 1. Nguyên lý GRAPH — Node & Edge

Knowledge graph là một **đồ thị có hướng, có thuộc tính** (directed property graph),
KHÔNG dùng Neo4j — nó được lưu phẳng dưới dạng **CSV + JSONL** (xem §3). Mỗi thực thể
trong tòa nhà là một **node**; mỗi mối quan hệ là một **edge**.

### 1.1. Node (thực thể) — `graph_nodes.csv` / `.jsonl`

Mỗi node có 17 cột (định nghĩa ở `graph_build.NODE_FIELDS`):

| cột | ý nghĩa |
|---|---|
| `node_id` | ID canonical ổn định, có tiền tố theo loại: `board_`, `tz_` (zone), `lp_`/`circuit_`, `floor_`, `eplz_`, `meter_`… |
| `node_type` | loại thực thể (xem bảng dưới) |
| `name`, `label` | tên người đọc + nhãn ngắn (device tag) |
| `source_system` | nguồn: `ifc_arch`, `ifc_ele`, `energyplus`, `derived`, `greenflow_post` |
| `source_file` | file gốc (`ELE_enriched.ifc`, IDF…) |
| `ifc_global_id`, `eplus_name`, `xeokit_object_id` | khóa liên kết sang IFC / EnergyPlus / 3D viewer |
| `zone_id`, `floor_id`, `room_id` | khóa không gian |
| `coordinates` | `[x,y,z]` mét (khi định vị được) |
| `properties_json` | thuộc tính kỹ thuật (điện áp, pha, mã hệ thống…) |
| **`value_class`** | **giá trị được biện minh thế nào** (xem §1.3) |
| **`confidence`** | độ tin cậy ∈ {exact, high, medium, low, manual_review} |
| `notes` | ghi chú |

**14 loại node (5705 node):**

| node_type | số lượng | nguồn | value_class |
|---|--:|---|---|
| `CableTray` (máng/phụ kiện cáp) | 1784 | IFC ELE | ifc_derived |
| `LightFixture` (đèn) | 1408 | IFC ELE | ifc_derived |
| `HVACDevice` | 1234 | IFC HVAC | ifc_derived |
| `ThermalZone` (vùng nhiệt) | 308 | IFC ARCH | ifc_derived |
| `EnergyPlusZone` | 308 | EnergyPlus | energyplus_simulated |
| `PTAC` (mô hình HVAC đại diện zone) | 305 | EnergyPlus | energyplus_simulated |
| `Outlet` (ổ cắm) | 187 | IFC ELE | ifc_derived |
| `Circuit` (mạch — thật/giả lập) | 80 | derived | naming_inferred |
| `ElectricalBoard` (tủ phân phối) | 57 | IFC ELE | ifc_derived |
| `Alarm` (đầu báo) | 12 | IFC ELE | ifc_derived |
| `Floor` | 10 | IFC ARCH | ifc_derived |
| `Meter` (đồng hồ tòa nhà) | 10 | EnergyPlus | energyplus_simulated |
| `Building` | 1 | IFC ARCH | ifc_derived |
| `WeatherTimeseries` | 1 | EnergyPlus | energyplus_simulated |

### 1.2. Edge (quan hệ) — `graph_edges.csv` / `.jsonl`

Mỗi edge có 11 cột (`graph_build.EDGE_FIELDS`):

| cột | ý nghĩa |
|---|---|
| `edge_id` | ID ổn định (suy ra từ source+target+type) |
| `source_node_id`, `target_node_id` | hai đầu mút (có hướng) |
| `relationship_type` | loại quan hệ (xem bảng) |
| `direction` | directed/undirected |
| **`weight`** | trọng số phân bổ ∈ [0,1] (cho quan hệ phân bổ tải) |
| `source` | nguồn bằng chứng |
| **`method`** | quan hệ được suy ra **bằng cách nào** (vd `system_code+floor+nearest`) |
| **`confidence`** | độ tin cậy quan hệ |
| `evidence_json` | bằng chứng hỗ trợ (khoảng cách m, mã hệ thống, category…) |
| `notes` | thường là `load_category` |

**14 loại quan hệ (13446 edge):**

| relationship_type | số lượng | ý nghĩa & độ tin cậy |
|---|--:|---|
| `OBJECT_LOCATED_ON_FLOOR` | 3477 | vật điện nằm trên tầng (IFC storey containment — **high**) |
| `OBJECT_ASSIGNED_TO_ZONE` | 3476 | gán vào IfcSpace gần nhất cùng tầng (**medium/low**) |
| `CIRCUIT_SUPPLIES_LOAD_POINT` | 1607 | mạch cấp cho đèn/ổ, gom theo mã hệ thống Phần Lan |
| `HVAC_DEVICE_SERVES_ZONE` | 1185 | thiết bị HVAC phục vụ zone gần nhất |
| `ZONE_LOAD_ALLOCATED_TO_BOARD` | 1032 | **tải zone được phân bổ về board** (có `weight`) ⭐ |
| `ZONE_LOAD_ALLOCATED_TO_CIRCUIT` | 1032 | tải zone phân bổ về mạch |
| `FLOOR_HAS_ROOM` | 308 | tầng chứa phòng/zone |
| `ZONE_MAPS_TO_EPLUS_ZONE` | 308 | đồng nhất zone IFC ↔ zone EnergyPlus (**exact**) |
| `ZONE_HAS_HVAC_LOAD` | 308 | zone có tải HVAC |
| `WEATHER_CONTEXT_FOR_HVAC_LOAD` | 308 | bối cảnh thời tiết cho tải HVAC |
| `ENERGYPLUS_PTAC_REPRESENTS_HVAC_FOR` | 305 | PTAC là mô hình **đại diện** (không 1:1 với HVAC thật) |
| `BOARD_SUPPLIES_CIRCUIT` | 80 | board cấp cho mạch |
| `BUILDING_HAS_FLOOR` | 10 | tòa nhà có tầng (**exact**) |
| `METER_MEASURES_ENTITY` | 10 | đồng hồ đo tòa nhà (**exact**) |

⭐ `ZONE_LOAD_ALLOCATED_TO_BOARD` là **xương sống** của lớp điện: nó nối năng lượng
mô phỏng (zone) với hạ tầng phân phối (board), kèm `weight` (Σ = 1 mỗi cặp
zone×category) và `confidence`. Đây chính là quan hệ mà 3D "supply links" vẽ ra.

### 1.3. value_class — "giá trị này đáng tin tới đâu?"

Đây là cốt lõi triết lý của hệ: **không con số nào vô danh tính**. Mỗi giá trị mang
một trong các nhãn (enum trong `provenance.py`):

| value_class | nghĩa | ví dụ |
|---|---|---|
| `measured` | đo thật từ đồng hồ/cảm biến | đồng hồ tòa nhà, thời tiết |
| `energyplus_simulated` | E+ mô phỏng | năng lượng lights/equipment/HVAC của zone |
| `ifc_derived` | đọc từ IFC | điện áp/pha/mã hệ thống của board |
| `spatially_inferred` | suy theo không gian | gán đèn vào tầng/zone gần nhất |
| `naming_inferred` | suy theo tên/mã | gom đèn→mạch theo `Järjestelmien tunnukset` |
| `assumption_based` | dùng giả định | dòng điện tính bằng PF/điện áp mặc định |
| `manual_review` | thiếu bằng chứng | cần người kiểm, không dùng cho điều khiển |

> **Quy tắc:** `confidence = exact` mới được coi là topology thật. `confidence ∈
> {low, manual_review}` → phải hiện cảnh báo, không tự động hành động.

### 1.4. Graph được xây thế nào — `graph_build.py` (Phase 5)

Hàm `run()` ráp đồ thị theo các tiểu-đồ-thị, đọc từ các artifact phase trước:

1. **Spatial**: Building → Floors (`BUILDING_HAS_FLOOR`) → Zones (`FLOOR_HAS_ROOM`),
   và Zone ↔ EnergyPlusZone (`ZONE_MAPS_TO_EPLUS_ZONE`, exact — nhờ `zone_id = 'tz_'
   + sanitize(IfcSpace.GlobalId)`).
2. **Electrical assets**: board / load-point / cable / circuit thành node; thêm
   `BOARD_SUPPLIES_CIRCUIT`.
3. **Định vị**: `OBJECT_LOCATED_ON_FLOOR` (storey containment), `OBJECT_ASSIGNED_TO_ZONE`
   (nearest IfcSpace) từ `object_to_floor_room_zone_map.csv`.
4. **Mạch→tải**: `CIRCUIT_SUPPLIES_LOAD_POINT`.
5. **Phân bổ tải**: `ZONE_LOAD_ALLOCATED_TO_BOARD` / `…_TO_CIRCUIT` (kèm weight) từ
   `zone_load_to_board_allocation.csv`.
6. **Meters**: `METER_MEASURES_ENTITY`.
7. **Merge HVAC subgraph** (Phase 8): `hvac_nodes.csv` + `hvac_energy_graph_edges.csv`.

Kết quả ghi ra `graph_nodes.{csv,jsonl}`, `graph_edges.{csv,jsonl}`, `graph_schema.md`,
`graph_data_dictionary.csv` + bản mirror tiểu-đồ-thị điện trong `data/electrical_distribution/`.

---

## 2. DATABASE — dữ liệu nằm ở đâu?

Điểm thiết kế quan trọng: **nguồn sự thật là FILE**, không phải DB. Postgres chỉ là
bản nạp tùy chọn để truy vấn nhanh. Vì sao? → để pipeline chạy & demo được **không
cần dựng DB**, và để mọi artifact versioned/diff được.

### 2.1. File-backed (mặc định, bắt buộc)

| dạng | file | vai trò |
|---|---|---|
| CSV | `graph_nodes.csv`, `graph_edges.csv`, `electrical_boards.csv`, `board_annual_summary.csv`, `zone_load_to_board_allocation.csv`… | đồ thị + bảng tổng hợp (đã commit) |
| JSONL | `graph_nodes.jsonl`, `graph_rag_entity_cards.jsonl`, `graph_rag_relationship_cards.jsonl` | đồ thị dạng dòng + **RAG cards** |
| Parquet | `board_estimated_timeseries.parquet`, `board_load_category_timeseries.parquet` | timeseries board (lớn, **gitignored**, tái tạo bằng `--phase timeseries`) |
| turbovec | `storage/processed/vector/electrical_kg.tv` (+ `electrical_kg_cards.json`) | **vector index** của RAG cards |

API điện (`api/routers/electrical.py`) đọc **trực tiếp** các file này → endpoint hoạt
động ngay sau khi pipeline chạy, không cần DB.

### 2.2. Postgres (tùy chọn — `--load-db`)

`loaders/postgres.py` nạp idempotent (recreate-and-fill) vào 5 bảng:

```
el_graph_nodes(node_id PK, node_type, name, floor_id, zone_id,
               ifc_global_id, eplus_name, value_class, confidence, properties_json JSONB)
el_graph_edges(edge_id PK, source_node_id, target_node_id, relationship_type,
               weight, method, confidence, evidence_json JSONB)   -- + index src/tgt
el_board_summary(board_id PK, device_tag, voltage_v, phase_count, rated_current_a,
                 total_kwh, peak_total_kw, estimated_peak_current_a, loading_pct, overload_status)
el_zone_board_allocation(zone_id, eplus_zone_name, load_category, board_id,
                         weight, mapping_confidence, mapping_method)
el_manual_review(item_id PK, subject_id, subject_type, reason, recommended_action, confidence)
```

> Lưu ý phân biệt với graph của **chatbot chính**: bảng `entity_relations` (Postgres,
> truy vấn bằng recursive CTE trong `agent/tools/graph_tool.py`) là đồ thị **thiết
> bị/zone vận hành** — KHÁC với `el_graph_*` (đồ thị **phân phối điện**). Hai đồ thị
> bổ trợ nhau, không trùng.

### 2.3. Vector store — turbovec

`vector/store.py` bọc `turbovec.IdMapIndex` (index nhị phân lượng tử hoá, id ổn định
uint64). Embedding do `vector/embedder.py` sinh ngoài (turbovec không tự nhúng). Dùng
chung hạ tầng với chatbot chính, nhưng **collection riêng** `electrical_kg.tv`.

---

## 3. Nguyên lý GRAPH-RAG

RAG = **Retrieval-Augmented Generation**: thay vì để LLM "nhớ" số liệu (dễ bịa), ta
**truy hồi** thẻ tri thức liên quan rồi để LLM diễn giải **chỉ dựa trên** thẻ đó, kèm
provenance. "Graph-RAG" ở đây nghĩa là các thẻ được **sinh ra từ đồ thị** (mỗi thẻ tóm
tắt một node + các quan hệ của nó).

### 3.1. Bước 1 — Sinh CARDS (`graph_rag.py`, Phase 9)

Mỗi card là 1 JSON: một đoạn **`text`** (để nhúng) + **structured provenance**.

- **Entity cards (375)**: cho mỗi **board / zone / floor**. Ví dụ board card:
  ```json
  {
    "card_id": "board_1T4Dk9...", "card_type": "entity", "entity_type": "ElectricalBoard",
    "title": "Board RKE01",
    "text": "Electrical distribution board RKE01 on floor floor_basement, system S03…
             400 V, 3-phase. Estimated annual energy 531465 kWh, peak 236.6 kW,
             estimated peak current … A, status rating_missing. Serves ~28 zones…",
    "properties": {voltage_v, phase_count, rated_current_a, system_code, floor_id…},
    "demand":     {total_kwh, peak_total_kw, estimated_peak_current_a, loading_pct, overload_status},
    "provenance": "IFC-derived asset; demand estimated from EnergyPlus-simulated zone energy…",
    "confidence": "ifc_derived asset; medium/low allocation",
    "caveats":    ["rated current missing → overload cannot be assessed", …],
    "linked_entities": ["tz_…", …],
    "recommended_dashboard_view": "board_view"
  }
  ```
- **Relationship cards (9)**: một thẻ cho mỗi **loại quan hệ** (mô tả nghĩa +
  provenance), để khi hỏi "board↔zone nghĩa là gì" LLM hiểu đó là *ước lượng*.

Đồng thời sinh 4 tài liệu hướng dẫn: `graph_rag_answer_policy.md`,
`graph_rag_example_questions.md`, `graph_rag_schema.md`, `graph_rag_retrieval_queries.sql`.

### 3.2. Bước 2 — Nhúng & index (`loaders/pgvector.py :: load()`)

```
cards (entity + relationship)  ──embed(text)──▶  vectors  ──▶  turbovec IdMapIndex
                                                              (electrical_kg.tv)
              + lưu electrical_kg_cards.json (id dòng → card)
```

Embedder mặc định ở dev là **`hashing`** (HashingEmbedder, KHÔNG cần torch, dim 384) để
chạy được mọi nơi. Production đổi `EMBEDDER = "bge-m3"` (đa ngôn ngữ 1024 chiều) →
retrieval ngữ nghĩa thật. **Đổi embedder phải reindex** (dim khác).

### 3.3. Bước 3 — Truy hồi (`search()`)

```
question ──embed(kind="query")──▶ turbovec.search(k) ──▶ card_ids ──▶ cards
                                          │ (nếu index/embedder hỏng)
                                          ▼
                                  _keyword_search() fallback (đếm từ trùng)
```

Thiết kế **luôn trả lời được**: nếu chưa build index hoặc thiếu model, tự rơi về tìm
kiếm từ khoá → endpoint `/api/graph/rag/answer` không bao giờ 500.

> Khác biệt với RAG của **chatbot chính** (`chat/service.py`): chatbot dùng **hybrid**
> dense (bge-m3→turbovec) **+** lexical (Postgres full-text) **→ RRF fuse → cross-encoder
> rerank** trên `kb_chunks`. Graph-RAG điện đơn giản hơn (dense hoặc keyword) vì tập thẻ
> nhỏ (384) và có cấu trúc.

### 3.4. Bước 4 — Trả lời CÓ PROVENANCE (`answer()`)

```python
cards = search(question, k=5)
top = cards[0]
answer = top.text
       + "Caveats: " + "; ".join(top.caveats)
       + "Provenance: " + top.provenance + "; confidence: " + top.confidence
return {answer, value_labels_required:[measured, energyplus_simulated, ifc_derived,
        spatially_inferred, naming_inferred, assumption_based, manual_review],
        sources:[{card_id, title, view}…], policy}
```

`value_labels_required` + `policy` ép tầng diễn giải (LLM hoặc UI) phải nói rõ số liệu
là đo/mô phỏng/suy luận.

### 3.5. ANSWER POLICY — luật bất di bất dịch (`graph_rag_answer_policy.md`)

Khi trả lời, agent **BẮT BUỘC**:
1. **Gắn nhãn mọi giá trị** (measured / energyplus_simulated / ifc_derived /
   spatially_inferred / naming_inferred / assumption_based / manual_review).
2. **Không overclaim topology**: board→zone là *phân bổ ước lượng*, không phải bảng
   mạch đã nghiệm thu — trừ khi edge `confidence = exact`.
3. **Quá tải**: chỉ khẳng định overload/loading-% khi board có `rated_current_a` thật.
   Nếu không → `rating_missing` + chỉ xếp hạng nhu cầu.
4. **Board là tài sản phân phối**, không phải tải tiêu thụ.
5. Luôn nêu **confidence** và **manual-review**, trích **bằng chứng** (method, khoảng
   cách, mã hệ thống).

---

## 4. AGENT GỌI NHƯ THẾ NÀO

Hiện có **2 đường gọi đang chạy** và **1 đường khuyến nghị wire thêm**.

### ① Qua HTTP endpoint (đang dùng — frontend & mọi client)

`api/routers/electrical.py` expose:

| endpoint | trả về |
|---|---|
| `GET /api/graph/rag/answer?question=…` | gọi `pgvector.answer()` → câu trả lời + sources + value_labels + policy |
| `GET /api/graph/entities/{id}/neighbors` | hàng xóm trong đồ thị (edge tới/đi) |
| `GET /api/graph/entities/{id}/evidence` | bằng chứng (method/confidence/evidence) của mọi edge dính tới entity |
| `GET /api/electrical/scene` | toàn bộ payload 3D (boards/zones/links/loads/floors) |
| `GET /api/electrical/boards/{id}` …`/served-zones` …`/timeseries` | chi tiết board + zone được cấp + timeseries |

→ Trang **Electrical Distribution Twin** (`web/.../electrical/page.tsx`) dùng ô "Ask the
electrical knowledge graph" gọi thẳng `/api/graph/rag/answer`.

### ② Qua Python tool (`agent/tools/electrical_graph_tool.py`)

Module file-backed, tái dùng dashboard builders + `pgvector.answer`:

```python
available()                  # đã build artifact chưa
neighbors(entity_id)         # hàng xóm đồ thị
board_demand(board_id)       # nhu cầu + zone được cấp + provenance
served_zones(board_id)       # board cấp cho zone nào
zone_supply(zone_id)         # zone được board nào cấp (confidence)
top_boards(n)                # xếp hạng board theo peak kW
boards_missing_rating()      # board thiếu rated current
answer(question)             # graph-RAG (delegate pgvector.answer)
```

Mọi kết quả mang provenance để agent tuân answer policy.

### ③ Đường khuyến nghị: đăng ký vào chatbot function-calling

Hiện `chat/data_tools.py :: TOOL_SPECS` mới có tool **vận hành tòa nhà** (KPI, timeseries
zone, top consumers, alerts, trigger action) — **chưa** có tool điện. Chatbot
(`chat/service.py`) chạy vòng lặp:

```
user → retrieve(kb_chunks, hybrid) → LLM(tools=TOOL_SPECS)
     → [tool_calls? → dispatch(name,args) → feed kết quả lại]×(≤4) → câu trả lời
```

Để chatbot **tự gọi** graph-RAG điện, chỉ cần thêm 1 tool vào `TOOL_SPECS` + `_DISPATCH`:

```python
# trong data_tools.py
from greenflow.agent.tools import electrical_graph_tool as elec

def query_electrical_graph(conn, building_id, question: str) -> dict:
    return elec.answer(question)              # file-backed, bỏ qua conn

TOOL_SPECS.append({"type": "function", "function": {
    "name": "query_electrical_graph",
    "description": "Hỏi đồ thị phân phối điện: board nào cấp cho zone, nhu cầu/peak "
                   "board, quá tải, mạch, độ tin cậy. Trả lời kèm provenance.",
    "parameters": {"type": "object",
        "properties": {"question": {"type": "string"}}, "required": ["question"]}}})
_DISPATCH["query_electrical_graph"] = query_electrical_graph
```

(LLM chỉ chọn tool + điền `question`; thực thi là code → an toàn, không SQL tự do.)

### ④ LangGraph agent (báo cáo/tối ưu)

Agent vận hành (`agent/`, các node optimization/prediction/báo cáo) dùng
`agent/tools/graph_tool.py` để lấy **ngữ cảnh semantic** từ `entity_relations`
(Postgres) — đồ thị thiết bị/zone, khác đồ thị điện. Có thể bổ sung ngữ cảnh điện cho
node "building semantic report" bằng cách gọi `electrical_graph_tool` tương tự.

---

## 5. Luồng end-to-end ví dụ

**Hỏi:** *"Board nào tải lớn nhất và có quá tải không?"*

```
1. /api/graph/rag/answer?question=…   (hoặc chatbot tự gọi query_electrical_graph)
2. search(): embed câu hỏi → turbovec → top card = "Board RKE01"
3. answer(): ghép text + caveats + provenance
4. Trả về:
   answer: "Board RKE01 … 400V 3-pha, peak ~236.6 kW, status rating_missing.
            Caveats: rated current missing → không đánh giá được quá tải (chỉ xếp
            hạng nhu cầu). Provenance: IFC-derived asset; demand = EnergyPlus-simulated
            zone energy × inferred allocation; confidence: ifc_derived; medium/low allocation."
   value_labels_required: [measured, energyplus_simulated, ifc_derived, …]
   sources: [{card_id: board_1T4Dk9…, view: board_view}]
```

→ Đúng answer policy: nêu peak (energyplus_simulated × inferred), **không** khẳng định
quá tải vì thiếu rated current, gắn nhãn provenance.

---

## 6. Bảng tham chiếu nhanh

| Bạn cần | File / Endpoint |
|---|---|
| Định nghĩa node/edge | `backend/greenflow/electrical/graph_build.py` (`NODE_FIELDS`, `EDGE_FIELDS`) |
| Enum provenance | `electrical/provenance.py` (`ValueClass`, `Confidence`, `SourceSystem`) |
| Đồ thị đã build | `data/knowledge_graph_build/graph_nodes.csv`, `graph_edges.csv`, `graph_schema.md` |
| Sinh RAG cards | `electrical/graph_rag.py` → `graph_rag_entity_cards.jsonl`, `_relationship_cards.jsonl` |
| Answer policy | `data/knowledge_graph_build/graph_rag_answer_policy.md` |
| Nhúng + truy hồi + answer | `electrical/loaders/pgvector.py` (`load/search/answer`) |
| Vector store / embedder | `vector/store.py` (turbovec), `vector/embedder.py` (bge-m3 / hashing) |
| Nạp Postgres (tùy chọn) | `electrical/loaders/postgres.py` (`el_graph_*`, `el_board_summary`…) |
| Agent tool điện | `agent/tools/electrical_graph_tool.py` |
| Chatbot function-calling | `chat/data_tools.py` (`TOOL_SPECS`, `_DISPATCH`), `chat/service.py` |
| API điện | `api/routers/electrical.py` |
| Build lại | `python scripts/build_electrical_kg.py --all` (`--phase graph\|rag\|…`, `--load-db`) |

---

## 7. Tóm tắt một câu

> GreenFlow biến kết quả **EnergyPlus mô phỏng** + **IFC** thành một **đồ thị thuộc tính
> có hướng** (5705 node / 13446 edge, mỗi phần tử gắn provenance), từ đồ thị sinh ra
> **thẻ RAG** đem nhúng vào **turbovec**; khi hỏi, hệ **truy hồi thẻ** và trả lời **kèm
> nhãn provenance + answer policy** — để agent suy luận về phân phối điện mà **không bao
> giờ bịa số, không double-count, không khẳng định topology/quá tải vượt quá bằng chứng**.
