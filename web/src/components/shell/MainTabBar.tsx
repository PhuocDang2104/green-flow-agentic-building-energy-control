"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Boxes, Bot, FlaskConical } from "lucide-react";

const TABS = [
  { href: "/dashboard", label: "Dashboard & 3D View", icon: Boxes },
  { href: "/agent-actions", label: "Agents & Actions", icon: Bot },
  { href: "/simulation-baseline", label: "Control & Simulation", icon: FlaskConical },
];

export default function MainTabBar() {
  const pathname = usePathname();
  return (
    <nav className="sticky top-16 z-30 flex justify-center px-4 pt-4">
      <div className="flex items-center gap-1 rounded-full border border-border bg-white p-1 shadow-card">
        {TABS.map(({ href, label, icon: Icon }) => {
          const active = pathname?.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-medium transition
                ${active ? "bg-teal text-white" : "text-text-secondary hover:bg-surface-muted hover:text-text-primary"}`}
            >
              <Icon size={15} strokeWidth={2} />
              <span className="hidden sm:inline">{label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
