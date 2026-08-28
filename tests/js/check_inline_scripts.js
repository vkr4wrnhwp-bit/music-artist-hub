/* Parse-check a batch of JavaScript sources without running them.
 *
 * Reads a JSON manifest — [{id, file, source}, ...] — compiles each entry
 * with vm.Script, and prints [{id, ok, message, line, column}, ...].
 *
 * vm.Script compiles and throws on a syntax error but never executes, so
 * this is `node --check` semantics for many sources in one process. That
 * matters: the suite checks ~100 sources, and spawning a node per source
 * costs more than the rest of the Python suite put together.
 *
 * Sources are compiled as classic scripts, which is what a <script> with
 * no type attribute is. A `type="module"` block would need
 * SourceTextModule and the --experimental-vm-modules flag; the caller is
 * responsible for not sending one.
 *
 *     node check_inline_scripts.js manifest.json
 */
"use strict";

const fs = require("fs");
const vm = require("vm");

/* V8 puts the location in the stack preamble rather than on the error:
 *
 *     templates/catalog.html:609
 *           html += '...' + (ok ?  font-medium"..." : "...")
 *                                               ^^^^^^^^^^^
 *     SyntaxError: Unexpected string
 *
 * so the line number has to be read back out of it. */
function locate(err) {
  const stack = String(err && err.stack ? err.stack : "");
  const head = stack.split("\n")[0] || "";
  const m = head.match(/:(\d+)$/);
  return m ? parseInt(m[1], 10) : null;
}

function main() {
  const manifestPath = process.argv[2];
  if (!manifestPath) {
    process.stderr.write("usage: check_inline_scripts.js <manifest.json>\n");
    process.exit(2);
  }

  const entries = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  const results = entries.map(function (entry) {
    try {
      /* Compile only. Nothing in these sources runs, so a template that
       * calls fetch() or touches document at load is still safe here. */
      new vm.Script(entry.source, { filename: entry.file });
      return { id: entry.id, ok: true };
    } catch (err) {
      return {
        id: entry.id,
        ok: false,
        name: err && err.name ? err.name : "Error",
        message: err && err.message ? err.message : String(err),
        line: locate(err),
      };
    }
  });

  process.stdout.write(JSON.stringify(results));
}

main();
