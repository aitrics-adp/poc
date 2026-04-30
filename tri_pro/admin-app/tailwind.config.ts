import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: "#2563EB", soft: "#E6EEFB", deep: "#1E3A8A" },
        warn: "#F59E0B",
        danger: "#DC2626",
        success: "#16A34A",
      },
    },
  },
  plugins: [],
};
export default config;
