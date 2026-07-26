"""Artist OS engines — the spine every OS-layer page reads.

Pure functions over a track's passport/lockbox JSON plus a `ctx` dict of
real account signals (statement lanes, fans, links, club members). No
invented numbers: estimates exist only where the artist's own statements
provide a basis, and every function says what it doesn't know.
"""

# (key, label, critical, fix_route) — critical means a rights/blocking
# issue: empty or negative stays RED and blocks Clean Release.
PASSPORT_FIELDS = [
    ("artist_name",     "Artist name",              False, None),
    ("legal_name",      "Legal name",               False, None),
    ("label",           "Label",                    False, None),
    ("release_title",   "Release title",            False, None),
    ("upc",             "UPC",                      False, "/identifiers"),
    ("isrc",            "ISRC",                     False, "/identifiers"),
    ("songwriters",     "Songwriters",              True,  None),
    ("producers",       "Producers",                False, None),
    ("publishers",      "Publishers",               False, "/publishing"),
    ("pro",             "PRO affiliation",          False, "/publishing"),
    ("mlc_status",      "MLC registration",         False, "/mechanicals"),
    ("soundexchange_status", "SoundExchange",       False, "/neighboring-rights"),
    ("content_id_status", "YouTube Content ID",     False, "/connections"),
    ("split_sheet_status", "Split sheet",           True,  None),
    ("sample_clearance", "Sample clearance",        True,  None),
    ("beat_license",    "Beat license",             True,  None),
    ("featured_approval", "Featured artist approval", True, None),
    ("master_owner",    "Master owner",             True,  None),
    ("pub_admin",       "Publishing administrator", False, "/publishing"),
    ("explicit",        "Explicit status",          False, None),
    ("artwork_rights",  "Artwork rights",           True,  None),
    ("ai_disclosure",   "AI disclosure",            True,  None),
    ("territories",     "Territory restrictions",   False, None),
    ("release_date",    "Release date",             False, "/releases"),
    ("dsp_routing",     "DSP profile routing",      False, "/connections"),
]

_NEGATIVE = ("blocked", "issue", "unresolved", "declined", "disputed", "no")
_POSITIVE_HINTS = ("registered", "cleared", "signed", "licensed", "approved",
                   "complete", "done", "yes", "clean", "routed", "n/a",
                   "none needed", "not applicable", "original", "owned")


def field_state(key, value, critical):
    """green / yellow / red for one passport field."""
    v = (value or "").strip().lower()
    if not v:
        return "red" if critical else "yellow"
    if any(n in v for n in _NEGATIVE):
        return "red"
    if v in ("pending", "in review", "submitted", "waiting"):
        return "yellow"
    return "green"


def passport_report(track):
    passport = track.get("passport") or {}
    items = []
    for key, label, critical, fix in PASSPORT_FIELDS:
        value = passport.get(key, "")
        if key == "release_title" and not value:
            value = track.get("release_title") or ""
        if key == "release_date" and not value:
            value = track.get("release_date") or ""
        state = field_state(key, value, critical)
        items.append({"key": key, "label": label, "value": value,
                      "state": state, "critical": critical, "fix": fix})
    reds = [i for i in items if i["state"] == "red"]
    yellows = [i for i in items if i["state"] == "yellow"]
    overall = "red" if reds else ("yellow" if yellows else "green")
    done = len([i for i in items if i["state"] == "green"])
    return {"items": items, "overall": overall,
            "greens": done, "yellows": len(yellows), "reds": len(reds),
            "pct": round(100 * done / len(items))}


# --- Rights / Split Lockbox ----------------------------------------------------

LOCKBOX_DOCS = [
    ("split_sheet",       "Split sheet",              True),
    ("producer_agreement", "Producer agreement",      False),
    ("beat_license",      "Beat license",             True),
    ("sample_clearance",  "Sample clearance",         True),
    ("featured_approval", "Featured artist approval", True),
    ("artwork_license",   "Artwork license",          False),
    ("video_license",     "Video license",            False),
    ("ai_voice_consent",  "AI voice consent",         False),
]

APPROVAL_STATES = ("pending", "signed", "declined", "needs resend")


def lockbox_report(track):
    box = track.get("lockbox") or {}
    docs = []
    for key, label, needed in LOCKBOX_DOCS:
        entry = box.get(key) or {}
        na = bool(entry.get("not_applicable"))
        uploaded = bool(entry.get("file"))
        approvals = entry.get("approvals") or []
        signed = all(a.get("state") == "signed" for a in approvals) if approvals else True
        declined = any(a.get("state") == "declined" for a in approvals)
        state = ("n/a" if na else
                 "declined" if declined else
                 "ready" if (uploaded and signed) else
                 "awaiting signatures" if uploaded else
                 "missing")
        docs.append({"key": key, "label": label, "required": needed,
                     "state": state, "file": entry.get("file", ""),
                     "approvals": approvals, "not_applicable": na})
    def ok(*keys):
        return all(d["state"] in ("ready", "n/a")
                   for d in docs if d["key"] in keys)
    caps = {
        "release":  ok("split_sheet", "beat_license", "sample_clearance",
                       "featured_approval"),
        "monetize": ok("split_sheet", "beat_license", "sample_clearance"),
        "sync":     ok("split_sheet", "beat_license", "sample_clearance",
                       "featured_approval", "artwork_license"),
        "pitch":    ok("split_sheet"),
    }
    return {"docs": docs, "caps": caps}


# --- Clean Release --------------------------------------------------------------

def clean_release(track, ctx):
    """17 checks -> score 0-100; red rights issues block submission.
    ctx carries real account signals; unknown stays honest yellow."""
    rep = passport_report(track)
    p = {i["key"]: i for i in rep["items"]}
    box = lockbox_report(track)

    def pf(key):  # passport field state
        return p[key]["state"]

    checks = [
        ("Audio quality confirmed",  "green" if (track.get("passport") or {}).get("audio_ok") else "yellow", False),
        ("Artwork specs confirmed",  "green" if (track.get("passport") or {}).get("artwork_ok") else "yellow", False),
        ("Metadata complete",        rep["overall"], True),
        ("Artist profile routing",   pf("dsp_routing"), False),
        ("Splits locked",            "green" if box["docs"][0]["state"] in ("ready", "n/a") else "red", True),
        ("Publishing set",           pf("publishers"), False),
        ("Mechanical collection (MLC)", pf("mlc_status"), False),
        ("SoundExchange",            pf("soundexchange_status"), False),
        ("Content ID",               pf("content_id_status"), False),
        ("AI disclosure",            pf("ai_disclosure"), True),
        ("Sample & beat licenses",   "green" if all(
            d["state"] in ("ready", "n/a") for d in box["docs"]
            if d["key"] in ("beat_license", "sample_clearance")) else "red", True),
        ("Featured artist approval", "green" if box["docs"][4]["state"] in ("ready", "n/a") else "red", True),
        ("Pre-save / smart link live", "green" if ctx.get("live_links") else "yellow", False),
        ("Spotify pitch reminder set", "green" if ctx.get("release_scheduled") else "yellow", False),
        ("Apple/YouTube profile ready", pf("dsp_routing"), False),
        ("Social assets prepared",   "green" if ctx.get("rollout_assets") else "yellow", False),
        ("Fan capture in place",     "green" if ctx.get("fans") else "yellow", False),
    ]
    items = [{"label": lbl, "state": st, "critical": crit}
             for lbl, st, crit in checks]
    score = round(sum({"green": 1, "yellow": 0.4, "red": 0}[i["state"]]
                      for i in items) / len(items) * 100)
    blocked = any(i["state"] == "red" and i["critical"] for i in items)
    return {"items": items, "score": score, "blocked": blocked}


# --- Royalty Lane Tracker -------------------------------------------------------

LANES = [
    ("master",       "Master royalties"),
    ("mechanicals",  "Publishing mechanicals"),
    ("pro",          "PRO performance"),
    ("soundexchange", "SoundExchange / digital performance"),
    ("neighboring",  "Neighboring rights"),
    ("content_id",   "YouTube Content ID"),
    ("ugc",          "TikTok / Meta / UGC"),
    ("sync",         "Sync licensing"),
    ("fan_sales",    "Direct fan sales"),
]

# Rough lane shares of a typical indie catalog's collected total — used
# ONLY to size an estimate from the artist's OWN statement revenue.
_LANE_SHARE = {"mechanicals": 0.06, "pro": 0.12, "soundexchange": 0.05,
               "neighboring": 0.04, "content_id": 0.05, "ugc": 0.04}


def _lane_state(lane, track, ctx):
    passport = track.get("passport") or {}
    data_lanes = ctx.get("lanes_with_data") or set()
    if lane == "master":
        return "connected" if ctx.get("statement_rows") else "missing"
    if lane == "mechanicals":
        s = field_state("mlc_status", passport.get("mlc_status"), False)
        return {"green": "connected", "yellow": "needs action", "red": "needs action"}[s] \
            if passport.get("mlc_status") or s != "yellow" else "missing"
    if lane == "pro":
        return "connected" if field_state("pro", passport.get("pro"), False) == "green" else "missing"
    if lane == "soundexchange":
        s = passport.get("soundexchange_status", "")
        return "connected" if field_state("soundexchange_status", s, False) == "green" \
            else ("in review" if s.strip().lower() in ("pending", "in review", "submitted") else "missing")
    if lane == "neighboring":
        return "connected" if "neighboring" in data_lanes else "missing"
    if lane == "content_id":
        s = passport.get("content_id_status", "")
        return "connected" if field_state("content_id_status", s, False) == "green" \
            else ("in review" if s.strip().lower() in ("pending", "in review", "submitted") else "missing")
    if lane == "ugc":
        return "connected" if "ugc" in data_lanes else (
            "needs action" if field_state("content_id_status",
                                          passport.get("content_id_status"), False) == "green"
            else "missing")
    if lane == "sync":
        return "connected" if ctx.get("sync_active") else "not eligible" \
            if (track.get("passport") or {}).get("sample_clearance", "").strip().lower() \
            and field_state("sample_clearance", passport.get("sample_clearance"), True) == "red" \
            else "missing"
    if lane == "fan_sales":
        return "connected" if ctx.get("club_members") else "missing"
    return "missing"


def lane_grid(track, ctx):
    total = float(ctx.get("statement_total") or 0)
    lanes = []
    for key, label in LANES:
        state = _lane_state(key, track, ctx)
        est = None
        if state in ("missing", "needs action") and key in _LANE_SHARE and total > 0:
            est = round(total * _LANE_SHARE[key], 2)
        lanes.append({"key": key, "label": label, "state": state,
                      "estimate": est,
                      "estimate_basis": ("share of your own statement earnings"
                                         if est is not None else None)})
    return lanes


# --- Missing Money Action Queue -------------------------------------------------

_DIFFICULTY = {"mlc_status": "medium", "pro": "medium", "soundexchange_status": "easy",
               "content_id_status": "easy", "split_sheet_status": "easy",
               "sample_clearance": "hard", "beat_license": "easy",
               "featured_approval": "medium", "isrc": "easy", "upc": "easy",
               "ai_disclosure": "easy", "artwork_rights": "easy",
               "songwriters": "easy", "master_owner": "easy"}

_DOCS_FOR = {"mlc_status": "Songwriter splits", "split_sheet_status": "Signed split sheet",
             "sample_clearance": "Clearance letter", "beat_license": "License PDF",
             "featured_approval": "Written approval", "artwork_rights": "Artwork license or ownership note"}


def action_queue(tracks_with_ctx):
    """tracks_with_ctx: [(track, ctx)] -> prioritized actions across catalog."""
    actions = []
    for track, ctx in tracks_with_ctx:
        rep = passport_report(track)
        for item in rep["items"]:
            if item["state"] == "green":
                continue
            urgency = "release-blocking" if item["critical"] else "collect sooner"
            actions.append({
                "track": track["title"], "track_id": track["id"],
                "lane": item["label"],
                "problem": "%s is %s on “%s”." % (
                    item["label"],
                    "missing" if not item["value"] else "unresolved",
                    track["title"]),
                "impact": None, "difficulty": _DIFFICULTY.get(item["key"], "easy"),
                "urgency": urgency, "fix": item["fix"] or ("/tracks/" + track["id"]),
                "docs": _DOCS_FOR.get(item["key"], ""),
                "status": "open", "critical": item["critical"],
            })
        for lane in lane_grid(track, ctx):
            if lane["state"] in ("missing", "needs action") and lane["estimate"]:
                actions.append({
                    "track": track["title"], "track_id": track["id"],
                    "lane": lane["label"],
                    "problem": "“%s” has no %s collection set up." % (
                        track["title"], lane["label"].lower()),
                    "impact": lane["estimate"], "difficulty": "medium",
                    "urgency": "money on the table",
                    "fix": "/tracks/" + track["id"], "docs": "",
                    "status": "open", "critical": False,
                })
    actions.sort(key=lambda a: (not a["critical"], -(a["impact"] or 0)))
    return actions


# --- Street Banker Certified ----------------------------------------------------

CERT_LEVELS = ["Unranked", "Verified", "Certified", "Priority",
               "Select", "Elite", "Upstream Ready"]


def certification(summary):
    """summary: real account aggregates -> (level, reasons_for_next).
    Rule-based only; every requirement names the real signal it reads."""
    checks = [
        ("Verified",       summary.get("tracks", 0) >= 1 and summary.get("passport_avg", 0) >= 40,
         "Add a track and complete 40% of its Metadata Passport"),
        ("Certified",      summary.get("passport_avg", 0) >= 70 and summary.get("clean_avg", 0) >= 60,
         "Reach 70% passport completion and a 60 Clean Release score"),
        ("Priority",       summary.get("lanes_connected", 0) >= 3 and summary.get("fans", 0) > 0,
         "Connect 3 royalty lanes and capture your first fans"),
        ("Select",         summary.get("clean_avg", 0) >= 80 and summary.get("lockbox_ready", 0) >= 1,
         "Hit an 80 Clean Release score with one fully signed lockbox"),
        ("Elite",          summary.get("passport_avg", 0) >= 90 and summary.get("lanes_connected", 0) >= 5,
         "Reach 90% passports and 5 connected lanes"),
        ("Upstream Ready", summary.get("clean_avg", 0) >= 90 and summary.get("reds", 1) == 0
                           and summary.get("statement_rows", 0) > 0,
         "Zero red rights issues, 90+ Clean Release, and real statements on file"),
    ]
    level = "Unranked"
    next_need = checks[0][2]
    for name, passed, need in checks:
        if passed:
            level = name
        else:
            next_need = need
            break
    else:
        next_need = None
    return {"level": level, "next": next_need,
            "ladder": [{"name": n, "passed": p, "need": d} for n, p, d in checks]}
