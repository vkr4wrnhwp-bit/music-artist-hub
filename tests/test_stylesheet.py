"""The stylesheet is built, committed, and therefore able to go stale.

Swapping the Tailwind Play CDN for a built file trades 120 kB of runtime
compiler for 14 kB of static CSS. The cost of that trade is a new failure
mode: add a class to a template, forget to rebuild, and the page renders
without it. Nothing crashes. Nothing logs. It just looks wrong, and only
on the page you were last editing.

So the suite samples the classes actually used across the templates and
fails when the stylesheet does not carry them. Rebuild from the repo root:

    npm install tailwindcss@3
    npx tailwindcss -c tools/tailwind.config.js \\
        -i tools/tailwind-input.css \\
        -o static/css/tailwind.css --minify

Then bump the ?v= on the <link> and VERSION in static/js/sw.js, or
browsers keep serving the old sheet.
"""
import io
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(HERE, "static", "css", "tailwind.css")

# Enough of Tailwind's vocabulary to tell "this page uses utilities" from
# "this page is styled entirely by its own CSS".
TW_PREFIXES = ("flex", "grid", "text-", "bg-", "border-", "rounded",
               "w-", "h-", "p-", "px-", "py-", "m-", "mx-", "my-", "gap-",
               "font-", "items-", "justify-", "space-", "max-w-", "min-h-")
TW_BARE = {"block", "inline", "hidden", "relative", "absolute", "fixed",
           "truncate", "uppercase", "italic", "underline"}


def _css():
    return io.open(CSS, encoding="utf8").read()


def test_the_stylesheet_is_committed():
    assert os.path.exists(CSS), "static/css/tailwind.css is missing"
    assert os.path.getsize(CSS) > 20000, "stylesheet looks truncated"


def test_no_template_still_pulls_the_cdn_compiler():
    """cdn.tailwindcss.com is the JIT compiler, not a stylesheet - it is
    120 kB of JavaScript that generates CSS in the browser on every page
    load, and Tailwind's own docs say not to ship it."""
    import glob
    offenders = []
    for p in glob.glob(os.path.join(HERE, "templates", "**", "*.html"),
                       recursive=True):
        if "cdn.tailwindcss.com" in io.open(p, encoding="utf8").read():
            offenders.append(os.path.basename(p))
    assert not offenders, "still loading the CDN compiler: %s" % offenders


def test_every_template_that_needs_styles_links_the_stylesheet():
    """A page that loaded the CDN before must link the built file now, or
    it renders unstyled."""
    import glob
    missing = []
    for p in glob.glob(os.path.join(HERE, "templates", "**", "*.html"),
                       recursive=True):
        s = io.open(p, encoding="utf8").read()
        # Only pages that carry their own <head>; the rest inherit it.
        if "<head>" not in s:
            continue
        # A page using no Tailwind utilities does not need the sheet.
        # login.html is styled entirely by its own lsr-* stylesheet.
        # Anchor on the token start: "w-" matches inside "lsr-row-title"
        # otherwise, and every custom class looks like a utility.
        if not any(t.startswith(TW_PREFIXES) or t in TW_BARE
                   for blob in re.findall(r'class="([^"]*)"', s)
                   for t in blob.split()):
            continue
        if "/static/css/tailwind.css" not in s:
            missing.append(os.path.basename(p))
    assert not missing, "no stylesheet link: %s" % missing


# --- staleness -----------------------------------------------------------

def _used_classes():
    """Classes appearing in class="..." across every template."""
    import glob
    used = set()
    for p in glob.glob(os.path.join(HERE, "templates", "**", "*.html"),
                       recursive=True):
        s = io.open(p, encoding="utf8").read()
        for blob in re.findall(r'class="([^"]*)"', s):
            # Skip Jinja expressions - the class list inside them is
            # conditional and often split across branches.
            if "{" in blob:
                continue
            for c in blob.split():
                used.add(c)
    return used


_HEX = re.compile(r'\\([0-9a-fA-F]{1,6}) ?')


def _unescaped_css():
    """Tailwind escapes selectors two different ways: simple characters
    get a backslash (text-[9px] -> .text-\\[9px\\]) but others become hex
    escapes (a comma is \\2c followed by a space). Reversing both is more
    reliable than trying to reproduce the escaping."""
    css = _HEX.sub(lambda m: chr(int(m.group(1), 16)), _css())
    return css.replace("\\", "")


def test_the_stylesheet_is_not_stale():
    """Checks the arbitrary-value classes used in the templates against
    the build. Those are unambiguously Tailwind's to generate - nothing
    else in the project produces a class with brackets in it - so any one
    of them missing means the build predates the template.

    This is the test that fails when somebody adds a class and forgets to
    rebuild."""
    css = _unescaped_css()
    missing = [c for c in _used_classes()
               if "[" in c and "]" in c and "." + c not in css]
    assert not missing, (
        "%d arbitrary-value classes are in the templates but not the built "
        "stylesheet - it is stale, rebuild it. Sample: %s"
        % (len(missing), sorted(missing)[:10]))


def test_chart_js_is_not_loaded_on_every_page():
    """69 kB for six pages that draw a chart. The other 274 routes should
    not pay for it."""
    base = io.open(os.path.join(HERE, "templates", "base.html"),
                   encoding="utf8").read()
    # Match the script tag, not the words - the comment explaining why it
    # is absent naturally contains the name.
    assert "npm/chart.js" not in base, \
        "Chart.js is back in base.html - every route pays 69 kB for it"
    assert "{% block head_scripts %}" in base


def test_the_pages_that_draw_charts_still_load_chart_js():
    for name in ("valuation", "royalties", "overview", "stats", "recovery",
                 "audience"):
        s = io.open(os.path.join(HERE, "templates", name + ".html"),
                    encoding="utf8").read()
        assert "new Chart(" in s, name
        assert "chart.js" in s.lower(), \
            "%s draws a chart but no longer loads Chart.js" % name
