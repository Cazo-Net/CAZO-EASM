/** @type {import('tailwindcss').Config} */
// Colours follow the main app's "Ink & Signal" palette (frontend/src/app/globals.css):
// navy-ink neutrals instead of grey zinc, signal blue as the one accent.
const ink = {
  50: "hsl(220 25% 97%)",
  100: "hsl(220 25% 94%)",
  200: "hsl(220 20% 86%)",
  300: "hsl(220 16% 78%)",
  400: "hsl(220 13% 68%)",
  500: "hsl(220 13% 60%)", // secondary text; AA on ink-900 and ink-950
  600: "hsl(220 12% 48%)",
  700: "hsl(225 18% 22%)",
  800: "hsl(225 18% 16%)",
  900: "hsl(225 28% 9%)",
  950: "hsl(225 35% 6%)",
};
const signal = {
  50: "hsl(221 100% 97%)",
  100: "hsl(221 96% 93%)",
  200: "hsl(221 96% 86%)",
  300: "hsl(221 94% 78%)",
  400: "hsl(221 94% 70%)",
  500: "hsl(221 92% 62%)",
  600: "hsl(221 83% 53%)",
  700: "hsl(222 78% 46%)",
  800: "hsl(223 72% 38%)",
  900: "hsl(224 65% 30%)",
};
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: { zinc: ink, blue: signal },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "-apple-system", "sans-serif"],
      },
    },
  },
  plugins: [],
};
