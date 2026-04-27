import type { Config } from "tailwindcss";
import tailwindcssAnimate from "tailwindcss-animate";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./context/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      colors: {
        base: "hsl(var(--bg-base))",
        surface: "hsl(var(--bg-surface))",
        raised: "hsl(var(--bg-raised))",
        "subtle-border": "hsl(var(--border-subtle))",
        accent: {
          DEFAULT: "hsl(var(--accent))",
          hover: "hsl(var(--accent-hover))",
          glow: "hsl(var(--accent-glow))",
        },
        "t-primary": "hsl(var(--text-primary))",
        "t-secondary": "hsl(var(--text-secondary))",
        "t-muted": "hsl(var(--text-muted))",
        "risk-low": "hsl(var(--risk-low))",
        "risk-medium": "hsl(var(--risk-medium))",
        "risk-high": "hsl(var(--risk-high))",
        "risk-critical": "hsl(var(--risk-critical))",
        background: "hsl(var(--bg-base))",
        foreground: "hsl(var(--text-primary))",
        card: {
          DEFAULT: "hsl(var(--bg-surface))",
          foreground: "hsl(var(--text-primary))",
        },
        popover: {
          DEFAULT: "hsl(var(--bg-raised))",
          foreground: "hsl(var(--text-primary))",
        },
        primary: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--primary-foreground, 0 0% 100%))",
        },
        secondary: {
          DEFAULT: "hsl(var(--bg-raised))",
          foreground: "hsl(var(--text-primary))",
        },
        muted: {
          DEFAULT: "hsl(var(--bg-raised))",
          foreground: "hsl(var(--text-secondary))",
        },
        destructive: {
          DEFAULT: "hsl(var(--risk-critical))",
          foreground: "hsl(0 0% 100%)",
        },
        border: "hsl(var(--border-subtle))",
        input: "hsl(var(--border-subtle))",
        ring: "hsl(var(--accent))",
      },
    },
  },
  plugins: [tailwindcssAnimate],
};

export default config;
