/**
 * Tailwind build config for the FAIRGAME SPA.
 *
 * Replaces the old runtime `cdn.tailwindcss.com` JIT script (which could not
 * be pinned with SRI) with a pre-built, self-hosted stylesheet. The `content`
 * globs are scanned for the utility classes actually used across the HTML
 * partials and the JS bundles; the theme mirrors the tokens the CDN config
 * used inline (blue -> indigo brand + the loaded webfonts).
 *
 * Rebuild after changing markup/classes:
 *   cd web && npm install && npm run build:css
 */
module.exports = {
  content: [
    "./index.html",
    "./partials/**/*.html",
    "./js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        blue: {
          50: "#eef1ff", 100: "#e0e7ff", 200: "#c7d2fe", 300: "#a5b4fc",
          400: "#818cf8", 500: "#6366f1", 600: "#4f46e5", 700: "#4338ca",
          800: "#3730a3", 900: "#312e81",
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
        display: ['"Schibsted Grotesk"', "ui-sans-serif", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
    },
  },
};
