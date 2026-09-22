"""Reading the renewal terms out of a contract's own text.

The second half of the renewal reminders (owner, 2026-09-14: "it
automatically reads the contracts uploaded to create alarms for you").
The first half typed the dates on the row; this half pulls candidates
out of the file and shows them beside the sentence they came from, for
a person to check and save. Nothing here is saved on its own.

What it does:
  * text out of a PDF (pypdf), a DOCX (the document XML inside the
    zip) or a TXT; a scanned PDF has no text and the page says so
  * dates, a term length, a notice period and an auto-renewal clause
    found by pattern, each with the sentence it came from
  * a renewal date that is either stated ("expires on 31 December
    2027") or derived (effective date plus the term), and the reading
    says which

What it does not do: judge the contract, guess a date it did not find,
or trust itself. Every finding is labelled "found in the document,
check it", and the row keeps saying whose dates the saved ones are.
No model is involved; the deployment has no model key, and a pattern
that shows its sentence is easier to check than a summary that hides it.
"""
import calendar
import html
import io
import re
import zipfile
from datetime import date

MAX_TEXT = 400_000       # characters kept from a document
MAX_DATES = 12           # dates listed on the row
SNIPPET = 240            # characters of the sentence shown

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTHS["sept"] = 9

_MONTH_RE = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|"
             r"aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
_DATE_PATTERNS = (
    # 15th day of January, 2026 / 15 January 2026
    re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?(" + _MONTH_RE + r")\.?,?\s+(\d{4})\b", re.I),
    # January 15, 2026 / Jan. 15 2026
    re.compile(r"\b(" + _MONTH_RE + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I),
    # 2026-01-15
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    # 1/15/2026, read as month/day/year
    re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"),
)

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fourteen": 14,
    "fifteen": 15, "eighteen": 18, "twenty": 20, "twenty-four": 24, "thirty": 30,
    "thirty-six": 36, "forty-five": 45, "forty-eight": 48, "sixty": 60,
    "ninety": 90, "one hundred twenty": 120, "one hundred and twenty": 120,
    "one hundred eighty": 180, "one hundred and eighty": 180,
}
_NUM = r"(\d+|one hundred(?: and)? (?:twenty|eighty)|twenty-four|thirty-six|forty-five|forty-eight|[a-z]+)"

_TERM_RE = re.compile(
    r"\b(?:(?:initial|first|original)\s+)?term\s+(?:of|for)\s+" + _NUM +
    r"\s*(?:\(\s*(\d+)\s*\))?\s*(year|month)s?\b", re.I)
_TERM_RE2 = re.compile(
    r"\b" + _NUM + r"\s*(?:\(\s*(\d+)\s*\))?[-\s](year|month)s?\s+(?:initial\s+)?term\b", re.I)
# "the term of this Agreement shall be two (2) years"
_TERM_RE3 = re.compile(
    r"\bterm\b[^.;]{0,60}?\b(?:shall\s+be|is|will\s+be|of)\s+(?:for\s+)?(?:a\s+period\s+of\s+)?" + _NUM +
    r"\s*(?:\(\s*(\d+)\s*\))?\s*(year|month)s?\b", re.I)
_NOTICE_RE = re.compile(
    r"\b" + _NUM + r"\s*(?:\(\s*(\d+)\s*\))?\s*days?['’]?\s+(?:(?:prior|advance|previous)\s+)?"
    r"(?:written\s+)?notice\b", re.I)
_NOTICE_RE2 = re.compile(
    r"\bnotice\b[^.;]{0,80}?\b(?:at\s+least|not\s+less\s+than|no\s+less\s+than|a\s+minimum\s+of|of)\s+"
    + _NUM + r"\s*(?:\(\s*(\d+)\s*\))?\s*days?\b", re.I)
_AUTO_NO_RE = re.compile(
    r"\b(?:shall|will|does|do)\s+not\s+(?:be\s+)?(?:automatically\s+)?renew|\bno\s+automatic\s+renewal|"
    r"\bnot\s+(?:be\s+)?subject\s+to\s+(?:automatic|auto)\s*-?\s*renewal|\bnon-renew(?:able|ing)\b", re.I)
_AUTO_YES_RE = re.compile(
    r"\bautomatic(?:ally)?\s+(?:be\s+)?(?:renew|extend)|\bauto\s*-?\s*renew|\bevergreen\b|"
    r"\b(?:shall|will)\s+(?:be\s+)?(?:renew|extend)(?:ed)?\s+for\s+(?:an?\s+)?(?:additional|successive|further|subsequent)\b|"
    r"\brenew(?:s|ed)?\s+(?:automatically|for\s+successive)\b", re.I)

_END_WORDS = re.compile(r"\b(?:renew|expir|terminat|end(?:s|ing)?\s+(?:on|of)|until|through|ends?\b|"
                        r"conclud|last\s+day)", re.I)
_START_WORDS = re.compile(r"\b(?:effective|commenc|dated|as\s+of|entered\s+into|made\s+(?:on|this)|"
                          r"executed|signed|begin)", re.I)


# --- text out of the file -----------------------------------------------------

# The three a reader exists for. Anything else is filed without being
# read, which extract_text already reports as "unsupported"; this lets a
# caller skip the work rather than ask and be told no.
READABLE = ("pdf", "docx", "txt")


def extract_text(data, ext):
    """(text, status). Status is one of ok, empty, no_reader, unsupported,
    broken. "empty" is a file with no text layer, a scanned PDF usually."""
    ext = (ext or "").lower().lstrip(".")
    if ext == "txt":
        text = data.decode("utf-8", errors="replace")
    elif ext == "docx":
        try:
            text = _docx_text(data)
        except (zipfile.BadZipFile, KeyError, ValueError):
            return "", "broken"
    elif ext == "pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return "", "no_reader"
        try:
            reader = PdfReader(io.BytesIO(data))
            parts = []
            for page in reader.pages:
                parts.append(page.extract_text() or "")
                if sum(len(p) for p in parts) > MAX_TEXT:
                    break
            text = "\n".join(parts)
        except Exception:  # pypdf raises its own family plus ValueError on bad bytes
            return "", "broken"
    else:
        return "", "unsupported"
    text = text[:MAX_TEXT]
    if len(re.findall(r"[A-Za-z]", text)) < 20:
        return text, "empty"
    return text, "ok"


def _docx_text(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", " ", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    return html.unescape(xml)


# --- the terms in the text ----------------------------------------------------

def _sentences(text):
    flat = re.sub(r"[ \t\r\f\v]+", " ", text)
    # a clause ends at a full stop or semicolon, or at a blank line
    return [s.strip() for s in re.split(r"(?<=[.;])\s+|\n\s*\n|\n(?=\s*(?:\d+\.|\([a-z\d]+\)|[A-Z]{2,}))", flat)
            if s and s.strip()]


def _snippet(sentence):
    s = re.sub(r"\s+", " ", sentence).strip()
    return s if len(s) <= SNIPPET else s[:SNIPPET - 1].rstrip() + "…"


def _number(word, bracketed):
    if bracketed:
        return int(bracketed)
    w = (word or "").lower().strip()
    if w.isdigit():
        return int(w)
    return _WORD_NUMBERS.get(w)


def _dates_in(sentence):
    found = []
    for i, pat in enumerate(_DATE_PATTERNS):
        for m in pat.finditer(sentence):
            try:
                if i == 0:
                    d = date(int(m.group(3)), MONTHS[m.group(2).lower().rstrip(".")], int(m.group(1)))
                elif i == 1:
                    d = date(int(m.group(3)), MONTHS[m.group(1).lower().rstrip(".")], int(m.group(2)))
                elif i == 2:
                    d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                else:
                    d = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            except (ValueError, KeyError):
                continue
            if 1990 <= d.year <= 2100:
                found.append((d, m.group(0), i == 3))
    return found


def _add_months(d, months):
    y, m = divmod(d.month - 1 + months, 12)
    y += d.year
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def find_terms(text):
    """Everything the text says about its term, each with its sentence."""
    out = {
        "renews_on": {"value": "", "how": "not_found", "snippet": ""},
        "effective_on": {"value": "", "how": "not_found", "snippet": ""},
        "term_months": {"value": None, "how": "not_found", "snippet": ""},
        "notice_days": {"value": None, "how": "not_found", "snippet": ""},
        "auto_renews": {"value": None, "how": "not_found", "snippet": ""},
        "dates": [],
    }
    end_dates, start_dates = [], []
    for sentence in _sentences(text):
        snip = _snippet(sentence)
        for d, raw, ambiguous in _dates_in(sentence):
            role = ""
            if _END_WORDS.search(sentence):
                role = "end"
                end_dates.append((d, snip))
            elif _START_WORDS.search(sentence):
                role = "start"
                start_dates.append((d, snip))
            if len(out["dates"]) < MAX_DATES:
                out["dates"].append({"value": d.isoformat(), "raw": raw, "role": role,
                                     "snippet": snip, "ambiguous": ambiguous})
        if out["term_months"]["value"] is None:
            m = _TERM_RE.search(sentence) or _TERM_RE2.search(sentence) or _TERM_RE3.search(sentence)
            if m:
                n = _number(m.group(1), m.group(2))
                if n:
                    out["term_months"] = {"value": n * (12 if m.group(3).lower().startswith("year") else 1),
                                          "how": "found", "snippet": snip}
        if out["notice_days"]["value"] is None:
            m = _NOTICE_RE.search(sentence) or _NOTICE_RE2.search(sentence)
            if m:
                n = _number(m.group(1), m.group(2))
                if n is not None and 0 < n <= 365:
                    out["notice_days"] = {"value": n, "how": "found", "snippet": snip}
        if out["auto_renews"]["value"] is None:
            if _AUTO_NO_RE.search(sentence):
                out["auto_renews"] = {"value": False, "how": "found", "snippet": snip}
            elif _AUTO_YES_RE.search(sentence):
                out["auto_renews"] = {"value": True, "how": "found", "snippet": snip}
    if start_dates:
        d, snip = start_dates[0]
        out["effective_on"] = {"value": d.isoformat(), "how": "found", "snippet": snip}
    if end_dates:
        # the latest date a clause about ending names: an initial term's
        # end, not the signing date that sentence may also mention
        d, snip = max(end_dates, key=lambda t: t[0])
        out["renews_on"] = {"value": d.isoformat(), "how": "found", "snippet": snip}
    elif start_dates and out["term_months"]["value"]:
        d, snip = start_dates[0]
        out["renews_on"] = {"value": _add_months(d, out["term_months"]["value"]).isoformat(),
                            "how": "derived", "snippet": snip}
    return out


def summary(findings, status):
    """One plain sentence for the row."""
    if status == "empty":
        return "The file has no readable text, so nothing could be found. A scanned PDF reads this way; type the dates by hand."
    if status == "no_reader":
        return "This server cannot read PDFs yet. Type the dates by hand."
    if status == "unsupported":
        return "Only PDF, DOCX and TXT files can be read. Type the dates by hand."
    if status == "broken":
        return "The file could not be opened as a document. Type the dates by hand."
    if status == "unavailable":
        return "The file could not be fetched from storage just now. Try again, or type the dates by hand."
    parts = []
    r = findings.get("renews_on") or {}
    if r.get("how") == "found":
        parts.append("an end date")
    elif r.get("how") == "derived":
        parts.append("an end date worked out from the start date and the term")
    n = findings.get("notice_days") or {}
    if n.get("value"):
        parts.append("a %d-day notice period" % n["value"])
    a = findings.get("auto_renews") or {}
    if a.get("value") is True:
        parts.append("an automatic renewal clause")
    elif a.get("value") is False:
        parts.append("a clause saying it does not renew on its own")
    if not parts:
        return "Read the text and found no term, notice period or renewal clause. Type the dates by hand."
    if len(parts) == 1:
        joined = parts[0]
    else:
        joined = ", ".join(parts[:-1]) + " and " + parts[-1]
    return "Found " + joined + ". Check each against the document before saving."


# --- the flags on a contract's row ------------------------------------------
# Each is something the document LITERALLY SAYS, found by pattern, shown with
# the sentence it came from. None of them is a judgement about whether the
# deal is good: that is a lawyer's work, this is pattern matching, and a
# confident wrong opinion on a contract is expensive. "watch" means it is
# worth your attention, not that it is unfair.
#
# (key, tone, label, pattern)
FLAG_RULES = (
    ("auto_renew", "watch", "Renews automatically",
     r"\b(?:automatically\s+renew\w*|renew\w*\s+automatically|auto[-\s]?renew\w*"
     r"|shall\s+(?:be\s+)?(?:automatically\s+)?extended)\b"),
    ("exclusive", "watch", "Exclusive",
     r"\bexclusiv(?:e|ely|ity)\b"),
    ("perpetual", "watch", "Perpetual",
     r"\b(?:in\s+perpetuity|perpetual(?:ly)?|forever)\b"),
    ("assignment", "watch", "Rights assigned, not licensed",
     r"\b(?:hereby\s+)?assigns?\b(?:[^.;]{0,60}?\b(?:all\s+)?(?:right|title|interest|copyright)s?\b)"),
    ("all_media", "watch", "All media, now known or later invented",
     r"\b(?:now\s+known\s+or\s+(?:here)?(?:after|inafter)\s+(?:devised|invented|developed)"
     r"|all\s+media\s+now\s+known)\b"),
    ("nonexclusive", "fine", "Non-exclusive",
     r"\bnon[-\s]?exclusiv(?:e|ely|ity)\b"),
    ("terminate_any", "fine", "Can be ended by either party",
     r"\beither\s+party\s+may\s+terminate\b"),
)

# A non-exclusive contract is not also an exclusive one: the word contains
# the other, so the narrower finding wins.
FLAG_BEATS = {"nonexclusive": ("exclusive",)}


def find_flags(text, findings=None):
    """What this contract says, flagged. [{key, tone, label, snippet}].

    tone is "watch" or "fine". Order is watch first, then the order above,
    so the ones that cost people money are read first.
    """
    out = {}
    for sentence in _sentences(text or ""):
        for key, tone, label, pattern in FLAG_RULES:
            if key in out:
                continue
            if re.search(pattern, sentence, re.I):
                out[key] = {"key": key, "tone": tone, "label": label,
                            "snippet": _snippet(sentence)}
    for winner, losers in FLAG_BEATS.items():
        if winner in out:
            for loser in losers:
                out.pop(loser, None)

    # Two that are not a phrase anywhere in the text but a fact about what
    # was read: they come from the terms, not from a sentence.
    f = findings or {}
    months = (f.get("term_months") or {}).get("value")
    if months and months > 36:
        out["long_term"] = {"key": "long_term", "tone": "watch",
                            "label": "Term over three years",
                            "snippet": (f.get("term_months") or {}).get("snippet", "")}
    notice = (f.get("notice_days") or {}).get("value")
    if notice is not None and notice >= 60:
        out["long_notice"] = {"key": "long_notice", "tone": "fine",
                              "label": "%d days to give notice" % notice,
                              "snippet": (f.get("notice_days") or {}).get("snippet", "")}
    if not (f.get("renews_on") or {}).get("value") and f:
        out["no_end"] = {"key": "no_end", "tone": "watch",
                         "label": "No end date found",
                         "snippet": ""}

    order = [k for k, _t, _l, _p in FLAG_RULES] + ["long_term", "long_notice", "no_end"]
    found = [out[k] for k in order if k in out]
    return sorted(found, key=lambda x: 0 if x["tone"] == "watch" else 1)


def flags_line(flags):
    """'2 to watch, 2 fine' - or a plain sentence when there is nothing."""
    watch = len([f for f in flags if f["tone"] == "watch"])
    fine = len(flags) - watch
    if not flags:
        return "Nothing flagged in this one."
    parts = []
    if watch:
        parts.append("%d to watch" % watch)
    if fine:
        parts.append("%d fine" % fine)
    return ", ".join(parts)
