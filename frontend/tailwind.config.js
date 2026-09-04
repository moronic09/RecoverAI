/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        paper: '#F7F5F0',
        ink: '#12213D',
        'paper-line': '#DDD8CC',
        revival: '#0F8B5C',
        flatline: '#B4472F',
        brand: {
          50: '#e5f5ee', 100: '#c9eadb', 500: '#0F8B5C', 600: '#0b704a', 700: '#095b3d', 900: '#063d2a',
        },
        surface: {
          DEFAULT: '#0f172a',
          card: '#1e293b',
          border: '#334155',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
