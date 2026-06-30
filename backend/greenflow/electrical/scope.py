"""Phase 4b — aggregate-zone child mapping for redistribution.

Outputs:

- mapping/zone_scope_child_weights.csv
- mapping/zone_scope_redistribution_report.json
"""

from __future__ import annotations

from . import canonical as C
from . import config as cfg
from ..zone_redistribution import (
    SCOPE_CHILD_WEIGHTS_CSV,
    SCOPE_REDISTRIBUTION_REPORT_JSON,
    build_child_weights,
)


def run() -> dict[str, int]:
    cfg.ensure_dirs()
    zones = C.read_rows_csv(cfg.OUT_MAPPING / "zones.csv")
    rows, summary = build_child_weights(zones)
    C.write_rows_csv(cfg.OUT_MAPPING / SCOPE_CHILD_WEIGHTS_CSV, rows)
    C.write_json(
        cfg.OUT_MAPPING / SCOPE_REDISTRIBUTION_REPORT_JSON,
        {"summary": summary.to_dict(), "notes": [
            "Weights are area-based among non-aggregate child candidates on the same storey/floor.",
            "Aggregate raw rows are not deleted here; callers opt into redistribution by feature flag.",
        ]},
    )
    return {
        "aggregates": summary.aggregate_count,
        "mapped_aggregates": summary.mapped_aggregate_count,
        "child_zones": summary.child_count,
        "weight_rows": summary.weight_rows,
        "unmapped_aggregates": len(summary.unmapped_aggregate_ids),
    }


if __name__ == "__main__":
    print(run())
