"use client";

import type React from "react";

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));
const smooth = (start: number, end: number, value: number) => {
  const t = clamp01((value - start) / (end - start));
  return t * t * (3 - 2 * t);
};

export default function PinnedPieChart({ progress }: { progress: number }) {
  const travel = smooth(2, 3, progress);
  const show = smooth(1.84, 2.06, progress) * (1 - smooth(3.18, 3.42, progress));
  const x = 79 - 53 * travel;
  const y = 34 + 18 * travel;
  const width = 390 + 180 * travel;
  const rotate = -2.5 + 2.5 * travel;

  return (
    <div
      className="gf-pinned-pie"
      style={
        {
          opacity: show,
          pointerEvents: show > 0.85 ? "auto" : "none",
          transform: `translate3d(${x}vw, ${y}vh, 0) translate(-50%, -50%) rotate(${rotate}deg)`,
          width,
        } as React.CSSProperties
      }
      aria-hidden={show < 0.2}
    >
      <div className="gf-pinned-pie-card gf-chartcard" tabIndex={show > 0.85 ? 0 : -1}>
        <img
          src="/assets/landing/HVAC_light_pie.png"
          alt="Energy share by end use - HVAC 48%, Lighting 22%"
          draggable={false}
          className="w-full select-none"
          style={{ objectFit: "contain" }}
        />
        <div className="gf-chartpop gf-pinned-pie-pop" role="tooltip">
          <p className="gf-chartpop-title">End-use energy share</p>
          <div className="gf-chartpop-stats">
            {[
              ["HVAC", "48%"],
              ["Lighting", "22%"],
              ["Office equipment", "12%"],
              ["Other loads", "18%"],
            ].map(([label, value]) => (
              <div key={label} className="gf-chartpop-row">
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          <p className="gf-chartpop-cap">Hanoi commercial buildings</p>
        </div>
      </div>
    </div>
  );
}
