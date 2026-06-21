"use client";

export default function SectionHero() {
  return (
    <div className="gf-section is-visible" data-section="0">
      <div className="flex w-full max-w-5xl flex-col items-center text-center"
           style={{ transform: "translateY(-21vh)" }}>
        <h1 className="gf-hero-title text-balance text-[42px] font-semibold leading-[1.05] sm:text-[54px] lg:text-[62px]"
            style={{ color: "var(--gf-ink)" }}>
          <span className="gf-line-mask"><span data-reveal className="gf-line-inner">
            The <span className="gf-em">all-in-one</span> platform
          </span></span>
          <span className="gf-line-mask"><span data-reveal className="gf-line-inner">
            for building intelligence
          </span></span>
        </h1>
        <p data-reveal className="gf-hero-sub mt-5 max-w-xl text-[16px] leading-7" style={{ color: "var(--gf-muted)" }}>
          Understand, predict and optimize energy across your building —
          with a living 3D digital twin and safe agent actions.
        </p>
      </div>
    </div>
  );
}
