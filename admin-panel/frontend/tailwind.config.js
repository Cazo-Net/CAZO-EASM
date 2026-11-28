/** @type {import('tailwindcss').Config} */
// Colours follow the main app's "Crimson on black" palette
// (frontend/src/app/globals.css): neutral black and grey surfaces instead of
// zinc, crimson as the one accent. `blue` is remapped so existing classes
// pick it up.
const ink = {
  50: "hsl(0 0% 97%)",
  100: "hsl(0 0% 95%)",
  200: "hsl(0 0% 86%)",
  300: "hsl(0 0% 78%)",
  400: "hsl(0 0% 68%)",
  500: "hsl(0 0% 62%)", // secondary text; AA on ink-900 and ink-950
  600: "hsl(0 0% 48%)",
  700: "hsl(0 0% 21%)",
  800: "hsl(0 0% 15%)",
  900: "hsl(0 0% 8%)",
  950: "hsl(0 0% 4.5%)",
};
const signal = {
  50: "hsl(350 100% 97%)",
  100: "hsl(350 96% 93%)",
  200: "hsl(350 96% 86%)",
  300: "hsl(351 94% 78%)",
  400: "hsl(352 90% 68%)",
  500: "hsl(352 82% 58%)",
  600: "hsl(350 82% 50%)",
  700: "hsl(350 82% 44%)",
  800: "hsl(350 78% 36%)",
  900: "hsl(350 70% 28%)",
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
