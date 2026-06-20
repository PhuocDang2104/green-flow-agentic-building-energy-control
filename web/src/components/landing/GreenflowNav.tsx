"use client";

import { Cloud, Sun } from "lucide-react";

const NAV = [
  { label: "Problem", section: 5 },
  { label: "Agents", section: 6 },
  { label: "Impacts", section: 1 },
];

export default function GreenflowNav({
  active, theme, onToggleTheme, onNav,
}: {
  active: number;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onNav: (section: number) => void;
}) {
  return (
    <nav className="gf-nav" aria-label="GreenFlow landing navigation">
      <button onClick={() => onNav(0)} className="flex items-center gap-2 pr-1"
              aria-label="GreenFlow home">
        <img src="/assets/landing/greenflow_logo.png" alt="GreenFlow"
             className="h-7 w-auto" draggable={false} />
      </button>
      <div className="hidden items-center gap-1 sm:flex">
        {NAV.map((n) => {
          const on = active === n.section
            || (n.label === "Impacts" && active >= 1 && active <= 4);
          return (
            <button
              key={n.label}
              onClick={() => onNav(n.section)}
              className="rounded-full px-3.5 py-1.5 text-[13px] font-medium transition"
              style={{
                color: on ? "var(--gf-green)" : "var(--gf-muted)",
                background: on ? "var(--gf-green-soft)" : "transparent",
              }}
            >
              {n.label}
            </button>
          );
        })}
      </div>
      <button
        onClick={onToggleTheme}
        className="grid h-9 w-9 place-items-center rounded-full transition"
        style={{ background: "var(--gf-green-soft)", color: "var(--gf-green)" }}
        aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
      >
        {theme === "light" ? <Sun size={16} /> : <Cloud size={16} />}
      </button>
    </nav>
  );
}
