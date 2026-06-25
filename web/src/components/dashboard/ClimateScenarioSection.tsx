"use client";

import { useMemo, useState, type ReactNode } from "react";
import { CloudSun, RotateCcw, Save, Play, Loader2, Wind } from "lucide-react";
import { api } from "@/lib/api";

type Scenario = {
  outdoor_temp_c: number;
  humidity_pct: number;
  solar_multiplier: number;
  wind_speed_ms: number;
  wind_direction_deg: number;
};

const BASELINE: Scenario = {
  outdoor_temp_c: 33.0,
  humidity_pct: 65,
  solar_multiplier: 1.0,
  wind_speed_ms: 2.5,
  wind_direction_deg: 135,
};

const CLIMATE_MAP_IMAGE = "/assets/landing/hanoi_climate_map_google_3d.png";
const WIND_POINTS = [
  { left: 18, top: 28 },
  { left: 76, top: 30 },
  { left: 25, top: 76 },
  { left: 72, top: 72 },
  { left: 50, top: 82 },
];
const DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
const dirLabel = (deg: number) => DIRS[Math.round(((deg % 360) / 45)) % 8];

function heatIndexC(tC: number, rh: number): number {
  const T = tC * 9 / 5 + 32;
  if (T < 80) return tC;
  let HI =
    -42.379 + 2.04901523 * T + 10.14333127 * rh - 0.22475541 * T * rh -
    6.83783e-3 * T * T - 5.481717e-2 * rh * rh + 1.22874e-3 * T * T * rh +
    8.5282e-4 * T * rh * rh - 1.99e-6 * T * T * rh * rh;
  if (rh < 13 && T >= 80 && T <= 112) {
    HI -= ((13 - rh) / 4) * Math.sqrt((17 - Math.abs(T - 95)) / 17);
  }
  return (HI - 32) * 5 / 9;
}

type Band = { key: string; label: string; color: string; fill: string };
function band(hiC: number): Band {
  if (hiC < 30) return { key: "normal", label: "Normal", color: "#16a34a", fill: "#22c55e" };
  if (hiC < 37) return { key: "warm", label: "Warm", color: "#d97706", fill: "#f59e0b" };
  if (hiC < 41) return { key: "stress", label: "Heat stress", color: "#ea580c", fill: "#f97316" };
  return { key: "extreme", label: "Extreme heat", color: "#b91c1c", fill: "#ef4444" };
}

function coolingStressFactor(s: Scenario): number {
  const f =
    1 + 0.03 * (s.outdoor_temp_c - BASELINE.outdoor_temp_c)
      + 0.004 * (s.humidity_pct - BASELINE.humidity_pct)
      + 0.55 * (s.solar_multiplier - 1)
      - 0.035 * (s.wind_speed_ms - BASELINE.wind_speed_ms);
  return Math.max(1, f);
}

function Badge({ label, value, tone = "neutral" }: { label: string; value: string; tone?: string }) {
  const t: Record<string, string> = {
    neutral: "bg-white/90 text-slate-700",
    warn: "bg-amber-500/90 text-white",
    hot: "bg-orange-500/90 text-white",
    danger: "bg-red-600/90 text-white",
  };
  return (
    <div className={`rounded-xl px-2.5 py-1.5 text-[11px] shadow-floating backdrop-blur ${t[tone]}`}>
      <span className="opacity-70">{label}</span>
      <div className="text-[13px] font-semibold leading-tight">{value}</div>
    </div>
  );
}

function Row({ label, value, status, statusTone, children }: {
  label: string;
  value: string;
  status: string;
  statusTone: string;
  children: ReactNode;
}) {
  const tone: Record<string, string> = {
    normal: "bg-success/15 text-success",
    warn: "bg-warning/15 text-warning",
    hot: "bg-orange-500/15 text-orange-600",
    danger: "bg-danger/15 text-danger",
  };
  return (
    <tr className="border-t border-border">
      <td className="px-3 py-2 text-[13px] font-medium">{label}</td>
      <td className="px-3 py-2 text-right text-[13px] tabular-nums">{value}</td>
      <td className="w-[150px] px-3 py-2">{children}</td>
      <td className="px-3 py-2">
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${tone[statusTone]}`}>{status}</span>
      </td>
    </tr>
  );
}

export default function ClimateScenarioSection() {
  const [s, setS] = useState<Scenario>({
    ...BASELINE,
    outdoor_temp_c: 35.2,
    humidity_pct: 68,
    solar_multiplier: 1.15,
    wind_speed_ms: 1.8,
  });
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [result, setResult] = useState<any | null>(null);

  const set = (k: keyof Scenario, v: number) => {
    setS((p) => ({ ...p, [k]: v }));
    setSaved(false);
    setResult(null);
  };

  const hi = useMemo(() => heatIndexC(s.outdoor_temp_c, s.humidity_pct), [s]);
  const b = band(hi);
  const csf = coolingStressFactor(s);
  const upliftPct = Math.round((csf - 1) * 100);
  const reliefTone = s.wind_speed_ms >= 3 ? "normal" : s.wind_speed_ms >= 1.5 ? "warn" : "danger";
  const reliefLabel = s.wind_speed_ms >= 3 ? "Good relief" : s.wind_speed_ms >= 1.5 ? "Low relief" : "Stagnant";

  const tempTone = s.outdoor_temp_c >= 38 ? "danger" : s.outdoor_temp_c >= 34 ? "hot" : s.outdoor_temp_c >= 31 ? "warn" : "normal";
  const humTone = s.humidity_pct >= 80 ? "danger" : s.humidity_pct >= 65 ? "warn" : "normal";
  const solarTone = s.solar_multiplier >= 1.2 ? "danger" : s.solar_multiplier >= 1.05 ? "hot" : "normal";
  const heatOpacity = Math.min(0.42, 0.12 + Math.max(0, hi - 30) / 36);
  const windRad = ((s.wind_direction_deg + 180) % 360) * Math.PI / 180;
  const arrowLen = 14 + Math.min(40, s.wind_speed_ms * 12);
  const windArrowDeg = Math.atan2(Math.sin(windRad), Math.cos(windRad)) * 180 / Math.PI;

  const payload = {
    scenario_id: "el_nino_heat_stress",
    location: "Hanoi",
    outdoor_temp_delta_c: +(s.outdoor_temp_c - BASELINE.outdoor_temp_c).toFixed(2),
    relative_humidity_delta_pct: s.humidity_pct - BASELINE.humidity_pct,
    solar_multiplier: s.solar_multiplier,
    wind_speed_ms: s.wind_speed_ms,
    wind_direction_deg: s.wind_direction_deg,
    cooling_stress_factor: +csf.toFixed(3),
    comfort_drift_c: +(Math.max(0, hi - 30) * 0.35).toFixed(2),
  };

  const reset = () => {
    setS({ ...BASELINE });
    setSaved(false);
    setResult(null);
  };
  const save = async () => {
    try { await api.saveScenario(payload); } catch { /* best-effort */ }
    setSaved(true);
  };
  const run = async () => {
    setBusy(true);
    setResult(null);
    try {
      setResult(await api.runIdfSimulation(payload));
    } catch (e: any) {
      setResult({
        surrogate: true,
        hvac_load_uplift_pct: upliftPct,
        peak_demand_change_kw: +(upliftPct * 0.66).toFixed(1),
        comfort_risk_zones: Math.min(14, Math.round(Math.max(0, hi - 30) * 1.2)),
        zone_temp_drift_c: payload.comfort_drift_c,
        ventilation_relief_level: reliefLabel,
        note: `offline estimate (${e})`,
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="mt-4">
      <div className="mb-3 flex items-center gap-2">
        <CloudSun size={16} className="text-teal" />
        <h2 className="text-sm font-semibold">Building Climate Monitor</h2>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-[11px] text-text-muted">
                  {["Scenario Parameter", "Current", "Control", "Status"].map((h) => (
                    <th key={h} className="px-3 py-2 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <Row label="Outdoor Temperature" value={`${s.outdoor_temp_c.toFixed(1)} C`} status={tempTone === "normal" ? "Mild" : tempTone === "warn" ? "Warm" : "High"} statusTone={tempTone}>
                  <input type="range" min={28} max={45} step={0.1} value={s.outdoor_temp_c}
                    onChange={(e) => set("outdoor_temp_c", +e.target.value)} className="w-full accent-orange-500" />
                </Row>
                <Row label="Relative Humidity" value={`${s.humidity_pct}%`} status={humTone === "normal" ? "Normal" : humTone === "warn" ? "Humid" : "Very humid"} statusTone={humTone}>
                  <input type="range" min={40} max={95} step={1} value={s.humidity_pct}
                    onChange={(e) => set("humidity_pct", +e.target.value)} className="w-full accent-sky-500" />
                </Row>
                <Row label="Solar Multiplier" value={`${s.solar_multiplier.toFixed(2)}x`} status={solarTone === "normal" ? "Normal" : solarTone === "hot" ? "High gain" : "Extreme"} statusTone={solarTone}>
                  <input type="range" min={0.8} max={1.5} step={0.01} value={s.solar_multiplier}
                    onChange={(e) => set("solar_multiplier", +e.target.value)} className="w-full accent-amber-500" />
                </Row>
                <Row label="Wind Speed" value={`${s.wind_speed_ms.toFixed(1)} m/s`} status={reliefLabel} statusTone={reliefTone}>
                  <input type="range" min={0} max={8} step={0.1} value={s.wind_speed_ms}
                    onChange={(e) => set("wind_speed_ms", +e.target.value)} className="w-full accent-teal" />
                </Row>
                <Row label="Wind Direction" value={`${dirLabel(s.wind_direction_deg)} (${s.wind_direction_deg} deg)`} status="Direction" statusTone="normal">
                  <input type="range" min={0} max={315} step={45} value={s.wind_direction_deg}
                    onChange={(e) => set("wind_direction_deg", +e.target.value)} className="w-full accent-slate-400" />
                </Row>
                <Row label="Cooling Stress" value={`+${upliftPct}%`} status={upliftPct >= 20 ? "Above baseline" : upliftPct >= 8 ? "Elevated" : "Normal"}
                  statusTone={upliftPct >= 20 ? "danger" : upliftPct >= 8 ? "warn" : "normal"}>
                  <span className="text-[11px] text-text-muted">Auto-estimated</span>
                </Row>
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center gap-2 border-t border-border px-3 py-3">
            <button onClick={reset} className="btn-secondary text-[13px]"><RotateCcw size={14} /> Reset Baseline</button>
            <button onClick={save} className="btn-secondary text-[13px]"><Save size={14} /> {saved ? "Saved" : "Save Scenario"}</button>
            <button onClick={run} disabled={busy} className="btn-primary text-[13px]">
              {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run IDF Simulation
            </button>
          </div>

          {result && (
            <div className="border-t border-border px-3 py-3">
              <p className="mb-2 text-[12px] font-semibold text-text-secondary">
                Simulated building response {result.surrogate ? "- surrogate estimate" : ""}
              </p>
              <div className="grid grid-cols-2 gap-2 text-[12px] md:grid-cols-3">
                <Out k="HVAC load uplift" v={`+${result.hvac_load_uplift_pct}%`} />
                <Out k="Peak demand change" v={`+${result.peak_demand_change_kw} kW`} />
                <Out k="Comfort-risk zones" v={`${result.comfort_risk_zones}`} />
                <Out k="Zone temp drift" v={`+${result.zone_temp_drift_c} C`} />
                <Out k="Ventilation relief" v={`${result.ventilation_relief_level}`} />
              </div>
            </div>
          )}
        </div>

        <div className="card overflow-hidden p-0">
          <div className="flex items-center justify-between px-4 py-2.5">
            <h3 className="text-[14px] font-semibold">Hanoi Climate Impact Map</h3>
            <span className="rounded-full px-2 py-0.5 text-[11px] font-medium" style={{ background: `${b.color}22`, color: b.color }}>
              {b.label}
            </span>
          </div>

          <div className="relative h-[340px] w-full overflow-hidden bg-slate-950">
            <div
              className="absolute inset-0 bg-cover bg-center"
              style={{
                backgroundImage: `url(${CLIMATE_MAP_IMAGE})`,
              }}
            />
            <div className="absolute inset-0 bg-gradient-to-b from-black/10 via-transparent to-black/35" />
            <div
              className="absolute inset-0 mix-blend-multiply"
              style={{
                opacity: heatOpacity,
                background:
                  `radial-gradient(circle at 55% 48%, ${b.fill} 0 12%, transparent 42%), radial-gradient(circle at 36% 66%, ${b.fill} 0 9%, transparent 33%)`,
              }}
            />
            {WIND_POINTS.map((point, index) => (
              <div
                key={`wind-${index}`}
                className="pointer-events-none absolute z-10 h-0.5 origin-center rounded-full bg-white/80 shadow-[0_0_10px_rgba(255,255,255,0.72)]"
                style={{
                  left: `${point.left}%`,
                  top: `${point.top}%`,
                  width: `${arrowLen}px`,
                  opacity: 0.58 + Math.min(0.38, s.wind_speed_ms / 16),
                  transform: `rotate(${windArrowDeg}deg)`,
                }}
              >
                <span className="absolute -right-0.5 -top-[3px] h-0 w-0 border-y-[4px] border-l-[7px] border-y-transparent border-l-white/90" />
              </div>
            ))}
            <div className="absolute left-[49%] top-[47%] h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow-[0_0_0_8px_rgba(255,255,255,0.2),0_0_28px_rgba(255,255,255,0.5)]"
              style={{ background: b.color }} />

            <div className="pointer-events-none absolute left-3 top-3 grid w-[150px] gap-1.5">
              <Badge label="Outdoor Temp" value={`${s.outdoor_temp_c.toFixed(1)} C`} tone={tempTone === "danger" ? "danger" : tempTone === "hot" ? "hot" : "neutral"} />
              <Badge label="Heat Index" value={`${hi.toFixed(1)} C`} tone={b.key === "extreme" ? "danger" : b.key === "stress" ? "hot" : b.key === "warm" ? "warn" : "neutral"} />
            </div>
            <div className="pointer-events-none absolute right-3 top-3 grid w-[140px] gap-1.5 text-right">
              <Badge label="Humidity" value={`${s.humidity_pct}%`} tone={humTone === "danger" ? "danger" : humTone === "warn" ? "warn" : "neutral"} />
              <Badge label="Solar Risk" value={s.solar_multiplier >= 1.2 ? "High" : s.solar_multiplier >= 1.05 ? "Elevated" : "Normal"} tone={solarTone === "danger" ? "danger" : "neutral"} />
            </div>
            <div className="pointer-events-none absolute bottom-3 left-3 flex items-center gap-2 rounded-xl bg-white/90 px-3 py-2 text-[11px] shadow-floating backdrop-blur">
              <Wind size={13} className="text-slate-500" />
              <span className="font-semibold text-slate-800">{s.wind_speed_ms.toFixed(1)} m/s {dirLabel(s.wind_direction_deg)}</span>
              <span className="text-text-muted">- {reliefLabel}</span>
            </div>
            <div className="pointer-events-none absolute bottom-3 right-3 rounded-xl px-3 py-2 text-[12px] font-semibold text-white shadow-floating"
              style={{ background: b.color }}>
              Cooling load +{upliftPct}%
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}

function Out({ k, v }: { k: string; v: string }) {
  return (
    <div className="rounded-lg bg-surface-muted px-2.5 py-1.5">
      <p className="text-[10px] text-text-muted">{k}</p>
      <p className="text-[13px] font-semibold">{v}</p>
    </div>
  );
}
