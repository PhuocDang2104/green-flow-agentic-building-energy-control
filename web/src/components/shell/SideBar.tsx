"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Archive, Bot, Boxes, Building2, FileText, FlaskConical, GitCompareArrows,
  PanelLeftClose, PanelLeft, Settings, Sparkles,
} from "lucide-react";
import { useAppStore } from "@/stores/appStore";

const MAIN = [
  { href: "/dashboard", label: "Dashboard & 3D View", icon: Boxes },
  { href: "/agent-actions", label: "Agents & Actions", icon: Bot },
  { href: "/simulation-baseline", label: "Control & Simulation", icon: FlaskConical },
];

const BOTTOM = [
  { href: "/archive", label: "Archive", icon: Archive },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function SideBar() {
  const pathname = usePathname();
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const toggle = useAppStore((s) => s.toggleSidebar);
  const setChatbotOpen = useAppStore((s) => s.setChatbotOpen);

  const NavItem = ({ href, label, icon: Icon }: { href: string; label: string; icon: any }) => {
    const active = pathname?.startsWith(href);
    return (
      <Link
        href={href}
        title={collapsed ? label : undefined}
        className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition
          ${active ? "bg-teal-soft text-teal" : "text-text-secondary hover:bg-surface-muted hover:text-text-primary"}
          ${collapsed ? "justify-center" : ""}`}
      >
        <Icon size={18} strokeWidth={active ? 2.4 : 2}
              className={active ? "text-teal" : "text-text-muted group-hover:text-text-primary"} />
        {!collapsed && <span className="truncate">{label}</span>}
      </Link>
    );
  };

  return (
    <aside
      className={`hidden lg:flex ${collapsed ? "w-[76px]" : "w-[248px]"}
        shrink-0 flex-col border-r border-border bg-white transition-[width] duration-200`}
    >
      {/* brand */}
      <div className="flex h-16 items-center gap-2.5 px-4">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-teal text-white">
          <Building2 size={18} />
        </span>
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <p className="truncate text-[15px] font-semibold leading-tight">GreenFlow</p>
            <p className="text-[11px] text-text-muted">v0.1.0</p>
          </div>
        )}
        <button onClick={toggle}
                className="grid h-7 w-7 place-items-center rounded-lg text-text-muted hover:bg-surface-muted">
          {collapsed ? <PanelLeft size={16} /> : <PanelLeftClose size={16} />}
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pb-4">
        {/* Favourites */}
        {!collapsed && (
          <p className="px-3 pb-1.5 pt-3 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
            Favourites
          </p>
        )}
        <div className="space-y-0.5">
          <button
            onClick={() => setChatbotOpen(true)}
            title={collapsed ? "Ask Copilot" : undefined}
            className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium text-text-secondary transition hover:bg-surface-muted hover:text-text-primary ${collapsed ? "justify-center" : ""}`}
          >
            <Sparkles size={18} className="text-text-muted" />
            {!collapsed && "Ask Copilot"}
          </button>
          <Link href="/simulation-baseline"
                title={collapsed ? "Baseline vs Optimized" : undefined}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium text-text-secondary transition hover:bg-surface-muted hover:text-text-primary ${collapsed ? "justify-center" : ""}`}>
            <GitCompareArrows size={18} className="text-text-muted" />
            {!collapsed && "Baseline vs Optimized"}
          </Link>
          <Link href="/archive"
                title={collapsed ? "Reports" : undefined}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium text-text-secondary transition hover:bg-surface-muted hover:text-text-primary ${collapsed ? "justify-center" : ""}`}>
            <FileText size={18} className="text-text-muted" />
            {!collapsed && "Reports"}
          </Link>
        </div>

        {/* Main menu */}
        {!collapsed && (
          <p className="px-3 pb-1.5 pt-5 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
            Main menu
          </p>
        )}
        {collapsed && <div className="my-3 border-t border-border" />}
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
