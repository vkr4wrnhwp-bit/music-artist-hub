"""Street Banker Studio - deployment configuration and the studio_v1 flag.

WHY A FLAG AT ALL
-----------------
Studio adds routes, schema and navigation to a product people are using
today, so a deployment needs a way to switch it off. It started OFF by
default, which was right while it was an empty shell and wrong once it
worked: the owner of the product had to ask three separate times where his
own features had gone. It is now ON unless a deployment sets the variable to
0/false/no/off. The schema still lands independently of the surface, which is
the only safe order when a migration has to run against a live database.

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

_FALSE = ("0", "false", "no", "off")


def _explicitly_off(*names):
    """On by default; off only when a deployment says so.

    These started off-by-default, which is right for a surface nobody has seen
    yet and wrong once it works: the owner of the product had to ask three
    times where his own features were. An unset variable now means "on", and
    turning it off is still one variable away.
    """
    for name in names:
        value = (os.environ.get(name) or "").strip().lower()
        if value in _FALSE:
            return True
    return False


def enabled():
    """The studio_v1 flag. ON unless a deployment turns it off.

    Two names accepted: STUDIO_V1_ENABLED matches the flag's name in the build
    plan, STUDIO_ENABLED matches the environment-variable list in the same
    document. Either set to 0/false/no/off switches the whole product off.
    """
    return not _explicitly_off("STUDIO_V1_ENABLED", "STUDIO_ENABLED")


# Sub-flags, each gating one room. All require enabled() as well, so turning
# the product off turns every room off without touching seventeen variables.
def mix_doctor_enabled():
    return enabled() and not _explicitly_off("STUDIO_MIX_DOCTOR_ENABLED")


def master_station_enabled():
    return enabled() and not _explicitly_off("STUDIO_MASTER_STATION_ENABLED")


def album_mode_enabled():
    return enabled() and not _explicitly_off("STUDIO_ALBUM_MASTER_ENABLED")


def delivery_enabled():
    return enabled() and not _explicitly_off("STUDIO_DELIVERY_ENABLED")


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


_BUILD = None


def build_version():
    """The deployed build, read off the service worker's version stamp.

    Shown on the cockpit so "is the site updated" is answered by the page
    itself: if the stamp on screen matches the newest deploy, the browser is
    current; if it is missing or older, the browser is showing a cached page
    and no amount of server-side pushing will change what that tab renders.
    """
    global _BUILD
    if _BUILD is None:
        import os as _os
        import re as _re
        try:
            path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                 "static", "js", "sw.js")
            with open(path, encoding="utf-8") as handle:
                match = _re.search(r"VERSION\s*=\s*.(sb-v\d+).", handle.read())
            _BUILD = match.group(1) if match else "unknown"
        except OSError:
            _BUILD = "unknown"
    return _BUILD
