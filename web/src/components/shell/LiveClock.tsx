"use client";

import { useEffect, useRef, useState } from "react";
import { Clock } from "lucide-react";
import { api } from "@/lib/api";
import { useAppStore } from "@/stores/appStore";
import { usePollMs } from "@/hooks/usePollMs";

const TZ = { timeZone: "Asia/Ho_Chi_Minh" } as const;

// weekday · dd/mm/yyyy · hh:mm in building-local (Vietnam) time
function fmt(ms: number): string {
  const d = new Date(ms);
  const wd = d.toLocaleDateString("vi-VN", { ...TZ, weekday: "long" });
  const date = d.toLocaleDateString("vi-VN", { ...TZ, day: "2-digit", month: "2-digit", year: "numeric" });
  const time = d.toLocaleTimeString("vi-VN", { ...TZ, hour: "2-digit", minute: "2-digit", hour12: false });
  return `${wd}, ${date} ${time}`;
}

/**
 * Digital-twin clock. The API snaps `now` to the telemetry grid (15-min), so
 * polling alone makes the minutes jump in chunks. Instead we run the virtual
 * clock locally between polls — advancing by `speed` virtual seconds per real
 * second — and only resync to the server value, which keeps the minutes ticking
 * continuously. Resync is monotonic (never steps backward) except on a loop
 * wrap, where the server time drops by ~the whole window.
 */
export default function LiveClock() {
  const streaming = useAppStore((s) => s.streaming);
  const [label, setLabel] = useState("…");
  const virtualMs = useRef<number | null>(null);
  const speed = useRef(0);
  const last = useRef(0);

  // poll the authoritative virtual time + speed
  const pollMs = usePollMs(60000);
  useEffect(() => {
    const sync = () =>
      api
        .replayStatus()
        .then((s) => {
          speed.current = s.streaming ? s.speed || 0 : 0;
          const serverMs = s.now ? Date.parse(s.now) : NaN;
          if (Number.isNaN(serverMs)) return;
          const cur = virtualMs.current;
          const wrapped = cur != null && cur - serverMs > 30 * 60 * 1000; // loop reset
          if (cur == null || !s.streaming || serverMs > cur || wrapped) {
            virtualMs.current = serverMs;
          }
        })
        .catch(() => {});
    sync();
    const t = setInterval(sync, pollMs);
    return () => clearInterval(t);
  }, [pollMs]);

  // smooth local ticker — advances the virtual clock between polls (~10fps)
  useEffect(() => {
    last.current = performance.now();
    const tick = () => {
      const t = performance.now();
      const dt = t - last.current;
      last.current = t;
      if (virtualMs.current == null) return;
      if (speed.current > 0) virtualMs.current += dt * speed.current; // dt(ms)*speed = virtual ms
      const next = fmt(virtualMs.current);
      setLabel((prev) => (prev === next ? prev : next));
    };
    tick();
    const t = setInterval(tick, 100);
    return () => clearInterval(t);
  }, []);

  return (
    <span className="hidden items-center gap-1.5 text-xs text-text-secondary md:flex tabular-nums">
      <Clock size={13} className={`text-teal ${streaming ? "animate-pulse" : ""}`} />
      <span className="capitalize">{label}</span>
    </span>
  );
}
