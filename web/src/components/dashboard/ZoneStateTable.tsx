"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, RotateCcw, Search } from "lucide-react";
import { fmtKw, fmtTemp, titleCase } from "@/lib/format";
import StatusPill from "@/components/shared/StatusPill";
import Skeleton from "@/components/shared/Skeleton";
import { useAppStore } from "@/stores/appStore";
import type { Zone, ZoneState } from "@/lib/types";

type SortKey = "zone" | "type" | "occupancy" | "temperature" | "load" | "comfort" | "peak";
type SortDirection = "asc" | "desc";
type RiskFilter = "all" | "normal" | "watch" | "high";

type ZoneRow = {
  zone: Zone;
  state?: ZoneState | null;
  roomType: string;
  comfort: string;
  peak: string;
};

const riskRank: Record<string, number> = { normal: 0, watch: 1, high: 2 };

function compareNullable(a: string | number | undefined | null,
                         b: string | number | undefined | null): number {
  const aMissing = a == null || a === "";
  const bMissing = b == null || b === "";
  if (aMissing || bMissing) return aMissing === bMissing ? 0 : aMissing ? 1 : -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}

function SortIcon({ active, direction }: { active: boolean; direction: SortDirection }) {
  if (!active) return <ArrowUpDown size={12} className="opacity-45" />;
  return direction === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />;
}

function SortHeader({ label, column, active, direction, onSort, align = "left" }: {
  label: string;
  column: SortKey;
  active: boolean;
  direction: SortDirection;
  onSort: (column: SortKey) => void;
  align?: "left" | "right";
}) {
  return (
    <th scope="col" aria-sort={active ? (direction === "asc" ? "ascending" : "descending") : "none"}
      className="px-5 py-2.5 font-medium">
      <button type="button" onClick={() => onSort(column)}
        className={`group inline-flex w-full items-center gap-1.5 rounded-sm transition-colors hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal/40 ${
          align === "right" ? "justify-end" : "justify-start"
        } ${active ? "text-teal" : "text-text-muted"}`}>
        <span>{label}</span>
        <SortIcon active={active} direction={direction} />
      </button>
    </th>
  );
}

export default function ZoneStateTable({ zones }: { zones: Zone[] }) {
  const zoneStates = useAppStore((state) => state.zoneStates);
  const selectedEntityKey = useAppStore((state) => state.selectedEntityKey);
  const selectEntity = useAppStore((state) => state.selectEntity);
  const activeRowRef = useRef<HTMLTableRowElement | null>(null);
  const tableScrollRef = useRef<HTMLDivElement | null>(null);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [comfortFilter, setComfortFilter] = useState<RiskFilter>("all");
  const [peakFilter, setPeakFilter] = useState<RiskFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("zone");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const roomTypes = useMemo(() => Array.from(new Set(
    zones.map((zone) => zone.room_type).filter(Boolean),
  )).sort((a, b) => titleCase(a).localeCompare(titleCase(b))), [zones]);

  const rows = useMemo<ZoneRow[]>(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    const filtered = zones.map((zone) => {
      const state = zoneStates[zone.entity_key] || zone.latest_state;
      return {
        zone,
        state,
        roomType: zone.room_type || "unknown",
        comfort: String(state?.comfort_risk || "unknown").toLocaleLowerCase(),
        peak: String(state?.peak_risk || "unknown").toLocaleLowerCase(),
      };
    }).filter((row) => {
      const matchesQuery = !normalizedQuery ||
        row.zone.name.toLocaleLowerCase().includes(normalizedQuery) ||
        titleCase(row.roomType).toLocaleLowerCase().includes(normalizedQuery);
      return matchesQuery &&
        (typeFilter === "all" || row.roomType === typeFilter) &&
        (comfortFilter === "all" || row.comfort === comfortFilter) &&
        (peakFilter === "all" || row.peak === peakFilter);
    });

    return filtered.sort((a, b) => {
      let result = 0;
      if (sortKey === "zone") result = compareNullable(a.zone.name, b.zone.name);
      if (sortKey === "type") result = compareNullable(a.roomType, b.roomType);
      if (sortKey === "occupancy") {
        result = compareNullable(a.state?.occupancy_count, b.state?.occupancy_count);
      }
      if (sortKey === "temperature") {
        result = compareNullable(a.state?.temperature_c, b.state?.temperature_c);
      }
      if (sortKey === "load") result = compareNullable(a.state?.total_power_kw, b.state?.total_power_kw);
      if (sortKey === "comfort") {
        result = compareNullable(riskRank[a.comfort] ?? 99, riskRank[b.comfort] ?? 99);
      }
      if (sortKey === "peak") result = compareNullable(riskRank[a.peak] ?? 99, riskRank[b.peak] ?? 99);
      if (result === 0) result = compareNullable(a.zone.name, b.zone.name);
      return sortDirection === "asc" ? result : -result;
    });
  }, [comfortFilter, peakFilter, query, sortDirection, sortKey, typeFilter, zoneStates, zones]);

  const filtered = query !== "" || typeFilter !== "all" ||
    comfortFilter !== "all" || peakFilter !== "all";

  const resetFilters = () => {
    setQuery("");
    setTypeFilter("all");
    setComfortFilter("all");
    setPeakFilter("all");
  };

  const sort = (column: SortKey) => {
    if (column === sortKey) setSortDirection((direction) => direction === "asc" ? "desc" : "asc");
    else {
      setSortKey(column);
      setSortDirection("asc");
    }
  };

  const selectRow = (entityKey: string) => selectEntity(entityKey);
  useEffect(() => {
    const row = activeRowRef.current;
    const scroller = tableScrollRef.current;
    if (!row || !scroller) return;
    const rowTop = row.offsetTop;
    const rowBottom = rowTop + row.offsetHeight;
    const viewTop = scroller.scrollTop;
    const viewBottom = viewTop + scroller.clientHeight;
    if (rowTop >= viewTop && rowBottom <= viewBottom) return;
    scroller.scrollTo({
      top: Math.max(0, rowTop - scroller.clientHeight / 2 + row.offsetHeight / 2),
      behavior: "smooth",
    });
  }, [selectedEntityKey]);

  const onRowKeyDown = (event: KeyboardEvent<HTMLTableRowElement>, entityKey: string) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectRow(entityKey);
    }
  };

  return (
    <section data-tour-id="zone-state-table" className="card overflow-hidden" aria-labelledby="zone-state-heading">
      <div className="border-b border-border px-5 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 id="zone-state-heading" className="text-sm font-semibold">Zone state</h3>
            <p className="mt-0.5 text-[11px] text-text-muted">
              Showing <span className="font-medium tabular-nums text-text-secondary">{rows.length}</span> of{" "}
              <span className="font-medium tabular-nums text-text-secondary">{zones.length}</span> zones
            </p>
          </div>

          <div className="flex flex-1 flex-wrap items-center justify-end gap-2 lg:flex-nowrap">
            <label className="relative min-w-[210px] flex-1 lg:max-w-[290px]">
              <span className="sr-only">Search zones</span>
              <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
              <input value={query} onChange={(event) => setQuery(event.target.value)}
                placeholder="Search zone or type…"
                className="h-8 w-full rounded-lg border border-border bg-white pl-9 pr-3 text-[12px] outline-none transition focus:border-teal/50 focus:ring-2 focus:ring-teal/10" />
            </label>
            <label>
              <span className="sr-only">Filter by zone type</span>
              <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}
                className="h-8 rounded-lg border border-border bg-white px-3 text-[12px] text-text-secondary outline-none transition focus:border-teal/50 focus:ring-2 focus:ring-teal/10">
                <option value="all">All types</option>
                {roomTypes.map((roomType) => (
                  <option key={roomType} value={roomType}>{titleCase(roomType)}</option>
                ))}
              </select>
            </label>
            <label>
              <span className="sr-only">Filter by comfort status</span>
              <select value={comfortFilter}
                onChange={(event) => setComfortFilter(event.target.value as RiskFilter)}
                className="h-8 rounded-lg border border-border bg-white px-3 text-[12px] text-text-secondary outline-none transition focus:border-teal/50 focus:ring-2 focus:ring-teal/10">
                <option value="all">All comfort</option>
                <option value="normal">Comfort: normal</option>
                <option value="watch">Comfort: watch</option>
                <option value="high">Comfort: high</option>
              </select>
            </label>
            <label>
              <span className="sr-only">Filter by peak status</span>
              <select value={peakFilter} onChange={(event) => setPeakFilter(event.target.value as RiskFilter)}
                className="h-8 rounded-lg border border-border bg-white px-3 text-[12px] text-text-secondary outline-none transition focus:border-teal/50 focus:ring-2 focus:ring-teal/10">
                <option value="all">All peak risk</option>
                <option value="normal">Peak: normal</option>
                <option value="watch">Peak: watch</option>
                <option value="high">Peak: high</option>
              </select>
            </label>
            {filtered && (
              <button type="button" onClick={resetFilters}
                className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-[11px] font-medium text-text-muted transition hover:bg-surface-muted hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal/40">
                <RotateCcw size={13} /> Reset
              </button>
            )}
          </div>
        </div>
      </div>

      <div ref={tableScrollRef} className="max-h-[300px] overflow-auto overscroll-contain">
        <table className="w-full min-w-[920px] text-[13px]">
          <thead className="sticky top-0 z-10 bg-white/95 shadow-[0_1px_0_rgba(226,232,240,0.95)] backdrop-blur">
            <tr className="text-left text-xs">
              <SortHeader label="Zone" column="zone" active={sortKey === "zone"}
                direction={sortDirection} onSort={sort} />
              <SortHeader label="Type" column="type" active={sortKey === "type"}
                direction={sortDirection} onSort={sort} />
              <SortHeader label="Occupancy" column="occupancy" active={sortKey === "occupancy"}
                direction={sortDirection} onSort={sort} />
              <SortHeader label="Temp" column="temperature" active={sortKey === "temperature"}
                direction={sortDirection} onSort={sort} />
              <SortHeader label="Load" column="load" active={sortKey === "load"}
                direction={sortDirection} onSort={sort} />
              <SortHeader label="Comfort" column="comfort" active={sortKey === "comfort"}
                direction={sortDirection} onSort={sort} />
              <SortHeader label="Peak" column="peak" active={sortKey === "peak"}
                direction={sortDirection} onSort={sort} />
            </tr>
          </thead>
          <tbody>
            {zones.length === 0 && Array.from({ length: 8 }).map((_, rowIndex) => (
              <tr key={`sk-${rowIndex}`} className="border-t border-border/60">
                {Array.from({ length: 7 }).map((_, columnIndex) => (
                  <td key={columnIndex} className="px-5 py-2"><Skeleton className="h-4 w-16" /></td>
                ))}
              </tr>
            ))}
            {zones.length > 0 && rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-16 text-center">
                  <p className="text-[13px] font-medium text-text-secondary">No zones match these filters</p>
                  <button type="button" onClick={resetFilters}
                    className="mt-2 text-[12px] font-medium text-teal hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal/40">
                    Clear filters
                  </button>
                </td>
              </tr>
            )}
            {rows.map(({ zone, state, roomType }) => {
              const active = selectedEntityKey === zone.entity_key;
              return (
                <tr key={zone.entity_key} tabIndex={0}
                  ref={active ? activeRowRef : undefined}
                  aria-selected={active}
                  onClick={() => selectRow(zone.entity_key)}
                  onKeyDown={(event) => onRowKeyDown(event, zone.entity_key)}
                  className={`cursor-pointer border-t border-border/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-teal/40 ${
                    active ? "bg-teal-soft" : "hover:bg-surface-muted/60"
                  }`}>
                  <td className="px-5 py-2 font-medium">{zone.name}</td>
                  <td className="px-5 py-2 text-text-secondary">{titleCase(roomType)}</td>
                  <td className="px-5 py-2 tabular-nums">
                    {state?.occupancy_count == null ? "–" : `${state.occupancy_count} ppl`}
                  </td>
                  <td className="px-5 py-2 tabular-nums">{fmtTemp(state?.temperature_c)}</td>
                  <td className="px-5 py-2 tabular-nums">{fmtKw(state?.total_power_kw)}</td>
                  <td className="px-5 py-2"><StatusPill status={state?.comfort_risk} /></td>
                  <td className="px-5 py-2"><StatusPill status={state?.peak_risk} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
