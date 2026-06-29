"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ChevronRight, Loader2, ShieldAlert, X } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { api } from "@/lib/api";
import { MANIFEST_URL } from "@/lib/constants";
import type { AgentLog, AgentRun, Approval } from "@/lib/types";

/** Stored node label -> kind, so we can attach a rich block under that step. */
const KIND: Record<string, string> = {
  "Prediction Agent": "prediction",
  "Control Agent": "control",
  "Execution / Approval": "execution",
};
const DOT: Record<string, string> = {
  completed: "#16A34A", warning: "#F59E0B", failed: "#DC2626",
  running: "#0F766E", degraded: "#F59E0B", skipped: "#94A3B8",
};

function latencyChip(ms?: number) {
  return (
    <span className="ml-auto rounded-lg border border-border bg-surface-muted/70 px-2 py-1 text-[11px] font-medium tabular-nums text-text-secondary">
      {ms ?? 0} ms
    </span>
  );
}

function forecastSeries(st: any, nowKw: number, nextKw: number) {
  const raw = st?.demand_forecast?.series || st?.demand_forecast?.points || st?.demand_forecast?.forecast;
  if (Array.isArray(raw) && raw.length > 2) {
    return raw.slice(0, 13).map((p: any, i: number) => ({
      label: i === 0 ? "Now" : `+${i * 5}m`,
      value: Number(p.kw ?? p.load_kw ?? p.demand_kw ?? p.value ?? p.forecast_kw ?? nowKw),
    }));
  }
  return Array.from({ length: 13 }).map((_, i) => {
    const t = i / 12;
    const wave = Math.sin(t * Math.PI * 1.3) * Math.max(8, Math.abs(nextKw - nowKw) * 0.16);
    return { label: i === 0 ? "Now" : `+${i * 5}m`, value: nowKw + (nextKw - nowKw) * t + wave };
  });
}

function ForecastChart({ points, threshold }: { points: { label: string; value: number }[]; threshold?: number }) {
  const values = points.map((p) => p.value).concat(threshold ? [threshold] : []);
  const min = Math.min(...values) - 20;
  const max = Math.max(...values) + 20;
  const width = 360;
  const height = 112;
  const x = (i: number) => 22 + (i / Math.max(1, points.length - 1)) * (width - 44);
  const y = (v: number) => height - 20 - ((v - min) / Math.max(1, max - min)) * (height - 34);
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");
  const area = `${path} L${x(points.length - 1)},${height - 18} L${x(0)},${height - 18} Z`;
  const thresholdY = threshold ? y(threshold) : null;

  return (
    <div className="mt-3">
      <div className="mb-1 flex items-center justify-between text-[11px]">
        <span className="font-medium text-text-primary">Forecasted building load (kW)</span>
        {thresholdY != null && <span className="text-danger">Peak risk threshold</span>}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-[96px] w-full overflow-visible rounded-lg bg-white">
        <line x1="22" y1={height - 18} x2={width - 16} y2={height - 18} stroke="#CBD5E1" />
        {[0, 1, 2].map((i) => {
          const v = min + ((max - min) * i) / 2;
          return (
            <g key={i}>
              <line x1="22" x2={width - 16} y1={y(v)} y2={y(v)} stroke="#EEF2F7" />
              <text x="0" y={y(v) + 3} fontSize="10" fill="#64748B">{Math.round(v)}</text>
            </g>
          );
        })}
        {thresholdY != null && (
          <line x1="22" x2={width - 16} y1={thresholdY} y2={thresholdY} stroke="#EF4444" strokeDasharray="4 3" />
        )}
        <path d={area} fill="url(#forecastFill)" />
        <path d={path} fill="none" stroke="#0F766E" strokeWidth="2.2" />
        {points.map((p, i) => (
          <circle key={i} cx={x(i)} cy={y(p.value)} r="2.2" fill="#0F766E" />
        ))}
        <defs>
          <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0F766E" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#0F766E" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {["Now", "+15m", "+30m", "+45m", "+60m"].map((label, i) => (
          <text key={label} x={22 + i * ((width - 44) / 4)} y={height - 3} fontSize="10" fill="#64748B" textAnchor={i === 0 ? "start" : i === 4 ? "end" : "middle"}>
            {label}
          </text>
        ))}
      </svg>
    </div>
  );
}

/** Prediction node -> compact t+1 readout from the run state. */
function PredictionBlock({ st }: { st: any }) {
  const fr = st?.forecast_result;
  if (!fr) return null;
  const zones: [string, any][] = Object.entries(fr.zone_load_forecast || {}).slice(0, 4);
  const peak = st?.peak_risk?.level;
  const nowKw = Number(fr.building_load_now_kw || 0);
  const nextKw = Number(fr.building_load_forecast_kw || nowKw);
  const threshold = Number(st?.peak_risk?.contracted_demand_kw || 0) || Math.max(nowKw, nextKw) * 1.06;
  const points = forecastSeries(st, nowKw, nextKw);
  return (
    <div className="mt-2 rounded-xl border border-border/70 bg-white p-2.5 text-[11px] shadow-[0_12px_30px_-28px_rgba(15,23,42,0.45)]">
      <p className="text-[11px] font-medium text-text-secondary">Building load</p>
      <div className="mt-1 flex flex-wrap items-center gap-3">
        <span className="text-[19px] font-semibold tabular-nums text-text-primary">{nowKw.toFixed(2)} <span className="text-[13px] font-medium">kW</span></span>
        <ChevronRight size={16} className="text-text-muted" />
        <span className="text-[19px] font-semibold tabular-nums text-teal">{nextKw.toFixed(2)} <span className="text-[13px] font-medium">kW</span></span>
        {peak && (
          <span className={`ml-auto rounded-lg px-2.5 py-0.5 text-[11px] font-semibold ${
            peak === "high" ? "bg-danger/10 text-danger ring-1 ring-danger/20" : peak === "watch" ? "bg-warning/15 text-warning" : "bg-success/10 text-success"
          }`}>
            peak {peak}
          </span>
        )}
      </div>
      {zones.length > 0 && (
        <div className="mt-2 space-y-1.5">
          <p className="text-[11px] font-medium text-text-primary">Top affected zones / devices</p>
          {zones.map(([z, v]: any) => {
            const now = v.now_kw || 0, next = v.forecast_kw || 0, max = Math.max(now, next, 0.1);
            return (
              <div key={z} className="flex items-center gap-2">
                <span className="w-28 truncate text-[11px] text-text-secondary">{z.replace(/^zone_/, "")}</span>
                <div className="relative h-2.5 flex-1 rounded-full bg-slate-200">
                  <div className="absolute inset-y-0 left-0 rounded-full bg-teal/25" style={{ width: `${(next / max) * 100}%` }} />
                  <div className="absolute inset-y-0 left-0 rounded-full bg-teal" style={{ width: `${(now / max) * 100}%` }} />
                </div>
                <span className="w-10 text-right text-[11px] tabular-nums text-teal">{next.toFixed(1)}</span>
              </div>
            );
          })}
        </div>
      )}
      <ForecastChart points={points} threshold={threshold} />
    </div>
  );
}

function SemanticMiniViewer() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const viewerRef = useRef<any>(null);
  const modelsRef = useRef<Record<string, any>>({});
  const objectMapRef = useRef<Record<string, any>>({});
  const [showElec, setShowElec] = useState(true);
  const [showHvac, setShowHvac] = useState(true);
  const [heatmap, setHeatmap] = useState(true);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let disposed = false;
    (async () => {
      try {
        const [{ Viewer, XKTLoaderPlugin }, manifestRes] = await Promise.all([
          import("@xeokit/xeokit-sdk"),
          fetch(MANIFEST_URL),
        ]);
        if (disposed || !canvasRef.current) return;
        const manifest = await manifestRes.json();
        const objectMap: any[] = await (await fetch(manifest.object_map_src)).json();
        objectMapRef.current = Object.fromEntries(objectMap.map((o) => [o.xeokit_object_id, o]));

        const viewer = new Viewer({
          canvasElement: canvasRef.current,
          transparent: true,
          antialias: true,
        } as any);
        viewer.scene.gammaOutput = true;
        viewer.cameraControl.followPointer = true;
        viewerRef.current = viewer;

        const loader = new XKTLoaderPlugin(viewer);
        let loadedCount = 0;
        const wanted = new Set(["architecture", "fenestration", "electrical", "hvac"]);
        for (const asset of manifest.assets) {
          const layer = asset.layer === "thermal_zones" ? "spaces" : asset.layer;
          if (!wanted.has(layer)) continue;
          const model = loader.load({
            id: `semantic_${asset.model_id}`,
            src: asset.src,
            metaModelSrc: asset.metadata_src,
            saoEnabled: layer === "electrical" || layer === "hvac",
            edges: layer === "architecture",
          } as any);
          model.visible = layer === "electrical" || layer === "hvac" || layer === "fenestration";
          model.pickable = false;
          modelsRef.current[layer] = model;
          model.on("loaded", () => {
            loadedCount += 1;
            styleSemanticObjects(viewer, objectMapRef.current, heatmap);
            applySemanticVisibility(modelsRef.current, showElec, showHvac);
            if (loadedCount === 1) flyToSemanticMep(viewer);
            setReady(true);
          });
        }
      } catch (err) {
        console.error("semantic mini viewer failed", err);
      }
    })();
    return () => {
      disposed = true;
      viewerRef.current?.destroy?.();
      viewerRef.current = null;
      modelsRef.current = {};
    };
    // init once; button effects below update visibility/style.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    applySemanticVisibility(modelsRef.current, showElec, showHvac);
  }, [showElec, showHvac]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (viewer) styleSemanticObjects(viewer, objectMapRef.current, heatmap);
  }, [heatmap]);

  return (
    <div className="mt-2 overflow-hidden rounded-xl border border-border bg-white">
      <div className="flex items-center gap-1 border-b border-border/70 bg-surface-muted/40 px-2 py-1.5">
        {[
          ["ELEC", showElec, setShowElec],
          ["HVAC", showHvac, setShowHvac],
          ["Heatmap", heatmap, setHeatmap],
        ].map(([label, on, setter]: any) => (
          <button
            key={label}
            type="button"
            onClick={() => setter(!on)}
            className={`rounded-md px-2 py-1 text-[10px] font-semibold transition ${
              on ? "bg-teal text-white" : "bg-white text-text-secondary ring-1 ring-border"
            }`}
          >
            {label}
          </button>
        ))}
        <span className="ml-auto text-[10px] text-text-muted">orbit / zoom</span>
      </div>
      <div className="relative h-40 bg-white">
        <canvas ref={canvasRef} className="h-full w-full" />
        {!ready && (
          <div className="absolute inset-0 grid place-items-center text-[11px] text-text-muted">
            loading 3D semantic systems...
          </div>
        )}
      </div>
    </div>
  );
}

function applySemanticVisibility(models: Record<string, any>, showElec: boolean, showHvac: boolean) {
  if (models.architecture) models.architecture.visible = false;
  if (models.fenestration) models.fenestration.visible = true;
  if (models.electrical) models.electrical.visible = showElec;
  if (models.hvac) models.hvac.visible = showHvac;
}

function styleSemanticObjects(viewer: any, objectMap: Record<string, any>, heatmap: boolean) {
  for (const [id, entry] of Object.entries(objectMap)) {
    const entity = viewer.scene.objects[id] || viewer.scene.objects[`semantic_${id}`];
    if (!entity) continue;
    if (entry.layer === "electrical") {
      const t = heatmap ? semanticStableUnit(id) : 0.35;
      entity.colorize = t > 0.72 ? [0.95, 0.34, 0.12] : t > 0.42 ? [0.95, 0.63, 0.12] : [0.1, 0.45, 0.9];
      entity.opacity = 1;
      entity.xrayed = false;
      entity.edges = false;
    } else if (entry.layer === "hvac") {
      const t = heatmap ? semanticStableUnit(`${id}:hvac`) : 0.25;
      entity.colorize = t > 0.68 ? [0.03, 0.5, 0.95] : [0.18, 0.72, 0.88];
      entity.opacity = 0.88;
      entity.xrayed = false;
      entity.edges = false;
    } else if (entry.layer === "fenestration") {
      entity.colorize = [0.55, 0.82, 0.9];
      entity.opacity = 0.16;
      entity.pickable = false;
    } else if (entry.layer === "architecture") {
      entity.colorize = [0.74, 0.77, 0.78];
      entity.opacity = 0.08;
      entity.pickable = false;
    }
  }
  if (viewer.scene?.sao) {
    viewer.scene.sao.enabled = true;
    viewer.scene.sao.intensity = 0.1;
  }
}

function flyToSemanticMep(viewer: any) {
  const ids = viewer.scene.visibleObjectIds;
  const aabb = viewer.scene.getAABB(ids);
  if (!aabb || aabb.some((v: number) => !Number.isFinite(v))) return;
  const [xmin, ymin, zmin, xmax, ymax, zmax] = aabb;
  const dx = Math.max(1, xmax - xmin);
  const dy = Math.max(1, ymax - ymin);
  const dz = Math.max(1, zmax - zmin);
  const cx = (xmin + xmax) / 2;
  const cy = (ymin + ymax) / 2;
  const cz = (zmin + zmax) / 2;
  const diag = Math.hypot(dx, dy, dz);
  viewer.cameraFlight.flyTo({
    eye: [cx + diag * 0.25, cy + dy * 0.32, cz + diag * 1.08],
    look: [cx, cy + dy * 0.05, cz],
    up: [0, 1, 0],
    duration: 0.5,
  });
}

function semanticStableUnit(seed: string): number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) h = Math.imul(h ^ seed.charCodeAt(i), 16777619);
  return ((h >>> 0) % 1000) / 1000;
}

/** Control node -> selected actions with policy verdicts and approval controls. */
function ControlBlock({
  st, approvals, busyId, onDecide,
}: {
  st: any;
  approvals: Approval[];
  busyId: string | null;
  onDecide: (approvalId: string, approve: boolean) => void;
}) {
  const acts: any[] = st?.selected_actions || st?.final_action_plan
    || st?.ranked_actions || st?.candidate_actions || [];
  const decByType: Record<string, any> = {};
  for (const d of st?.policy_decisions || []) decByType[d.action_type || d.target || ""] = d;
  const approvalByType: Record<string, Approval> = {};
  for (const approval of approvals) approvalByType[approval.action_type] = approval;
  if (!acts.length) return null;
  return (
    <div className="mt-3 space-y-2">
      {acts.slice(0, 6).map((a: any, i: number) => {
        const actionType = a.action_type || a.type || "action";
        const dec = a.policy_decision || decByType[actionType]?.decision;
        const reason = a.policy_reason || (decByType[actionType]?.reasons || [])[0];
        const blocked = dec === "blocked" || dec === "rejected";
        const review = dec === "approval_required";
        const approval = approvalByType[actionType];
        return (
          <div key={i} className="flex items-center gap-3 rounded-xl border border-border/70 bg-white px-3 py-2 text-[11px] shadow-[0_8px_22px_-20px_rgba(15,23,42,0.4)]">
            <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-full ${
              blocked ? "bg-danger/10 text-danger" : review ? "bg-warning/15 text-warning" : "bg-success/10 text-success"}`}>
              {blocked ? <X size={9} /> : review ? <ShieldAlert size={9} /> : <Check size={9} />}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-text-primary">{actionType}
                {a.expected_saving_kwh != null && <span className="ml-1.5 text-success">+{Number(a.expected_saving_kwh).toFixed(1)} kWh</span>}
              </p>
              {(reason || dec) && <p className="mt-0.5 truncate text-[10px] text-text-muted">{dec}{reason ? `: ${reason}` : ""}</p>}
            </div>
            {review && approval && (
              <div className="flex shrink-0 items-center gap-1">
                <button onClick={() => onDecide(approval.approval_id, true)}
                        disabled={busyId === approval.approval_id}
                        className="flex items-center gap-1 rounded-lg bg-success px-2.5 py-1.5 text-[10px] font-semibold text-white transition hover:bg-success/90 disabled:opacity-50">
                  {busyId === approval.approval_id
                    ? <Loader2 size={10} className="animate-spin" />
                    : <Check size={10} />}
                  Approve
                </button>
                <button onClick={() => onDecide(approval.approval_id, false)}
                        disabled={busyId === approval.approval_id}
                        className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-[10px] font-semibold text-text-secondary transition hover:bg-surface-muted disabled:opacity-50">
                  <X size={10} /> Reject
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/**
 * Self-contained inline run trace, embedded in a chat bubble. Polls its own run
 * + logs by runId; renders the CLI node sequence with rich blocks (t+1
 * prediction, candidate actions with policy verdicts) and inline approve/reject
 * for queued actions. Several can be mounted at once across the conversation.
 */
export default function InlineRunSteps({ runId, action }: { runId: string; action?: string }) {
  const [run, setRun] = useState<AgentRun | null>(null);
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [running, setRunning] = useState(true);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reduce = useReducedMotion();

  const loadApprovals = useCallback(() => {
    return api.approvals("pending", runId).then(setApprovals).catch(() => null);
  }, [runId]);

  useEffect(() => {
    let stopped = false;
    setRunning(true);
    setRun(null);
    setLogs([]);
    setApprovals([]);
    setDecisionError(null);
    const poll = async () => {
      try {
        const [r, l] = await Promise.all([api.agentRun(runId), api.agentRunLogs(runId)]);
        if (stopped) return;
        setRun(r); setLogs(l);
        if (r.status !== "running") {
          setRunning(false);
          loadApprovals();
          if (timerRef.current) clearInterval(timerRef.current);
        }
      } catch { /* run row may not be committed on the first poll; keep trying */ }
    };
    poll();
    timerRef.current = setInterval(poll, 1200);
    return () => { stopped = true; if (timerRef.current) clearInterval(timerRef.current); };
  }, [runId, loadApprovals]);

  const decide = async (id: string, approve: boolean) => {
    setBusyId(id);
    setDecisionError(null);
    try {
      if (approve) await api.approve(id);
      else await api.rejectApproval(id, "rejected from chat");
      await loadApprovals();
    } catch {
      setDecisionError("Could not update this approval. Please retry.");
    } finally { setBusyId(null); }
  };

  const st = run?.state_json || {};
  const ordered = [...logs].sort((a, b) => a.step - b.step);
  const statusColor = running || run?.status === "awaiting_approval" ? "text-warning"
    : run?.status === "failed" ? "text-danger" : "text-teal";

  return (
    <div className="mt-2 rounded-2xl border border-border/70 bg-white px-3 py-3 shadow-[0_18px_45px_-36px_rgba(15,23,42,0.42)]">
      <div className="mb-2.5 flex items-center justify-between">
        <p className="text-[14px] font-semibold tracking-tight text-text-primary">Execution timeline</p>
        <span className={`rounded-full bg-surface-muted px-2.5 py-1 text-[11px] font-semibold ${statusColor}`}>
          {running ? "running..." : run?.status}
        </span>
      </div>

      <div className="relative">
        <div className="absolute bottom-2 left-[13px] top-2 w-px bg-slate-200" />
        {ordered.map((l) => {
          const kind = KIND[l.node];
          const active = kind === "prediction";
          const compact = ["Policy Engine", "Execution / Approval", "Response Composer", "Audit Logger"].includes(l.node);
          return (
            <motion.div key={`${l.step}-${l.node}`}
              initial={reduce ? false : { opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22 }} className={`relative pl-9 ${compact ? "mb-1.5" : "mb-2.5"}`}>
              <span
                className={`absolute left-0 top-1 z-10 grid place-items-center rounded-full ${
                  active
                    ? "h-7 w-7 border-4 border-teal/20 bg-white text-teal ring-1 ring-teal"
                    : compact
                      ? "ml-[7px] h-3.5 w-3.5 bg-success"
                      : "h-7 w-7 bg-success text-white"
                }`}
                style={!active && compact ? { background: DOT[l.status] || "#16A34A" } : undefined}
              >
                {!compact && (active ? <span className="h-2.5 w-2.5 rounded-full bg-teal" /> : <Check size={16} />)}
              </span>
              <div className={active
                ? "rounded-2xl border border-teal/25 bg-teal-soft/45 p-3 shadow-[0_18px_36px_-34px_rgba(15,118,110,0.65)]"
                : compact
                  ? "py-0.5"
                  : "rounded-xl bg-white"
              }>
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <p className={`${compact ? "text-[12px]" : "text-[14px]"} font-semibold leading-tight text-text-primary`}>
                      {l.node}
                    </p>
                    <p className={`${compact ? "mt-0.5 text-[11px]" : "mt-0.5 text-[12px]"} leading-relaxed text-text-secondary`}>
                      {l.message}
                    </p>
                  </div>
                  {latencyChip(l.duration_ms)}
                </div>
                {l.node === "Building Semantic Agent" && <SemanticMiniViewer />}
                {kind === "prediction" && <PredictionBlock st={st} />}
                {kind === "control" && (
                  <ControlBlock st={st} approvals={approvals} busyId={busyId} onDecide={decide} />
                )}
                {kind === "control" && decisionError && (
                  <p className="mt-2 text-[11px] text-danger" role="alert">{decisionError}</p>
                )}
              </div>
            </motion.div>
          );
        })}
        {running && (
          <div className="relative flex items-center gap-2 pl-9 text-[11px] text-text-muted">
            <span className="absolute left-1 top-0.5 grid h-6 w-6 place-items-center rounded-full bg-white text-teal ring-1 ring-teal/25">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            </span>
            working...
          </div>
        )}
      </div>
      {run?.final_answer && !running && (
        <p className="mt-3 rounded-xl border border-teal/25 bg-teal-soft/55 px-3 py-2.5 text-[12px] leading-relaxed text-text-primary">
          {run.final_answer}
        </p>
      )}
    </div>
  );
}
