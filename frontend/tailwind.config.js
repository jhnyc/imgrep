/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#a0c4ff",
        secondary: "#bdb2ff",
        // Excalidraw pastel palette
        'ex-red': '#ffadad',
        'ex-orange': '#ffd6a5',
        'ex-yellow': '#fdffb6',
        'ex-green': '#caffbf',
        'ex-cyan': '#9bf6ff',
        'ex-blue': '#a0c4ff',
        'ex-purple': '#bdb2ff',
        'ex-pink': '#ffc6ff',
        'ex-gray': '#e2e2e2',
        // Dark mode canvas
        'canvas-dark': '#1a1a1a',
        'canvas-gray': '#404040',
      },
      fontFamily: {
        'hand-drawn': ['Virgil', 'Kalam', 'Patrick Hand', 'cursive'],
      },
      boxShadow: {
        'sketchy': '3px 3px 0 #1a1a1a',
        'sketchy-sm': '2px 2px 0 #1a1a1a',
        'sketchy-lg': '4px 4px 0 #1a1a1a',
      },
    },
  },
  plugins: [],
}
