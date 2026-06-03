import type { Config } from "tailwindcss";

// Bloomberg-terminal-inspired dark palette: near-black bg, amber accents,
// green/red for up/down, monospace numerics.
const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: "#0a0e14",
          panel: "#0f141c",
          panelAlt: "#131a24",
          border: "#1e2733",
          text: "#c9d4e0",
          muted: "#6b7787",
          amber: "#f5a623",
          up: "#2ecc71",
          down: "#ff4d4f",
          accent: "#3b82f6",
        },
      },
      fontFamily: {
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
