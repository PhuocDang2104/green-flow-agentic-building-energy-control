"use client";

export default function SectionHero() {
  return (
    <div className="gf-section" data-section="0">
      <div className="flex w-full max-w-5xl flex-col items-center text-center">
        <span data-reveal className="gf-card mb-6 rounded-full px-4 py-1.5 text-[12px] font-medium"
              style={{ color: "var(--gf-green)" }}>
          Agentic digital twin · building intelligence
        </span>
        <h1 className="text-balance text-[clamp(34px,6vw,68px)] font-semibold leading-[1.05] tracking-tight"
            style={{ color: "var(--gf-ink)" }}>
          <span className="gf-line-mask"><span data-reveal className="gf-line-inner">
            The <span className="gf-em">all-in-one</span> platform
          </span></span>
          <span className="gf-line-mask"><span data-reveal className="gf-line-inner">
            for building intelligence
          </span></span>
        </h1>
        <p data-reveal className="mt-5 max-w-xl text-[15px]" style={{ color: "var(--gf-muted)" }}>
          Understand, predict and optimize energy across your building —
          with a living 3D digital twin and safe agent actions.
        </p>
      </div>
    </div>
  );
}
