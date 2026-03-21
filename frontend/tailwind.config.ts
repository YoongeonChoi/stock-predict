import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        border: "var(--border)",
        text: "var(--text)",
        "text-secondary": "var(--text-secondary)",
        accent: "var(--accent)",
        positive: "var(--positive)",
        negative: "var(--negative)",
        warning: "var(--warning)",
      },
    },
  },
  plugins: [],
};
export default config;
