"use client";

import { cn } from "@/lib/utils";
import React, { type ReactNode } from "react";

interface AuroraBackgroundProps extends React.HTMLProps<HTMLDivElement> {
  children: ReactNode;
  showRadialGradient?: boolean;
}

export const AuroraBackground = ({
  className,
  children,
  showRadialGradient = true,
  ...props
}: AuroraBackgroundProps) => {
  return (
    <div
      className={cn(
        "transition-bg relative flex h-[100vh] flex-col items-center justify-center bg-[#f3f7f4] text-slate-950 dark:bg-[#06130f]",
        className,
      )}
      {...props}
    >
      <div
        className="absolute inset-0 overflow-hidden"
        style={
          {
            "--aurora":
              "repeating-linear-gradient(100deg,#35c985_8%,#dff8ea_14%,#a6edc5_18%,#6ed9a7_24%,#f5fbf8_30%,#86e5b7_36%,#e8fbf1_42%,#bdf3d5_48%,#4fcf93_54%)",

            "--dark-gradient":
              "repeating-linear-gradient(100deg,#06130f_0%,#0b1b16_7%,transparent_10%,transparent_12%,#06130f_16%)",

            "--white-gradient":
              "repeating-linear-gradient(100deg,#ffffff_0%,#f2fff8_7%,transparent_10%,transparent_12%,#eafff4_16%)",

            "--blue-300": "#bdf3d5",
            "--blue-400": "#24bf7a",
            "--blue-500": "#35c985",
            "--indigo-300": "#a6edc5",
            "--violet-200": "#f5fbf8",

            "--black": "#0f1f1a",
            "--white": "#f5fbf8",
            "--transparent": "transparent",
          } as React.CSSProperties
        }
      >
        {/* Light-mode prism / refraction layer */}
        <div
          className="pointer-events-none absolute inset-0 opacity-48 blur-[18px] mix-blend-normal dark:opacity-20 dark:mix-blend-screen"
          style={
            {
              backgroundImage: `
                linear-gradient(
                  108deg,
                  rgba(214, 250, 231, 0.18) 0%,
                  rgba(132, 229, 182, 0.28) 12%,
                  rgba(255,255,255,0.18) 22%,
                  rgba(58, 204, 139, 0.24) 34%,
                  rgba(183, 244, 216, 0.24) 46%,
                  rgba(255,255,255,0.18) 58%,
                  rgba(113, 219, 169, 0.24) 70%,
                  rgba(233, 251, 242, 0.2) 84%,
                  rgba(78, 200, 142, 0.18) 100%
                )
              `,
              backgroundSize: "220% 220%",
              backgroundPosition: "50% 50%",
              maskImage:
                "radial-gradient(circle at 76% 24%, black 0%, rgba(0,0,0,0.95) 20%, transparent 62%)",
              WebkitMaskImage:
                "radial-gradient(circle at 76% 24%, black 0%, rgba(0,0,0,0.95) 20%, transparent 62%)",
            } as React.CSSProperties
          }
        />

        {/* Main aurora */}
        <div
          className={cn(
            `after:animate-aurora pointer-events-none absolute -inset-[10px]
             [background-image:var(--white-gradient),var(--aurora)]
             [background-size:320%,_220%]
             [background-position:50%_50%,50%_50%]
             opacity-95 blur-[5px] filter will-change-transform
             mix-blend-normal dark:mix-blend-normal
             [--aurora:repeating-linear-gradient(100deg,var(--blue-500)_8%,var(--violet-200)_14%,var(--indigo-300)_18%,var(--blue-300)_24%,var(--white)_30%,#8be8b9_36%,var(--white)_42%,#d8f8e8_48%,var(--blue-400)_54%)]
             [--dark-gradient:repeating-linear-gradient(100deg,var(--black)_0%,var(--black)_7%,var(--transparent)_10%,var(--transparent)_12%,var(--black)_16%)]
             [--white-gradient:repeating-linear-gradient(100deg,var(--white)_0%,#f4fff9_7%,var(--transparent)_10%,var(--transparent)_12%,#ecfbf3_16%)]
             after:absolute after:inset-0
             after:[background-image:var(--white-gradient),var(--aurora)]
             after:[background-size:220%,_120%]
             after:[background-attachment:fixed]
             after:mix-blend-overlay
             after:content-[""]
             dark:opacity-75 dark:blur-[10px]
             dark:[background-image:var(--dark-gradient),var(--aurora)]
             dark:invert-0
             after:dark:[background-image:var(--dark-gradient),var(--aurora)]
             after:dark:mix-blend-screen`,
            showRadialGradient &&
              `[mask-image:radial-gradient(ellipse_at_78%_18%,black_12%,var(--transparent)_72%)]`,
          )}
        />
      </div>

      {children}
    </div>
  );
};
