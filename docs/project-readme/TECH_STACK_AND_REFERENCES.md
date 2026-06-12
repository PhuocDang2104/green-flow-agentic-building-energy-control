# GreenFlow — Technology Stack & References

> Doc này chốt **công nghệ dùng cho từng module**, mức ưu tiên (P0/P1/P2), lý do chọn, cái cần **bỏ để tránh phình**, và **các dự án/paper tham chiếu** (học theo cái đã chứng minh). Bám đúng các quyết định đã chốt: E+ archetype + IdealLoads, surrogate LightGBM học từ E+, validate bằng batch counterfactual, IFC đóng băng, Postgres-only, dữ liệu 3 tháng (3–5/2025), thời tiết thật.

---

## 1. Bảng stack theo layer

| Layer / Module | Công nghệ | Vai trò | Mức | Lý do |
|---|---|---|---|---|
| BIM extract | **IfcOpenShell** (`ifcopenshell.geom` iterator) | Đọc IFC, footprint world-coord, PIP map device→zone | P0 | Đã kiểm chứng (iterator + mm/m + z-band) |
| Semantic graph | **Brick Schema vocabulary** trong Postgres `entity_relations` | Chuẩn hoá quan hệ zone/device/point | P0 | Chuẩn ngành (ASHRAE 223P), agent reasoning sạch |
| Database | **PostgreSQL 15+ + pgvector** | Metadata, time-series (cột rộng), graph (CTE), vector | P0 | 1 DB lo hết, đúng nguyên tắc stack gọn |
| Mô phỏng | **EnergyPlus 24.x** (batch) | "Tòa nhà ảo" sinh vật lý | P0 | Source of truth |
| IDF tooling | **eppy** | Đọc/sửa IDF — lõi `action_to_idf`, parse output | P0 | Foundational, Python thuần |
| Archetype | **archetypal** | Template archetype + đọc/sửa IDF trên nền eppy | P0 | Hợp quyết định "archetype, không convert 308 phòng" |
| Geometry IDF (nếu cần dựng) | **honeybee-energy** / **geomeppy** | Dựng zone/surface E+ từ hình học sạch | P1 | Chỉ khi cần dựng model có hình học |
| Weather | **ladybug** (đọc/ghi EPW) + **EPW TMY HCMC** | Thời tiết cho E+ | P0 | Nhanh, đáng tin |
| ML forecast/surrogate | **LightGBM** (XGBoost/RandomForest dự phòng) | Bộ "đoán nhanh" học từ output E+ | P1 | Pattern surrogate-of-E+ đã chứng minh |
| Occupancy | **Ultralytics YOLO** (pretrained) + **ByteTrack** | Đếm người trên video demo | P1 | Pretrained, không train; tracking ổn định count |
| Agent runtime | **LangGraph** (gọn) | Orchestrator + tool nodes + human-in-loop | P0 | Đủ cho copilot; giữ ít node |
| LLM | cấu hình được (Claude / OpenAI) qua biến env | Điều phối + giải thích (KHÔNG quyết safety) | P0 | Không hardcode 1 provider |
| Backend | **FastAPI** | API + LangGraph runtime + tích hợp E+/ML | P0 | Cùng Python với ifcopenshell/E+/ML |
| 3D web | **xeokit** *(khuyến nghị)* hoặc GLB + React Three Fiber | Digital twin 3D, pick/highlight zone | P0 | Xem mục 3 |
| Frontend | **Next.js + React + TS + Tailwind** | 3 page dashboard | P0 | — |
| RAG | **pgvector** + embedding model | Hỏi tài liệu MEP/policy | P2 | Chỉ khi có chat-hỏi-docs |
| E+ as tool | **EnergyPlus-MCP** | Expose E+ thành tool agent gọi | P2 (tùy chọn) | Hợp framing "E+ là tool" |

---

## 2. Quyết định cho EnergyPlus + IDF tooling

- **eppy** = nền: đọc IDF vào cấu trúc Python, sửa object/schedule. Dùng cho `sim/action_to_idf.py` (chỉ sửa `Schedule:Compact` của setpoint/lighting/availability) và parse output.
- **archetypal** = quản template archetype (open office / meeting / lobby…), đọc/sửa IDF trên nền eppy. Dùng để gắn lịch vào từng archetype zone.
- **honeybee-energy / geomeppy**: chỉ lấy khi cần **dựng hình học** E+ — MVP dùng prototype IDF + archetype nên thường KHÔNG cần.
- **Bỏ OpenStudio SDK** (nặng) trừ khi bắt buộc import gbXML.
- **Không auto-convert hình học 308 phòng từ IFC sang IDF** (đã chốt) — dùng archetype, map zone→archetype.

## 3. Quyết định cho 3D viewer (chọn 1)

| | **xeokit** (khuyến nghị) | GLB tiền-convert + React Three Fiber |
|---|---|---|
| Mạnh | Build sẵn cho BIM, render model lớn nhanh, **giữ IFC GlobalId**, pick/highlight/cắt lớp sẵn | UI 3D tùy biến cao, nhẹ, kiểm soát render |
| Yếu | SDK/format riêng (XKT), UI kém tùy biến hơn | **Phải tự** giữ `mesh_entity_map` + tự làm pick/highlight |
| Hợp khi | Muốn nhanh-tới-demo trên building 308 phòng + nghìn thiết bị | Cần UI 3D rất riêng |

→ **Khuyến nghị xeokit** để bớt hẳn mảng "map mesh↔GUID + pick". Pipeline: IFC → XKT (convert sẵn) → xeokit viewer, dùng GlobalId nối tới DB state.

## 4. Quyết định cho Weather → EPW

- **MVP: tải sẵn EPW TMY của HCMC** (EPWmap / climate.onebuilding.org). Nhanh, đáng tin, xong ngay.
- **Năm thật 2025**: chỉ làm nếu cần — lấy **Open-Meteo historical** (có shortwave radiation nên đủ cột bức xạ) → ghép EPW bằng **ladybug.epw**. Lưu ý: căn **thứ-trong-tuần 2025** (1/1/2025 = thứ Tư) + **timezone UTC+7**.
- **Khai báo Plan B trong report**: tái dùng hình học Nordic + EPW HCMC → ghi rõ giả định, đừng giấu.

## 5. Lớp semantic — dùng vocabulary Brick (không cần triplestore)

Lưu trong Postgres `entity_relations`, nhưng **đặt tên class/quan hệ theo Brick** (chuẩn ngành, hợp ASHRAE 223P) thay vì tự chế.

**Map `zone_equipment_map` (PIP) → quan hệ Brick:**

| Dữ liệu GreenFlow | Brick class | Quan hệ Brick |
|---|---|---|
| zone (IfcSpace) | `Zone` / `HVAC_Zone` | — |
| terminal scope=zone (AirTerminal, CooledBeam, Damper) | `Terminal_Unit` (`RVAV`, `Chilled_Beam`…) | `Terminal feeds Zone` |
| đèn (LightFixture) | `Lighting_Equipment` | `isPartOf Lighting_System`, `hasLocation Zone` |
| thiết bị plant (Valve/Coil/Fan) | `HVAC_Equipment` | `isPartOf HVAC_System` |
| cảm biến temp/RH/CO2 (virtual edge) | `Temperature_Sensor` / `CO2_Sensor` | `hasLocation Zone`, `isPointOf Equipment` |
| meter | `Meter` (`Electric_Meter`) | `meters Zone/Building` |
| setpoint | `Setpoint` | `isPointOf Terminal/Zone` |

Quan hệ chuẩn dùng: `feeds`, `isFedBy`, `hasPoint`, `isPointOf`, `isPartOf`, `hasLocation`, `hasPart`.

Lợi ích: credibility chuẩn ngành; agent trả lời sạch "thiết bị nào *feeds* zone này / point nào thuộc thiết bị"; đáp ứng systems-thinking của seminar. **Không cần RDF/SPARQL** — chỉ mượn từ vựng.

## 6. ML & Agent (tóm tắt, chi tiết ở doc ML/Agent)

- **Surrogate**: LightGBM train trên **sweep ~vài trăm–1000 run E+** (Latin Hypercube: ngày thời tiết × occupancy × setpoint). Input kiểu Sinergym (weather, giờ sin/cos, occupancy, setpoint, power/temp trước) → output energy/temp. Đo MAE/RMSE/CV-RMSE; bán điểm "nhanh hơn E+ ~10×".
- **KPI theo BOPTEST**: energy, cost, **thermal discomfort (K·h)**, peak, CO2/IAQ, comfort_violation_min.
- **Agent = copilot có guardrails** (đúng pattern "LLM recommendation 2025"): LLM điều phối + giải thích; **chọn action kiểu MPC-lite** (enumerate candidate → surrogate sàng → E+ validate top-k → chọn theo ràng buộc comfort/IAQ/peak + `regrettable_substitution_check`); policy là **rule deterministic**.
- **Không RL** cho MVP (khó train/giải thích/an toàn) — để roadmap.

## 7. Bỏ / để sau (chống phình)

| Bỏ/hoãn | Lý do |
|---|---|
| Neo4j / TimescaleDB / Redis Streams | Postgres + CTE + partition đủ cho P0 |
| Triplestore RDF/SPARQL cho Brick | Chỉ mượn vocabulary, lưu Postgres |
| OpenStudio SDK | Nặng; eppy/archetypal đủ |
| RL (Sinergym closed-loop) | Đã chọn batch counterfactual; RL để roadmap |
| LLM tự sinh IDF (EPlus-LLM) | Bài toán khác (modeling automation), không cần |
| Auto-convert 308-space IFC→IDF | Không khả thi hackathon; dùng archetype |
| Time-series EAV cho hot path | Dùng **cột rộng** (`zone_state_ts`, `device_state_ts`) để khỏi nổ dòng |

## 8. Gợi ý version / cài đặt

```text
EnergyPlus        24.x (pin bản ổn định, set ENERGYPLUS_BIN)
ifcopenshell      0.8.x   (đã test 0.8.5, dùng geom iterator)
shapely           2.0.x   (PIP, STRtree)
eppy / geomeppy   bản PyPI mới nhất
archetypal        bản mới nhất
ladybug-core      bản mới nhất (đọc/ghi EPW)
lightgbm          bản mới nhất
ultralytics(YOLO) bản mới nhất (pretrained, person class)
langgraph         bản mới nhất
fastapi + uvicorn bản mới nhất
postgres          15+ (image pgvector/pgvector:pg16 — port 5433 theo docker-compose)
web (xeokit)      xeokit-sdk / xeokit-bim-viewer (npm)
```

> Lưu ý cổng DB: docker-compose map Postgres ra **5433** → `DATABASE_URL` phải dùng `:5433`.

---

## 9. References (học theo cái nào)

**Simulation + control loop**
- [Sinergym (GitHub)](https://github.com/ugr-sail/sinergym) · [paper 2025](https://arxiv.org/html/2412.08293v1) — học vector quan sát + từ vựng action (né RL realtime).
- [BOPTEST (LBL)](https://buildings.lbl.gov/publications/building-optimization-testing) · [GitHub](https://github.com/ibpsa/project1-boptest) — học định nghĩa KPI chuẩn (thermal discomfort K·h, energy, cost, peak).

**Surrogate / forecast ML**
- [LightGBM surrogate of physics-based building simulator (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0378778823006254) · [Surrogate of EnergyPlus (ORNL)](https://info.ornl.gov/sites/publications/Files/Pub160865.pdf) — train LightGBM trên ~1000 run E+, nhanh ~10×.

**LLM + building / agent**
- [LLMs for building energy applications (Springer 2025)](https://link.springer.com/content/pdf/10.1007/s12273-025-1235-9.pdf) · [LLM multi-agent for building energy modeling (iScience 2025)](https://www.cell.com/iscience/fulltext/S2589-0042(25)02128-5) — xác nhận pattern "copilot đề xuất", không phải controller tự động.

**3D / BIM web**
- [xeokit SDK](https://xeokit.io/) · [xeokit-bim-viewer](https://github.com/xeokit/xeokit-bim-viewer) · [ThatOpen web-ifc](https://thatopen.github.io/engine_web-ifc/docs/)

**IDF tooling**
- [eppy](https://github.com/jamiebull1/geomeppy) · [geomeppy](https://geomeppy.readthedocs.io/en/latest/Start%20here.html) · [archetypal](https://archetypal.readthedocs.io/en/stable/reading_idf.html)

**Semantic standards**
- [Brick Schema](https://brickschema.org/) · [Brick vs Haystack](https://medium.com/@erik_paulson/a-comparison-of-the-brick-schema-and-project-haystack-2a9adde5013a) · [ASHRAE 223P + Haystack + Brick](https://marketing.project-haystack.org/project-haystack-media/press-releases/ashraes-bacnet-committee-project-haystack-and-brick-schema-collaborating-to-provide-unified-data-semantic-modeling-solution)

**Weather**
- [Ladybug Tools](https://github.com/ladybug-tools/ladybug) · [EPWmap](https://www.ladybug.tools/epwmap/)
