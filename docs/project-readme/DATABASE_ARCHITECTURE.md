# GreenFlow Database Architecture

Sơ đồ này mô tả cách GreenFlow lưu dữ liệu BIM, telemetry, graph semantics, vector retrieval và artifacts mô phỏng để AI chat có thể hiểu ngữ cảnh tòa nhà và truy vấn metrics.

```mermaid
flowchart LR
    subgraph S0["Raw Sources"]
        IFC1["ARCH IFC"]
        IFC2["HVAC IFC"]
        IFC3["ELE IFC"]
        IFC4["STRUCT IFC"]
        CCTV["CCTV / YOLO"]
        EDGE["Edge Devices"]
        WEA["Weather API"]
        TAR["Tariff / Schedule"]
    end

    subgraph S1["Ingestion & Extraction"]
        EXT["BIM Extractor\nifcopenshell"]
        BUS["Streaming Bus\nRedis Streams"]
        SYN["Synthetic Telemetry Generator"]
    end

    subgraph S2["Canonical Data Layer"]
        META["PostgreSQL\nBuilding / Floor / Zone / Device Metadata"]
        TS["Timeseries Tables\nTelemetry / Occupancy / Forecast / KPI"]
        GRAPH["Neo4j or Graph Tables\nBuilding Semantics / Relationships"]
        VEC["pgvector\nDocs / Policies / Notes / Summaries"]
        OBJ["Object Storage\nIFC / Video / E+ Artifacts / Model Files"]
    end

    subgraph S3["Analytics & AI Layer"]
        EPLUS["EnergyPlus Simulation"]
        MLP["ML Models\nEnergy / Temp / Anomaly / Comfort"]
        AGENT["AI Orchestrator / Chat"]
        RULE["Policy / Guardrails"]
        RPT["Dashboards / Reports"]
    end

    IFC1 --> EXT
    IFC2 --> EXT
    IFC3 --> EXT
    IFC4 --> EXT

    CCTV --> BUS
    EDGE --> BUS
    WEA --> BUS
    TAR --> BUS
    EXT --> META
    EXT --> GRAPH
    EXT --> VEC
    EXT --> OBJ

    META --> SYN
    BUS --> SYN
    SYN --> TS
    SYN --> GRAPH
    SYN --> VEC

    TS --> EPLUS
    GRAPH --> EPLUS
    META --> EPLUS
    OBJ --> EPLUS
    EPLUS --> TS
    EPLUS --> OBJ

    TS --> MLP
    GRAPH --> MLP
    VEC --> AGENT
    META --> AGENT
    TS --> AGENT
    GRAPH --> AGENT
    MLP --> AGENT
    RULE --> AGENT

    AGENT --> RPT
    TS --> RPT
    GRAPH --> RPT
    VEC --> RPT
    OBJ --> RPT
```

## Quy ước lưu trữ

- Raw IFC giữ nguyên trong `Dataset/BIM`.
- Canonical extraction lưu thành JSON/CSV/Parquet để app và agent dùng trực tiếp.
- Time-series lớn nên lưu Parquet hoặc bảng partitioned trong PostgreSQL / TimescaleDB.
- Quan hệ tòa nhà và truy vấn nhiều bước nên để trong Neo4j hoặc graph tables.
- Text ngữ nghĩa, policy, transcript, simulation summary nên embed vào `pgvector`.
- File nặng như IFC, video, EnergyPlus output, model artifacts nên để object storage.

## Mục tiêu cho AI chat

AI chat không hỏi trực tiếp một file BIM thô. Nó đi qua 4 lớp:

1. `PostgreSQL` lấy metrics hiện tại.
2. `Neo4j` lấy ngữ cảnh quan hệ tòa nhà.
3. `pgvector` lấy policy, notes, transcript, simulation summary.
4. `EnergyPlus` hoặc ML models lấy dự báo / what-if / validation.

Nhờ vậy chat có thể trả lời các câu như:

- zone nào đang tiêu thụ điện cao nhất;
- thiết bị nào phục vụ zone này;
- action nào an toàn để giảm load;
- tại sao simulation pass hoặc fail;
- metric nào đang vượt ngưỡng.
