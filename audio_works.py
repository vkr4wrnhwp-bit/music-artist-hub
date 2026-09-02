"""Audio work items - the shared engine behind phases 4, 5 and 6.

FOUR PRODUCTS, ONE SHAPE
------------------------
Global Release Pack (dubbing), Campaign Audio Toolkit (voiceover and sound
effects), Remix Lab Audio Engine (stem separation) and Artist Voice Vault
(voice identity) all do the same thing structurally: take audio somebody owns,
confirm they own it, run one gated operation, and keep what came back.

Four near-identical modules would drift, and the one that drifts is the one
that forgets the rights check. So the work item is one table and one submit
path, and the products differ in which feature key they pass.

RIGHTS ARE CONFIRMED PER WORK ITEM, NOT PER ACCOUNT
---------------------------------------------------
"I own my catalogue" ticked once at signup is not a claim about the file
somebody uploaded this afternoon. The gate's rights check reads a flag this
module records against THIS item, with who confirmed it and when.

THE LIKENESS SCREEN IS SERVER-SIDE
----------------------------------
remix_lab_config.check_reference_text() was written with a note saying the
server must call it before any generation request leaves the building, and
that the browser copy is convenience rather than enforcement. This module is
where that gets honoured - screen_reference() runs on every free-text brief,
for every product here, not only Remix Lab.

Refusing an imitation request is not squeamishness. A remix brief that says
"same voice as <a real singer>" is a request to imitate a specific person,
and the person it imitates has no say in it at the moment it is typed.
"""
import json
import uuid

from db import get_db, _now

# feature key -> (capability, human label, does it need a source file)
WORK_KINDS = {
    "dubbing": ("dubbing", "Dubbed version", True),
    "stem_separation": ("stems", "Stem separation", True),
    "voice_isolation": ("voice_isolation", "Voice isolation", True),
    "sound_effects": ("sound_effects", "Sound effect", False),
    "campaign_voiceover": ("speech", "Campaign voiceover", False),
    "music_generation": ("music", "Generated music", False),
    "voice_vault": ("voice_identity", "Voice registration", False),
    # Reads a track and reports what is measurable in it. Generates nothing,
    # which is why Remix Lab can run without music generation switched on.
    "remix_plan": ("music", "Composition plan", True),
}

WORK_STATUSES = ("draft", "queued", "running", "ready", "refused", "failed")


def _uid():
    return uuid.uuid4().hex


def _row(r):
    return dict(r) if r is not None else None


def _dump(v):
    return json.dumps(v) if v is not None else None


def _load(v, default=None):
    if not v:
        return default
    try:
        return json.loads(v)
    except (ValueError, TypeError):
        return default


def init_works():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS audio_works (
                id TEXT PRIMARY KEY,
                partner_id TEXT,
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                brief TEXT NOT NULL DEFAULT '',
                options TEXT NOT NULL DEFAULT '{}',
                source_asset_id TEXT,
                output_asset_ids TEXT NOT NULL DEFAULT '[]',
                job_id TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                is_mock INTEGER NOT NULL DEFAULT 0,
                /* Recorded against THIS item, with who and when. A tick at
                   signup is not a claim about a file uploaded this
                   afternoon. */
                rights_confirmed INTEGER NOT NULL DEFAULT 0,
                rights_confirmed_by TEXT NOT NULL DEFAULT '',
                rights_confirmed_at TEXT,
                refusal_code TEXT NOT NULL DEFAULT '',
                refusal_reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_works_user
                ON audio_works(user_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_works_kind
                ON audio_works(kind, status);
        """)


# --- the likeness screen ----------------------------------------------------

def screen_reference(text):
    """The authoritative imitation check, for every product here.

    Delegates to remix_lab_config, which owns the pattern list and whose
    browser copy already shows the same warning inline. One list, checked in
    the place that can actually stop a request.

    Returns the offending phrase, or None.
    """
    try:
        from remix_lab_config import check_reference_text
    except Exception:
        # A missing config module must not turn the screen off. Refusing to
        # run is the safe direction here: the whole point is that generation
        # does not proceed unscreened.
        raise RuntimeError("the likeness screen is unavailable")
    return check_reference_text(text or "")


def safety_warning():
    try:
        from remix_lab_config import SAFETY_WARNING
        return SAFETY_WARNING
    except Exception:
        return ("This cannot imitate a real person's voice, likeness or "
                "protected style. Describe the musical direction instead.")


# --- work items -------------------------------------------------------------

def create_work(user_id, kind, title="", brief="", options=None,
                source_asset_id=None, partner_id=None):
    if kind not in WORK_KINDS:
        raise ValueError("unknown work kind: %s" % kind)
    wid = _uid()
    with get_db() as db:
        db.execute(
            "INSERT INTO audio_works (id, partner_id, user_id, kind, title, brief, "
            "options, source_asset_id, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,?, 'draft', ?)",
            (wid, partner_id, user_id, kind, (title or "")[:200],
             (brief or "")[:2000], _dump(dict(options or {})),
             source_asset_id, _now()))
    return get_work(wid, partner_id)


def get_work(work_id, partner_id=None):
    with get_db() as db:
        row = _row(db.execute(
            "SELECT * FROM audio_works WHERE id = ? AND partner_id IS ?",
            (work_id, partner_id)).fetchone())
    if row:
        row["options"] = _load(row.get("options"), {})
        row["output_asset_ids"] = _load(row.get("output_asset_ids"), [])
    return row


def list_works(user_id=None, kind=None, partner_id=None, limit=100):
    query = "SELECT * FROM audio_works WHERE partner_id IS ?"
    args = [partner_id]
    if user_id:
        query += " AND user_id = ?"
        args.append(user_id)
    if kind:
        query += " AND kind = ?"
        args.append(kind)
    query += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    with get_db() as db:
        rows = [dict(r) for r in db.execute(query, args).fetchall()]
    for row in rows:
        row["options"] = _load(row.get("options"), {})
        row["output_asset_ids"] = _load(row.get("output_asset_ids"), [])
    return rows


def confirm_rights(work_id, confirmed_by, partner_id=None):
    """Records the confirmation with who and when.

    Deliberately a separate call from create_work: the confirmation is an act
    a person performs, and a default argument on a constructor is not one.
    """
    with get_db() as db:
        cur = db.execute(
            "UPDATE audio_works SET rights_confirmed = 1, rights_confirmed_by = ?, "
            "rights_confirmed_at = ? WHERE id = ? AND partner_id IS ?",
            (confirmed_by or "", _now(), work_id, partner_id))
    return cur.rowcount > 0


def set_status(work_id, status, partner_id=None, job_id=None,
               output_asset_ids=None, is_mock=None, refusal_code=None,
               refusal_reason=None):
    if status is not None and status not in WORK_STATUSES:
        raise ValueError("unknown status: %s" % status)
    sets, args = [], []
    if status is not None:
        sets.append("status = ?")
        args.append(status)
        if status in ("ready", "refused", "failed"):
            sets.append("completed_at = ?")
            args.append(_now())
    if job_id is not None:
        sets.append("job_id = ?")
        args.append(job_id)
    if output_asset_ids is not None:
        sets.append("output_asset_ids = ?")
        args.append(_dump(list(output_asset_ids)))
    if is_mock is not None:
        sets.append("is_mock = ?")
        args.append(1 if is_mock else 0)
    if refusal_code is not None:
        sets.append("refusal_code = ?")
        args.append(refusal_code)
    if refusal_reason is not None:
        sets.append("refusal_reason = ?")
        args.append((refusal_reason or "")[:600])
    if not sets:
        return False
    args.extend([work_id, partner_id])
    with get_db() as db:
        cur = db.execute("UPDATE audio_works SET %s WHERE id = ? AND partner_id IS ?"
                         % ", ".join(sets), args)
    return cur.rowcount > 0


def delete_work(work_id, partner_id=None):
    with get_db() as db:
        db.execute("DELETE FROM audio_works WHERE id = ? AND partner_id IS ?",
                   (work_id, partner_id))


# --- the one submit path ----------------------------------------------------

class WorkRefusal(Exception):
    def __init__(self, reason, code="refused"):
        Exception.__init__(self, reason)
        self.reason = reason
        self.code = code


def submit_work(work_id, partner_id=None, member=None, adapter_key=None):
    """Screen, gate, dispatch. The only way a work item reaches a provider.

    Order matters and is the same as everywhere else in this product: the
    checks that cost nothing and can refuse outright run before the ones that
    cost a database round trip or a network call.

      1. does the item exist
      2. the likeness screen, on the brief the person typed
      3. rights, recorded against this item
      4. audio_policy.gate(), which does the other ten
    """
    import audio_jobs
    import audio_providers as ap

    work = get_work(work_id, partner_id)
    if work is None:
        raise WorkRefusal("That item does not exist.", "missing")

    capability, label, needs_source = WORK_KINDS[work["kind"]]

    # 2. The likeness screen, before anything else costs anything. This is the
    #    check remix_lab_config asked the server to make.
    offending = screen_reference(work.get("brief") or "")
    if offending:
        reason = ("%s The phrase that stopped it was \"%s\"."
                  % (safety_warning(), offending))
        set_status(work_id, "refused", partner_id, refusal_code="imitation",
                   refusal_reason=reason)
        raise WorkRefusal(reason, "imitation")

    # 3. Rights, for this item, not for the account.
    if not work.get("rights_confirmed"):
        reason = ("Confirm you own or control this audio, or have the rights "
                  "holder's authorisation, before it is processed.")
        set_status(work_id, "refused", partner_id, refusal_code="rights_required",
                   refusal_reason=reason)
        raise WorkRefusal(reason, "rights_required")

    if needs_source and not work.get("source_asset_id"):
        raise WorkRefusal("This needs a source recording.", "no_source")

    request = _build_request(work, capability, ap, partner_id)

    submission = audio_jobs.submit(
        work["kind"], work["user_id"], request,
        partner_id=partner_id, member=member,
        subject_id=work_id, rights_confirmed=True,
        adapter_key=adapter_key,
        input_asset_ids=[work["source_asset_id"]] if work.get("source_asset_id") else None,
        idempotency_key="work:%s" % work_id)

    if not submission.allowed:
        set_status(work_id, "refused", partner_id,
                   refusal_code=submission.decision.code,
                   refusal_reason=submission.decision.reason)
        raise WorkRefusal(submission.decision.reason, submission.decision.code)

    job = submission.job
    result = (job or {}).get("result") or {}

    # The job may already have ended badly inside submit(): the provider
    # refused (terminal) or the call broke. Before this both were written up
    # as "queued", and an item that could never finish sat there saying it
    # had not started yet.
    if job.get("status") in ("rejected", "failed"):
        outcome = "refused" if job.get("status") == "rejected" else "failed"
        code = job.get("error_code") or outcome
        reason = job.get("error_message") or (
            "The provider declined this." if outcome == "refused"
            else "The provider reported a failure.")
        set_status(work_id, outcome, partner_id, job_id=job["id"],
                   refusal_code=code, refusal_reason=reason)
        raise WorkRefusal(reason, code)

    status = "ready" if job.get("status") == "completed" else "queued"

    # Keep whatever came back. Without this the column exists, the item page
    # reads it, and every byte a provider returned is thrown away the moment
    # the request ends - so a separated stem had nowhere to go and nothing to
    # go there with.
    outputs = harvest_outputs(work, result, partner_id)

    set_status(work_id, status, partner_id, job_id=job["id"],
               is_mock=bool(result.get("is_mock")),
               output_asset_ids=outputs or None)
    return get_work(work_id, partner_id), result


def settle_work(work_id, partner_id=None):
    """Bring a slow item up to date with its job.

    There is no background worker on this deployment, so a dub that the vendor
    finishes ten minutes after submission is settled the next time somebody
    looks at it: the item page, the outputs manifest the Rack reads, and the
    operator's "advance waiting jobs" all call this. Safe on a settled item -
    it returns it unchanged.

    A finished dub is downloaded here and kept, once. The download is free at
    the vendor and idempotent, so a poll that completed the job without
    fetching (the admin sweep) costs nothing to catch up on.
    """
    import audio_jobs
    import audio_store as astore

    work = get_work(work_id, partner_id)
    if work is None or work["status"] not in ("queued", "running") \
            or not work.get("job_id"):
        return work
    job = astore.get_job(partner_id, work["job_id"])
    if job is None:
        return work
    if job.get("status") == "running":
        job = audio_jobs.poll(partner_id, job["id"]) or job

    status = job.get("status")
    if status == "completed":
        result = dict(job.get("result") or {})
        if not work["output_asset_ids"] and not any(
                blob for _label, blob, _mime in _audio_parts(result)):
            result.update(audio_jobs.collect_outputs(partner_id, job) or {})
        outputs = harvest_outputs(work, result, partner_id)
        set_status(work_id, "ready", partner_id,
                   is_mock=bool(result.get("is_mock")),
                   output_asset_ids=(work["output_asset_ids"] + outputs)
                   if outputs else None)
    elif status == "rejected":
        set_status(work_id, "refused", partner_id,
                   refusal_code=job.get("error_code") or "refused",
                   refusal_reason=job.get("error_message")
                   or "The provider declined this and will not be asked again.")
    elif status == "failed":
        set_status(work_id, "failed", partner_id,
                   refusal_code=job.get("error_code") or "failed",
                   refusal_reason=job.get("error_message")
                   or "The provider reported a failure.")
    elif status == "running" and work["status"] != "running":
        set_status(work_id, "running", partner_id)
    return get_work(work_id, partner_id)


# Result shapes differ per capability, so the harvester names them rather
# than guessing: a stem separation returns a LIST under "stems", a finished
# dub a list under "outputs" (one per language), everything else one blob
# under "audio".
def _audio_parts(result):
    """[(label, bytes, mime)] for whatever this result actually carries."""
    parts = []
    for stem in (result.get("stems") or []):
        parts.append(((stem.get("name") or "stem"), stem.get("audio"),
                      stem.get("mime_type") or "audio/wav"))
    for out in (result.get("outputs") or []):
        parts.append(((out.get("language") or out.get("name") or "output"),
                      out.get("audio"), out.get("mime_type") or "audio/mpeg"))
    if result.get("audio"):
        label = result.get("language") or "output"
        parts.append((label, result.get("audio"),
                      result.get("mime_type") or "audio/wav"))
    return parts


_EXT_BY_MIME = {"audio/wav": "wav", "audio/x-wav": "wav", "audio/wave": "wav",
                "audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/mp4": "m4a",
                "audio/aac": "aac", "audio/flac": "flac", "audio/x-flac": "flac",
                "audio/ogg": "ogg", "audio/webm": "webm", "audio/L16": "pcm"}


def _ext_for(mime):
    mime = (mime or "").split(";")[0].strip().lower()
    if mime in _EXT_BY_MIME:
        return _EXT_BY_MIME[mime]
    return "wav" if "wav" in mime else "mp3"


def harvest_outputs(work, result, partner_id=None):
    """Store what a provider returned as retrievable assets.

    Empty audio is SKIPPED rather than stored. The mock adapters return
    correctly-shaped results with no bytes - deliberately, so a demo cannot be
    mistaken for real work - and writing those as files would leave an artist
    with a Vault full of silent stems that look like output.
    """
    import audio_retention
    import audio_store as astore
    import blob_store

    parts = [(label, blob, mime) for label, blob, mime in _audio_parts(result)
             if blob]
    if not parts:
        return []

    stored = []
    for label, blob, mime in parts:
        name = "%s_%s.%s" % (work["kind"], _safe(label), _ext_for(mime))
        try:
            path = _save_output(name, blob, mime)
        except Exception:
            continue
        stored.append(astore.create_asset(
            partner_id, work["user_id"], path,
            file_name=name, mime_type=mime, file_size=len(blob),
            asset_type="generated",
            retention_days=audio_retention.retention_days(partner_id, "generated")))
    return stored


def _safe(label):
    keep = [c if (c.isalnum() or c in "-_") else "-" for c in (label or "out")]
    return "".join(keep).strip("-").lower()[:40] or "out"


def _save_output(name, blob, mime):
    """Private storage, never the public uploads tree - a separated vocal is
    the artist's master, taken apart."""
    import os
    import time

    import blob_store
    fname = "out_%d_%s" % (int(time.time() * 1000), name)
    if blob_store.configured():
        try:
            if blob_store.put("studio/" + fname, blob, mime):
                return blob_store.PREFIX + "studio/" + fname
        except Exception:
            pass
    import audio_studio
    with open(os.path.join(audio_studio._studio_dir(), fname), "wb") as handle:
        handle.write(blob)
    return audio_studio.STUDIO_PREFIX + fname


def _source_file(work, partner_id=None):
    """Where the uploaded source actually is, in a form an adapter can send.

    The work item holds an asset id; an adapter needs a file. Before this the
    request carried only the id, and the real adapter opened
    `request["audio_path"]` - a KeyError on every file-backed lane, recorded
    as an adapter error and never retried. The mock never noticed because it
    never opens anything.

    A local upload becomes a path (streamed by the SDK, not read into memory
    twice); a bucket object is fetched into bytes, because the vendor cannot
    be handed a private signed URL that expires under it. The name and type
    travel with it so the multipart part is labelled honestly.
    """
    import os

    import audio_store as astore
    import blob_store

    asset_id = work.get("source_asset_id")
    asset = astore.get_asset(partner_id, asset_id) if asset_id else None
    key = (asset or {}).get("storage_key") or ""
    if not key:
        return {}
    out = {"file_name": (asset.get("file_name") or "source")[:120],
           "mime_type": asset.get("mime_type") or "audio/wav"}
    import audio_studio
    if key.startswith(audio_studio.STUDIO_PREFIX):
        out["audio_path"] = os.path.join(audio_studio._studio_dir(),
                                         key[len(audio_studio.STUDIO_PREFIX):])
    elif blob_store.is_remote(key):
        data = blob_store.fetch(key)
        if data:
            out["audio_bytes"] = data
    elif os.path.isabs(key) and os.path.exists(key):
        out["audio_path"] = key
    return out


def _build_request(work, capability, ap, partner_id=None):
    """The capability-shaped request for this kind of work."""
    options = work.get("options") or {}
    brief = work.get("brief") or ""

    if capability == "speech":
        return ap.SpeechRequest(brief, voice_id=options.get("voice_id"),
                                language=options.get("language"))
    if capability == "sound_effects":
        return {"prompt": brief,
                "duration_seconds": options.get("duration_seconds") or 3.0}
    if capability == "dubbing":
        langs = [x for x in (options.get("languages") or []) if x] or ["es"]
        request = {"source_asset_id": work.get("source_asset_id"),
                   "target_languages": langs, "target_lang": langs[0],
                   "name": work.get("title") or "",
                   "operation": "create_project"}
        request.update(_source_file(work, partner_id))
        return request
    if capability == "stems":
        request = {"source_asset_id": work.get("source_asset_id"),
                   "stem_variation": options.get("stem_variation") or "",
                   "operation": "separate"}
        request.update(_source_file(work, partner_id))
        return request
    if capability == "voice_isolation":
        request = {"source_asset_id": work.get("source_asset_id"),
                   "operation": "isolate"}
        request.update(_source_file(work, partner_id))
        return request
    if capability == "music":
        # remix_plan analyses; music_generation creates. Same capability,
        # different verb, and only one of them costs a generation.
        if work.get("kind") == "remix_plan":
            request = {"source_asset_id": work.get("source_asset_id"),
                       "prompt": brief, "operation": "composition_plan"}
            request.update(_source_file(work, partner_id))
            return request
        return {"prompt": brief, "operation": "generate"}
    if capability == "voice_identity":
        return {"owner_person_id": options.get("owner_person_id") or "",
                "owner_verified": bool(options.get("owner_verified")),
                "operation": "register_verified_voice"}
    return {"prompt": brief}
