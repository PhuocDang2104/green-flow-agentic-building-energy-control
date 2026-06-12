"use client";

import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";

export default function PolicySummaryCard() {
  const [policy, setPolicy] = useState<any>(null);
  useEffect(() => {
    api.policyConfig().then(setPolicy).catch(() => null);
  }, []);
  const auto = policy?.auto_actions;
  return (
    <div className="card px-5 py-4">
      <h3 className="flex items-center gap-1.5 text-sm font-semibold">
        <ShieldCheck size={15} className="text-teal" /> Policy guardrails
      </h3>
      {auto ? (
        <ul className="mt-3 space-y-1.5 text-[13px] text-text-secondary">
          <li>Auto-actions: <b className="text-text-primary">{auto.enabled ? "enabled" : "disabled"}</b></li>
          <li>Max setpoint delta: <b className="text-text-primary">{auto.max_setpoint_delta_c}°C</b></li>
          <li>Min occupancy confidence: <b className="text-text-primary">{auto.min_occupancy_confidence}</b></li>
          <li>Max comfort risk after: <b className="text-text-primary">{auto.max_comfort_risk_after}</b></li>
          <li>Blocked zones: <b className="text-text-primary">{auto.blocked_zone_types?.join(", ")}</b></li>
          <li>Approval required: <b className="text-text-primary">
            {policy.approval_required_actions?.slice(0, 3).join(", ")}…</b></li>
        </ul>
      ) : (
        <p className="mt-3 text-[13px] text-text-muted">Loading policy…</p>
      )}
    </div>
  );
}
