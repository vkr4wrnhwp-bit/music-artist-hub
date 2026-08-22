/** Content sources for the Street Banker stylesheet.
 *
 *  Templates alone are not enough. rackdsp.js and the other browser
 *  modules assemble class strings at runtime - "sw h-7 w-7 text-[11px]",
 *  "fader w-28", the lane and knob classes - so scanning only .html would
 *  drop every class the Rack generates and produce a stylesheet that looks
 *  correct right up until somebody opens the Rack.
 *
 *  The .py files are here because a few routes and config modules carry
 *  class strings for badges and status chips.
 *
 *  Paths are relative to the repo root, so this rebuilds anywhere:
 *
 *      npm install tailwindcss@3
 *      npx tailwindcss -c tools/tailwind.config.js -i tools/tailwind-input.css \
 *          -o static/css/tailwind.css --minify
 *
 *  Then bump the ?v= on the <link> in the templates and VERSION in
 *  static/js/sw.js, or browsers keep serving the old sheet.
 */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
    "./*.py",
  ],
  darkMode: "class",
  theme: { extend: {} },
  plugins: [],
};
