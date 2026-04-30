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
      fontSize: {
        // 어르신 모드용 큰 폰트
        elder: ["22px", { lineHeight: "1.5" }],
        "elder-lg": ["28px", { lineHeight: "1.4" }],
      },
    },
  },
  plugins: [],
};
export default config;
