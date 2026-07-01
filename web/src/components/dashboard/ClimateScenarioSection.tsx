"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Cloud, CloudRain, CloudSun, Clock3, Droplets, Sun, Thermometer, Wind,
  type LucideIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import type { WeatherState } from "@/lib/types";
import { usePollMs } from "@/hooks/usePollMs";
import { useAppStore } from "@/stores/appStore";

const CLIMATE_MAP_IMAGE = "/assets/landing/hanoi_climate_map_google_3d.png";

type Tone = "normal" | "neutral" | "warn" | "hot" | "danger";
type Reading = { label: string; tone: Tone };

function heatIndexC(tC: number, rh: number): number {
  const tF = tC * 9 / 5 + 32;
  if (tF < 80) return tC;
  let heatIndex =
    -42.379 + 2.04901523 * tF + 10.14333127 * rh - 0.22475541 * tF * rh -
    6.83783e-3 * tF * tF - 5.481717e-2 * rh * rh +
    1.22874e-3 * tF * tF * rh + 8.5282e-4 * tF * rh * rh -
    1.99e-6 * tF * tF * rh * rh;
  if (rh < 13 && tF >= 80 && tF <= 112) {
    heatIndex -= ((13 - rh) / 4) * Math.sqrt((17 - Math.abs(tF - 95)) / 17);
  }
  return (heatIndex - 32) * 5 / 9;
}

function temperatureReading(value?: number): Reading {
  if (value == null) return { label: "Unavailable", tone: "neutral" };
  if (value < 31) return { label: "Comfortable", tone: "normal" };
  if (value < 34) return { label: "Warm", tone: "warn" };
  if (value < 38) return { label: "High", tone: "hot" };
  return { label: "Extreme", tone: "danger" };
}

function humidityReading(value?: number): Reading {
  if (value == null) return { label: "Unavailable", tone: "neutral" };
  if (value < 40) return { label: "Dry", tone: "warn" };
  if (value < 65) return { label: "Comfortable", tone: "normal" };
  if (value < 80) return { label: "Humid", tone: "warn" };
  return { label: "Very humid", tone: "danger" };
}

function solarReading(value?: number): Reading {
  if (value == null) return { label: "Unavailable", tone: "neutral" };
  if (value < 200) return { label: "Low", tone: "normal" };
  if (value < 600) return { label: "Moderate", tone: "warn" };
  if (value < 800) return { label: "High", tone: "hot" };
  return { label: "Very high", tone: "danger" };
}

function windReading(value?: number): Reading {
  if (value == null) return { label: "Unavailable", tone: "neutral" };
  if (value < 1.5) return { label: "Still air", tone: "warn" };
  if (value < 3) return { label: "Light breeze", tone: "neutral" };
  return { label: "Good airflow", tone: "normal" };
}

function cloudReading(value?: number): Reading {
  if (value == null) return { label: "Unavailable", tone: "neutral" };
  if (value < 25) return { label: "Mostly clear", tone: "normal" };
  if (value < 70) return { label: "Partly cloudy", tone: "neutral" };
  return { label: "Overcast", tone: "warn" };
}

function rainReading(value?: number): Reading {
  if (value == null) return { label: "Unavailable", tone: "neutral" };
  if (value <= 0.05) return { label: "Dry", tone: "normal" };
  if (value < 2) return { label: "Light rain", tone: "neutral" };
  return { label: "Rain", tone: "warn" };
}

function heatReading(value?: number): Reading {
  if (value == null) return { label: "No heat index", tone: "neutral" };
  if (value < 30) return { label: "Normal", tone: "normal" };
  if (value < 37) return { label: "Caution", tone: "warn" };
  if (value < 41) return { label: "Heat stress", tone: "hot" };
  return { label: "Extreme heat", tone: "danger" };
}

const toneClass: Record<Tone, string> = {
  normal: "bg-success/12 text-success",
  neutral: "bg-slate-100 text-slate-600",
  warn: "bg-warning/15 text-warning",
  hot: "bg-orange-500/12 text-orange-600",
  danger: "bg-danger/12 text-danger",
};

const toneColor: Record<Tone, string> = {
  normal: "#16a34a",
  neutral: "#64748b",
  warn: "#d97706",
  hot: "#ea580c",
  danger: "#dc2626",
};

function formatSnapshotTime(value?: string): string {
  if (!value) return "Waiting for replay timestamp";
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short", day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(new Date(value));
}

function number(value?: number, digits = 1): string {
  return value == null ? "–" : Number(value).toFixed(digits);
}

function WeatherMetric({ icon: Icon, label, value, detail, reading }: {
  icon: LucideIcon;
  label: string;
  value: string;
  detail: string;
  reading: Reading;
}) {
  return (
    <article className="rounded-xl bg-surface-muted/65 px-3.5 py-3">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white text-teal shadow-sm">
          <Icon size={16} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium text-text-muted">{label}</p>
          <div className="mt-0.5 flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-[17px] font-semibold tracking-tight tabular-nums text-text-primary">{value}</p>
            <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-medium ${toneClass[reading.tone]}`}>
              {reading.label}
            </span>
          </div>
          <p className="mt-1 text-[10px] leading-snug text-text-muted">{detail}</p>
        </div>
      </div>
    </article>
  );
}

function MapBadge({ label, value, tone = "neutral" }: {
  label: string;
  value: string;
  tone?: Tone;
}) {
  const dark = tone === "hot" || tone === "danger";
  return (
    <div
      className={`rounded-xl px-2.5 py-1.5 text-[11px] shadow-floating backdrop-blur ${
        dark ? "text-white" : "bg-white/90 text-slate-700"
      }`}
      style={dark ? { background: `${toneColor[tone]}e8` } : undefined}
    >
      <span className="opacity-70">{label}</span>
      <div className="text-[13px] font-semibold leading-tight tabular-nums">{value}</div>
    </div>
  );
}

export default function ClimateScenarioSection() {
  const liveWeather = useAppStore((state) => state.weatherState);
  const replayTimestamp = useAppStore((state) => state.replayTimestamp);
  const setWeatherState = useAppStore((state) => state.setWeatherState);
  const [fallbackWeather, setFallbackWeather] = useState<WeatherState | null>(null);
  const [loadError, setLoadError] = useState(false);
  const pollMs = usePollMs(30000);

  useEffect(() => {
    let stopped = false;
    const load = () => {
      api.currentWeather()
        .then((snapshot) => {
          if (stopped) return;
          setFallbackWeather(snapshot);
          setWeatherState(snapshot);
          setLoadError(false);
        })
        .catch(() => { if (!stopped) setLoadError(true); });
    };
    load();
    const timer = setInterval(load, pollMs);
    return () => { stopped = true; clearInterval(timer); };
  }, [pollMs, setWeatherState]);

  const weather = liveWeather || fallbackWeather;
  const temperature = weather?.outdoor_temp_c;
  const humidity = weather?.humidity_pct;
  const solar = weather?.solar_w_m2;
  const wind = weather?.wind_speed_mps;
  const cloud = weather?.cloud_cover_pct;
  const rain = weather?.precipitation_mm;
  const heatIndex = useMemo(
    () => temperature == null || humidity == null ? undefined : heatIndexC(temperature, humidity),
    [temperature, humidity],
  );

  const tempBand = temperatureReading(temperature);
  const humidityBand = humidityReading(humidity);
  const solarBand = solarReading(solar);
  const windBand = windReading(wind);
  const cloudBand = cloudReading(cloud);
  const rainBand = rainReading(rain);
  const heatBand = heatReading(heatIndex);
  const snapshotTime = weather?.timestamp || replayTimestamp || weather?.replay_at;
  const heatOpacity = heatIndex == null
    ? 0.08
    : Math.min(0.4, 0.1 + Math.max(0, heatIndex - 30) / 38);

  return (
    <section data-tour-id="weather-context-panel" className="mt-4" aria-labelledby="weather-heading">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <CloudSun size={16} className="text-teal" />
          <h2 id="weather-heading" className="text-sm font-semibold">Weather at replay time</h2>
        </div>
        <div className="flex items-center gap-1.5 text-[11px] text-text-muted">
          <Clock3 size={13} />
          <span className="tabular-nums">{formatSnapshotTime(snapshotTime)}</span>
          <span aria-hidden="true">·</span>
          <span>{weather?.location_name || "Hanoi"}</span>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.04fr_1fr]">
        <div className="card p-4">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <h3 className="text-[14px] font-semibold">Recorded weather snapshot</h3>
              <p className="mt-0.5 max-w-[60ch] text-[11px] leading-relaxed text-text-muted">
                Read-only measurements aligned to the same 30-minute replay timestamp as load, occupancy and zone state.
              </p>
            </div>
            <span className={`shrink-0 rounded-md px-2 py-1 text-[10px] font-medium ${toneClass[heatBand.tone]}`}>
              {heatBand.label}
            </span>
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <WeatherMetric icon={Thermometer} label="Outdoor temperature"
              value={`${number(temperature)}°C`} detail="Dry-bulb air temperature"
              reading={tempBand} />
            <WeatherMetric icon={Droplets} label="Relative humidity"
              value={`${number(humidity, 0)}%`} detail="Moisture relative to saturation"
              reading={humidityBand} />
            <WeatherMetric icon={Sun} label="Solar irradiance"
              value={`${number(solar, 0)} W/m²`} detail="Global horizontal radiation"
              reading={solarBand} />
            <WeatherMetric icon={Wind} label="Wind speed"
              value={`${number(wind)} m/s`} detail="Recorded speed; direction is not provided"
              reading={windBand} />
            <WeatherMetric icon={Cloud} label="Cloud cover"
              value={`${number(cloud, 0)}%`} detail="Estimated fraction of covered sky"
              reading={cloudBand} />
            <WeatherMetric icon={CloudRain} label="Precipitation"
              value={`${number(rain, 1)} mm`} detail="Precipitation in this weather interval"
              reading={rainBand} />
          </div>

          <div className="mt-3 flex items-center justify-between gap-3 border-t border-border/70 pt-3 text-[10px] text-text-muted">
            <span>{loadError && !weather ? "Weather snapshot unavailable" : "Synced from weather_15m"}</span>
            <span className="tabular-nums">30-minute source interval</span>
          </div>
        </div>

        <div className="card overflow-hidden p-0">
          <div className="flex items-center justify-between gap-3 px-4 py-2.5">
            <div>
              <h3 className="text-[14px] font-semibold">Hanoi weather context</h3>
              <p className="text-[10px] text-text-muted">Heat overlay derived from temperature and humidity</p>
            </div>
            <span className={`rounded-md px-2 py-0.5 text-[11px] font-medium ${toneClass[heatBand.tone]}`}>
              {heatBand.label}
            </span>
          </div>

          <div className="relative h-[340px] w-full overflow-hidden bg-slate-950">
            <div className="absolute inset-0 bg-cover bg-center"
              style={{ backgroundImage: `url(${CLIMATE_MAP_IMAGE})` }} />
            <div className="absolute inset-0 bg-gradient-to-b from-black/10 via-transparent to-black/40" />
            <div className="absolute inset-0 mix-blend-multiply"
              style={{
                opacity: heatOpacity,
                background: `radial-gradient(circle at 55% 48%, ${toneColor[heatBand.tone]} 0 12%, transparent 42%), radial-gradient(circle at 36% 66%, ${toneColor[heatBand.tone]} 0 9%, transparent 33%)`,
              }} />
            <div className="absolute left-[49%] top-[47%] h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow-[0_0_0_8px_rgba(255,255,255,0.2),0_0_28px_rgba(255,255,255,0.5)]"
              style={{ background: toneColor[heatBand.tone] }} />

            <div className="pointer-events-none absolute left-3 top-3 grid w-[150px] gap-1.5">
              <MapBadge label="Outdoor temperature" value={`${number(temperature)}°C`} tone={tempBand.tone} />
              <MapBadge label="Derived heat index" value={`${number(heatIndex)}°C`} tone={heatBand.tone} />
            </div>
            <div className="pointer-events-none absolute right-3 top-3 grid w-[140px] gap-1.5 text-right">
              <MapBadge label="Humidity" value={`${number(humidity, 0)}%`} tone={humidityBand.tone} />
              <MapBadge label="Solar irradiance" value={`${number(solar, 0)} W/m²`} tone={solarBand.tone} />
            </div>
            <div className="pointer-events-none absolute bottom-3 left-3 flex items-center gap-2 rounded-xl bg-white/90 px-3 py-2 text-[11px] shadow-floating backdrop-blur">
              <Wind size={13} className="text-slate-500" />
              <span className="font-semibold text-slate-800 tabular-nums">{number(wind)} m/s</span>
              <span className="text-text-muted">{windBand.label}</span>
            </div>
            <div className="pointer-events-none absolute bottom-3 right-3 rounded-xl bg-slate-950/82 px-3 py-2 text-right text-[11px] text-white shadow-floating backdrop-blur">
              <p className="text-white/65">Weather recorded</p>
              <p className="font-semibold tabular-nums">{formatSnapshotTime(snapshotTime)}</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
