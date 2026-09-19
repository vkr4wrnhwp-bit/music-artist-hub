"""Press Desk — the artist's own media list, announcements and pitches.

Everything here belongs to one artist and is reached only from their
session. The public half is a single route, /press/<token>, which is the
page a journalist opens: one announcement, its assets, and nothing that
requires an account.

On sending, which is the part worth being careful about:

  A press pitch is not a fan blast. It goes to a small chosen list, one
  message at a time, and the reply has to land somewhere the artist
  actually reads. So the desk prepares personalised messages first and
  treats sending as a separate, explicit act with two routes:

    From your own inbox   Always available. The desk writes each message
                          and hands it over. The journalist sees a real
                          person's address and replies to it.

    From Street Banker    Only when a provider is connected AND a real
                          sending domain is set. It is refused - not
                          quietly degraded - while EMAIL_FROM is unset,
                          because the shared test sender delivers only to
                          the account owner's own inbox. Every send would
                          report success and no journalist would ever get
                          one. A press desk that lies about delivery is
                          worse than one that cannot send.

  Recipients marked do-not-contact or bounced are dropped in the store
  while the pitch is built, so no form can reach them.
"""
import os

import artist_identity
import blob_store
import email_provider as emailer
import db as store
import press_store

from flask import (Blueprint, abort, redirect, render_template, request,
                   session, url_for)

bp = Blueprint("press", __name__)

_base_url = lambda: ""          # replaced by init()

DEFAULT_SUBJECT = "{artist} — {title}"

DEFAULT_BODY = """Hi {name},

I'm sending this over for {outlet} — {title}.

Everything is here, including the audio, the artwork and the details:
{link}

Happy to answer anything or set up an interview.

Thanks,
{artist}"""


def artist_required(fn):
    """The global login wall already turns anonymous visitors away; this
    resolves the artist and hands it to the handler."""
    def guarded(*args, **kwargs):
        user_id = session.get("user_id")
        user = store.get_user(user_id) if user_id else None
        if user is None:
            return redirect(url_for("login", next=request.path))
        return fn(user, *args, **kwargs)
    guarded.__name__ = fn.__name__
    return guarded


def send_state():
    """Whether the platform can send press email on this deployment, and
    the plain reason when it cannot. Read at request time, so a key added
    to the environment changes the answer without a redeploy of copy."""
    if not emailer.configured():
        return {
            "platform": False,
            "reason": "No email provider is connected on this deployment.",
            "detail": ("Prepared messages are still yours to send — copy "
                       "each one into your own email, which is where a "
                       "journalist's reply should land anyway."),
        }
    if emailer.using_shared_test_sender():
        return {
            "platform": False,
            "reason": "The sending address has not been set up yet.",
            "detail": ("Street Banker is on a shared test sender, which "
                       "only delivers to the account owner's own inbox. "
                       "Sending from here would report success and reach "
                       "nobody, so it is switched off until a real sending "
                       "domain is configured."),
        }
    return {"platform": True, "reason": "", "detail": ""}


PRESS_KIT_KIND = "press_kit"        # the Vault kind /epk/vault-save writes


def _kit_choices(user):
    """What the pitch can carry as the press kit: the public kit's link,
    and every copy saved to the Vault, newest first. Each is
    (value, label, link, vault_file_id)."""
    out = []
    epk = store.get_epk(user["id"]) or {}
    if epk.get("slug"):
        out.append(("public", "Public press kit (live page)",
                    "%s/epk/%s" % (_base_url().rstrip("/"), epk["slug"]), ""))
    for v in store.list_vault_files(user["id"]):
        if v["kind"] != PRESS_KIT_KIND:
            continue
        url = blob_store.url_for(v["path"])
        if not url.startswith("http"):
            url = _base_url().rstrip("/") + url
        out.append(("vault:" + v["id"], v["label"] or "Press kit", url, v["id"]))
    return out


def _kit_bytes(user, file_id):
    """A saved press kit read back for an attachment, or None."""
    row = next((v for v in store.list_vault_files(user["id"])
                if v["id"] == file_id and v["kind"] == PRESS_KIT_KIND), None)
    if row is None:
        return None, ""
    path = row["path"]
    if blob_store.is_remote(path):
        return blob_store.fetch(path), row["label"]
    try:
        with open(blob_store.safe_local_path(path, _uploads()), "rb") as fh:
            return fh.read(), row["label"]
    except (OSError, ValueError):
        return None, row["label"]


_uploads_dir = None                 # set by init(); the app's UPLOADS_DIR


def _uploads():
    if callable(_uploads_dir):
        return _uploads_dir()
    return _uploads_dir or os.path.join(os.path.dirname(store.db_path()), "uploads")


def _ctx(user, **extra):
    base = {
        "active_page": "press-desk",
        "vocab": {
            "roles": press_store.CONTACT_ROLES,
            "contact_statuses": press_store.CONTACT_STATUSES,
            "status_labels": press_store.CONTACT_STATUS_LABELS,
            "kinds": press_store.RELEASE_KINDS,
            "recipient_labels": press_store.RECIPIENT_LABELS,
            "recipient_statuses": press_store.RECIPIENT_STATUSES,
            "coverage_kinds": press_store.COVERAGE_KINDS,
            "placeholders": press_store.PLACEHOLDERS,
            "max_recipients": press_store.MAX_RECIPIENTS,
        },
        "send_state": send_state(),
    }
    base.update(extra)
    return base


# --- the desk ---------------------------------------------------------------

@bp.route("/press-desk")
@artist_required
def desk(user):
    return render_template("press/desk.html", **_ctx(
        user,
        stats=press_store.desk_stats(user["id"]),
        pitches=press_store.list_pitches(user["id"])[:6],
        follow_ups=press_store.needs_follow_up(user["id"]),
        coverage=press_store.list_coverage(user["id"])[:5],
        releases=press_store.list_releases(user["id"])[:5],
    ))


# --- contacts ---------------------------------------------------------------

@bp.route("/press-desk/contacts")
@artist_required
def contacts(user):
    filters = {k: request.args.get(k, "")
               for k in ("q", "role", "status", "tag")}
    return render_template("press/contacts.html", **_ctx(
        user,
        contacts=press_store.list_contacts(
            user["id"], search=filters["q"], role=filters["role"],
            status=filters["status"], tag=filters["tag"]),
        filters=filters,
    ))


@bp.route("/press-desk/contacts/new", methods=["GET", "POST"])
@artist_required
def contact_new(user):
    if request.method == "POST":
        if not (request.form.get("name") or "").strip():
            return render_template("press/contact_form.html", **_ctx(
                user, contact=None,
                error="A contact needs at least a name."))
        press_store.add_contact(user["id"], request.form,
                                _tags(request.form))
        return redirect(url_for("press.contacts"))
    return render_template("press/contact_form.html",
                           **_ctx(user, contact=None, error=""))


@bp.route("/press-desk/contacts/<contact_id>/edit", methods=["GET", "POST"])
@artist_required
def contact_edit(user, contact_id):
    contact = press_store.get_contact(user["id"], contact_id)
    if contact is None:
        abort(404)
    if request.method == "POST":
        press_store.update_contact(user["id"], contact_id, request.form,
                                   _tags(request.form))
        return redirect(url_for("press.contacts"))
    return render_template("press/contact_form.html",
                           **_ctx(user, contact=contact, error=""))


@bp.route("/press-desk/contacts/<contact_id>/status", methods=["POST"])
@artist_required
def contact_status(user, contact_id):
    press_store.set_contact_status(user["id"], contact_id,
                                   request.form.get("status") or "")
    return redirect(request.form.get("back") or url_for("press.contacts"))


@bp.route("/press-desk/contacts/<contact_id>/delete", methods=["POST"])
@artist_required
def contact_delete(user, contact_id):
    press_store.delete_contact(user["id"], contact_id)
    return redirect(url_for("press.contacts"))


@bp.route("/press-desk/contacts/import", methods=["GET", "POST"])
@artist_required
def contacts_import(user):
    result = None
    if request.method == "POST":
        text = request.form.get("csv") or ""
        added, skipped, problems = press_store.import_contacts_csv(
            user["id"], text)
        result = {"added": added, "skipped": skipped, "problems": problems}
    return render_template("press/import.html", **_ctx(user, result=result))


def _tags(form):
    raw = form.get("tags") or ""
    return [t.strip()[:40] for t in raw.split(",") if t.strip()][:12]


# --- announcements ----------------------------------------------------------

@bp.route("/press-desk/announcements")
@artist_required
def releases(user):
    return render_template("press/releases.html", **_ctx(
        user, releases=press_store.list_releases(user["id"])))


@bp.route("/press-desk/announcements/new", methods=["GET", "POST"])
@artist_required
def release_new(user):
    if request.method == "POST":
        release_id = press_store.create_release(user["id"], request.form)
        return redirect(url_for("press.release_edit", release_id=release_id))
    return render_template("press/release_form.html", **_ctx(
        user, release=None, artist_name=artist_identity.display_name(user)))


@bp.route("/press-desk/announcements/<release_id>", methods=["GET", "POST"])
@artist_required
def release_edit(user, release_id):
    release = press_store.get_release(user["id"], release_id)
    if release is None:
        abort(404)
    if request.method == "POST":
        press_store.update_release(user["id"], release_id, request.form)
        release = press_store.get_release(user["id"], release_id)
    return render_template("press/release_form.html", **_ctx(
        user, release=release, artist_name=artist_identity.display_name(user),
        embargoed=press_store.embargo_active(release)))


@bp.route("/press-desk/announcements/<release_id>/delete", methods=["POST"])
@artist_required
def release_delete(user, release_id):
    press_store.delete_release(user["id"], release_id)
    return redirect(url_for("press.releases"))


# --- pitches ----------------------------------------------------------------

@bp.route("/press-desk/pitch/new", methods=["GET", "POST"])
@artist_required
def pitch_new(user):
    releases_all = press_store.list_releases(user["id"])
    contacts_all = press_store.list_contacts(user["id"])
    if request.method == "POST":
        chosen = request.form.getlist("contact_ids")
        release_id = request.form.get("release_id") or ""
        if not release_id or not chosen:
            return render_template("press/pitch_form.html", **_ctx(
                user, releases=releases_all, contacts=contacts_all,
                default_subject=DEFAULT_SUBJECT, default_body=DEFAULT_BODY,
                error=("Pick an announcement and at least one contact."
                       if not chosen else "Pick an announcement.")))
        # The press kit, if one was chosen: its link fills {kit}, and a
        # saved copy is attached by a platform send (2026-09-19).
        kit_pick = request.form.get("kit") or ""
        kit_link, kit_file_id = "", ""
        for value, _label, link, fid in _kit_choices(user):
            if value == kit_pick:
                kit_link, kit_file_id = link, fid
        pitch_id, prepared, skipped = press_store.create_pitch(
            user["id"], release_id, chosen,
            request.form.get("subject") or DEFAULT_SUBJECT,
            request.form.get("body") or DEFAULT_BODY,
            request.form.get("mode") or press_store.MODE_OWN_INBOX,
            artist_name=artist_identity.display_name(user),
            link_base=_base_url(), kit_link=kit_link, kit_file_id=kit_file_id)
        if pitch_id is None:
            abort(404)
        session["press_skipped"] = [list(s) for s in skipped]
        return redirect(url_for("press.pitch", pitch_id=pitch_id))
    return render_template("press/pitch_form.html", **_ctx(
        user, releases=releases_all, contacts=contacts_all,
        kits=_kit_choices(user),
        default_subject=DEFAULT_SUBJECT, default_body=DEFAULT_BODY, error=""))


@bp.route("/press-desk/pitch/<pitch_id>")
@artist_required
def pitch(user, pitch_id):
    record = press_store.get_pitch(user["id"], pitch_id)
    if record is None:
        abort(404)
    release = press_store.get_release(user["id"], record["release_id"])
    skipped = session.pop("press_skipped", [])
    kit_file = None
    if record.get("kit_file_id"):
        kit_file = next((v for v in store.list_vault_files(user["id"])
                         if v["id"] == record["kit_file_id"]), None)
    return render_template("press/pitch.html", **_ctx(
        user, pitch=record, release=release, kit_file=kit_file,
        recipients=press_store.pitch_recipients(user["id"], pitch_id),
        skipped=skipped, base_url=_base_url()))


@bp.route("/press-desk/pitch/<pitch_id>/send", methods=["POST"])
@artist_required
def pitch_send(user, pitch_id):
    """Send every prepared message in this pitch, one email each.

    Refused outright unless the deployment can really deliver — see
    send_state(). Each recipient is marked from its own result, so a
    partial failure is visible per outlet instead of being averaged into
    a success message.
    """
    record = press_store.get_pitch(user["id"], pitch_id)
    if record is None:
        abort(404)
    state = send_state()
    if not state["platform"]:
        return render_template("press/blocked.html", **_ctx(
            user, pitch=record, state=state)), 409

    # A saved press kit goes as a real file on a platform send. When it
    # cannot be read the send still goes, with the link the message
    # already carries, and the page says the file did not go.
    attachments = None
    if record.get("kit_file_id"):
        data, label = _kit_bytes(user, record["kit_file_id"])
        if data:
            import base64
            attachments = [{"filename": "%s.html" % (
                "".join(c if c.isalnum() else "-" for c in (label or "press-kit").lower()).strip("-") or "press-kit"),
                "content": base64.b64encode(data).decode("ascii")}]
        else:
            session["press_kit_missing"] = True

    sent, failed = 0, 0
    for recipient in press_store.pitch_recipients(user["id"], pitch_id):
        if recipient["status"] not in ("prepared", "failed"):
            continue
        if not recipient["email"]:
            continue
        ok = emailer.send(recipient["email"], recipient["subject"],
                          _as_html(recipient["body"]), reply_to=user["email"],
                          attachments=attachments)
        press_store.mark_sent(recipient["id"], ok)
        sent += 1 if ok else 0
        failed += 0 if ok else 1
    press_store.mark_pitch_sent(user["id"], pitch_id)
    session["press_send_result"] = {"sent": sent, "failed": failed}
    return redirect(url_for("press.pitch", pitch_id=pitch_id))


def _as_html(text):
    """Plain text to a readable email body. No template, no images, no
    tracking pixel: a press pitch that arrives looking like a marketing
    campaign gets filed as one."""
    from markupsafe import escape
    paragraphs = [p.strip() for p in (text or "").split("\n\n") if p.strip()]
    return "".join(
        "<p style=\"margin:0 0 14px;font:15px/1.6 -apple-system,Segoe UI,"
        "Roboto,Helvetica,Arial,sans-serif;color:#1A1714\">%s</p>"
        % str(escape(p)).replace("\n", "<br>") for p in paragraphs)


@bp.route("/press-desk/pitch/<pitch_id>/delete", methods=["POST"])
@artist_required
def pitch_delete(user, pitch_id):
    press_store.delete_pitch(user["id"], pitch_id)
    return redirect(url_for("press.desk"))


@bp.route("/press-desk/recipients/<recipient_id>/status", methods=["POST"])
@artist_required
def recipient_status(user, recipient_id):
    record = press_store.get_recipient(user["id"], recipient_id)
    if record is None:
        abort(404)
    press_store.set_recipient_status(user["id"], recipient_id,
                                     request.form.get("status") or "",
                                     request.form.get("note") or "")
    return redirect(request.form.get("back")
                    or url_for("press.pitch", pitch_id=record["pitch_id"]))


# --- coverage ---------------------------------------------------------------

@bp.route("/press-desk/coverage", methods=["GET", "POST"])
@artist_required
def coverage(user):
    if request.method == "POST":
        if (request.form.get("outlet") or "").strip():
            press_store.add_coverage(user["id"], request.form)
        return redirect(url_for("press.coverage"))
    return render_template("press/coverage.html", **_ctx(
        user, coverage=press_store.list_coverage(user["id"]),
        releases=press_store.list_releases(user["id"]),
        contacts=press_store.list_contacts(user["id"])))


@bp.route("/press-desk/coverage/<coverage_id>/delete", methods=["POST"])
@artist_required
def coverage_delete(user, coverage_id):
    press_store.delete_coverage(user["id"], coverage_id)
    return redirect(url_for("press.coverage"))


# --- the public page a journalist opens -------------------------------------

@bp.route("/press/<token>")
def press_page(token):
    """One announcement, opened by one recipient. The token identifies
    which, so an open is attributable — that is the whole reason these
    are per-recipient rather than one shared link.

    No account, no PIN, no gate: a journalist who was sent something is
    supposed to be able to read it.
    """
    recipient = press_store.get_recipient_by_token(token)
    if recipient is None:
        abort(404)
    pitch_record = press_store.get_pitch(recipient["user_id"],
                                         recipient["pitch_id"])
    if pitch_record is None:
        abort(404)
    release = press_store.get_release_any(pitch_record["release_id"])
    if release is None:
        abort(404)

    first = press_store.mark_opened(token)
    if first is not None:
        contact = press_store.get_contact(recipient["user_id"],
                                          recipient["contact_id"]) or {}
        who = contact.get("outlet") or contact.get("name") or "A contact"
        store.notify(recipient["user_id"], "press",
                     "%s opened your pitch" % who[:80],
                     "%s — %s" % (contact.get("name") or "",
                                  release["headline"] or release["title"]),
                     "/press-desk/pitch/%s" % recipient["pitch_id"])

    return render_template(
        "press_release_public.html", release=release,
        embargoed=press_store.embargo_active(release),
        outlet=(press_store.get_contact(recipient["user_id"],
                                        recipient["contact_id"]) or {}))


# --- wiring -----------------------------------------------------------------

def init(app, base_url, uploads_dir=None):
    """Register the Press Desk. `base_url` is a callable returning the
    address links are built from — it must be the canonical one, because
    a link baked into an email outlives the request that made it.
    `uploads_dir` is the app's uploads folder (a value or a callable), so
    a saved press kit can be read back for an attachment."""
    global _base_url, _uploads_dir
    _base_url = base_url
    _uploads_dir = uploads_dir
    press_store.init_press()
    app.register_blueprint(bp)
