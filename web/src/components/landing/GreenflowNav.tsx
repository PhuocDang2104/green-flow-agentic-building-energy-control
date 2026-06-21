"use client";

import Link from "next/link";
import { LogIn, Moon, Sun } from "lucide-react";

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
      <button onClick={() => onNav(0)} className="gf-nav-home flex items-center gap-2 pr-1"
              aria-label="GreenFlow home">
        <img src="/assets/landing/greenflow_logo.png" alt="GreenFlow"
             className="h-10 w-auto" draggable={false} />
      </button>
      <div className="hidden items-center gap-1 sm:flex">
        {NAV.map((n) => {
          const on = active === n.section
            || (n.label === "Impacts" && active >= 1 && active <= 4);
          return (
            <button
              key={n.label}
              onClick={() => onNav(n.section)}
              className={`gf-nav-link ${on ? "is-active" : ""}`}
            >
              {n.label}
            </button>
          );
        })}
      </div>
      <button
        onClick={onToggleTheme}
        className={`gf-theme-toggle ${theme === "dark" ? "is-dark" : "is-light"}`}
        aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
      >
        <span className="gf-theme-stars" aria-hidden />
        <span className="gf-theme-hills" aria-hidden />
        <span className="gf-theme-orb">
          {theme === "light" ? <Sun size={13} /> : <Moon size={13} />}
        </span>
      </button>
      <Link href="/dashboard" className="gf-login-button" aria-label="Login to GreenFlow dashboard">
        <LogIn size={16} />
        <span className="hidden sm:inline">Login</span>
      </Link>
    </nav>
  );
}
