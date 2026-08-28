# -*- coding: utf-8 -*-
"""Every script the pages ship actually parses.

A sweep that rewrites class strings has to put the quotes back.
`templates/catalog.html` came out of one migration reading

    (ok ?  font-medium"border-green-500/15 text-green-400" : "...")

- the opening quote a token too late, so `font-medium` is a bare
identifier and the string after it is a syntax error. That kills the
*whole* <script> block, not the one line: the catalog's track drawer,
release drawer, tab switcher and release filter all went dead at once,
and the registration chips the line draws never rendered at all.

Nothing caught it. The page still returned 200, Jinja still rendered,
`test_design_system.py` passed on the broken file, and the only symptom
was a console message nobody was reading. This file is the missing half
of `test_no_template_has_an_unterminated_tag`: that one guards markup a
sweep mangled, this one guards script a sweep mangled.

It compiles rather than runs, so it is cheap and total - every inline
block in every template plus every file in static/js, on every run.

Limits, stated plainly: parsing is not behaviour. A block that compiles
can still throw on the first line, select a class that no longer exists,
or compute the wrong thing. `test_design_system.py` covers the dead
selector case and `test_artist_eq_runtime.py` actually executes one
script; this test only proves the parser gets to the end.
"""
import io
import os
import re
import glob
import json
import shutil
import subprocess
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HARNESS = os.path.join(HERE, "js", "check_inline_scripts.js")

NODE = os.environ.get("SB_NODE_BIN") or shutil.which("node") or shutil.which("node.exe")

# Same bargain as tests/test_artist_eq_runtime.py: skipping is the right
# default because not every machine has Node, but a silent skip removes
# the protection without anyone noticing. Set SB_REQUIRE_JS_TESTS=1
# wherever the suite is expected to be complete.
_REQUIRED = os.environ.get("SB_REQUIRE_JS_TESTS") == "1"

needs_node = pytest.mark.skipif(
    NODE is None and not _REQUIRED,
    reason="node is not on PATH; set SB_REQUIRE_JS_TESTS=1 to make this fail "
           "instead of skip, or SB_NODE_BIN to point at a node binary")

# A <script> with a src is a file, checked separately; one with a type
# this repo does not execute is data. `#sbeq-config` and friends are
# application/json - valid JSON is not valid script, and treating them
# as script would fail every run.
JS_TYPES = {"", "text/javascript", "application/javascript"}

SCRIPT = re.compile(r'<script([^>]*)>(.*?)</script>', re.S | re.I)
HAS_SRC = re.compile(r'\bsrc\s*=')
TYPE_ATTR = re.compile(r'\btype\s*=\s*["\']([^"\']+)')


def _rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def _read(p):
    return io.open(p, encoding="utf8", errors="ignore").read()


def _blank(m):
    """Drop a Jinja tag, keeping the line count so line numbers survive.

    No `{{ }}` or `{% %}` in this repo currently spans a line, so this is
    exact today. If one ever does *inside a JS string literal*, the
    newline this puts back would break that string and show up here as a
    false positive - which is a loud, findable failure rather than a
    silent one, and the right trade against every line number after it
    drifting.
    """
    return "\n" * m.group(0).count("\n")


def _neutralise(js):
    """Make a Jinja-templated script parseable as plain JavaScript.

    Statements and comments vanish; expressions become `0`, which is
    valid wherever an interpolation is - a bare value, an argument, an
    object member, or inside a quoted string.
    """
    js = re.sub(r'\{#.*?#\}', _blank, js, flags=re.S)
    js = re.sub(r'\{%.*?%\}', _blank, js, flags=re.S)
    js = re.sub(r'\{\{.*?\}\}', lambda m: "0" + _blank(m), js, flags=re.S)
    return js


def _template_blocks():
    """Every executable inline <script>, padded to its true line number.

    The padding is what makes a failure actionable: V8 reports the line
    it choked on, and blank-filling everything above the block means that
    number is the line in the template rather than an offset into some
    fragment.
    """
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "templates", "**", "*.html"),
                              recursive=True)):
        src = _read(p)
        for i, m in enumerate(SCRIPT.finditer(src)):
            attrs, body = m.group(1), m.group(2)
            if HAS_SRC.search(attrs):
                continue
            t = TYPE_ATTR.search(attrs)
            if (t.group(1).lower() if t else "") not in JS_TYPES:
                continue
            if not body.strip():
                continue
            start = src.count("\n", 0, m.start(2))
            out.append({"id": "%s#%d" % (_rel(p), i),
                        "file": _rel(p),
                        "source": "\n" * start + _neutralise(body)})
    return out


def _js_files():
    return [{"id": _rel(p), "file": _rel(p), "source": _read(p)}
            for p in sorted(glob.glob(os.path.join(ROOT, "static", "js", "*.js")))]


def _compile(entries):
    """Run the batch through Node; return the entries that failed."""
    if not NODE or not os.path.exists(NODE):
        pytest.fail("no usable node binary (%r) - cannot parse-check the "
                    "pages' JavaScript" % (NODE,))
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
    try:
        json.dump(entries, handle)
        handle.close()
        proc = subprocess.run([NODE, HARNESS, handle.name],
                              capture_output=True, text=True, timeout=120,
                              cwd=ROOT)
        assert proc.returncode == 0, (
            "the parse-check harness itself failed to run:\n%s"
            % (proc.stderr or "")[:2000])
        return [r for r in json.loads(proc.stdout) if not r["ok"]]
    finally:
        os.unlink(handle.name)


def _report(bad, what):
    return "%d %s failed to parse. A syntax error kills the entire block, " \
           "not just the line - every handler it defines goes with it.\n%s" % (
               len(bad), what,
               "\n".join("  %s:%s  %s: %s"
                         % (r["id"].split("#")[0], r.get("line") or "?",
                            r.get("name"), r.get("message"))
                         for r in bad[:12]))


def test_the_javascript_runtime_is_available_when_it_is_required():
    """Guard the guard: if this suite is meant to cover the browser, say so."""
    if not _REQUIRED:
        pytest.skip("SB_REQUIRE_JS_TESTS is not set; JS coverage is optional here")
    assert NODE, (
        "SB_REQUIRE_JS_TESTS=1 but no node binary was found. Without it a "
        "sweep can mangle a quote in every template and the whole Python "
        "suite still reports green.")


@needs_node
def test_every_inline_template_script_parses():
    blocks = _template_blocks()
    assert blocks, "no inline scripts found - the extractor is broken, " \
                   "not the templates"
    bad = _compile(blocks)
    assert not bad, _report(bad, "inline template script(s)")


@needs_node
def test_every_static_script_parses():
    files = _js_files()
    assert files, "no files in static/js - the glob is broken"
    bad = _compile(files)
    assert not bad, _report(bad, "file(s) in static/js")


@needs_node
def test_the_checker_catches_the_bug_it_was_written_for():
    """Keeps the two tests above honest.

    Without this the file could rot into something that passes whatever
    the templates contain - a neutraliser that swallowed the whole script
    would look exactly like a clean run.
    """
    good = '''
      var html = "";
      ["pro", "mlc"].forEach(function (k) {
        var ok = !!reg[k];
        html += '<div class="border px-3 ' + (ok ? "font-medium border-sb-good/15" : "border-sb-crit/15") + '">' + k + "</div>";
      });
    '''
    # The exact shape the migration produced: the opening quote one token
    # too late, so `font-medium` is a bare identifier.
    broken = good.replace('(ok ? "font-medium border-sb-good/15"',
                          '(ok ?  font-medium"border-sb-good/15"')
    assert broken != good, "the fixture no longer contains the line it mangles"

    assert not _compile([{"id": "fixture-good", "file": "fixture.js",
                          "source": good}]), \
        "the checker rejects a script that is fine"

    bad = _compile([{"id": "fixture-broken", "file": "fixture.js",
                     "source": broken}])
    assert bad, "the checker passed the exact bug it was written to catch"
    assert bad[0]["name"] == "SyntaxError", bad[0]


@needs_node
def test_jinja_survives_neutralisation():
    """The neutraliser must not turn valid templated JS into a failure.

    Every false positive here costs somebody an investigation, so the
    interpolation shapes the templates actually use are pinned.
    """
    cases = {
        "bare value": 'var n = {{ count }};',
        "quoted": 'var s = "{{ name }}";',
        "argument": 'init({{ a }}, {{ b }});',
        "object member": 'var o = {k: {{ v }}};',
        "json filter": 'var d = {{ payload | tojson }};',
        "statement": '{% if x %}var a = 1;{% endif %}',
        "loop": '{% for k in keys %}push({{ k }});{% endfor %}',
        "comment": '{# nothing to see #}var z = 1;',
    }
    entries = [{"id": k, "file": "fixture.js", "source": _neutralise(v)}
               for k, v in cases.items()]
    bad = _compile(entries)
    assert not bad, "the Jinja neutraliser breaks valid templated JS:\n%s" % (
        "\n".join("  %s: %s" % (r["id"], r.get("message")) for r in bad))


def test_line_numbers_are_not_thrown_away():
    """The padding that makes a failure reportable is easy to lose.

    This asserts the offset arithmetic without needing Node: a block that
    starts on template line N must be padded with N newlines, so V8's
    reported line is the line somebody can open.
    """
    src = "<html>\n<body>\n<script>\nvar a = 1;\n</script>\n</html>\n"
    m = SCRIPT.search(src)
    start = src.count("\n", 0, m.start(2))
    padded = "\n" * start + _neutralise(m.group(2))
    # `var a = 1;` is on line 4 of the fragment above.
    assert padded.split("\n").index("var a = 1;") + 1 == 4, padded
