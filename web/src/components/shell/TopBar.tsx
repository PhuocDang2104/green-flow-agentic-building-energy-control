"use client";

import { Building2, ChevronDown, User } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { fmtTime } from "@/lib/format";

export default function TopBar() {
  const replayTimestamp = useAppStore((s) => s.replayTimestamp);
  const wsConnected = useAppStore((s) => s.wsConnected);

  return (
    <header className="sticky top-0 z-40 h-16 border-b border-border bg-white/85 backdrop-blur">
      <div className="mx-auto flex h-full max-w-[1480px] items-center justify-between px-5">
        <div className="flex items-center gap-5">
          <div className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-xl bg-teal text-white">
              <Building2 className="h-4.5 w-4.5" size={18} />
            </span>
            <span className="text-[17px] font-semibold tracking-tight">GreenFlow</span>
          </div>
          <button className="btn-secondary !py-1.5 text-[13px]">
            GreenFlow Archetype · Hanoi
            <ChevronDown className="h-3.5 w-3.5 text-text-muted" />
          </button>
        </div>

        <div className="flex items-center gap-4">
          <div className="hidden items-center gap-2 text-[13px] text-text-secondary md:flex">
            <span className="text-text-muted">Replay</span>
            <span className="font-medium text-text-primary">{fmtTime(replayTimestamp)}</span>
          </div>
          <span className="flex items-center gap-1.5 text-xs text-text-secondary">
            <span className={`h-2 w-2 rounded-full ${wsConnected ? "bg-success" : "bg-text-muted"}`} />
            {wsConnected ? "Data live" : "Connecting"}
          </span>
          <span className="grid h-8 w-8 place-items-center rounded-full bg-surface-muted text-text-secondary">
            <User size={15} />
          </span>
        </div>
      </div>
    </header>
  );
}
