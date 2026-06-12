export function fmtKw(v?: number | null): string {
  if (v === undefined || v === null) return "–";
  return `${Number(v).toFixed(v >= 10 ? 1 : 2)} kW`;
}

export function fmtKwh(v?: number | null): string {
  if (v === undefined || v === null) return "–";
  return `${Number(v).toFixed(1)} kWh`;
}

export function fmtVnd(v?: number | null): string {
  if (v === undefined || v === null) return "–";
  return `${Math.round(Number(v)).toLocaleString("vi-VN")} ₫`;
}

export function fmtTemp(v?: number | null): string {
  if (v === undefined || v === null) return "–";
  return `${Number(v).toFixed(1)}°C`;
}

export function fmtPct(v?: number | null): string {
  if (v === undefined || v === null) return "–";
  return `${Math.round(Number(v) * 100)}%`;
}

export function fmtTime(iso?: string | null): string {
  if (!iso) return "–";
  const d = new Date(iso);
  return d.toLocaleString("en-GB", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function fmtClock(iso?: string | null): string {
  if (!iso) return "–";
  return new Date(iso).toLocaleTimeString("en-GB", {
    hour: "2-digit", minute: "2-digit",
  });
}

export function titleCase(s?: string | null): string {
  if (!s) return "";
  return s.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
