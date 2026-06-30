"""Classify IFC spaces for energy aggregation.

Only explicit aggregate-area names are excluded automatically. Geometric
heuristics are review signals because large rooms can still be valid thermal
zones.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


ATOMIC = "atomic_energy_zone"
AGGREGATE = "aggregate_context"
REVIEW = "review_required"

_AGGREGATE_NAME = re.compile(
    r"(?:^|:)\s*(?:VOLUME\s*/|GFA(?:\s|$)|HEATED\s+NETAREA|NETAREA|GROSS(?:\s|$))",
    re.IGNORECASE,
)
_CONTEXT_NAME = re.compile(
    r"(?:TURNING\s+FREE\s+SPACE|SHAFT|CHASE|VENT)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EnergyScope:
    scope: str
    counts_toward_energy: bool
    confidence: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "energy_scope": self.scope,
            "counts_toward_energy": self.counts_toward_energy,
            "scope_confidence": self.confidence,
            "scope_reason": self.reason,
        }


def classify_energy_scope(
    name: str | None,
    *,
    area_m2: float | None = None,
    volume_m3: float | None = None,
    height_m: float | None = None,
) -> EnergyScope:
    label = (name or "").strip()
    if _AGGREGATE_NAME.search(label):
        return EnergyScope(AGGREGATE, False, "high", "explicit_aggregate_name")

    reasons = []
    if _CONTEXT_NAME.search(label):
        reasons.append("context_space_name")
    if area_m2 is not None and area_m2 >= 1500:
        reasons.append("large_area")
    inferred_height = height_m
    if inferred_height is None and area_m2 and volume_m3:
        inferred_height = volume_m3 / area_m2
    if inferred_height is not None and inferred_height > 5:
        reasons.append("unusual_height")
    if reasons:
        return EnergyScope(REVIEW, True, "low", ",".join(reasons))
    return EnergyScope(ATOMIC, True, "high", "default_atomic_space")


def counts_toward_energy(value: object) -> bool:
    """Parse CSV/DB boolean values without treating the string 'False' as true."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def dedup_enabled() -> bool:
    return energy_scope_mode() in {"dedup", "redistribute"}


def redistribution_enabled() -> bool:
    return energy_scope_mode() == "redistribute"


def energy_scope_mode() -> str:
    from .config import get_settings

    return get_settings().greenflow_energy_scope_mode.strip().lower()


def telemetry_scope_mode() -> str:
    from .config import get_settings

    return get_settings().greenflow_telemetry_scope_mode.strip().lower()


def effective_counts_toward_energy(value: object) -> bool:
    return counts_toward_energy(value) if dedup_enabled() else True


def counted_zone_sql(alias: str = "z") -> str:
    return f"{alias}.counts_toward_energy" if dedup_enabled() else "TRUE"
