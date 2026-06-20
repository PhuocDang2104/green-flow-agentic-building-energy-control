"use client";

/** Floating chart image with 3D tilt + soft shadow. Parallax via data-parallax. */
export default function FloatingChart({
  src, alt, className = "", depth = 1, tilt = -8,
}: {
  src: string; alt: string; className?: string; depth?: number; tilt?: number;
}) {
  return (
    <div
      className={`relative ${className}`}
      data-parallax={depth}
      style={{ transformStyle: "preserve-3d" }}
    >
      <img
        src={src}
        alt={alt}
        className="h-auto w-full select-none"
        draggable={false}
        style={{
          transform: `perspective(1000px) rotateY(${tilt}deg) rotateX(4deg)`,
          filter: "drop-shadow(0 26px 40px rgba(0,60,30,0.22))",
          objectFit: "contain",
        }}
      />
    </div>
  );
}
