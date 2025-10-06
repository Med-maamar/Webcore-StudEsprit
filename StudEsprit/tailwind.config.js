/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './templates/**/*.html',
    './dashboard/templates/**/*.html',
    './node_modules/flowbite/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        esprit: {
          red: '#c8102e',
          dark: '#121217',
          light: '#f8f9fb',
          gray: '#4b5563',
        },
      },
      borderRadius: {
        '2xl': '1rem',
      },
    },
  },
  plugins: [require('flowbite/plugin')],
}
