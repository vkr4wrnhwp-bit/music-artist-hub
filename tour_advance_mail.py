"""The advance packet: one email to the venue, built from the show's own rows.

WHAT AN ADVANCE IS
------------------
A tour manager writes to each venue a few weeks out: here is who we are,
here is the bill and the times we have, here is what we bring and what we
need, here are the questions we still cannot answer ourselves, and here
are the rider and the stage plot. The venue answers, the answers go into
the advance checklist, and the show is "advanced".

Everything in the email is read from rows that already exist - the
schedule, the lineup, the advance checklist, the people list - so the
email can never say something the app does not know. Nothing here
invents a time, a number or a name.

NO MONEY, EVER
--------------
The deal was made between the buyer and the agent; the advance goes to
the production office and the house crew. Guarantee, backend, deposits
and settlement figures are never read here, and a test holds that line.

THIS MODULE HAS NO I/O
----------------------
It composes. Reading files, creating share tokens and sending live in
tour_os.py, where the permissions are. The stage-plot catalogue below is
a mirror of static/js/stageplot.js and a test diffs the two, so the
input list the email carries is the one the designer shows.
"""
import html as _html
import re
from datetime import datetime

# key -> the input templates that item contributes. "{n}" is the
# instance number, written only when there is more than one of them -
# exactly what stageplot.js does.
PLOT_INPUTS = [
    ("riser", []),
    ("drums", ["Kick — Beta 52", "Snare — SM57", "Hi-Hat — SM81", "Rack Tom — e604",
               "Floor Tom — e604", "OH L — SM81", "OH R — SM81"]),
    ("gtr", ["Guitar Amp {n} — SM57"]),
    ("bass", ["Bass — DI"]),
    ("keys", ["Keys {n} L — DI", "Keys {n} R — DI"]),
    ("acoustic", ["Acoustic {n} — DI"]),
    ("vox", ["Vocal {n} — SM58"]),
    ("playback", ["Tracks L — DI", "Tracks R — DI"]),
    ("dj", ["DJ L — DI", "DJ R — DI"]),
    ("wedge", []),
    ("power", []),
]

# The advance checklist items a venue can answer, phrased as the question
# a tour manager actually asks. Anything not listed is asked as
# "Please confirm: <label>". Travel and VIP items are ours to sort, not
# the venue's, so they are never asked.
QUESTIONS = {
    "promoter": "Who is the promoter rep on the night, and how do we reach them?",
    "buyer": "Who is the buyer for this date, for our records?",
    "venue_contact": "Who is our day-of contact at the venue, and on what number?",
    "capacity": "What is the capacity for the night?",
    "ticketing": "Where do tickets stand, and what is the walk-up price?",
    "show_times": "Please confirm doors, set times and changeover.",
    "curfew": "Is there a curfew, and is it hard?",
    "load_in": "What time can we load in, and where is the load-in door?",
    "dock": "Is there a dock or a ramp, and does it take a van and trailer?",
    "stage": "What are the stage dimensions, and is there a riser?",
    "power": "What power is available on stage, and where are the drops?",
    "sound": "Who is the house engineer, and what are the PA and monitor rig?",
    "lighting": "Who runs lights, and can our operator take the desk?",
    "backline": "What backline does the house provide?",
    "labor": "Is there house crew for load-in and load-out?",
    "rigging": "Is there any rigging available, and who signs it off?",
    "parking": "Where does the van park, and is there overnight parking?",
    "bus_parking": "Is there bus parking with shore power?",
    "dressing_rooms": "How many dressing rooms, and do they lock?",
    "showers": "Are there showers backstage?",
    "laundry": "Is there laundry we can use?",
    "wifi": "Is there Wi-Fi backstage, and what is the password?",
    "hospitality": "What hospitality is provided on arrival?",
    "catering": "Is there a hot meal, and at what time?",
    "buyout": "If there is a buyout instead of a meal, how much per person?",
    "security": "What does security look like at the stage and the doors?",
    "settlement_location": "Where do we settle, and with whom?",
    "settlement_contact": "Who settles the show at the end of the night?",
    "tax_paperwork": "Is any tax paperwork needed before settlement?",
    "payment_method": "How will we be paid on the night?",
    "merch_percentage": "Is there a merch table, and does the house take a percentage?",
    "ticket_comps": "How many comps are on the night?",
    "guest_allotment": "How many guest-list spots do we have, and when is the cutoff?",
}

ASK_CATEGORIES = ("general", "production", "artist", "business")

# Advance items that are answered by the venue and belong in "confirmed"
# when they carry a value. Same set: what the venue can answer.
CONFIRM_CATEGORIES = ASK_CATEGORIES

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"(https?://[^\s<>\"]+)")


# --- the input list ----------------------------------------------------------

def channel_list(plot):
    """The same list stageplot.js shows under the plot, from the saved
    state: {items: {key: count}}."""
    items = (plot or {}).get("items") or {}
    out = []
    for key, templates in PLOT_INPUTS:
        try:
            n = int(items.get(key) or 0)
        except (TypeError, ValueError):
            n = 0
        for i in range(1, n + 1):
            for tpl in templates:
                out.append(" ".join(tpl.replace("{n}", str(i) if n > 1 else "").split()))
    return out


def input_list_text(channels, artist=""):
    lines = ["INPUT LIST" + (" — " + artist if artist else ""),
             "%d channel%s" % (len(channels), "" if len(channels) == 1 else "s"), ""]
    for i, ch in enumerate(channels, 1):
        lines.append("%2d. %s" % (i, ch))
    if not channels:
        lines.append("No inputs on the plot yet.")
    return "\n".join(lines) + "\n"


# --- who to write to ---------------------------------------------------------

def candidate_recipients(people, advance_rows, show_id):
    """Addresses this show already knows: venue and promoter people on the
    bill, then any address typed into the advance's contact items. In
    that order, without duplicates. The form offers the first and lists
    the rest; nothing is sent to anyone a person did not pick."""
    seen, out = set(), []

    def add(addr):
        addr = (addr or "").strip()
        if addr and _EMAIL_RE.fullmatch(addr) and addr.lower() not in seen:
            seen.add(addr.lower())
            out.append(addr)

    for p in people or []:
        if p.get("category") in ("Venue", "Promoters") and (
                not p.get("shows") or show_id in (p.get("shows") or [])):
            add(p.get("email"))
    for row in advance_rows or []:
        if row.get("item_key") in ("venue_contact", "promoter", "buyer", "settlement_contact"):
            for text in (row.get("value") or "", row.get("comments") or ""):
                for m in _EMAIL_RE.findall(text):
                    add(m)
    return out


def contact_first_name(advance_rows):
    """The leading name in the venue-contact item, if somebody typed one:
    "Jane Doe, jane@..." -> "Jane". Nothing guessed from an address."""
    for row in advance_rows or []:
        if row.get("item_key") == "venue_contact":
            text = (row.get("value") or "").strip()
            m = re.match(r"^([A-Za-z][A-Za-z'\-]+)(?:\s+[A-Za-z][A-Za-z'\-]+)?", text)
            if m and "@" not in m.group(0):
                return m.group(1)
    return ""


# --- the email ---------------------------------------------------------------

def _when(schedule_row, fmt_time):
    t = fmt_time(schedule_row.get("start_time") or "")
    precision = schedule_row.get("precision") or "exact"
    if precision == "tbd" or not t:
        return "TBD"
    if precision == "approx":
        return "about " + t
    return t


_TIME_LABELS = [("call", "Crew call"), ("load_in", "Load-in"), ("soundcheck", "Soundcheck"),
                ("doors", "Doors"), ("support", "Support"), ("set", "Set"),
                ("curfew", "Curfew"), ("bus_call", "Bus call")]


def compose(tour, show, schedule, lineup, advance_rows, sender, links,
            attachment_names, fmt_time, fmt_day, venue=None):
    """{subject, text}. Every line traces to a row; see the module note."""
    artist = (tour.get("artist_name") or tour.get("name") or "We").strip()
    venue_name = (show.get("venue") or "your room").strip()
    city = (show.get("city") or "").strip()
    day = fmt_day(show.get("date") or "") or (show.get("date") or "")
    first = contact_first_name(advance_rows)

    subject = "Advance: %s at %s — %s%s" % (
        artist, venue_name, day, (" (%s)" % city) if city else "")

    lines = ["Hi%s," % ((" " + first) if first else ""), ""]
    lines.append("%s here, advancing %s at %s on %s%s. Below is what we have on our "
                 "side. Please correct anything that is wrong and answer the open "
                 "questions when you can."
                 % (sender.get("name") or artist, artist, venue_name, day,
                    (" in " + city) if city else ""))
    lines.append("")

    # The show
    lines += ["THE SHOW", "Date: %s" % day,
              "Venue: %s%s" % (venue_name, (", " + city) if city else "")]
    if venue and (venue.get("address") or "").strip():
        lines.append("Address we have: %s" % venue["address"].strip())
    bill = []
    for row in lineup or []:
        name = (row.get("act_name") or "").strip()
        if not name:
            continue
        span = ""
        if row.get("set_start"):
            span = fmt_time(row["set_start"])
            if row.get("set_end"):
                span += "–" + fmt_time(row["set_end"])
        tag = ", headline" if row.get("is_headliner") else ""
        bill.append(name + ((" (%s%s)" % (span, tag)) if span else (" (headline)" if tag else "")))
    if bill:
        lines.append("Bill, in running order: " + " · ".join(bill))
    elif (show.get("support") or "").strip():
        lines.append("Bill: " + show["support"].strip())
    if (show.get("capacity") or "").strip():
        lines.append("Capacity we have on file: %s" % show["capacity"].strip())
    if (show.get("ticket_url") or "").strip():
        lines.append("Tickets: %s" % show["ticket_url"].strip())
    lines.append("")

    # Times, from the schedule
    by_cat = {}
    for row in schedule or []:
        by_cat.setdefault(row.get("category"), row)
    times = [(label, _when(by_cat[key], fmt_time)) for key, label in _TIME_LABELS if key in by_cat]
    if times:
        lines.append("TIMES WE ARE WORKING TO")
        for label, when in times:
            lines.append("%s: %s" % (label, when))
        lines.append("")

    # Confirmed and open, from the advance checklist
    confirmed = [(r["label"], (r.get("value") or "").strip()) for r in advance_rows or []
                 if r.get("category") in CONFIRM_CATEGORIES and r.get("status") == "complete"
                 and (r.get("value") or "").strip()]
    if confirmed:
        lines.append("WHAT WE HAVE CONFIRMED")
        for label, value in confirmed:
            lines.append("• %s: %s" % (label, value))
        lines.append("")
    open_items = [r for r in advance_rows or []
                  if r.get("category") in ASK_CATEGORIES and r.get("status") in ("incomplete", "waiting")]
    if open_items:
        lines.append("WHAT WE STILL NEED FROM YOU")
        for r in open_items:
            lines.append("• " + QUESTIONS.get(r.get("item_key"), "Please confirm: %s." % r.get("label")))
        lines.append("")

    # Guest list, when we already know it
    if (show.get("guest_allocation") or "").strip():
        line = "GUEST LIST\nWe have %s spots on our side" % show["guest_allocation"].strip()
        if (show.get("guest_cutoff") or "").strip():
            line += "; our list reaches you by %s" % show["guest_cutoff"].strip()
        lines += [line + ".", ""]

    if attachment_names:
        lines.append("ATTACHED")
        for name in attachment_names:
            lines.append("• " + name)
        lines.append("")

    link_lines = []
    if links.get("rider"):
        link_lines.append("Our tech rider, stage plot and input list, no login needed: %s" % links["rider"])
    if links.get("production"):
        link_lines.append("Production pack for the house crew (files and times): %s" % links["production"])
    if link_lines:
        lines += ["LINKS"] + link_lines + [""]

    lines += ["Thanks — looking forward to it.", "", sender.get("name") or artist]
    tail = ", ".join(x for x in (sender.get("role") or "", tour.get("name") or "") if x)
    if tail:
        lines.append(tail)
    contact = " · ".join(x for x in (sender.get("email") or "", sender.get("phone") or "") if x)
    if contact:
        lines.append(contact)
    return {"subject": subject, "text": "\n".join(lines)}


def html_for(text):
    """The plain text, escaped, with the links clickable. A venue reads
    this on a phone at a bar; a layout is not what it needs."""
    escaped = _html.escape(text or "")
    escaped = _URL_RE.sub(lambda m: '<a href="%s">%s</a>' % (m.group(1), m.group(1)), escaped)
    return ('<pre style="font-family:inherit;white-space:pre-wrap;font-size:15px;'
            'line-height:1.5;margin:0">%s</pre>' % escaped)
