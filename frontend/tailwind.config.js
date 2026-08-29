/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Semantic names rather than colour names, so the dark theme and the
        // high-contrast theme can redefine them without every component
        // changing. Values come from CSS variables set in index.css.
        ink: "rgb(var(--ink) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        faint: "rgb(var(--faint) / <alpha-value>)",
        paper: "rgb(var(--paper) / <alpha-value>)",
        raised: "rgb(var(--raised) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)",
        brand: "rgb(var(--brand) / <alpha-value>)",
        "brand-soft": "rgb(var(--brand-soft) / <alpha-value>)",
        good: "rgb(var(--good) / <alpha-value>)",
        warn: "rgb(var(--warn) / <alpha-value>)",
        bad: "rgb(var(--bad) / <alpha-value>)",
      },
      fontFamily: {
        // The CJK stacks are separate because a font that renders Hangul well
        // often renders hanzi badly, and a learner copying a character needs
        // the shape to be right.
        sans: ["var(--font-ui)", "system-ui", "sans-serif"],
        ko: ["var(--font-ko)", "system-ui", "sans-serif"],
        ja: ["var(--font-ja)", "system-ui", "sans-serif"],
        zh: ["var(--font-zh)", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        pop: { "50%": { transform: "scale(1.06)" } },
        shake: {
          "20%, 60%": { transform: "translateX(-4px)" },
          "40%, 80%": { transform: "translateX(4px)" },
        },
      },
      animation: {
        "fade-up": "fade-up .22s ease-out",
        pop: "pop .3s ease-out",
        shake: "shake .32s ease-in-out",
      },
    },
  },
  plugins: [],
};
