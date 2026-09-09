"""The ACRCloud desk - register your catalog, scan a long recording.

Two capabilities, one page each, and both of them are the same argument from
opposite ends:

  REGISTER  sends the owner's own masters into their ACRCloud custom bucket,
            so ACRCloud's index knows what belongs to them. Nothing is
            findable until this has happened - an unregistered master is
            invisible to every scan anybody ever runs.

  SCAN      hands ACRCloud a long recording - a DJ set, a livestream rip, a
            podcast - and gets back every track it detected with a start and
            an end. When one of those detections is a master registered
            above, the row lights up and offers to open a usage case with the
            timestamp and the file name carried as evidence.

THE POINT IS THE SECOND ONE FINDING THE FIRST. A scan that only names other
people's records is a music-ID toy. A scan that says "your record is in this
set at 1:12:40, confidence 96" is the beginning of a claim, which is why the
case button carries the evidence line rather than only a title.

WHAT THIS DESK WILL NOT DO
--------------------------
It does not create a bucket or a container. If the account has none, the page
says which kind to make and what a good name is, and the owner makes it in
their own ACRCloud console. Creating a billable resource on somebody's behalf
because a page needed one is not a thing this code gets to do.

It does not claim an amount. Every case it opens is worth 0 - the same as the
MLC sweep's - because nothing in a fingerprint answer measures money. The
evidence is the value.

It does not monitor. Same standing rule as `acr_provider.py`: nothing here
runs on a schedule, and every call happens because somebody pressed a button.

ACCESS. The account owner does everything. A person holding a seat at a
partner reads the same pages, and may only press buttons if their role carries
`act_as_artist` (partner_store.PERMS) - so a viewer or a billing contact sees
exactly what was found and cannot spend the account's ACRCloud quota. The
check is in the route, not only in the template: a hidden button is a
courtesy, and `_require_act` is the boundary.
"""

import os

from flask import (Blueprint, abort, redirect, render_template, request,
                   session, url_for)

import acr_console as console
import acr_store as astore
import blob_store
import db as store
import partner_store as pstore

bp = Blueprint("acrdesk", __name__, url_prefix="/fingerprints")

_current_user = None
_dashboard_context = None
_uploads_dir = None

# A one-shot line for the person who just pressed a button. It lives in the
# session rather than in a table because it is news, not a record: a refusal
# writes nothing durable, and the next page load consumes this and it is gone.
_NOTICE = "acr.notice"

# What the page tells somebody to make when they have no custom bucket. Named
# here so the instruction is one string rather than three paraphrases.
BUCKET_KIND = "File"
BUCKET_ADVICE = ("In the ACRCloud console, open Audio & File Recognition, "
                 "create a bucket of type \"File\" in the same region as your "
                 "project, and name it after this account - \"Street Banker "
                 "masters\" is a fine name. Come back and it will be listed "
                 "here.")
CONTAINER_ADVICE = ("In the ACRCloud console, open File Scanning and create a "
                    "container that points at your custom bucket as well as "
                    "ACRCloud's music database. Without one there is nothing "
                    "for a recording to be scanned against.")

MAX_SCAN_UPLOAD = 80 * 1024 * 1024      # what this deployment will take inline


# --- identity and access -------------------------------------------------------

def _me():
    return _current_user() if _current_user else None


def _seat():
    me = _me()
    return pstore.member_for_user(me["id"]) if me else None


def _can_act():
    """May this login spend the account's ACRCloud quota?

    An account with no partner seat is its own owner and may. A seated
    account may only when its role carries `act_as_artist` - the same
    permission that already governs a partner reaching into an artist's desk.
    """
    seat = _seat()
    if seat is None:
        return True
    return pstore.can(seat, "act_as_artist")


def _require_act():
    if not _can_act():
        abort(403)


def _notice(text, tone="warn"):
    session[_NOTICE] = {"text": (text or "")[:600], "tone": tone}


def _take_notice():
    return session.pop(_NOTICE, None)


def _ctx():
    return _dashboard_context() if _dashboard_context else {}


def _uploads():
    return _uploads_dir() if callable(_uploads_dir) else (_uploads_dir or "")


def _vault_bytes(path):
    """The stored file, read back. None when the object cannot be reached -
    which is reported as itself, never as a registration that did not
    happen."""
    if not path:
        return None
    if blob_store.is_remote(path):
        return blob_store.fetch(path)
    try:
        with open(blob_store.safe_local_path(path, _uploads()), "rb") as handle:
            return handle.read()
    except (OSError, ValueError):
        return None


# --- the registry page ----------------------------------------------------------

def _console_state(me):
    """Everything the page needs to say about the connection, measured.

    A failed bucket call is not an empty bucket list. The two states read
    identically on a careless page - "no buckets" - and mean opposite things,
    so the refusal is carried out separately and shown as itself.
    """
    state = {"on": console.configured(), "missing": console.missing_env(),
             "buckets": [], "containers": [], "error": "", "asked": False}
    if not state["on"]:
        return state
    state["asked"] = True
    try:
        state["buckets"] = console.buckets(type_=BUCKET_KIND)
    except console.AcrConsoleError as e:
        state["error"] = e.msg
        return state
    try:
        state["containers"] = console.containers()
    except console.AcrConsoleError as e:
        state["error"] = e.msg
    return state


@bp.route("/")
def index():
    me = _me()
    if me is None:
        return redirect(url_for("login", next=request.path))
    registrations = astore.list_registrations(me["id"])
    vault = store.list_vault_files(me["id"])
    eligible = astore.eligible_vault_files(vault, registrations)
    state = _console_state(me)
    return render_template(
        "acr/index.html", active_page="beats",
        state=state, eligible=eligible, registrations=registrations,
        scans=astore.list_scans(me["id"], limit=10),
        can_act=_can_act(), notice=_take_notice(),
        bucket_advice=BUCKET_ADVICE, container_advice=CONTAINER_ADVICE,
        registerable_kinds=astore.REGISTERABLE_KINDS,
        max_register_mb=console.MAX_REGISTER_BYTES // (1024 * 1024),
        **_ctx())


@bp.route("/register", methods=["POST"])
def register():
    """Send ONE master to the bucket, because the owner asked for that one.

    One at a time on purpose. A "register everything" button would put an
    unbounded number of multi-megabyte uploads inside a single web request on
    a deployment with eight request slots, and would bill the account for
    files nobody looked at first.
    """
    me = _me()
    if me is None:
        return redirect(url_for("login", next="/fingerprints/"))
    _require_act()
    if not console.configured():
        _notice("ACRCloud's console API is not connected, so nothing was sent.")
        return redirect("/fingerprints/")
    vault_id = (request.form.get("vault_id") or "").strip()
    bucket_id = (request.form.get("bucket_id") or "").strip()
    row = next((v for v in store.list_vault_files(me["id"])
                if v["id"] == vault_id), None)
    if row is None:
        abort(404)
    if not bucket_id:
        _notice("Choose the bucket to register into first.")
        return redirect("/fingerprints/")
    existing = astore.registration_for(me["id"], vault_id)
    if existing:
        _notice("\"%s\" is already registered with ACRCloud - it was not sent "
                "again." % (existing["title"] or row["label"] or "That file"),
                tone="idle")
        return redirect("/fingerprints/")
    data = _vault_bytes(row["path"])
    if data is None:
        _notice("The stored file could not be read back, so nothing was sent "
                "to ACRCloud.")
        return redirect("/fingerprints/")
    filename = os.path.basename((row["path"] or "").split("?")[0]) or "master.wav"
    title = (row["label"] or filename)[:200]
    bucket_name = ""
    try:
        bucket_name = next((b["name"] for b in console.buckets(type_=BUCKET_KIND)
                            if b["id"] == bucket_id), "")
    except console.AcrConsoleError:
        pass
    try:
        answer = console.upload_audio(bucket_id, filename, data, title,
                                      custom={"street_banker_vault_id": vault_id,
                                              "street_banker_user_id": me["id"],
                                              "title": title})
    except console.AcrConsoleError as e:
        # ACRCloud's own words, and NO row: a registration that did not happen
        # must not appear in a list of registrations.
        _notice("ACRCloud refused: %s" % e.msg)
        return redirect("/fingerprints/")
    written = astore.record_registration(me["id"], vault_id, answer, title=title,
                                         filename=filename, bucket_name=bucket_name,
                                         bytes_sent=len(data))
    if written is None:
        _notice("\"%s\" was already registered - the second press was ignored."
                % title, tone="idle")
    else:
        _notice("\"%s\" is registered with ACRCloud (%s)."
                % (title, answer.get("state_word") or "accepted"), tone="good")
    return redirect("/fingerprints/")


# --- scanning --------------------------------------------------------------------

@bp.route("/scans", methods=["POST"])
def new_scan():
    me = _me()
    if me is None:
        return redirect(url_for("login", next="/fingerprints/"))
    _require_act()
    if not console.configured():
        _notice("ACRCloud's console API is not connected, so nothing was scanned.")
        return redirect("/fingerprints/")
    container_id = (request.form.get("container_id") or "").strip()
    if not container_id:
        _notice("Choose the file-scanning container to scan against first.")
        return redirect("/fingerprints/")
    url = (request.form.get("url") or "").strip()
    upload = request.files.get("recording")
    data, filename = None, ""
    if upload is not None and upload.filename:
        data = upload.read(MAX_SCAN_UPLOAD + 1)
        if len(data) > MAX_SCAN_UPLOAD:
            _notice("That recording is over %d MB. Paste a link to it instead - "
                    "ACRCloud fetches the file itself and it never passes "
                    "through here." % (MAX_SCAN_UPLOAD // (1024 * 1024)))
            return redirect("/fingerprints/")
        filename = upload.filename
    if not data and not url:
        _notice("A scan needs a recording: upload one, or paste a link "
                "ACRCloud can fetch.")
        return redirect("/fingerprints/")
    name = filename or url
    try:
        job = console.scan_file(container_id, filename=filename, data=data,
                                url=url or None, name=name)
    except console.AcrConsoleError as e:
        _notice("ACRCloud refused: %s" % e.msg)
        return redirect("/fingerprints/")
    scan_id = astore.create_scan(me["id"], job["job_id"], container_id, name,
                                 source_kind="url" if url and not data else "file",
                                 state=job.get("state_word") or "queued")
    return redirect("/fingerprints/scans/%s" % scan_id)


@bp.route("/scans/<scan_id>")
def scan(scan_id):
    me = _me()
    if me is None:
        return redirect(url_for("login", next=request.path))
    row = astore.get_scan(me["id"], scan_id)
    if row is None:
        abort(404)
    hits = astore.list_hits(me["id"], scan_id)
    for hit in hits:
        # The clock strings and the case wording are built here, once, so the
        # template holds no arithmetic and no sentence a test cannot find.
        hit["start"] = console.clock(hit.get("start_ms"))
        hit["end"] = console.clock(hit.get("end_ms"))
        hit["case_title"], hit["case_note"] = astore.case_fields(row, hit)
    return render_template(
        "acr/scan.html", active_page="beats", scan=row, hits=hits,
        mine=astore.count_mine(hits), can_act=_can_act(),
        notice=_take_notice(), on=console.configured(),
        missing=console.missing_env(), **_ctx())


@bp.route("/scans/<scan_id>/refresh", methods=["POST"])
def refresh(scan_id):
    """Ask ACRCloud where the job is now, and keep whatever came back.

    A poll, pressed by a person. There is no background worker on this
    deployment, and a page that refreshed itself on a timer would spend the
    account's quota while nobody was looking at it.
    """
    me = _me()
    if me is None:
        return redirect(url_for("login", next="/fingerprints/"))
    _require_act()
    row = astore.get_scan(me["id"], scan_id)
    if row is None:
        abort(404)
    if not console.configured():
        _notice("ACRCloud's console API is not connected, so the scan was not "
                "checked.")
        return redirect("/fingerprints/scans/%s" % scan_id)
    try:
        answer = console.scan_results(row["job_id"])
    except console.AcrConsoleError as e:
        astore.set_scan_state(me["id"], scan_id, "error", e.msg)
        _notice("ACRCloud refused: %s" % e.msg)
        return redirect("/fingerprints/scans/%s" % scan_id)
    astore.set_scan_state(me["id"], scan_id, answer.get("state_word") or "processing")
    if answer.get("state") == console.STATE_READY:
        astore.replace_hits(me["id"], scan_id, answer.get("hits") or [])
    return redirect("/fingerprints/scans/%s" % scan_id)


def init(app, current_user=None, dashboard_context=None, uploads_dir=None):
    global _current_user, _dashboard_context, _uploads_dir
    _current_user = current_user
    _dashboard_context = dashboard_context
    _uploads_dir = uploads_dir or (
        lambda: os.path.join(os.path.dirname(store.db_path()), "uploads"))
    astore.init_acr()
    app.register_blueprint(bp)
