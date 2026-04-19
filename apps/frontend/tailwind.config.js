/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0d0d0d",
          raised: "#141414",
          border: "#262626",
          muted: "#a3a3a3",
        },
      },
    },
  },
  plugins: [],
};
