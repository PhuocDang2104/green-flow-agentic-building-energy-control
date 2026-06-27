"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Archive, Bot, Boxes, FileText, FlaskConical, GitCompareArrows,
  Settings, Sparkles, Zap,
} from "lucide-react";
import { useAppStore } from "@/stores/appStore";

const MAIN = [
  { href: "/dashboard", label: "Dashboard & 3D View", icon: Boxes },
  { href: "/electrical", label: "Electrical Graph", icon: Zap },
  { href: "/agent-actions", label: "Agents & Actions", icon: Bot },
  { href: "/simulation-baseline", label: "What-if Analysis", icon: FlaskConical },
];

const BOTTOM = [
  { href: "/archive", label: "Archive", icon: Archive },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function SideBar() {
  const pathname = usePathname();
  const setChatbotOpen = useAppStore((s) => s.setChatbotOpen);

  const NavItem = ({ href, label, icon: Icon }: { href: string; label: string; icon: any }) => {
    const active = pathname?.startsWith(href);
    return (
      <Link
        href={href}
        className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition
          ${active ? "bg-teal-soft text-teal" : "text-text-secondary hover:bg-surface-muted hover:text-text-primary"}`}
      >
        <Icon size={18} strokeWidth={active ? 2.4 : 2}
              className={active ? "text-teal" : "text-text-muted group-hover:text-text-primary"} />
        <span className="truncate">{label}</span>
      </Link>
    );
  };

  return (
    <aside
      className="fixed left-0 top-0 z-50 hidden h-screen w-[248px] flex-col border-r border-border bg-white lg:flex"
    >
      {/* brand */}
      <div className="flex h-16 items-center gap-2.5 px-4">
        <img
          src="/assets/landing/greenflow_favicon.png"
          alt="GreenFlow"
          className="h-9 w-9 shrink-0 rounded-xl object-contain"
        />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-semibold leading-tight">GreenFlow</p>
          <p className="text-[11px] text-text-muted">v0.1.0</p>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pb-4">
        {/* Favourites */}
        <p className="px-3 pb-1.5 pt-3 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
          Favourites
        </p>
        <div className="space-y-0.5">
          <button
            onClick={() => setChatbotOpen(true)}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium text-text-secondary transition hover:bg-surface-muted hover:text-text-primary"
          >
            <Sparkles size={18} className="text-text-muted" />
            Ask Copilot
          </button>
          <Link href="/simulation-baseline"
                className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium text-text-secondary transition hover:bg-surface-muted hover:text-text-primary">
            <GitCompareArrows size={18} className="text-text-muted" />
            Baseline vs Optimized
          </Link>
          <Link href="/archive"
                className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium text-text-secondary transition hover:bg-surface-muted hover:text-text-primary">
            <FileText size={18} className="text-text-muted" />
            Reports
          </Link>
        </div>

        {/* Main menu */}
        <p className="px-3 pb-1.5 pt-5 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
          Main menu
        </p>
        <div className="space-y-0.5">
          {MAIN.map((item) => <NavItem key={item.href} {...item} />)}
        </div>
      </nav>

      {/* bottom */}
      <div className="border-t border-border px-3 py-3">
        <div className="space-y-0.5">
          {BOTTOM.map((item) => <NavItem key={item.href} {...item} />)}
        </div>
      </div>
    </aside>
  );
}
