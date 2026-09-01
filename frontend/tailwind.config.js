/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        gg: {
          dark: "#0b0e14",
          surface: "#161b22",
          gold: "#e6b04c",
          goldHover: "#ffd275",
          red: "#e53e3e",
          green: "#2ecc71",
          blue: "#3498db",
          felt: "#133e29",
          feltBorder: "#0d2b1c",
          feltOuter: "#2c221e",
        }
      },
      boxShadow: {
        'glow-gold': '0 0 15px rgba(230, 176, 76, 0.4)',
        'glow-cyan': '0 0 20px rgba(56, 189, 248, 0.5)',
        'table': 'inset 0 0 80px rgba(0,0,0,0.8), 0 20px 50px rgba(0,0,0,0.9)',
      }
    },
  },
  plugins: [],
}
