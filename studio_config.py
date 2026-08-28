"""Street Banker Studio - deployment configuration and the studio_v1 flag.

WHY A FLAG AT ALL
-----------------
Studio adds routes, schema and navigation to a product people are using
today. Off by default means a deployment gets it deliberately, and means the
schema can land in one release and the surface in another - which is the only
safe order when the migration has to run on a live database.

WHY THE FLAG IS READ PER REQUEST
--------------------------------
It is read from the environment every time rather than captured at import.
Remix Lab was listed as live in a module-level constant once; when its engine
was connected, the sidebar badge, the hub-desk tile, the hub-desk footnote and
the command palette all went on calling a working page "example data, not
yours" - four wrong surfaces from one stale literal. A function cannot go
stale that way.

WHAT "ENABLED" DOES NOT MEAN
----------------------------
It does not mean audio processing works. Studio has three independent
capabilities and they fail separately:

  storage    - blob_store must be configured (R2). Unconfigured, uploads fall
               back to the Render disk, which is 1 GB and SHARED WITH THE
               SQLITE DATABASE. Large audio there takes the database down with
               it, so Studio refuses big uploads on the fallback rather than
               filling the disk politely.
  processing - there is no external mastering or mixing provider wired up, and
               there is no background worker on this deployment (one web
               service, 180s request timeout). Anything that cannot finish
               inside a request is queued and reported queued. It is never
               reported complete.
  analysis   - runs in the browser against the Rack's existing BS.1770-4
               engine, so it works with no provider at all.

Each is reported separately by `readiness()`. A single "Studio: on" would be
the same lie the Audio Studio told when it listed six flags and omitted the
one that gated them all.
"""
import os

_TRUE = ("1", "true", "yes", "on")


def _flag(name):
    return (os.environ.get(name) or "").strip().lower() in _TRUE


def enabled():
    """The studio_v1 flag.

    Two names accepted: STUDIO_V1_ENABLED matches the flag's name in the
    build plan, STUDIO_ENABLED matches the environment-variable list in the
    same document. Accepting both costs one `or` and saves an afternoon.
    """
    return _flag("STUDIO_V1_ENABLED") or _flag("STUDIO_ENABLED")


# Sub-flags, each gating one room. All require enabled() as well, so turning
# the product off turns every room off without touching seventeen variables.
def mix_doctor_enabled():
    return enabled() and _flag("STUDIO_MIX_DOCTOR_ENABLED")


def master_station_enabled():
    return enabled() and _flag("STUDIO_MASTER_STATION_ENABLED")


def album_mode_enabled():
    return enabled() and _flag("STUDIO_ALBUM_MASTER_ENABLED")


def delivery_enabled():
    return enabled() and _flag("STUDIO_DELIVERY_ENABLED")


def max_upload_bytes():
    """Must stay UNDER app.config['MAX_CONTENT_LENGTH'] (210 MB).

    Werkzeug refuses an oversize body before routing, so a ceiling above that
    one is a number this code prints and never enforces - the artist gets a
    bare 413 instead of a sentence telling them what to do. That exact bug
    shipped once with a 250 MB Remix Lab against a 25 MB ceiling.
    """
    try:
        value = int(os.environ.get("STUDIO_MAX_UPLOAD_BYTES") or 0)
    except (TypeError, ValueError):
        value = 0
    return value if 0 < value <= 200 * 1024 * 1024 else 200 * 1024 * 1024


def retention_days():
    try:
        value = int(os.environ.get("STUDIO_DEFAULT_RETENTION_DAYS") or 0)
    except (TypeError, ValueError):
        value = 0
    return value if value > 0 else 0        # 0 = keep until deleted


def processing_provider():
    """Empty means no external provider, which is the honest default.

    Nothing here invents a vendor. With no provider configured the Master
    Station offers analysis and preview only, and its render actions are
    disabled with the reason shown - rather than producing something that
    looks like a professional master and is not.
    """
    return (os.environ.get("STUDIO_PROCESSING_PROVIDER") or "").strip()


def provider_configured():
    """A provider name alone is not a configured provider. Without a base URL
    and a key it cannot make a single call, and reporting it as ready would
    move the failure from this screen to a job that dies later."""
    return bool(processing_provider()
                and (os.environ.get("STUDIO_PROVIDER_BASE_URL") or "").strip()
                and (os.environ.get("STUDIO_PROVIDER_API_KEY") or "").strip())


def readiness():
    """What actually works on this deployment, component by component.

    Returned as data so the page can render the real state instead of
    asserting one. Each entry: (key, ok, headline, detail).
    """
    import blob_store

    remote = False
    try:
        remote = blob_store.configured()
    except Exception:
        remote = False

    out = [
        ("analysis", True, "Analysis runs here",
         "Loudness, true peak and dynamics are measured in your browser by the "
         "same BS.1770-4 engine the Rack uses. No provider is involved."),
        ("storage", remote,
         "Object storage connected" if remote else "Object storage not configured",
         "Audio is stored in the bucket and served by short-lived signed URLs."
         if remote else
         "Uploads would fall back to the Render disk, which is 1 GB and shared "
         "with the database. Large audio there takes the database down with it, "
         "so Studio limits upload size until R2 is configured."),
        ("processing", provider_configured(),
         "Processing provider connected" if provider_configured()
         else "No processing provider",
         "Renders are sent to the configured provider."
         if provider_configured() else
         "Mastering and mixing renders are disabled. Analysis, preview and "
         "version tracking all work without one."),
        ("worker", False, "No background worker",
         "This deployment runs a single web service with a 180-second request "
         "timeout. Work that cannot finish inside a request is queued and "
         "reported queued - never reported finished."),
    ]
    return out
