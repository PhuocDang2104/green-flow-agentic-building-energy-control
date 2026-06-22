"""Provenance vocabulary: how every value and relationship is justified.

Two orthogonal axes:
- ``ValueClass`` — how a *value* was obtained (measured / simulated / IFC-derived
  / inferred / assumed / needs-review). The graph-RAG answer policy requires every
  numeric to be labelled with one of these.
- ``Confidence`` — how strong a *relationship/mapping* is (exact … manual_review).

Plus three record types that themselves become graph entities so assumptions and
open issues are first-class and queryable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class ValueClass:
    MEASURED = "measured"
    ENERGYPLUS_SIMULATED = "energyplus_simulated"
    IFC_DERIVED = "ifc_derived"
    SPATIALLY_INFERRED = "spatially_inferred"
    NAMING_INFERRED = "naming_inferred"
    ASSUMPTION_BASED = "assumption_based"
    MANUAL_REVIEW = "manual_review"


class Confidence:
    EXACT = "exact"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MANUAL_REVIEW = "manual_review"


class SourceSystem:
    IFC_ELE = "ifc_ele"
    IFC_ARCH = "ifc_arch"
    IFC_HVAC = "ifc_hvac"
    IFC_STRUCT = "ifc_struct"
    ENERGYPLUS = "energyplus"
    GREENFLOW_POST = "greenflow_postprocess"
    OPENMETEO = "openmeteo"
    DERIVED = "derived"


@dataclass
class Assumption:
    assumption_id: str
    subject_id: str          # entity/edge this assumption applies to
    parameter: str
    assumed_value: Any
    rationale: str
    value_class: str = ValueClass.ASSUMPTION_BASED

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationIssue:
    issue_id: str
    check: str
    severity: str            # info | warning | error
    subject_id: str
    detail: str
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ManualReviewItem:
    item_id: str
    subject_id: str
    subject_type: str
    reason: str
    recommended_action: str
    confidence: str = Confidence.MANUAL_REVIEW
    fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d
