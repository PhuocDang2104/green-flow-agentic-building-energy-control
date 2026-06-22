"""Canonical IDs, the Entity/Edge model, and table IO (CSV / JSONL / Parquet).

Every node and edge in the GreenFlow building knowledge graph is created through
this module so IDs are stable and provenance fields are never forgotten.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# IDs
# ---------------------------------------------------------------------------
def sanitize(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", s or "")


def zone_id_from_guid(space_guid: str) -> str:
    """Match the gold table's zone_id = 'tz_' + sanitised IfcSpace GlobalId."""
    return "tz_" + sanitize(space_guid)


def floor_id(storey_name: str) -> str:
    return "floor_" + sanitize(storey_name).lower()


def board_id(guid: str) -> str:
    return "board_" + sanitize(guid)


def load_point_id(guid: str) -> str:
    return "lp_" + sanitize(guid)


def cable_id(guid: str) -> str:
    return "cab_" + sanitize(guid)


def device_id(guid: str) -> str:
    return "dev_" + sanitize(guid)


def circuit_id(key: str) -> str:
    return "circuit_" + sanitize(key)


def meter_id(name: str) -> str:
    return "meter_" + sanitize(name)


def eplus_zone_node_id(eplus_name: str) -> str:
    return "ez_" + sanitize(eplus_name)


def entity_id(kind: str, key: str) -> str:
    return f"{kind}_{sanitize(key)}"


# ---------------------------------------------------------------------------
# Entity / Edge
# ---------------------------------------------------------------------------
@dataclass
class Entity:
    entity_id: str
    entity_type: str
    name: str = ""
    label: str = ""
    source_system: str = ""
    source_file: str = ""
    value_class: str = ""          # provenance.ValueClass for the entity's existence
    confidence: str = ""
    notes: str = ""
    ifc_global_id: str | None = None
    eplus_name: str | None = None
    xeokit_object_id: str | None = None
    floor_id: str | None = None
    room_id: str | None = None
    zone_id: str | None = None
    x: float | None = None
    y: float | None = None
    z: float | None = None
    properties: dict[str, Any] = field(default_factory=dict)       # canonical typed props
    raw_properties: dict[str, Any] = field(default_factory=dict)   # raw IFC psets

    def coords(self) -> list[float] | None:
        if self.x is None and self.y is None and self.z is None:
            return None
        return [self.x, self.y, self.z]

    def to_node_row(self) -> dict[str, Any]:
        return {
            "node_id": self.entity_id,
            "node_type": self.entity_type,
            "name": self.name,
            "label": self.label or self.name,
            "source_system": self.source_system,
            "source_file": self.source_file,
            "ifc_global_id": self.ifc_global_id or "",
            "eplus_name": self.eplus_name or "",
            "xeokit_object_id": self.xeokit_object_id or "",
            "zone_id": self.zone_id or "",
            "floor_id": self.floor_id or "",
            "room_id": self.room_id or "",
            "coordinates": json.dumps(self.coords()) if self.coords() else "",
            "properties_json": json.dumps(self.properties, ensure_ascii=False, default=str),
            "value_class": self.value_class,
            "confidence": self.confidence,
            "notes": self.notes,
        }

    def to_node_json(self) -> dict[str, Any]:
        r = self.to_node_row()
        r["coordinates"] = self.coords()
        r["properties"] = self.properties
        r.pop("properties_json", None)
        return r

    def to_entity_row(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "name": self.name,
            "source_system": self.source_system,
            "source_file": self.source_file,
            "ifc_global_id": self.ifc_global_id or "",
            "eplus_name": self.eplus_name or "",
            "xeokit_object_id": self.xeokit_object_id or "",
            "floor_id": self.floor_id or "",
            "room_id": self.room_id or "",
            "zone_id": self.zone_id or "",
            "x": self.x, "y": self.y, "z": self.z,
            "raw_properties_json": json.dumps(self.raw_properties, ensure_ascii=False, default=str),
            "value_class": self.value_class,
            "confidence": self.confidence,
            "notes": self.notes,
        }


@dataclass
class Edge:
    source_node_id: str
    target_node_id: str
    relationship_type: str
    direction: str = "directed"
    weight: float | None = None
    source: str = ""               # provenance.SourceSystem / method origin
    method: str = ""
    confidence: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    @property
    def edge_id(self) -> str:
        w = "" if self.weight is None else f"_{self.weight:.4f}"
        return sanitize(f"{self.source_node_id}__{self.relationship_type}__{self.target_node_id}{w}")

    def to_row(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "relationship_type": self.relationship_type,
            "direction": self.direction,
            "weight": self.weight,
            "source": self.source,
            "method": self.method,
            "confidence": self.confidence,
            "evidence_json": json.dumps(self.evidence, ensure_ascii=False, default=str),
            "notes": self.notes,
        }

    def to_json(self) -> dict[str, Any]:
        r = self.to_row()
        r["evidence"] = self.evidence
        r.pop("evidence_json", None)
        return r


# ---------------------------------------------------------------------------
# table IO
# ---------------------------------------------------------------------------
def write_rows_csv(path: str | Path, rows: list[dict[str, Any]],
                   fieldnames: list[str] | None = None) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        seen: set[str] = set()
        for r in rows:
            for k in r:
                if k not in seen:
                    seen.add(k)
                    fieldnames.append(k)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fieldnames})
    return len(rows)


def read_rows_csv(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def write_jsonl(path: str | Path, objs: Iterable[dict[str, Any]]) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for o in objs:
            fh.write(json.dumps(o, ensure_ascii=False, default=str))
            fh.write("\n")
            n += 1
    return n


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def write_parquet(path: str | Path, rows: list[dict[str, Any]]) -> int:
    import pyarrow as pa
    import pyarrow.parquet as pq
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows) if rows else pa.table({})
    pq.write_table(table, str(path))
    return len(rows)


def write_json(path: str | Path, obj: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
