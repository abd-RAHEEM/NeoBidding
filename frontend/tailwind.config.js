/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#F3EFE7",
        surface: "#FBF9F4",
        "surface-raised": "#FFFFFF",
        ink: "#1B1F24",
        muted: "#6B6F76",
        hairline: "#DDD6C8",
        accent: {
          orange: "#D9480F",
          green: "#0B6E4F",
          amber: "#B7791F",
          slate: "#5B6470",
          brick: "#A3262A",
        },
      },
      fontFamily: {
        serif: ['"Instrument Serif"', "Georgia", "serif"],
        sans: ['"Instrument Sans"', "system-ui", "-apple-system", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        subtle: "0 1px 2px rgba(27, 31, 36, 0.04)",
        card: "0 1px 3px rgba(27, 31, 36, 0.06), 0 1px 2px rgba(27, 31, 36, 0.04)",
      },
    },
  },
  plugins: [],
}
