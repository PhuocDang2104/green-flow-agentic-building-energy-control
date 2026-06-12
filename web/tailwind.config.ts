import type { Config } from "tailwindcss";

// GreenFlow design tokens (GREENFLOW_UI_UX_SPEC §5)
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#F8FAFC",
        surface: "#FFFFFF",
        "surface-muted": "#F1F5F9",
        border: "#E2E8F0",
        "text-primary": "#0F172A",
        "text-secondary": "#64748B",
        "text-muted": "#94A3B8",
        teal: { DEFAULT: "#0F766E", light: "#CCFBF1", soft: "#F0FDFA" },
        success: "#16A34A",
        warning: "#F59E0B",
        danger: "#DC2626",
        info: "#2563EB",
      },
      borderRadius: {
        card: "20px",
        button: "12px",
      },
      boxShadow: {
        card: "0 8px 24px rgba(15, 23, 42, 0.06)",
        floating: "0 16px 40px rgba(15, 23, 42, 0.12)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
