"""What state an account is in, decided ONCE, from what it has saved.

The Command Center used to infer emptiness widget by widget - twelve
independent `{% if %}`s each choosing their own empty variant - so a
brand-new account got the operational page with every widget in its
empty costume, and a failed database read looked exactly like an
account with nothing to do. The owner's zero-state spec (2026-09-22)
names four states and one rule, and this module is that rule:

    new          nothing saved, nothing done
    setup        some of the five essentials done, not all
    operational  the five essentials are done
    error        we could not read the account

  NEVER TRANSLATE A FAILED REQUEST INTO ZERO VALUES. `read()` raises;
  it does not swallow. `decide()` turns the raise into "error", which
  the page renders as "We could not load your Command Center", not as a
  fresh account. The two panels before this one (_firstrun_panel,
  _tutor_panel) both wrapped every query in `except Exception: return
  None`, which deleted the setup panel on a bad read and made the
  account look finished.

The five essentials keep firstrun.py's two rules - a step is done when
the thing EXISTS (delete it and the step comes back), and the list gets
out of the way once it is done - and add the owner's lock-and-reveal:
only three cards compete for attention at once, a locked card says why,
and a card is revealed only when the one before it is real.

Pure functions over a dict of booleans, so every rule here can be
checked without a database.
"""

# Each essential:
#   (key, title, why, href, cta, LOCKED_BY, REVEAL_AFTER, LOCK_TEXT)
# Two different kinds of dependency, because the owner's spec draws two:
#   LOCKED_BY     the card is SHOWN but its button is disabled until this
#                 key is done, and LOCK_TEXT says why (the smart link on
#                 a fresh account: visible, locked, explained - so the
#                 reader sees where setup is going)
#   REVEAL_AFTER  the card is not on the board at all until this key is
#                 done (the Rack after a song; capture after a link)
# The order is the order to do them in - each makes the next useful.
ESSENTIALS = [
    ("identity", "Tell us who you are",
     "Add the artist or label details Street Banker will use across "
     "every room.",
     "/epk", "Set up profile", None, None, ""),
    ("song", "Add your first song",
     "Create the catalog record that Studio, Publishing, and Releases "
     "will share.",
     "/tracks", "Add a song", None, None, ""),
    ("asset", "Open the Rack",
     "Add the working audio or assets that will move through Studio and "
     "Releases.",
     "/rack", "Open the Rack", None, "song", ""),
    ("link", "Create your first smart link",
     "Give listeners one place to find the music and become fans.",
     "/links/new", "Create smart link", "song", None,
     "Add a song first so Street Banker knows what the link supports."),
    ("capture", "Turn on fan capture",
     "Choose what listeners can share and record how consent will be "
     "handled.",
     "/links", "Set up capture", None, "link", ""),
]

KEYS = tuple(e[0] for e in ESSENTIALS)

# How many cards compete for attention at once. The rest are revealed
# as the ones before them are done (owner: "only three should compete
# for attention at once").
SHOW_AT_ONCE = 3

STATES = ("new", "setup", "operational", "error")


def read(uid, store, mls, release_ready_store):
    """The five facts, each a real query, each about a saved record.

    RAISES on any failure. That is the point: the caller decides what a
    failure means, and here it means "error", never "new".

    identity  artist or label details SAVED - the EPK profile or the
              pulse profile's artist name. NOT the signup name: the old
              has_profile counted `user["name"]`, so a brand-new account
              read "1 / 5 done" for having typed its name at signup
              (audit, 2026-09-22).
    song      a saved song or Work record: a passport, a catalog row, or
              a title on a statement the account uploaded (a statement
              is a record of a song the account owns).
    asset     working audio attached to a song: a Release-Ready master
              stored against a passport, or a Studio measurement that
              names a track. A rack PRESET is a setting, not an asset,
              so it does not count here.
    link      a smart link or campaign, in either of the two tables one
              can live in.
    capture   a campaign that captures email AND carries consent text -
              the two halves the alerts already check separately.
    """
    epk = store.get_epk(uid) or {}
    epk_data = epk.get("data") if isinstance(epk, dict) else None
    pulse = store.get_pulse_profile(uid) or {}
    identity = bool(
        (isinstance(epk_data, dict) and any(
            str(v or "").strip() for v in epk_data.values()))
        or str(pulse.get("artist_name") or "").strip())

    passports = store.list_os_tracks(uid)
    song = (bool(passports)
            or bool(store.get_catalog_tracks(uid))
            or bool(store.statement_titles(uid, 1)))

    masters = release_ready_store.masters_by_track(uid)
    analyses = store.get_track_analyses(uid, 50)
    asset = bool(masters) or any((a.get("track_id") or "").strip()
                                 for a in analyses)

    campaigns = mls.list_campaigns(uid)
    link = bool(campaigns) or bool(store.get_db_links(uid))

    capture = any(
        (c.get("settings") or {}).get("email_capture")
        and str((c.get("settings") or {}).get("consent_text") or "").strip()
        for c in campaigns if not c.get("archived_at"))

    return {"identity": identity, "song": song, "asset": asset,
            "link": link, "capture": capture}


def build(flags, reachable=None):
    """The five essentials for one account, with status and reveal.

    `flags`      {key: bool} from read()
    `reachable`  the keys this plan can open, or None for all. A step
                 nobody can reach is dropped rather than counted, so the
                 tally matches the doors on offer (firstrun's rule).

    Returns a dict the page renders from, never None: the zero-state
    page shows this list; the operational page shows it collapsed.
    """
    flags = flags or {}
    rows = []
    for key, title, why, href, cta, locked_by, reveal_after, lock_text in ESSENTIALS:
        if reachable is not None and key not in reachable:
            continue
        rows.append({"key": key, "title": title, "why": why, "href": href,
                     "cta": cta, "locked_by": locked_by,
                     "reveal_after": reveal_after, "lock_text": lock_text,
                     "done": bool(flags.get(key))})
    done_keys = {r["key"] for r in rows if r["done"]}

    # Status. COMPLETE when the thing exists. LOCKED when the card is on
    # the board but the key it is locked by is not done - and only then
    # does it show its lock text. Otherwise NOT STARTED. This module
    # knows nothing about "in progress": progress is a saved record or
    # it is nothing (owner: "opening a task does not count").
    for r in rows:
        if r["done"]:
            r["status"] = "complete"
        elif r["locked_by"] and r["locked_by"] not in done_keys:
            r["status"] = "locked"
        else:
            r["status"] = "not_started"

    # Reveal. A card with REVEAL_AFTER stays off the board until that
    # key is done. Of the rest, the first SHOW_AT_ONCE that are not
    # complete are offered, in order - on a fresh account that is
    # identity, song and the LOCKED link, so the reader sees where setup
    # is going without five tasks at once. Complete cards are kept (the
    # page shows them ticked) and do not use a slot.
    open_slots = SHOW_AT_ONCE
    for r in rows:
        if r["done"]:
            r["revealed"] = True
            continue
        if r["reveal_after"] and r["reveal_after"] not in done_keys:
            r["revealed"] = False
            continue
        if open_slots > 0:
            r["revealed"] = True
            open_slots -= 1
        else:
            r["revealed"] = False

    done = len(done_keys)
    total = len(rows)
    nxt = next((r for r in rows if r["status"] == "not_started"), None)
    return {
        "steps": rows,
        "shown": [r for r in rows if r["revealed"]],
        "done": done,
        "total": total,
        "remaining": total - done,
        "next": nxt,
        # A brand-new account gets different words to a half-set-up one
        # (the Start-here panel reads this).
        "fresh": done == 0,
        "complete": total > 0 and done == total,
        "progress": "%d of %d essentials complete." % (done, total),
    }


def state_of(essentials, has_records):
    """Which of the four states this account is in.

    `essentials`  what build() returned
    `has_records` whether ANY real record exists beyond the essentials -
                  fans, statements, shows - so an account that did real
                  work before finishing setup is not called "new".
    """
    if essentials["total"] == 0:
        # Nothing this plan can do is on the list: nothing to set up.
        return "operational"
    if essentials["complete"]:
        return "operational"
    if has_records:
        # Statements or fans on file: this account is WORKING, whatever
        # the checklist says, and its money and people must not sit
        # behind an onboarding page. The operational page keeps the
        # essentials panel until they are done (the spec's "gradual
        # transition into operations").
        return "operational"
    if essentials["done"] == 0:
        return "new"
    return "setup"


def decide(uid, store, mls, release_ready_store, reachable=None,
           has_records=None):
    """The state, the essentials, and - if reading failed - the reason.

    Returns {"state", "essentials", "error"}. On ANY exception in read()
    the state is "error" and essentials is None: the page must then say
    it could not load, and must not guess.
    """
    try:
        flags = read(uid, store, mls, release_ready_store)
    except Exception as exc:                          # noqa: BLE001
        return {"state": "error", "essentials": None, "error": repr(exc)}
    essentials = build(flags, reachable)
    if has_records is None:
        has_records = False
    return {"state": state_of(essentials, bool(has_records)),
            "essentials": essentials, "error": None}
