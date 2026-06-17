"use client";

import { Building2, PanelLeft } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import SearchBar from "./SearchBar";
import UserMenu from "./UserMenu";

export default function TopBar() {
  const toggle = useAppStore((s) => s.toggleSidebar);

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

        {/* right: user menu */}
        <UserMenu />
      </div>
    </header>
  );
}
