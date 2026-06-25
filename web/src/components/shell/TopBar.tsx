"use client";

import { useEffect } from "react";
import { Building2, PanelLeft, Radio } from "lucide-react";
import { api } from "@/lib/api";
import { useAppStore } from "@/stores/appStore";
import SearchBar from "./SearchBar";
import UserMenu from "./UserMenu";

export default function TopBar() {
  const toggle = useAppStore((s) => s.toggleSidebar);
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
        {/* left: sidebar toggle (desktop) / brand (mobile) */}
        <button
          onClick={toggle}
          className="hidden h-9 w-9 place-items-center rounded-lg text-text-secondary hover:bg-surface-muted lg:grid"
        >
          <PanelLeft size={18} />
        </button>
        <div className="flex items-center gap-2 lg:hidden">
          <span className="grid h-8 w-8 place-items-center rounded-xl bg-teal text-white">
            <Building2 size={17} />
          </span>
          <span className="text-[15px] font-semibold">GreenFlow</span>
        </div>

        {/* center: search */}
        <div className="flex flex-1 justify-center">
          <SearchBar />
        </div>

        {/* right: live streaming toggle + user menu */}
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
