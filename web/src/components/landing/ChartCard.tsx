"use client";

/**
 * A chart image presented as a hover-card: it lifts/scales with a deeper shadow
 * on hover and reveals a small, professional info popup with the key numbers.
 */
export default function ChartCard({
  src, alt, title, caption, stats, className = "", popupClass = "",
}: {
  src: string;
  alt: string;
  title: string;
  caption?: string;
  stats: { label: string; value: string }[];
  className?: string;
  popupClass?: string;
}) {
  return (
    <div className={`gf-chartcard group ${className}`} tabIndex={0}>
      <img src={src} alt={alt} draggable={false} className="w-full select-none"
           style={{ objectFit: "contain" }} />
      <div className={`gf-chartpop ${popupClass}`} role="tooltip">
        <p className="gf-chartpop-title">{title}</p>
        <div className="gf-chartpop-stats">
          {stats.map((s) => (
            <div key={s.label} className="gf-chartpop-row">
              <span>{s.label}</span>
              <strong>{s.value}</strong>
            </div>
          ))}
        </div>
        {caption && <p className="gf-chartpop-cap">{caption}</p>}
      </div>
    </div>
  );
}
