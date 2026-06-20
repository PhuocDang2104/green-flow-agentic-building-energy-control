"use client";

const LABELS = [
  "Hero", "Global energy challenge", "Controllable loads",
  "Hanoi breakdown", "El Niño heat risk", "Key problem", "Get started",
];

export default function SectionDots({
  count, active, onNav,
}: { count: number; active: number; onNav: (i: number) => void }) {
  return (
    <div className="gf-dots" role="tablist" aria-label="Section navigation">
      {Array.from({ length: count }).map((_, i) => (
        <button
          key={i}
          role="tab"
          aria-selected={active === i}
          aria-label={LABELS[i] || `Section ${i + 1}`}
          className={`gf-dot ${active === i ? "is-active" : ""}`}
          onClick={() => onNav(i)}
        />
      ))}
    </div>
  );
}
