"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Boxes, Bot, FlaskConical, Zap } from "lucide-react";

const TABS = [
  { href: "/dashboard", label: "Dashboard & 3D View", icon: Boxes },
  { href: "/electrical", label: "Electrical Graph", icon: Zap },
  { href: "/agent-actions", label: "Agents & Actions", icon: Bot },
  { href: "/simulation-baseline", label: "What-if Analysis", icon: FlaskConical },
];

// Mobile/tablet only — on desktop (lg+) the SideBar replaces this. Floating,
// icon-only pill bar fixed at the bottom centre.
export default function MainTabBar() {
  const pathname = usePathname();
  return (
    <nav className="fixed bottom-4 left-1/2 z-30 -translate-x-1/2 lg:hidden">
      <div className="flex items-center gap-1 rounded-full border border-border bg-white/95 p-1.5 shadow-floating backdrop-blur">
        {TABS.map(({ href, label, icon: Icon }) => {
          const active = pathname?.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              title={label}
              className={`grid h-11 w-11 place-items-center rounded-full transition
                ${active ? "bg-teal text-white" : "text-text-secondary hover:bg-surface-muted"}`}
            >
              <Icon size={19} strokeWidth={2} />
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
