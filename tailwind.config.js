module.exports = {
  content: [
    "./templates/**/*.html",        // global templates
    "./**/templates/**/*.html",     // app-specific templates
    "./static/src/**/*.{js,jsx,ts,tsx}" // optional if you use JS
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
