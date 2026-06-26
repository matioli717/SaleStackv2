/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        'brand': {
          500: '#ff0055',
          600: '#e6004c',
        },
        'accent': '#00e5ff',
        'surface': '#0a0a0a',
        'gold': '#ffd400',
      },
      fontFamily: {
        'display': ['Inter', 'sans-serif'],
        'body': ['Inter', 'sans-serif'],
      },
      letterSpacing: {
        'widest-xl': '0.25em',
      },
    },
  },
  plugins: [],
}
