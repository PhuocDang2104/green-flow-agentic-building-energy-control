"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, Search, Wind, X } from "lucide-react";
import { api } from "@/lib/api";
import { titleCase } from "@/lib/format";
import { useAppStore } from "@/stores/appStore";
import type { Device, Zone } from "@/lib/types";

/** Global search over zones + devices. Selecting an entity highlights it in
 *  the 3D viewer and routes to the dashboard. */
export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [zones, setZones] = useState<Zone[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const boxRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const router = useRouter();
  const selectEntity = useAppStore((s) => s.selectEntity);

  useEffect(() => {
    api.zones().then(setZones).catch(() => null);
    api.devices().then(setDevices).catch(() => null);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
      if (e.key === "Escape") setOpen(false);
    };
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, []);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return { zones: [] as Zone[], devices: [] as Device[] };
    return {
      zones: zones.filter((z) =>
        z.name.toLowerCase().includes(q) || z.room_type?.toLowerCase().includes(q)).slice(0, 6),
      devices: devices.filter((d) =>
        d.name.toLowerCase().includes(q) || d.tag?.toLowerCase().includes(q)).slice(0, 5),
    };
  }, [query, zones, devices]);

  const pick = (key: string) => {
    selectEntity(key);
    router.push("/dashboard");
    setOpen(false);
    setQuery("");
  };

  const hasResults = results.zones.length > 0 || results.devices.length > 0;

  return (
    <div ref={boxRef} className="relative w-full max-w-xl">
      <div className="flex items-center gap-2 rounded-xl border border-border bg-surface-muted/60 px-3.5 py-2 transition focus-within:border-teal focus-within:bg-white">
        <Search size={16} className="text-text-muted" />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocusCapture={() => setOpen(true)}
          placeholder="Search zones, devices, reports…"
          className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-text-muted"
        />
        {query ? (
          <button onClick={() => { setQuery(""); inputRef.current?.focus(); }}
                  className="text-text-muted hover:text-text-primary">
            <X size={14} />
          </button>
        ) : (
          <kbd className="hidden rounded-md border border-border bg-white px-1.5 py-0.5 text-[10px] font-medium text-text-muted sm:block">
            ⌘K
          </kbd>
        )}
      </div>

      {open && query && (
        <div className="absolute left-0 right-0 top-full z-50 mt-2 overflow-hidden rounded-2xl border border-border bg-white shadow-floating">
          {!hasResults && (
            <p className="px-4 py-4 text-[13px] text-text-muted">No matches for “{query}”.</p>
          )}
          {results.zones.length > 0 && (
            <Group label="Zones">
              {results.zones.map((z) => (
                <Row key={z.entity_key} icon={<Building2 size={15} className="text-teal" />}
                     onClick={() => pick(z.entity_key)}
                     title={z.name} subtitle={`${titleCase(z.room_type)} · ${z.floor_name ?? ""}`} />
              ))}
            </Group>
          )}
          {results.devices.length > 0 && (
            <Group label="Devices">
              {results.devices.map((d) => (
                <Row key={d.entity_key} icon={<Wind size={15} className="text-info" />}
                     onClick={() => pick(d.zone_key || d.entity_key)}
                     title={d.name} subtitle={`${titleCase(d.device_subtype)} · ${d.tag ?? ""}`} />
              ))}
            </Group>
          )}
        </div>
      )}
    </div>
  );
}

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="py-1">
      <p className="px-4 py-1 text-[11px] font-semibold uppercase tracking-wide text-text-muted">{label}</p>
      {children}
    </div>
  );
}

function Row({ icon, title, subtitle, onClick }: {
  icon: React.ReactNode; title: string; subtitle: string; onClick: () => void;
}) {
  return (
    <button onClick={onClick}
            className="flex w-full items-center gap-3 px-4 py-2 text-left transition hover:bg-surface-muted">
      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-surface-muted">{icon}</span>
      <span className="min-w-0">
        <span className="block truncate text-[13px] font-medium">{title}</span>
        <span className="block truncate text-[11px] text-text-muted">{subtitle}</span>
      </span>
    </button>
  );
}
