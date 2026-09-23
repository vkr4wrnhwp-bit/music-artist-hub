"""Street Banker Links data layer: campaigns, destinations, events, fans,
consents, and link variants. Tables are created in db.init_db(); this module
holds the queries so the campaign engine stays separate from the core store.
"""

import json
import uuid

from db import get_db, _now

# --- Campaigns -----------------------------------------------------------------

_EDITABLE = ("title", "artist_name", "release_type", "campaign_type",
             "release_date", "cover_url", "description")


def create_campaign(user_id, slug, fields):
    campaign_id = uuid.uuid4().hex
    now = _now()
    with get_db() as db:
        db.execute(
            "INSERT INTO ml_campaigns (id, user_id, slug, title, artist_name, release_type,"
            " campaign_type, status, release_date, cover_url, description, settings, created, updated)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (campaign_id, user_id, slug, fields.get("title") or "Untitled",
             fields.get("artist_name") or "", fields.get("release_type") or "Single",
             fields.get("campaign_type") or "release", "draft",
             fields.get("release_date") or "", fields.get("cover_url") or "",
             fields.get("description") or "",
             json.dumps(fields.get("settings") or {}), now, now),
        )
    return campaign_id


def update_campaign(campaign_id, user_id, fields):
    sets, vals = [], []
    for key in _EDITABLE:
        if key in fields:
            sets.append("%s = ?" % key)
            vals.append(fields[key] or "")
    if "settings" in fields:
        sets.append("settings = ?")
        vals.append(json.dumps(fields["settings"] or {}))
    if "status" in fields:
        sets.append("status = ?")
        vals.append(fields["status"])
    if fields.get("published_at"):
        sets.append("published_at = ?")
        vals.append(fields["published_at"])
    if "archived_at" in fields:
        sets.append("archived_at = ?")
        vals.append(fields["archived_at"])
    if not sets:
        return False
    sets.append("updated = ?")
    vals.extend([_now(), campaign_id, user_id])
    with get_db() as db:
        cur = db.execute(
            "UPDATE ml_campaigns SET %s WHERE id = ? AND user_id = ?" % ", ".join(sets), vals)
    return cur.rowcount > 0


def clear_campaign_cover(campaign_id, user_id):
    """Put the cover back to empty and hand back the path that was there.

    A campaign had no way to lose its cover: `_ml_cover_upload` names
    every upload with a fresh UUID, so the builder could only ever point
    the field at a NEW file. The old one stayed on the disk with nothing
    referencing it, and an artist who wanted no cover at all could not
    say so.

    Returns "" when the field was already empty, so clearing twice is a
    no-op rather than an error, and the caller learns whether there is a
    file worth unlinking without having to read the row first.
    """
    with get_db() as db:
        row = db.execute(
            "SELECT cover_url FROM ml_campaigns WHERE id = ? AND user_id = ?",
            (campaign_id, user_id)).fetchone()
        if row is None:
            return ""
        db.execute("UPDATE ml_campaigns SET cover_url = '', updated = ?"
                   " WHERE id = ? AND user_id = ?",
                   (_now(), campaign_id, user_id))
    return row["cover_url"] or ""


def _row(row):
    d = dict(row)
    d["settings"] = json.loads(d.get("settings") or "{}")
    return d


def get_campaign(campaign_id, user_id=None):
    q = "SELECT * FROM ml_campaigns WHERE id = ?"
    args = [campaign_id]
    if user_id is not None:
        q += " AND user_id = ?"
        args.append(user_id)
    with get_db() as db:
        row = db.execute(q, args).fetchone()
    return _row(row) if row else None


def get_campaign_by_slug(slug):
    with get_db() as db:
        row = db.execute("SELECT * FROM ml_campaigns WHERE slug = ?", (slug,)).fetchone()
    return _row(row) if row else None


def list_campaigns(user_id):
    with get_db() as db:
        rows = db.execute("SELECT * FROM ml_campaigns WHERE user_id = ? ORDER BY updated DESC",
                          (user_id,)).fetchall()
    return [_row(r) for r in rows]


def duplicate_campaign(campaign_id, user_id, new_slug):
    src = get_campaign(campaign_id, user_id)
    if src is None:
        return None
    fields = {k: src[k] for k in _EDITABLE}
    fields["title"] = src["title"] + " (copy)"
    fields["settings"] = src["settings"]
    new_id = create_campaign(user_id, new_slug, fields)
    set_destinations(new_id, get_destinations(campaign_id))
    return new_id


# --- Destinations ----------------------------------------------------------------

def set_destinations(campaign_id, destinations):
    """Replace the campaign's destination set."""
    with get_db() as db:
        db.execute("DELETE FROM ml_destinations WHERE campaign_id = ?", (campaign_id,))
        for d in destinations:
            db.execute(
                "INSERT INTO ml_destinations (id, campaign_id, service_key, service_name,"
                " url, sort_order, is_active) VALUES (?,?,?,?,?,?,1)",
                (uuid.uuid4().hex, campaign_id, d["service_key"], d["service_name"],
                 d["url"], d.get("sort_order", 0)),
            )


def get_destinations(campaign_id, active_only=False):
    q = "SELECT * FROM ml_destinations WHERE campaign_id = ?"
    if active_only:
        q += " AND is_active = 1"
    q += " ORDER BY sort_order, service_name"
    with get_db() as db:
        rows = db.execute(q, (campaign_id,)).fetchall()
    return [dict(r) for r in rows]


def get_destination(dest_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM ml_destinations WHERE id = ?", (dest_id,)).fetchone()
    return dict(row) if row else None


# --- Events ------------------------------------------------------------------------

def track(campaign_id, event_type, variant_id=None, service_key=None,
          fan_id=None, referrer=None, utm_source=None):
    """One event. fan_id is set when the request said who it was: a
    capture, a pre-save, or a view or click through a fan's own link
    (fan_mail.fan_token). Everything else is anonymous."""
    with get_db() as db:
        db.execute(
            "INSERT INTO ml_events (campaign_id, variant_id, event_type, service_key,"
            " fan_id, referrer, utm_source, created) VALUES (?,?,?,?,?,?,?,?)",
            (campaign_id, variant_id, event_type, service_key, fan_id,
             (referrer or "")[:300], (utm_source or "")[:100], _now()),
        )


def fan_event_since(campaign_id, fan_id, event_type, since):
    """Whether this fan raised this event on this campaign at or after
    `since` (an ISO stamp, the format _now() writes). The Fan CRM counts a
    visit once per sitting, not once per reload."""
    with get_db() as db:
        row = db.execute(
            "SELECT 1 FROM ml_events WHERE campaign_id = ? AND fan_id = ?"
            " AND event_type = ? AND created >= ? LIMIT 1",
            (campaign_id, fan_id, event_type, since)).fetchone()
    return row is not None


def event_counts(campaign_id):
    with get_db() as db:
        rows = db.execute(
            "SELECT event_type, COUNT(*) AS n FROM ml_events WHERE campaign_id = ?"
            " GROUP BY event_type", (campaign_id,)).fetchall()
    return {r["event_type"]: r["n"] for r in rows}


def breakdown(campaign_id, column, event_type=None, limit=8):
    if column not in ("service_key", "referrer", "utm_source", "variant_id"):
        raise ValueError(column)
    q = ("SELECT {col} AS k, COUNT(*) AS n FROM ml_events WHERE campaign_id = ?"
         " AND {col} IS NOT NULL AND {col} != ''").format(col=column)
    args = [campaign_id]
    if event_type:
        q += " AND event_type = ?"
        args.append(event_type)
    q += " GROUP BY {col} ORDER BY n DESC LIMIT {lim}".format(col=column, lim=int(limit))
    with get_db() as db:
        rows = db.execute(q, args).fetchall()
    return [(r["k"], r["n"]) for r in rows]


def timeline(campaign_id, days=14):
    with get_db() as db:
        rows = db.execute(
            "SELECT substr(created, 1, 10) AS day, COUNT(*) AS n FROM ml_events"
            " WHERE campaign_id = ? AND event_type = 'page_view'"
            " GROUP BY day ORDER BY day DESC LIMIT ?", (campaign_id, days)).fetchall()
    return list(reversed([(r["day"], r["n"]) for r in rows]))


def account_event_counts(user_id):
    with get_db() as db:
        rows = db.execute(
            "SELECT e.event_type, COUNT(*) AS n FROM ml_events e"
            " JOIN ml_campaigns c ON c.id = e.campaign_id WHERE c.user_id = ?"
            " GROUP BY e.event_type", (user_id,)).fetchall()
    return {r["event_type"]: r["n"] for r in rows}


# --- Fans + consents --------------------------------------------------------------

def upsert_fan(user_id, email, campaign_id, name=""):
    """Create or refresh a fan record; returns the fan id."""
    email = email.lower().strip()
    now = _now()
    with get_db() as db:
        row = db.execute("SELECT id FROM ml_fans WHERE user_id = ? AND email = ?",
                         (user_id, email)).fetchone()
        if row:
            db.execute(
                "UPDATE ml_fans SET last_campaign_id = ?, updated = ?,"
                " name = CASE WHEN name = '' THEN ? ELSE name END WHERE id = ?",
                (campaign_id, now, name.strip(), row["id"]))
            return row["id"]
        fan_id = uuid.uuid4().hex
        db.execute(
            "INSERT INTO ml_fans (id, user_id, email, name, first_campaign_id,"
            " last_campaign_id, created, updated) VALUES (?,?,?,?,?,?,?,?)",
            (fan_id, user_id, email, name.strip(), campaign_id, campaign_id, now, now))
        return fan_id


def set_fan_place(fan_id, country="", city=""):
    """Where a fan is, when the file said so. Never overwrites something
    with nothing: a later import that carries no location leaves the
    location an earlier one recorded."""
    country, city = (country or "").strip()[:80], (city or "").strip()[:80]
    if not country and not city:
        return
    with get_db() as db:
        db.execute(
            "UPDATE ml_fans SET country = CASE WHEN ? <> '' THEN ? ELSE country END,"
            " city = CASE WHEN ? <> '' THEN ? ELSE city END, updated = ? WHERE id = ?",
            (country, country, city, city, _now(), fan_id))


def confirm_list_import(user_id, draft_id, make_note):
    """File a previewed list, once, in one transaction. Returns the summary
    recorded, or None when the draft is not this user's live draft.

    Everything happens on one connection and is committed together: the
    draft's DELETE, every new fan with its tag, place and consent, the
    blanks filled on fans already here, and the fan_imports record. Until
    2026-09-18 confirm deleted the draft first and then filed row by row,
    four connections and four commits a row (about 7 rows a second on this
    machine), so a big list could outlive the worker's timeout and leave
    half a list, no draft and no record. Now a request killed partway
    leaves the draft in place and nothing written.

    The rows are the preview's. Each is checked against who is on file NOW:
      - marked new and still not on file: created, tagged "imported", its
        place as the file gave it, a list_import consent with make_note's
        sentence;
      - marked new but on file since the preview (they gave their email on
        a smart link in between): treated as already here, so no tag and no
        list_import consent is laid over the way they really arrived;
      - already here: only a country or city the record is MISSING is
        filled from the file. A place the record holds is never replaced.
    The summary recorded is the preview's, corrected by what actually
    happened, so the counts still add up to the rows read.
    """
    if not draft_id:
        return None
    now = _now()
    with get_db() as db:
        db.execute("DELETE FROM fan_import_drafts WHERE expires < ?", (now,))
        draft = db.execute(
            "SELECT * FROM fan_import_drafts WHERE id = ? AND user_id = ? AND expires >= ?",
            (draft_id, user_id, now)).fetchone()
        if draft is None:
            return None
        # The DELETE is the claim, inside the same transaction as the
        # writes: a second confirm waits on the lock and then finds nothing.
        if db.execute("DELETE FROM fan_import_drafts WHERE id = ? AND user_id = ?",
                      (draft_id, user_id)).rowcount != 1:
            return None
        try:
            summary = json.loads(draft["summary"] or "{}")
            rows = json.loads(draft["rows"] or "[]")
        except ValueError:
            summary, rows = {}, []
        note = (make_note(dict(draft)) or "")[:500]
        on_file = {r["email"]: r for r in db.execute(
            "SELECT id, email, country, city FROM ml_fans WHERE user_id = ?", (user_id,))}

        inserts, consents, fills = [], [], []
        arrived = gone = 0
        for row in rows:
            email = (row.get("email") or "").lower().strip()
            if not email:
                continue
            country = (row.get("country") or "").strip()[:80]
            city = (row.get("city") or "").strip()[:80]
            rec = on_file.get(email)
            if rec is None:
                if not row.get("new"):
                    gone += 1  # on file at the preview, deleted since: not re-added
                    continue
                fan_id = uuid.uuid4().hex
                inserts.append((fan_id, user_id, email, (row.get("name") or "").strip(),
                                None, None, json.dumps(["imported"]), country, city, now, now))
                consents.append((fan_id, None, "list_import", note, now))
                on_file[email] = {"id": fan_id, "country": country, "city": city}
                continue
            if row.get("new"):
                arrived += 1
            fill_country = country if country and not (rec["country"] or "").strip() else ""
            fill_city = city if city and not (rec["city"] or "").strip() else ""
            if fill_country or fill_city:
                fills.append((fill_country, fill_country, fill_city, fill_city, now, rec["id"]))

        db.executemany(
            "INSERT INTO ml_fans (id, user_id, email, name, first_campaign_id, last_campaign_id,"
            " tags, country, city, created, updated) VALUES (?,?,?,?,?,?,?,?,?,?,?)", inserts)
        db.executemany(
            "INSERT INTO ml_consents (fan_id, campaign_id, consent_type, consent_text, created)"
            " VALUES (?,?,?,?,?)", consents)
        db.executemany(
            "UPDATE ml_fans SET country = CASE WHEN country = '' AND ? <> '' THEN ? ELSE country END,"
            " city = CASE WHEN city = '' AND ? <> '' THEN ? ELSE city END, updated = ? WHERE id = ?",
            fills)

        done = dict(summary)
        done["new"] = len(inserts)
        done["already_here"] = int(summary.get("already_here") or 0) + arrived
        done["places_filled"] = len(fills)
        if arrived:
            done["arrived_since_preview"] = arrived
        if gone:
            done["removed_since_preview"] = gone
        db.execute("INSERT INTO fan_imports (id, user_id, source, summary, error, cursor, created)"
                   " VALUES (?,?,?,?,?,?,?)",
                   (uuid.uuid4().hex, user_id, "list", json.dumps(done), "", "", now))
    return done


def suppress_fan(user_id, email, reason):
    """Stop contacting this address, and record why. Returns whether a fan
    row on this account was marked.

    A reason rather than a flag: "why is this person not being emailed" is
    the question anyone actually asks, and a bare boolean cannot answer it.
    Scoped to the account in the UPDATE itself. Callers: the fan's own
    unsubscribe link and the artist's do-not-contact mark (fan_mail).
    """
    reason = (reason or "").strip()[:120] or "suppressed"
    with get_db() as db:
        cur = db.execute("UPDATE ml_fans SET suppressed = ?, suppressed_at = ?, updated = ?"
                         " WHERE user_id = ? AND email = ?",
                         (reason, _now(), _now(), user_id, (email or "").lower().strip()))
    return cur.rowcount > 0


def add_suppressed_fan(user_id, email, reason, created=None):
    """A fan row that exists only to hold a suppression: a Fan Club member
    whose CRM record was removed still gets drop emails (the membership is
    its own table), so their unsubscribe needs a row to land on. `created`
    is when they joined, so they are not counted as a new fan today.
    Returns the fan id; an address already on file is marked instead."""
    email = (email or "").lower().strip()
    if suppress_fan(user_id, email, reason):
        return (fan_by_email(user_id, email) or {}).get("id")
    fan_id = uuid.uuid4().hex
    now = _now()
    with get_db() as db:
        db.execute(
            "INSERT INTO ml_fans (id, user_id, email, name, first_campaign_id, last_campaign_id,"
            " suppressed, suppressed_at, created, updated) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (fan_id, user_id, email, "", None, None, (reason or "suppressed")[:120], now,
             created or now, now))
    return fan_id


def unsuppress_fan(user_id, email, only_reason=None):
    """Lift a suppression. only_reason, when given, lifts it only if that is
    the reason on file, so the artist cannot lift a fan's own unsubscribe
    and a fan cannot lift the artist's do-not-contact mark (fan_mail).
    Returns whether a row changed."""
    q = ("UPDATE ml_fans SET suppressed = '', suppressed_at = '', updated = ?"
         " WHERE user_id = ? AND email = ?")
    args = [_now(), user_id, (email or "").lower().strip()]
    if only_reason is not None:
        q += " AND suppressed = ?"
        args.append(only_reason)
    with get_db() as db:
        cur = db.execute(q, args)
    return cur.rowcount > 0


_FAN_COUNTERS = ("total_visits", "total_clicks", "total_presaves", "total_captures")


def bump_fan(fan_id, field, amount=1):
    if field not in _FAN_COUNTERS:
        raise ValueError(field)
    with get_db() as db:
        db.execute("UPDATE ml_fans SET %s = %s + ?, updated = ? WHERE id = ?" % (field, field),
                   (amount, _now(), fan_id))


def set_fan_intent(fan_id, score, level):
    with get_db() as db:
        db.execute("UPDATE ml_fans SET intent_score = ?, intent_level = ? WHERE id = ?",
                   (score, level, fan_id))


def fan_by_email(user_id, email):
    with get_db() as db:
        row = db.execute("SELECT * FROM ml_fans WHERE user_id = ? AND email = ?",
                         (user_id, (email or "").lower().strip())).fetchone()
    return dict(row) if row else None


def add_fan_tags(fan_id, tags):
    """Merge tags onto a fan; the list stays unique and ordered."""
    with get_db() as db:
        row = db.execute("SELECT tags FROM ml_fans WHERE id = ?", (fan_id,)).fetchone()
        if row is None:
            return []
        try:
            have = json.loads(row["tags"] or "[]")
        except ValueError:
            have = []
        merged = list(have) + [t for t in tags if t and t not in have]
        db.execute("UPDATE ml_fans SET tags = ?, updated = ? WHERE id = ?",
                   (json.dumps(merged), _now(), fan_id))
    return merged


def find_consent(fan_id, consent_type):
    with get_db() as db:
        row = db.execute("SELECT * FROM ml_consents WHERE fan_id = ? AND consent_type = ? LIMIT 1",
                         (fan_id, consent_type)).fetchone()
    return dict(row) if row else None


def get_fan(fan_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM ml_fans WHERE id = ?", (fan_id,)).fetchone()
    return dict(row) if row else None


def delete_fan(user_id, fan_id):
    """Remove one fan and everything that names them - consents and the
    events they generated - only if the fan belongs to this account.

    A person who asked to be forgotten is forgotten from the consent log
    too: keeping "they consented" about somebody whose record is gone is
    not a record of consent, it is the thing they asked to have removed.
    Returns whether a fan row went.
    """
    with get_db() as db:
        cur = db.execute("DELETE FROM ml_fans WHERE id = ? AND user_id = ?", (fan_id, user_id))
        if cur.rowcount:
            db.execute("DELETE FROM ml_consents WHERE fan_id = ?", (fan_id,))
            db.execute("DELETE FROM ml_events WHERE fan_id = ?", (fan_id,))
    return cur.rowcount > 0


def list_fans(user_id, query=""):
    q = "SELECT * FROM ml_fans WHERE user_id = ?"
    args = [user_id]
    if query:
        q += " AND (email LIKE ? OR name LIKE ?)"
        args.extend(["%" + query + "%"] * 2)
    q += " ORDER BY intent_score DESC, updated DESC"
    with get_db() as db:
        rows = db.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def campaign_fans(campaign_id):
    """Fans who consented on this campaign (deduped, with email)."""
    with get_db() as db:
        rows = db.execute(
            "SELECT DISTINCT f.* FROM ml_fans f "
            "JOIN ml_consents c ON c.fan_id = f.id "
            "WHERE c.campaign_id = ? AND f.email != ''", (campaign_id,)).fetchall()
    return [dict(r) for r in rows]


def add_consent(fan_id, campaign_id, consent_type, consent_text):
    with get_db() as db:
        db.execute(
            "INSERT INTO ml_consents (fan_id, campaign_id, consent_type, consent_text, created)"
            " VALUES (?,?,?,?,?)",
            (fan_id, campaign_id, consent_type, (consent_text or "")[:500], _now()))


def list_consents(fan_id):
    with get_db() as db:
        rows = db.execute("SELECT * FROM ml_consents WHERE fan_id = ? ORDER BY created",
                          (fan_id,)).fetchall()
    return [dict(r) for r in rows]


# --- Variants -----------------------------------------------------------------------

def create_variant(campaign_id, name, slug, utm_source="", utm_medium=""):
    variant_id = uuid.uuid4().hex
    with get_db() as db:
        db.execute(
            "INSERT INTO ml_variants (id, campaign_id, name, slug, utm_source, utm_medium,"
            " is_active, created) VALUES (?,?,?,?,?,?,1,?)",
            (variant_id, campaign_id, name, slug, utm_source, utm_medium, _now()))
    return variant_id


def get_variant_by_slug(slug):
    with get_db() as db:
        row = db.execute("SELECT * FROM ml_variants WHERE slug = ?", (slug,)).fetchone()
    return dict(row) if row else None


def list_variants(campaign_id):
    with get_db() as db:
        rows = db.execute("SELECT * FROM ml_variants WHERE campaign_id = ? ORDER BY created",
                          (campaign_id,)).fetchall()
    return [dict(r) for r in rows]


def variant_stats(campaign_id):
    with get_db() as db:
        rows = db.execute(
            "SELECT variant_id, event_type, COUNT(*) AS n FROM ml_events"
            " WHERE campaign_id = ? AND variant_id IS NOT NULL"
            " GROUP BY variant_id, event_type", (campaign_id,)).fetchall()
    out = {}
    for r in rows:
        out.setdefault(r["variant_id"], {})[r["event_type"]] = r["n"]
    return out
