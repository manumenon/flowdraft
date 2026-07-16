import type { Config } from 'tailwindcss';

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class', // Toggle dark/light palettes via CSS classes
  theme: {
    extend: {
      colors: {
        theme: {
          // Dark Theme Colors
          darkBg: '#121214',
          darkSurface: '#1a1a1e',
          darkBorder: '#2d2d34',
          darkText: '#e1e1e6',
          // Light Theme Colors
          lightBg: '#f8f9fa',
          lightSurface: '#ffffff',
          lightBorder: '#dee2e6',
          lightText: '#212529',
        },
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        handwriting: ['Caveat', 'cursive'],
        mono: ['Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config;
