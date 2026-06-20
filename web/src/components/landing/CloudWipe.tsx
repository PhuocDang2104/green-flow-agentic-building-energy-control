"use client";

import { forwardRef } from "react";

// Full-screen mist overlay used for the cinematic 2 -> 3 transition. The
// controller animates opacity/scale via GSAP; it never stays visible.
const CloudWipe = forwardRef<HTMLDivElement>((_props, ref) => {
  return <div ref={ref} className="gf-cloud-wipe" aria-hidden />;
});
CloudWipe.displayName = "CloudWipe";
export default CloudWipe;
