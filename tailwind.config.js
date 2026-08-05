module.exports = {
  content: [
    "./flask_app/templates/**/*.html",
    "./flask_app/static/js/**/*.js"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Poppins", "ui-sans-serif", "system-ui", "sans-serif"]
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
