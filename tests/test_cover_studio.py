"""The Cover Studio finish: the owner's mockup and audit of 2026-09-24.

Same two-column editor, same sticky cover, same black / cream / gold. What
these tests hold is the finish the audit asked for, ticket by ticket:

  1. words and states: one storage vocabulary (Studio Files, stored in the
     Vault), the one explanation of formats, three actions under the cover
     with PNG and SVG behind one Download button, brand settings inside the
     Type card with "Saved on this device" said out loud and "No brand kit
     saved" instead of an Apply button that looks live, a Starter preview
     pill, Generate that waits for a description, Variations 1 | 4 as a real
     choice gated by the month's allowance, and generating / done / failed
     states inside the Art card;
  2. the 04 Review & Export step;
  3. feedback, accessibility and the Fine-tune fold.

Nothing the editor could do before is gone: the last test in the first
group lists every control by id and every one must still render.

No test reaches OpenAI: cover_ai._transport is replaced wherever a key is
set, exactly as tests/test_cover_ai.py does.
"""
import base64
import glob
import io
import json
import os
import re
import shutil
import subprocess
import uuid

import pytest

import app as appmod
import artwork_config as ac
import cover_ai
import db as store
from brand_contrast import ratio

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(HERE, "templates", "artwork.html")
TOKENS = os.path.join(HERE, "tools", "tailwind-input.css")
PW = "cover-studio-1"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OWNER_EMAILS", raising=False)
    cover_ai.init_db()
    yield
    for plan in cover_ai.DEFAULT_ALLOWANCE:
        store.delete_kv("cover_renders:%s" % plan)


class FakeOpenAI:
    def __init__(self):
        self.calls = []

    def __call__(self, url, body, headers, timeout):
        self.calls.append(json.loads(body.decode()))
        return 200, json.dumps({"created": 1, "data": [
            {"b64_json": base64.b64encode(JPEG).decode()}]}).encode()


@pytest.fixture
def openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    fake = FakeOpenAI()
    monkeypatch.setattr(cover_ai, "_transport", fake)
    return fake


def _account(plan="pro", name="Artist"):
    email = "%s-%s@example.net" % (name.lower(), uuid.uuid4().hex[:8])
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    c._email, c._id = email, uid
    return c


def _page(c=None):
    c = c or _account()
    r = c.get("/artwork")
    assert r.status_code == 200
    return r.get_data(as_text=True)


def _source():
    return io.open(TEMPLATE, encoding="utf8").read()


def _text(html):
    """The words a person reads: tags stripped, whitespace folded."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html))


def _section(html, elem_id):
    """The markup of one element with this id, by tag balance. Enough for
    a section or a div that holds no unclosed tags of its own name."""
    m = re.search(r'<(\w+)[^>]*\bid="%s"' % re.escape(elem_id), html)
    assert m, "no element with id %s" % elem_id
    tag = m.group(1)
    start = m.start()
    depth = 0
    for t in re.finditer(r"<(/?)%s\b[^>]*>" % tag, html[start:]):
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return html[start:start + t.end()]
    raise AssertionError("unbalanced <%s id=%s>" % (tag, elem_id))


def _token(name):
    s = io.open(TOKENS, encoding="utf8").read()
    m = re.search(r'--sb-%s:\s*(#[0-9a-fA-F]{6})' % re.escape(name), s)
    assert m, name
    return m.group(1)


# --- ticket 1: words and states ---------------------------------------------

def test_one_storage_vocabulary():
    """Audit 5: section "Studio Files", button "Save to Studio Files",
    explanation "Studio Files are stored in your Vault.", success "Cover
    saved. View in Vault". The old words are gone everywhere."""
    page, src = _page(), _source()
    words = _text(page)
    assert "Save to Studio Files" in words
    assert "Studio Files are stored in your Vault." in words
    assert re.search(r"<h2[^>]*>\s*Studio Files\s*</h2>", page)
    assert "lands in your Studio Files" in words
    assert 'Cover saved. <a href="/vault">View in Vault</a>' in src
    for gone in ("Save cover to uploads", "Save to My Uploads", "Your studio files",
                 "lands in your uploads", "Saved to your uploads", "saved to your uploads"):
        assert gone not in page and gone not in src, gone


def test_the_one_formats_explanation():
    """Audit 1, checked against the code: Story and Banner are real reframes
    of the composition, so the sentence says so, and does not call them
    previews. One sentence, once."""
    words = _text(_page())
    sentence = ("AI artwork is generated as a square cover. You can reframe that "
                "artwork for Story and Banner here. Use Motion when you need "
                "animation or video.")
    assert sentence in words
    assert words.count("AI artwork is generated as a square cover") == 1
    assert "Square cover art only" not in words
    assert 'href="/suites/go/motion"' in _page()


def test_three_actions_under_the_cover_and_the_brand_kit_in_type():
    """Audit 4: Save to Studio Files (primary), Download (PNG and SVG in a
    menu), Preview formats. Save / Apply brand kit live in the Type card
    under Brand settings; "Saved on this device" is words, not a tooltip;
    with no kit saved the page says so instead of showing Apply."""
    page = _page()
    bench = page.split('id="cs-rail"')[0]
    assert 'id="save-cover-btn"' in bench and "Save to Studio Files" in _text(bench)
    menu = _section(page, "download-menu")
    assert 'role="menu"' in menu and 'id="download-png-btn"' in menu and 'id="download-svg-btn"' in menu
    dl = re.search(r'<button[^>]*id="download-btn"[^>]*>', page).group(0)
    assert 'aria-haspopup="menu"' in dl and 'aria-expanded="false"' in dl and 'aria-controls="download-menu"' in dl
    assert 'id="allfmt-btn"' in bench and "Preview formats" in _text(bench)
    assert 'id="brand-save"' not in bench and 'id="brand-apply"' not in bench
    typecard = _section(page, "step-type")
    brand = _section(typecard, "brand-settings")
    assert 'id="brand-save"' in brand and 'id="brand-apply"' in brand
    assert re.search(r'<button[^>]*id="brand-apply"[^>]*\bhidden\b', brand), \
        "Apply is not shown while no kit is saved"
    assert "No brand kit saved" in _text(brand)
    assert "Saved on this device" in _text(typecard)
    assert 'title="Remembers font' not in page, "the tooltip is not the only place it is said"
    assert re.search(r'<button[^>]*id="brand-settings-btn"[^>]*aria-expanded="false"', typecard)


def test_the_starter_pill_and_the_not_saved_line():
    page = _page()
    pill = re.search(r'<span[^>]*id="starter-pill"[^>]*>(.*?)</span>', page)
    assert pill and pill.group(1).strip() == "Starter preview"
    status = _section(page, "cover-save-status")
    assert "Not saved yet" in _text(status) and "Stored in Vault" in _text(status)
    assert 'data-saved="false"' in status
    # The starter is saveable, but only on purpose (audit 3).
    assert "This is the starter preview" in _source() and "confirm(" in _source()


def test_the_slug_clears_aa_on_the_bench():
    """The audit measured the old slug at about 3.9:1 at 12px. It is now
    ink-2, and this measures it against both ends of the bench gradient
    rather than trusting the token."""
    src = _source()
    slug = re.search(r"\.slug\s*\{[^}]*\}", src).group(0)
    assert "var(--sb-ink-2)" in slug, slug
    assert "rgba(239,233,220,.45)" not in slug
    for surface in ("on-gold", "ground"):
        r = ratio(_token("ink-2"), _token(surface))
        assert r >= 4.5, "ink-2 on %s = %.2f:1" % (surface, r)


def test_the_rail_has_four_steps_and_the_cards_fold():
    """Art, Type, Canvas, Review & Export: four steps, the active one named
    by aria-current. Each card is an h2 whose button is the disclosure, and
    aria-expanded agrees with what is shown."""
    page = _page()
    rail = _section(page, "cs-rail")
    steps = re.findall(r'<li class="cs-step" data-step="(\d)" data-state="(\w+)"', rail)
    assert steps == [("1", "active"), ("2", "todo"), ("3", "todo"), ("4", "todo")]
    assert rail.count('aria-current="step"') == 1
    assert "04 Review &amp; Export" in rail
    for sid, name, open_ in (("step-art", "Art", "true"), ("step-type", "Type", "true"),
                             ("step-canvas", "Canvas", "false"), ("step-review", "Review &amp; Export", "true")):
        card = _section(page, sid)
        assert 'data-open="%s"' % open_ in card.split(">", 1)[0], sid
        head = re.search(r'<h2 class="cs-h"><button[^>]*aria-expanded="(\w+)"[^>]*aria-controls="([\w-]+)"[^>]*>(.*?)</button></h2>', card, re.S)
        assert head, sid
        assert head.group(1) == open_, sid
        assert 'id="%s"' % head.group(2) in card, sid
        assert name in head.group(3), sid
    assert "Square 1:1" in _text(_section(page, "step-canvas"))
    # Every rail button points at a card that exists.
    for n in re.findall(r'data-open-step="(\d)"', rail):
        assert 'data-step="%s"' % n in page


def test_the_art_card_states():
    """Audit 3: Generate waits for a description; Variations is a real
    choice with a selected state; generating, done and failed are shown
    inside the Art card, under the button."""
    page = _page()
    art = _section(page, "step-art")
    assert "Generate with AI or upload your own artwork." in _text(art)
    assert re.search(r'<button[^>]*id="art-mode-ai"[^>]*aria-pressed="true"', art)
    assert re.search(r'<button[^>]*id="art-mode-upload"[^>]*aria-pressed="false"', art)
    assert re.search(r'<textarea[^>]*id="prompt-input"[^>]*maxlength="500"', art)
    assert re.search(r'<span id="prompt-len">0</span>/500', art)
    assert re.search(r'<button[^>]*id="generate-btn"[^>]*\bdisabled\b', art), "Generate waits for a description"
    assert re.search(r'<button[^>]*id="variations-1"[^>]*aria-pressed="true"', art)
    assert re.search(r'<button[^>]*id="variations-4"[^>]*aria-pressed="false"', art)
    note = re.search(r'<div[^>]*id="generate-note"[^>]*>', art).group(0)
    assert 'role="status"' in note and 'data-state="idle"' in note
    assert art.index('id="generate-btn"') < art.index('id="generate-note"'), "the state line sits under the button"
    # The upload pane is the other segment, folded until chosen.
    assert re.search(r'<div id="art-upload-pane" hidden>', art) and 'id="art-upload"' in art
    # The states are written into the script, one word each.
    src = _source()
    for state in ("generating", "done", "failed"):
        assert 'genState("%s"' % state in src, state


def test_the_four_choice_follows_the_allowance(openai, monkeypatch):
    """"4" uses four covers, says so, and is unavailable when fewer than
    four are left this month. At zero nothing that would render is left.
    An owner login is unlimited and is not told it uses four."""
    cover_ai.save_allowances({"covers_artist": "10"})
    c = _account("artist")
    art = _section(_page(c), "step-art")
    four = re.search(r'<button[^>]*id="variations-4"[^>]*>(.*?)</button>', art, re.S)
    assert four and "disabled" not in four.group(0) and "uses 4 covers" in _text(four.group(1))

    cover_ai.save_allowances({"covers_artist": "3"})
    art = _section(_page(c), "step-art")
    four = re.search(r'<button[^>]*id="variations-4"[^>]*>', art).group(0)
    assert "disabled" in four
    assert "4 needs 4 covers; 3 left this month." in _text(art)
    assert 'id="generate-btn"' in art and 'id="variations-1"' in art

    cover_ai.save_allowances({"covers_artist": "0"})
    art = _section(_page(c), "step-art")
    assert 'id="generate-btn"' not in art and 'id="variations-4"' not in art
    assert "Your plan has no cover renders." in _text(art)

    owner = _account("label", "Owner")
    monkeypatch.setenv("OWNER_EMAILS", owner._email)
    art = _section(_page(owner), "step-art")
    assert "uses 4 covers" not in _text(art)
    assert "Owner login: unlimited covers." in _text(art)
    assert re.search(r'<button[^>]*id="variations-4"[^>]*aria-pressed="false"[^>]*>4</button>', art)


def test_without_a_key_the_four_choice_is_free():
    art = _section(_page(), "step-art")
    four = re.search(r'<button[^>]*id="variations-4"[^>]*>(.*?)</button>', art, re.S)
    assert four and "disabled" not in four.group(0)
    assert "uses 4 covers" not in _text(art) and "covers left" not in _text(art)


def test_the_prompt_keeps_the_five_hundred_the_counter_promises():
    c = _account()
    long = "a" * 600
    got = c.post("/artwork/generate", data=json.dumps({"prompt": long}),
                 content_type="application/json").get_json()
    assert got["ok"] and got["prompt_used"].startswith("a" * 500 + ", ")
    assert "a" * 501 not in got["prompt_used"]


def test_the_mockup_chips_are_real_words_to_the_model():
    """The owner's mockup lists Abstract, Minimal, Neon and Urban beside
    the chips the page already had. Each is words in the prompt, like the
    rest, and each renders as a chip."""
    keys = {k for k, _g, _l, _w in ac.LOOK_OPTIONS}
    assert {"abstract", "neon", "minimal", "urban"} <= keys
    out = ac.build_prompt("a cover", ["abstract", "neon", "minimal"])
    for words in ("abstract composition", "neon light", "sparse composition"):
        assert words in out, words
    assert "close-up" not in out
    # Minimal and Urban share the Scene row, so one of them wins, like
    # Photographic and Illustrated do.
    assert "urban setting" in ac.build_prompt("a cover", ["urban"])
    assert "sparse composition" not in ac.build_prompt("a cover", ["urban", "minimal"])
    look = _section(_page(), "look-boxes")
    for label in ("Photographic", "Illustrated", "Graphic / type-led", "Abstract", "Moody light",
                  "Bright", "Golden hour", "Neon", "Film grain", "Clean digital", "Minimal", "Urban",
                  "Close up", "Wide"):
        assert label in _text(look), label
    assert 'value="minimal"' in look and 'name="look-scene"' in look


def test_no_em_dash_in_the_studio():
    assert "\u2014" not in _source()


def test_every_control_the_studio_had_is_still_there():
    """Keep every feature: folded or moved, never removed."""
    page = _page()
    for cid in ("title-input", "artist-input", "font-select", "aspect-select", "title-color",
                "artist-color", "text-size", "artist-size", "letter-spacing", "text-x", "text-y",
                "artist-x", "artist-y", "upper-toggle", "text-style", "text-reset-btn",
                "logo-upload", "logo-remove", "logo-size", "logo-x", "logo-y", "bg-color",
                "bg-clear", "img-scrim", "img-zoom", "img-panx", "img-pany", "prompt-input",
                "look-boxes", "generate-btn", "ai-image", "ai-save-btn", "ai-again-btn",
                "ai-remove-btn", "remix-input", "remix-btn", "art-upload", "cover-check-file",
                "cover-check-result", "save-cover-btn", "download-png-btn", "download-svg-btn",
                "allfmt-btn", "fmt-strip", "brand-save", "brand-apply", "art-uploads",
                "art-uploads-empty", "cover-frame", "slug-dims", "slug-font", "slug-src"):
        assert 'id="%s"' % cid in page, cid
    assert page.count('class="align-btn') == 3
    assert page.count("data-look-clear=") == len(ac.LOOK_GROUPS)


# --- the inline script parses ------------------------------------------------

def _node():
    found = shutil.which("node")
    if found:
        return found
    for pat in (os.path.expanduser("~/nodejs/*/node.exe"), "C:/Users/*/nodejs/*/node.exe"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def test_the_review_step_checks_the_canvas_not_a_file():
    """Ticket 2: 04 Review & Export. Three boxes the page ticks from state
    (disabled, never clickable), a Cover status that reads Ready only when
    all three hold, "Check this cover" first - the canvas rendered and
    measured with no file dialog - and the file path demoted to "Check
    another file"; a Vault link that waits for a save."""
    page = _page()
    card = _section(page, "step-review")
    for cid, label in (("review-art", "Artwork added"), ("review-info", "Release information"),
                       ("review-store", "Store-ready check")):
        box = re.search(r'<input type="checkbox" id="%s"[^>]*>' % cid, card)
        assert box and "disabled" in box.group(0) and 'aria-disabled="true"' in box.group(0), cid
        assert '<label for="%s"' % cid in card and label in card, cid
    status = re.search(r'<span id="review-status"[^>]*>([^<]*)</span>', card)
    assert status and 'data-ready="false"' in status.group(0) and status.group(1) == "Needs attention"
    assert card.index('id="check-this-cover"') < card.index('for="cover-check-file"'), "the canvas check comes first"
    assert re.search(r'<button type="button" id="check-this-cover"[^>]*>Check this cover</button>', card)
    assert "Check another file" in card and ">Check a cover<" not in card
    vault = re.search(r'<a id="review-vault-link"[^>]*>View saved file in Vault</a>', card)
    assert vault and " hidden" in vault.group(0) and 'href="/vault"' in vault.group(0)
    # The script: the canvas check renders the cover itself and shares the
    # file path's runner; the boxes follow every render; a pass holds only
    # for the canvas it measured.
    assert 'el("check-this-cover")' in page
    assert 'await runCheck(new File([blob], safeName() + "-cover.png"' in page
    assert "function updateReview()" in page and "updateReview();" in page
    assert 'state.checkedSvg === buildSvg(false) && state.checkedVerdict === "pass"' in page


def test_the_inline_script_parses(tmp_path):
    """node --check on every inline script the rendered page carries. A
    syntax error in the editor's script is a page that draws no cover and
    logs nothing a test client can see."""
    node = _node()
    if not node:
        pytest.skip("node is not installed here")
    page = _page()
    scripts = [m.group(1) for m in re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", page, re.S)]
    ours = [s for s in scripts if "buildSvg" in s]
    assert len(ours) == 1, "the editor's script is one inline block"
    for i, s in enumerate(scripts):
        f = tmp_path / ("inline-%d.js" % i)
        f.write_text(s, encoding="utf8")
        r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
