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
        surface: {
          0: 'var(--surface-0)',
          1: 'var(--surface-1)',
          2: 'var(--surface-2)',
          3: 'var(--surface-3)',
        },
        border: {
          subtle: 'var(--border-subtle)',
          themed: 'var(--border-default)',
          strong: 'var(--border-strong)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          soft: 'var(--accent-soft)',
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        handwriting: ['Caveat', 'cursive'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'glow-blue': '0 0 15px rgba(59, 130, 246, 0.5)',
        'glow-emerald': '0 0 15px rgba(16, 185, 129, 0.5)',
        'glow-violet': '0 0 15px rgba(139, 92, 246, 0.5)',
        'glow-amber': '0 0 15px rgba(245, 158, 11, 0.5)',
        'glow-rose': '0 0 15px rgba(244, 63, 94, 0.5)',
        'premium': '0 10px 30px -10px rgba(0, 0, 0, 0.5)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
} satisfies Config;
