"use client";

import { useEffect } from "react";
import { Radio } from "lucide-react";
import { api } from "@/lib/api";
import { useAppStore } from "@/stores/appStore";
import LiveClock from "./LiveClock";
import SearchBar from "./SearchBar";
import UserMenu from "./UserMenu";

export default function TopBar() {
  const streaming = useAppStore((s) => s.streaming);
  const setStreaming = useAppStore((s) => s.setStreaming);

  useEffect(() => {
    api.replayStatus().then((s) => setStreaming(!!s.streaming)).catch(() => {});
  }, [setStreaming]);

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
        <LiveClock />
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
