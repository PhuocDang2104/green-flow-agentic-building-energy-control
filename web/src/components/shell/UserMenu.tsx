"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut, Settings, User } from "lucide-react";

export default function UserMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);
  const router = useRouter();

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="grid h-9 w-9 place-items-center overflow-hidden rounded-full border border-border bg-white"
      >
        <img src="/assets/landing/user_logo.png" alt="Facility Manager" className="h-full w-full object-cover" />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-60 overflow-hidden rounded-2xl border border-border bg-white shadow-floating">
          <div className="flex items-center gap-3 border-b border-border px-4 py-3">
            <span className="grid h-10 w-10 place-items-center overflow-hidden rounded-full border border-border bg-white">
              <img src="/assets/landing/user_logo.png" alt="Facility Manager" className="h-full w-full object-cover" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-[13px] font-semibold">Facility Manager</p>
              <p className="truncate text-[11px] text-text-muted">vituonglaixanh@vingroup.net</p>
            </div>
          </div>
          <div className="p-1.5">
            <MenuItem icon={<User size={15} />} label="Profile" onClick={() => setOpen(false)} />
            <MenuItem icon={<Settings size={15} />} label="Settings"
                      onClick={() => { setOpen(false); router.push("/settings"); }} />
          </div>
          <div className="border-t border-border p-1.5">
            <MenuItem icon={<LogOut size={15} />} label="Sign out" danger
                      onClick={() => setOpen(false)} />
          </div>
        </div>
      )}
    </div>
  );
}

function MenuItem({ icon, label, onClick, danger }: {
  icon: React.ReactNode; label: string; onClick: () => void; danger?: boolean;
}) {
  return (
    <button onClick={onClick}
            className={`flex w-full items-center gap-3 rounded-xl px-3 py-2 text-[13px] font-medium transition
              ${danger ? "text-danger hover:bg-red-50" : "text-text-secondary hover:bg-surface-muted hover:text-text-primary"}`}>
      {icon}{label}
    </button>
  );
}
