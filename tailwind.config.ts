import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#12161f",
        panel: "#1e2430",
        line: "#2a3241",
        muted: "#8b95a7",
        brand: "#3b82f6",
      },
    },
  },
  plugins: [],
};
export default config;
