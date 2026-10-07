// Tokens do protótipo aprovado (5F.9): slate de base. Destaque teal (decisão
// do dono em 2026-10-06, 5H): trocar a cor do site é mudar só `destaque`.
const colors = require("tailwindcss/colors");

module.exports = {
  content: ["./app/templates/**/*.html", "./app/web/**/*.py"],
  theme: {
    extend: {
      colors: {
        destaque: colors.teal,
      },
      fontFamily: {
        sans: ['"Public Sans"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
