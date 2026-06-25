"use client";

import { useEffect, useState } from "react";
import { Clock, Radio } from "lucide-react";
import { api } from "@/lib/api";
import { useAppStore } from "@/stores/appStore";
import { usePollMs } from "@/hooks/usePollMs";
import SearchBar from "./SearchBar";
import UserMenu from "./UserMenu";

export default function TopBar() {
  const streaming = useAppStore((s) => s.streaming);
  const setStreaming = useAppStore((s) => s.setStreaming);
  const [now, setNow] = useState<string | null>(null);

  useEffect(() => {
    api.replayStatus().then((s) => setStreaming(!!s.streaming)).catch(() => {});
  }, [setStreaming]);

  // virtual-clock label — polls fast while live so it ticks through the day
  const pollMs = usePollMs(60000);
  useEffect(() => {
    const tick = () => api.replayStatus().then((s) => setNow(s.now)).catch(() => {});
    tick();
    const t = setInterval(tick, pollMs);
    return () => clearInterval(t);
  }, [pollMs]);

  // weekday · dd/mm/yyyy · hh:mm in building-local (Vietnam) time, in that order
  const clock = now
    ? (() => {
        const d = new Date(now), tz = { timeZone: "Asia/Ho_Chi_Minh" } as const;
        const wd = d.toLocaleDateString("vi-VN", { ...tz, weekday: "long" });
        const date = d.toLocaleDateString("vi-VN", { ...tz, day: "2-digit", month: "2-digit", year: "numeric" });
        const time = d.toLocaleTimeString("vi-VN", { ...tz, hour: "2-digit", minute: "2-digit", hour12: false });
        return `${wd}, ${date} ${time}`;
      })()
    : "…";

  const toggleLive = () => {
    const next = !streaming;
    setStreaming(next);  // optimistic
    api.replayStream(next).catch(() => setStreaming(!next));  // revert on failure
  };

  return (
    <header className="sticky top-0 z-40 h-16 border-b border-border bg-white/85 backdrop-blur">
      <div className="flex h-full items-center gap-4 px-5">
        {/* left: brand (mobile) */}
        <div className="flex items-center gap-2 lg:hidden">
          <img
            src="/assets/landing/greenflow_favicon.png"
            alt="GreenFlow"
            className="h-8 w-8 rounded-xl object-contain"
          />
          <span className="text-[15px] font-semibold">GreenFlow</span>
        </div>

        {/* center: search */}
        <div className="flex flex-1 justify-center">
          <SearchBar />
        </div>

        {/* right: virtual clock + live streaming toggle + user menu */}
        <span className="hidden items-center gap-1.5 text-xs text-text-secondary md:flex tabular-nums">
          <Clock size={13} className="text-teal" />
          <span className="capitalize">{clock}</span>
        </span>
        <button
          onClick={toggleLive}
          title={streaming ? "Streaming the digital twin — click to pause"
                           : "Replay the digital twin live"}
          className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition
            ${streaming ? "bg-teal text-white" : "text-text-secondary hover:bg-surface-muted"}`}
        >
          <Radio size={14} className={streaming ? "animate-pulse" : ""} />
          {streaming ? "Live" : "Go live"}
        </button>
        <UserMenu />
      </div>
    </header>
  );
}
