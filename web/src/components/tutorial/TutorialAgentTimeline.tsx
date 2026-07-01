"use client";

import { motion, useReducedMotion } from "motion/react";
import { Check, ChevronRight, ShieldCheck } from "lucide-react";
import { SemanticMiniViewer } from "@/components/chatbot/InlineRunSteps";

/**
 * Deterministic, canned agent execution timeline shown on /agent-actions while a
 * tutorial "optimization preview" is active. It mirrors the real InlineRunSteps
 * look but never calls any backend/execution endpoint — it exists purely so the
 * tour can spotlight each agent step. Carries the agent data-tour-id anchors.
 */
export default function TutorialAgentTimeline() {
  const reduce = useReducedMotion();
  const nodes = [
    { key: "semantic", tour: "simulation-agent-block", title: "Building Semantic Agent",
      message: "Reading the current timestep — 308 zones, devices, abnormal findings and semantic-graph relationships." },
    { key: "prediction", tour: "prediction-agent-block", title: "Prediction Agent",
      message: "Forecasting demand, peak-load zones and comfort risk over the horizon." },
    { key: "control", tour: "control-agent-block", title: "Control Agent",
      message: "Building candidate control trajectories for the next 8 timesteps." },
    { key: "policy", tour: "policy-engine-block", title: "Simulation & Policy Engine",
      message: "Simulated the top-4 plans and checked risk constraints — 2 candidates passed." },
  ];

  return (
    <div
      data-tour-id="agent-execution-timeline"
      className="rounded-2xl border border-border/70 bg-white px-3 py-3 shadow-[0_18px_45px_-36px_rgba(15,23,42,0.42)]"
    >
      <div className="mb-2.5 flex items-center justify-between">
        <p className="text-[14px] font-semibold tracking-tight text-text-primary">Execution timeline</p>
        <span className="rounded-full bg-teal-soft px-2.5 py-1 text-[11px] font-semibold text-teal">
          preview
        </span>
      </div>

      <div className="relative">
        <div className="absolute bottom-2 left-[13px] top-2 w-px bg-slate-200" />
        {nodes.map((n, i) => (
          <motion.div
            key={n.key}
            data-tour-id={n.tour}
            initial={reduce ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.28, delay: reduce ? 0 : i * 0.28 }}
            className="relative mb-2.5 pl-9"
          >
            <span className="absolute left-0 top-1 z-10 grid h-7 w-7 place-items-center rounded-full bg-success text-white">
              <Check size={15} />
            </span>
            <div className="rounded-xl bg-white">
              <p className="text-[14px] font-semibold leading-tight text-text-primary">{n.title}</p>
              <p className="mt-0.5 text-[12px] leading-relaxed text-text-secondary">{n.message}</p>

              {n.key === "semantic" && <SemanticMiniViewer />}
              {n.key === "prediction" && <PredictionPreview />}
              {n.key === "control" && <ControlPreview />}
            </div>
          </motion.div>
        ))}
      </div>

      <ApprovalQueuePreview />
    </div>
  );
}

function PredictionPreview() {
  const zones = [
    { z: "Open Office 220", now: 34.2, next: 41.8 },
    { z: "Server Room 118", now: 22.6, next: 24.1 },
    { z: "Lobby 100", now: 11.4, next: 15.9 },
  ];
  return (
    <div className="mt-2 rounded-xl border border-border/70 bg-white p-2.5 text-[11px]">
      <p className="font-medium text-text-secondary">Building load</p>
      <div className="mt-1 flex flex-wrap items-center gap-3">
        <span className="text-[19px] font-semibold tabular-nums text-text-primary">182.4 <span className="text-[13px]">kW</span></span>
        <ChevronRight size={16} className="text-text-muted" />
        <span className="text-[19px] font-semibold tabular-nums text-teal">214.8 <span className="text-[13px]">kW</span></span>
        <span className="ml-auto rounded-lg bg-warning/15 px-2.5 py-0.5 text-[11px] font-semibold text-warning">peak watch</span>
      </div>
      <div className="mt-2 space-y-1.5">
        {zones.map((v) => {
          const max = Math.max(v.now, v.next, 0.1);
          return (
            <div key={v.z} className="flex items-center gap-2">
              <span className="w-28 truncate text-text-secondary">{v.z}</span>
              <div className="relative h-2.5 flex-1 rounded-full bg-slate-200">
                <div className="absolute inset-y-0 left-0 rounded-full bg-teal/25" style={{ width: `${(v.next / max) * 100}%` }} />
                <div className="absolute inset-y-0 left-0 rounded-full bg-teal" style={{ width: `${(v.now / max) * 100}%` }} />
              </div>
              <span className="w-10 text-right tabular-nums text-teal">{v.next.toFixed(1)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ControlPreview() {
  const acts = [
    { type: "lighting_reduction", saving: 6.4 },
    { type: "peak_load_reduction", saving: 12.1 },
    { type: "hvac_setback_light", saving: 8.7 },
  ];
  return (
    <div className="mt-3 space-y-2">
      {acts.map((a) => (
        <div key={a.type} className="flex items-center gap-3 rounded-xl border border-border/70 bg-white px-3 py-2 text-[11px]">
          <span className="grid h-5 w-5 place-items-center rounded-full bg-success/10 text-success"><Check size={9} /></span>
          <p className="font-semibold text-text-primary">{a.type}
            <span className="ml-1.5 text-success">+{a.saving.toFixed(1)} kWh</span>
          </p>
        </div>
      ))}
    </div>
  );
}

function ApprovalQueuePreview() {
  const queued = [
    { type: "peak_load_reduction", saving: 12.1, peak: 4.3, comfort: 0 },
    { type: "hvac_setback_light", saving: 8.7, peak: 2.1, comfort: 0 },
  ];
  return (
    <div data-tour-id="action-queue" className="mt-3 rounded-2xl border border-border/70 bg-surface-muted/30 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold text-text-primary">
        <ShieldCheck size={14} className="text-teal" /> Human approval queue
      </div>
      <div className="space-y-2">
        {queued.map((a, i) => (
          <div
            key={a.type}
            {...(i === 0 ? { "data-tour-id": "approval-card" } : {})}
            className="rounded-xl border border-border/70 bg-white px-3 py-2.5 text-[11px]"
          >
            <div className="flex items-center justify-between">
              <p className="font-semibold text-text-primary">{a.type}</p>
              <span className="rounded-lg bg-warning/15 px-2 py-0.5 text-[10px] font-semibold text-warning">Awaiting approval</span>
            </div>
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-text-secondary">
              <span>Est. saving <b className="text-success">+{a.saving.toFixed(1)} kWh</b></span>
              <span>Peak −{a.peak.toFixed(1)} kW</span>
              <span>Comfort impact {a.comfort} min</span>
            </div>
            <div className="mt-2 flex items-center gap-1.5">
              <button
                disabled
                title="Disabled in tutorial mode"
                className="flex cursor-not-allowed items-center gap-1 rounded-lg bg-success/60 px-2.5 py-1.5 text-[10px] font-semibold text-white"
              >
                <Check size={10} /> Approve
              </button>
              <button
                disabled
                title="Disabled in tutorial mode"
                className="cursor-not-allowed rounded-lg border border-border px-2.5 py-1.5 text-[10px] font-semibold text-text-muted"
              >
                Reject
              </button>
              <span className="ml-auto text-[10px] text-text-muted">preview only</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
