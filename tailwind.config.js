module.exports = {
  content: [
    "./backend/app/templates/**/*.html",
    "./backend/app/static/js/**/*.js"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"]
      }
    }
  },
  plugins: [
    require("daisyui"),
    require("@tailwindcss/typography")
  ],
  daisyui: {
    themes: ["light"]
  }
};
