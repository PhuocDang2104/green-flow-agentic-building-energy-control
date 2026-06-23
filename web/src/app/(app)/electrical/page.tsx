"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  Loader2, Send, Zap, Layers, Activity, ShieldCheck, PlugZap, ChevronDown, Check,
} from "lucide-react";
import PageHeader from "@/components/shell/PageHeader";
import KpiCard from "@/components/dashboard/KpiCard";
import { api } from "@/lib/api";
import { fmtKw, fmtKwh, titleCase } from "@/lib/format";
import type { ColorMode } from "@/components/electrical/ElectricalTwin3D";

const Twin3D = dynamic(() => import("@/components/electrical/ElectricalTwin3D"), {
  ssr: false,
  loading: () => (
    <div className="grid h-full w-full place-items-center bg-[#070d1a] text-slate-400">
      <Loader2 className="animate-spin" />
    </div>
  ),
});

const STATUS_TONE: Record<string, string> = {
  normal: "bg-success/15 text-success", warning: "bg-warning/15 text-warning",
  overload: "bg-danger/15 text-danger", rating_missing: "bg-surface-muted text-text-muted",
  unmapped: "bg-surface-muted text-text-muted",
};
function StatusPill({ status }: { status?: string }) {
  const tone = STATUS_TONE[status ?? ""] ?? "bg-surface-muted text-text-muted";
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${tone}`}>{titleCase(status) || "–"}</span>;
}
const f = (v: any) => (v == null || v === "" || isNaN(Number(v)) ? null : Number(v));

/* fade-in on scroll */
function Reveal({ children, className }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => e.isIntersecting && setShown(true), { threshold: 0.12 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref}
      className={`transition-all duration-700 ${shown ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"} ${className ?? ""}`}>
      {children}
    </div>
  );
}

function SectionTitle({ icon: Icon, title, sub }: { icon: any; title: string; sub?: string }) {
  return (
    <div className="mb-3 flex items-center gap-2.5">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-teal-soft text-teal"><Icon size={17} /></span>
      <div>
        <h2 className="text-[15px] font-semibold leading-tight">{title}</h2>
        {sub && <p className="text-[12px] text-text-muted">{sub}</p>}
      </div>
    </div>
  );
}

export default function ElectricalPage() {
  const [overview, setOverview] = useState<any | null>(null);
  const [boards, setBoards] = useState<any[]>([]);
  const [scene, setScene] = useState<any | null>(null);
  const [circuits, setCircuits] = useState<any[]>([]);
  const [phase, setPhase] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const [colorMode, setColorMode] = useState<ColorMode>("status");
  const [selected, setSelected] = useState<any | null>(null);
  const [layers, setLayers] = useState({ boards: true, links: true, floors: true });
  const [floorSel, setFloorSel] = useState<Set<string>>(new Set());
  const [zoneSel, setZoneSel] = useState<Set<string>>(new Set());
  const [loadSel, setLoadSel] = useState<Set<string>>(new Set(["lighting", "plug", "alarm"]));
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const [question, setQuestion] = useState("Which board supplies the highest load and is it overloaded?");
  const [ragBusy, setRagBusy] = useState(false);
  const [ragAnswer, setRagAnswer] = useState<any | null>(null);

  useEffect(() => {
    api.elecOverview().then(setOverview).catch((e) => setErr(String(e)));
    api.elecBoards().then((r) => setBoards(r.boards)).catch(() => null);
    api.elecScene(true, 700).then(setScene).catch(() => null);
    api.elecCircuits().then((r) => setCircuits(r.circuits)).catch(() => null);
    api.elecPhaseBalance().then((r) => setPhase(r.phase_balance)).catch(() => null);
  }, []);

  // filter options + defaults (all floors / zone-types shown until unticked)
  type Opt = { id: string; label: string };
  const floorOpts: Opt[] = useMemo(() => (scene?.floors ?? []).map((ff: any) =>
    ({ id: ff.floor_id as string, label: (ff.name || ff.floor_id).replace("floor_", "") })), [scene]);
  const zoneTypeOpts: Opt[] = useMemo(() => {
    const set = new Set<string>();
    (scene?.zones ?? []).forEach((z: any) => set.add(z.room_type || "unknown"));
    return Array.from(set).sort().map((k) => ({ id: k, label: titleCase(k) || "Unknown" }));
  }, [scene]);
  const loadOpts: Opt[] = [{ id: "lighting", label: "Lights" }, { id: "plug", label: "Outlets" }, { id: "alarm", label: "Alarms" }];

  useEffect(() => {
    if (!scene) return;
    setFloorSel(new Set((scene.floors ?? []).map((ff: any) => ff.floor_id)));
    setZoneSel(new Set((scene.zones ?? []).map((z: any) => z.room_type || "unknown")));
  }, [scene]);

  const toggleSet = (s: Set<string>, setter: (x: Set<string>) => void, id: string) => {
    const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); setter(n);
  };

  const ask = async () => {
    if (!question.trim()) return;
    setRagBusy(true); setRagAnswer(null);
    try { setRagAnswer(await api.elecRagAnswer(question)); }
    catch (e) { setRagAnswer({ answer: `Error: ${e}` }); }
    finally { setRagBusy(false); }
  };

  const split = overview?.energy_split_kwh ?? {};
  const vsum = overview?.validation_summary ?? {};
  const ranking: any[] = overview?.board_demand_ranking ?? [];
  const top = ranking[0];
  const totalKwh = (Object.values(split) as any[]).reduce((a, b) => a + (Number(b) || 0), 0);

  const floorGroups = useMemo(() => {
    const g: Record<string, any> = {};
    for (const b of boards) {
      const k = b.floor_id || "—";
      g[k] = g[k] || { floor_id: k, boards: 0, peak: 0, kwh: 0 };
      g[k].boards++; g[k].peak += f(b.peak_total_kw) ?? 0; g[k].kwh += f(b.total_kwh) ?? 0;
    }
    return Object.values(g).sort((a: any, b: any) => b.kwh - a.kwh);
  }, [boards]);

  const phaseIssues = phase.filter((p) => p.status && p.status !== "balanced" && p.status !== "single_phase");

  if (err) {
    return (
      <div className="pb-6">
        <PageHeader title="Electrical Distribution Twin"
          subtitle="Board-level digital twin over the EnergyPlus zone dataset." />
        <div className="card p-8 text-center text-[13px] text-text-muted">
          Electrical API not reachable — {err}.<br />
          Start the backend (port 8000) and run <code>python scripts/build_electrical_kg.py --all</code>.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-10">
      <PageHeader
        title="Electrical Distribution Twin"
        subtitle="3D digital twin of the LV distribution — boards, supply topology and EnergyPlus-simulated demand, every value provenance-tagged."
      />

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiCard title="Distribution Boards" value={`${overview?.boards ?? "–"}`}
          delta={`${overview?.zones ?? 0} zones · ${scene?.counts?.links ?? 0} supply links`} status="info" />
        <KpiCard title="Largest Board" value={fmtKw(top?.peak_total_kw)}
          delta={top ? (top.device_tag || top.board_id) : undefined} status="normal" />
        <KpiCard title="Annual Energy" value={fmtKwh(totalKwh)} delta="EnergyPlus-simulated" status="success" />
        <KpiCard title="Validation" value={vsum.fail === 0 ? "Pass" : `${vsum.fail ?? "?"} fail`}
          delta={`no double-count · ${vsum.manual_review_items ?? 0} review`}
          status={vsum.fail === 0 ? "success" : "danger"} />
      </div>

      {/* ===== 3D TWIN ===== */}
      <Reveal>
        <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
          <div className="card relative overflow-hidden p-0" style={{ height: 620 }}>
            {scene ? (
              <Twin3D scene={scene} colorMode={colorMode}
                show={layers} floors={floorSel} zoneTypes={zoneSel} loadKinds={loadSel}
                selectedId={selected?.id}
                focusBoard={selected?.type === "board" ? selected.id : null}
                onSelect={(e) => setSelected(e)} />
            ) : (
              <div className="grid h-full place-items-center bg-[#070d1a] text-slate-400">
                <Loader2 className="animate-spin" />
              </div>
            )}

            {/* color-mode + filter overlay */}
            <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-2 p-3">
              <div className="pointer-events-auto flex gap-1 rounded-lg bg-slate-900/80 p-1 backdrop-blur">
                {(["status", "feeder", "load"] as ColorMode[]).map((m) => (
                  <button key={m} onClick={() => setColorMode(m)}
                    className={`rounded px-2.5 py-1 text-[11px] font-medium capitalize transition ${
                      colorMode === m ? "bg-teal text-white" : "text-slate-300 hover:bg-white/10"}`}>
                    {m === "status" ? "Overload" : m === "feeder" ? "Feeder" : "Load heat"}
                  </button>
                ))}
              </div>
              <div className="pointer-events-auto flex flex-wrap items-start justify-end gap-1.5">
                <FilterMenu id="floors" label="Floors" icon={Layers}
                  options={floorOpts} selected={floorSel}
                  open={openMenu === "floors"} setOpen={(o) => setOpenMenu(o ? "floors" : null)}
                  onToggle={(id) => toggleSet(floorSel, setFloorSel, id)}
                  onAll={() => setFloorSel(new Set(floorOpts.map((o) => o.id)))}
                  onNone={() => setFloorSel(new Set())} />
                <FilterMenu id="zones" label="Zones" icon={Layers}
                  options={zoneTypeOpts} selected={zoneSel}
                  open={openMenu === "zones"} setOpen={(o) => setOpenMenu(o ? "zones" : null)}
                  onToggle={(id) => toggleSet(zoneSel, setZoneSel, id)}
                  onAll={() => setZoneSel(new Set(zoneTypeOpts.map((o) => o.id)))}
                  onNone={() => setZoneSel(new Set())} />
                <FilterMenu id="loads" label="Loads" icon={PlugZap}
                  options={loadOpts} selected={loadSel}
                  open={openMenu === "loads"} setOpen={(o) => setOpenMenu(o ? "loads" : null)}
                  onToggle={(id) => toggleSet(loadSel, setLoadSel, id)}
                  onAll={() => setLoadSel(new Set(loadOpts.map((o) => o.id)))}
                  onNone={() => setLoadSel(new Set())} />
                {(["boards", "links"] as (keyof typeof layers)[]).map((k) => (
                  <button key={k} onClick={() => setLayers((s) => ({ ...s, [k]: !s[k] }))}
                    className={`rounded bg-slate-900/80 px-2 py-1.5 text-[11px] capitalize backdrop-blur transition ${
                      layers[k] ? "text-white" : "text-slate-500"}`}>{k}</button>
                ))}
              </div>
            </div>

            {/* legend */}
            <div className="pointer-events-none absolute bottom-3 left-3 rounded-lg bg-slate-900/80 px-3 py-2 text-[11px] text-slate-200 backdrop-blur">
              {colorMode === "status" && (
                <div className="flex items-center gap-3">
                  <Lg c="#22c55e" t="Normal" /><Lg c="#eab308" t="Warning" />
                  <Lg c="#ef4444" t="Overload" /><Lg c="#94a3b8" t="No rating" />
                </div>
              )}
              {colorMode === "feeder" && <span>Each colour = one feeding board (distribution group)</span>}
              {colorMode === "load" && (
                <div className="flex items-center gap-2">
                  <span>Low</span>
                  <span className="h-2 w-24 rounded"
                    style={{ background: "linear-gradient(90deg,#1e3a8a,#0ea5e9,#22c55e,#eab308,#f97316,#ef4444)" }} />
                  <span>High</span>
                </div>
              )}
            </div>
            <div className="pointer-events-none absolute bottom-3 right-3 text-[10px] text-slate-500">
              drag to orbit · scroll to zoom · click a board/zone
            </div>
          </div>

          {/* inspector */}
          <Inspector selected={selected} boards={boards} />
        </div>
      </Reveal>

      {/* ===== BOARD REGISTER ===== */}
      <Reveal>
        <SectionTitle icon={Zap} title="Distribution board register"
          sub="Estimated demand = EnergyPlus zone energy × inferred allocation. Overload only where a real rated current exists." />
        <div className="card overflow-hidden p-0">
          <div className="max-h-[460px] overflow-auto">
            <table className="w-full text-[13px]">
              <thead className="sticky top-0 z-10 bg-surface-muted text-left text-text-muted">
                <tr>
                  {["Board", "Floor", "System", "V", "Ph", "Rated A", "Peak kW", "Peak A", "Load %", "Annual kWh", "Status"]
                    .map((h, i) => <th key={h} className={`px-3 py-2 font-medium ${i >= 3 && i <= 9 ? "text-right" : ""}`}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {boards.length === 0 && <tr><td colSpan={11} className="px-4 py-8 text-center text-text-muted">Loading…</td></tr>}
                {[...boards].sort((a, b) => (f(b.peak_total_kw) ?? 0) - (f(a.peak_total_kw) ?? 0)).map((b) => {
                  const sel = selected?.id === b.board_id;
                  return (
                    <tr key={b.board_id}
                      onClick={() => setSelected({ type: "board", id: b.board_id, tag: b.device_tag, ...b })}
                      className={`cursor-pointer border-t border-border transition hover:bg-surface-muted ${sel ? "bg-teal-soft" : ""}`}>
                      <td className="px-3 py-1.5 font-medium">{b.device_tag || b.board_id.slice(0, 10)}</td>
                      <td className="px-3 py-1.5 text-text-secondary">{(b.floor_id || "").replace("floor_", "")}</td>
                      <td className="px-3 py-1.5 text-text-secondary">{b.system_code || "–"}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">{f(b.voltage_v) ?? "–"}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">{f(b.phase_count) ?? "–"}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-text-muted">{f(b.rated_current_a) || "—"}</td>
                      <td className="px-3 py-1.5 text-right font-medium tabular-nums">{f(b.peak_total_kw)?.toFixed(1) ?? "–"}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">{f(b.estimated_peak_current_a)?.toFixed(0) ?? "–"}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">{f(b.loading_pct)?.toFixed(0) ?? "—"}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-text-secondary">
                        {f(b.total_kwh) != null ? Math.round(f(b.total_kwh)!).toLocaleString() : "–"}</td>
                      <td className="px-3 py-1.5"><StatusPill status={b.overload_status} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </Reveal>

      {/* ===== FLOOR + CIRCUITS + PHASE ===== */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Reveal>
          <SectionTitle icon={Layers} title="Per-floor distribution" sub="Boards, estimated peak and annual energy by storey." />
          <div className="card p-0">
            {floorGroups.map((g: any) => {
              const maxKwh = Math.max(...floorGroups.map((x: any) => x.kwh), 1);
              return (
                <div key={g.floor_id} className="border-b border-border px-4 py-2.5 last:border-0">
                  <div className="flex items-center justify-between text-[13px]">
                    <span className="font-medium">{g.floor_id.replace("floor_", "")}</span>
                    <span className="text-text-muted">{g.boards} boards · {fmtKw(g.peak)} peak</span>
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-muted">
                      <div className="h-full rounded-full bg-teal" style={{ width: `${(g.kwh / maxKwh) * 100}%` }} />
                    </div>
                    <span className="w-24 text-right text-[12px] tabular-nums text-text-secondary">{fmtKwh(g.kwh)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </Reveal>

        <Reveal>
          <SectionTitle icon={Activity} title="Circuits & phase balance"
            sub={`${circuits.length} circuits · ${phaseIssues.length} phase-imbalance flags`} />
          <div className="card space-y-3 p-4">
            <div className="grid grid-cols-3 gap-2 text-center">
              <Stat label="Circuits" value={circuits.length} />
              <Stat label="Pseudo (HVAC/plug)" value={circuits.filter((c) => c.kind === "pseudo").length} />
              <Stat label="3-phase boards" value={phase.filter((p) => f(p.phase_count) === 3).length} />
            </div>
            <div className="max-h-[300px] overflow-auto rounded-lg border border-border">
              <table className="w-full text-[12px]">
                <thead className="sticky top-0 bg-surface-muted text-left text-text-muted">
                  <tr><th className="px-3 py-1.5 font-medium">Board</th>
                    <th className="px-3 py-1.5 font-medium">Ph</th>
                    <th className="px-3 py-1.5 text-right font-medium">Imbalance %</th>
                    <th className="px-3 py-1.5 font-medium">Status</th></tr>
                </thead>
                <tbody>
                  {phase.slice(0, 60).map((p, i) => (
                    <tr key={i} className="border-t border-border">
                      <td className="px-3 py-1 font-medium">{(p.board_id || "").replace("board_", "").slice(0, 10)}</td>
                      <td className="px-3 py-1">{f(p.phase_count) ?? "–"}</td>
                      <td className="px-3 py-1 text-right tabular-nums">{f(p.phase_imbalance_pct)?.toFixed(1) ?? "—"}</td>
                      <td className="px-3 py-1 text-text-secondary">{titleCase(p.status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Reveal>
      </div>

      {/* ===== PROVENANCE ===== */}
      <Reveal>
        <SectionTitle icon={ShieldCheck} title="Data provenance & engineering caveats"
          sub="What is measured, simulated, IFC-derived or inferred — read before using these numbers." />
        <div className="card grid gap-3 p-5 text-[13px] md:grid-cols-2">
          {[
            ["EnergyPlus-simulated", "Zone lights / equipment / HVAC energy and all board demand totals come from the EnergyPlus gold dataset — not metered.", "bg-emerald-500"],
            ["IFC-derived", "Board / load-point geometry, voltage, phase and system codes are read from the enriched IFC (Finnish MEP psets).", "bg-sky-500"],
            ["Spatially / naming-inferred", "Board↔zone supply links use system-code + floor + nearest-board evidence with a confidence — this is an estimated graph, not as-wired.", "bg-amber-500"],
            ["Manual-review / rating-missing", "Most board rated currents are placeholder 0 in the IFC, so overload is reported as 'rating_missing' (demand ranking only).", "bg-slate-400"],
          ].map(([t, d, c]) => (
            <div key={t as string} className="flex gap-2.5">
              <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${c}`} />
              <div><p className="font-medium">{t}</p><p className="text-[12px] text-text-muted">{d}</p></div>
            </div>
          ))}
          <p className="md:col-span-2 rounded-lg bg-surface-muted px-3 py-2 text-[12px] text-text-muted">
            This is an engineering-reasoning + visualisation layer. It is <b>not</b> a certified protection-coordination
            or load-flow study. Energy is never double-counted: Σ board energy = Σ allocated zone energy (validated 0.0% mismatch).
          </p>
        </div>
      </Reveal>

      {/* ===== GRAPH-RAG ===== */}
      <Reveal>
        <SectionTitle icon={Send} title="Ask the electrical knowledge graph"
          sub="Graph-RAG over entity & relationship cards — answers state provenance and confidence." />
        <div className="card p-5">
          <div className="flex gap-2">
            <input value={question} onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ask()}
              placeholder="e.g. Which board feeds zone X, and is it overloaded?"
              className="min-w-0 flex-1 rounded-lg border border-border px-3 py-2 text-[13px] outline-none focus:border-teal" />
            <button onClick={ask} disabled={ragBusy} className="btn-primary shrink-0">
              {ragBusy ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
            </button>
          </div>
          {ragAnswer && (
            <div className="mt-3 space-y-2 rounded-lg bg-surface-muted p-3 text-[13px]">
              <p className="whitespace-pre-wrap leading-relaxed">{ragAnswer.answer}</p>
              {ragAnswer.sources?.length > 0 && (
                <p className="text-[11px] text-text-muted">sources: {ragAnswer.sources.map((s: any) => s.entity_id || s).join(", ")}</p>
              )}
            </div>
          )}
        </div>
      </Reveal>
    </div>
  );
}

/* --- dropdown tick-box filter --- */
function FilterMenu({ label, icon: Icon, options, selected, open, setOpen, onToggle, onAll, onNone }: {
  id: string; label: string; icon: any;
  options: { id: string; label: string }[]; selected: Set<string>;
  open: boolean; setOpen: (o: boolean) => void;
  onToggle: (id: string) => void; onAll: () => void; onNone: () => void;
}) {
  const count = options.filter((o) => selected.has(o.id)).length;
  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)}
        className={`flex items-center gap-1 rounded bg-slate-900/80 px-2 py-1.5 text-[11px] backdrop-blur transition ${
          count ? "text-white" : "text-slate-500"}`}>
        <Icon size={12} /> {label}
        <span className="rounded bg-white/15 px-1 text-[10px]">{count}/{options.length}</span>
        <ChevronDown size={12} className={open ? "rotate-180" : ""} />
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-1 w-44 rounded-lg border border-slate-700 bg-slate-900/95 p-1.5 shadow-xl backdrop-blur">
          <div className="mb-1 flex gap-1 px-1">
            <button onClick={onAll} className="flex-1 rounded bg-white/10 py-0.5 text-[10px] text-slate-200 hover:bg-white/20">All</button>
            <button onClick={onNone} className="flex-1 rounded bg-white/10 py-0.5 text-[10px] text-slate-200 hover:bg-white/20">None</button>
          </div>
          <div className="max-h-52 overflow-y-auto">
            {options.map((o) => {
              const on = selected.has(o.id);
              return (
                <button key={o.id} onClick={() => onToggle(o.id)}
                  className="flex w-full items-center gap-2 rounded px-1.5 py-1 text-left text-[11px] text-slate-200 hover:bg-white/10">
                  <span className={`grid h-3.5 w-3.5 shrink-0 place-items-center rounded border ${
                    on ? "border-teal bg-teal text-white" : "border-slate-600"}`}>
                    {on && <Check size={10} />}
                  </span>
                  <span className="truncate">{o.label}</span>
                </button>
              );
            })}
            {options.length === 0 && <p className="px-1.5 py-2 text-[11px] text-slate-500">none</p>}
          </div>
        </div>
      )}
    </div>
  );
}

/* --- small helpers --- */
function Lg({ c, t }: { c: string; t: string }) {
  return <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />{t}</span>;
}
function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded-lg bg-surface-muted py-2">
      <p className="text-[18px] font-semibold leading-tight">{value}</p>
      <p className="text-[11px] text-text-muted">{label}</p>
    </div>
  );
}

function Inspector({ selected, boards }: { selected: any | null; boards: any[] }) {
  if (!selected) {
    return (
      <div className="card flex flex-col items-center justify-center gap-2 p-6 text-center text-text-muted">
        <PlugZap size={26} className="text-text-muted/60" />
        <p className="text-[13px]">Click a board or zone in the 3D view to inspect it.</p>
        <p className="text-[11px]">Toggle <b>Overload / Feeder / Load heat</b> to recolour the model.</p>
      </div>
    );
  }
  const b = selected.type === "board"
    ? boards.find((x) => x.board_id === selected.id) ?? selected : selected;

  if (selected.type === "board") {
    return (
      <div className="card space-y-3 p-5 text-[13px]">
        <div className="flex items-center justify-between">
          <h3 className="text-[15px] font-semibold">{b.device_tag || b.tag || selected.id.slice(0, 10)}</h3>
          <StatusPill status={b.overload_status || selected.overload_status} />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Field label="System" value={b.system_name || b.system_code} />
          <Field label="Floor" value={(b.floor_id || "").replace("floor_", "")} />
          <Field label="Voltage" value={f(b.voltage_v) ? `${f(b.voltage_v)} V` : null} />
          <Field label="Phases" value={f(b.phase_count)} />
          <Field label="Rated current" value={f(b.rated_current_a) ? `${f(b.rated_current_a)} A` : "missing"} />
          <Field label="Peak current" value={f(b.estimated_peak_current_a) ? `${f(b.estimated_peak_current_a)?.toFixed(0)} A` : null} />
        </div>
        <div className="space-y-1 rounded-lg bg-surface-muted p-3">
          <Row k="Peak demand" v={fmtKw(f(b.peak_total_kw) ?? f(selected.peak_kw))} />
          <Row k="Annual energy" v={fmtKwh(f(b.total_kwh) ?? f(selected.total_kwh))} />
          <Row k="Lights" v={fmtKwh(f(b.lights_kwh))} />
          <Row k="Equipment" v={fmtKwh(f(b.equipment_kwh))} />
          <Row k="HVAC" v={fmtKwh(f(b.hvac_kwh))} />
        </div>
        <p className="text-[11px] text-text-muted">
          value_class: <b>spatially_inferred</b> · demand = EnergyPlus zone energy × inferred allocation.
        </p>
      </div>
    );
  }
  // zone
  return (
    <div className="card space-y-3 p-5 text-[13px]">
      <h3 className="text-[15px] font-semibold">{selected.name || selected.id}</h3>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Room type" value={titleCase(selected.room_type)} />
        <Field label="Floor" value={(selected.floor_id || "").replace("floor_", "")} />
        <Field label="Area" value={f(selected.area_m2) ? `${f(selected.area_m2)?.toFixed(0)} m²` : null} />
        <Field label="Peak" value={fmtKw(f(selected.peak_kw))} />
      </div>
      <div className="space-y-1 rounded-lg bg-surface-muted p-3">
        <Row k="Annual energy" v={fmtKwh(f(selected.total_kwh))} />
        <Row k="Lights" v={fmtKwh(f(selected.lights_kwh))} />
        <Row k="Equipment" v={fmtKwh(f(selected.equipment_kwh))} />
        <Row k="HVAC" v={fmtKwh(f(selected.hvac_kwh))} />
      </div>
      <p className="text-[11px] text-text-muted">
        Feeding board: <b>{(selected.feeder_board || "—").replace("board_", "").slice(0, 10)}</b> ·
        energy value_class: <b>energyplus_simulated</b>.
      </p>
    </div>
  );
}
function Field({ label, value }: { label: string; value: any }) {
  return <div><p className="text-[11px] uppercase tracking-wide text-text-muted">{label}</p><p className="font-medium">{value ?? "–"}</p></div>;
}
function Row({ k, v }: { k: string; v: string }) {
  return <div className="flex justify-between"><span className="text-text-muted">{k}</span><span className="font-medium">{v}</span></div>;
}
