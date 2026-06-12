"use client";

import { useState } from "react";
import { fmtKwh, titleCase } from "@/lib/format";
import StatusPill from "@/components/shared/StatusPill";
import EmptyState from "@/components/shared/EmptyState";
import type { ActionItem, Approval } from "@/lib/types";

const TABS = [
  { id: "pending", label: "Pending approval" },
  { id: "executed", label: "Executed" },
  { id: "blocked", label: "Blocked" },
  { id: "proposed", label: "Recommended" },
] as const;

export default function ActionQueue({
  actions, approvals, onApprove, onReject, busyId,
}: {
  actions: ActionItem[];
  approvals: Approval[];
  onApprove: (approvalId: string) => void;
  onReject: (approvalId: string) => void;
  busyId: string | null;
}) {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("pending");

  const filtered = actions.filter((a) =>
    tab === "pending" ? a.status === "pending_approval"
      : tab === "executed" ? a.status === "executed"
      : tab === "blocked" ? ["blocked", "rejected"].includes(a.status)
      : a.status === "proposed");

  const approvalByAction = Object.fromEntries(
    approvals.map((ap) => [ap.action_id, ap]));

  return (
    <div className="card flex h-full flex-col">
      <div className="border-b border-border px-5 py-3">
        <h3 className="text-sm font-semibold">Action queue</h3>
        <div className="mt-2 flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition
                ${tab === t.id ? "bg-teal text-white" : "text-text-secondary hover:bg-surface-muted"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
        {filtered.length === 0 && (
          <EmptyState title={`No ${tab.replaceAll("_", " ")} actions`} />
        )}
        {filtered.map((a) => {
          const approval = approvalByAction[a.id];
          return (
            <div key={a.id} className="rounded-2xl border border-border/80 p-4">
              <div className="flex items-start justify-between gap-2">
                <p className="text-[14px] font-semibold">{titleCase(a.action_type)}</p>
                <StatusPill status={a.policy_decision || a.status} />
              </div>
              {a.reason && (
                <p className="mt-1 text-[13px] text-text-secondary">{a.reason}</p>
              )}
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-muted">
                <span>Saving <b className="text-text-primary">{fmtKwh(a.expected_saving_kwh)}</b></span>
                {a.expected_peak_reduction_kw != null && (
                  <span>Peak <b className="text-text-primary">-{a.expected_peak_reduction_kw} kW</b></span>
                )}
                {a.comfort_risk_after != null && (
                  <span>Comfort risk after <b className="text-text-primary">{a.comfort_risk_after}</b></span>
                )}
              </div>
              {(a.policy_reasons?.length ?? 0) > 0 && (
                <p className="mt-1.5 text-[11px] text-text-muted">
                  Policy: {a.policy_reasons!.join("; ")}
                </p>
              )}
              {a.status === "pending_approval" && approval && (
                <div className="mt-3 flex gap-2">
                  <button
                    className="btn-primary !px-3 !py-1.5 text-xs"
                    disabled={busyId === approval.approval_id}
                    onClick={() => onApprove(approval.approval_id)}
                  >
                    Approve
                  </button>
                  <button
                    className="btn-danger !px-3 !py-1.5 text-xs"
                    disabled={busyId === approval.approval_id}
                    onClick={() => onReject(approval.approval_id)}
                  >
                    Reject
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
