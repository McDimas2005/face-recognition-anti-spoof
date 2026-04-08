import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#f5f1ea",
        ink: "#12251b",
        accent: "#147a5b",
        sand: "#efe4d1",
        warning: "#b85c28",
      },
      boxShadow: {
        card: "0 20px 60px rgba(12, 34, 26, 0.08)",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;

