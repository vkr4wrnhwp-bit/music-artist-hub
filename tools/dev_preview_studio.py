"""Local preview of Street Banker Studio, on a THROWAWAY database.

Same contract as tools/dev_preview.py - DATABASE_PATH is pointed at a scratch
file before the app is imported, so this never touches real dev data - plus
two things that one does not:

  * studio_v1 is switched on, because every Studio route 404s while it is off.
  * a demo project is seeded with a REAL generated WAV, so the waveform and
    the loudness readout have something to draw and measure. The audio is a
    synthesised tone written here, not a recording of anybody's music.

    python tools/dev_preview_studio.py        # http://localhost:5066

Nothing in this file runs in production: it is under tools/, it is never
imported by app.py, and it writes only to a temporary database.
"""
import io
import math
import os
import struct
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ["DATABASE_PATH"] = os.path.join(
    tempfile.gettempdir(), "sb-studio-preview", "preview.db")
os.makedirs(os.path.dirname(os.environ["DATABASE_PATH"]), exist_ok=True)
os.environ["STUDIO_V1_ENABLED"] = "1"

import app as appmod  # noqa: E402

DEMO_EMAIL = "preview@example.net"
DEMO_PASSWORD = "preview-pass-123"


def _tone_wav(seconds=8, rate=44100):
    """A 16-bit stereo WAV with a moving level, so the waveform has a shape
    and the loudness gates have something to gate. Deliberately quiet-ish, to
    leave headroom rather than to look impressive."""
    frames = []
    total = seconds * rate
    for n in range(total):
        t = n / float(rate)
        # Two partials, plus a slow swell so the envelope is visible.
        swell = 0.35 + 0.45 * abs(math.sin(math.pi * t / seconds))
        sample = swell * (0.55 * math.sin(2 * math.pi * 196.0 * t)
                          + 0.30 * math.sin(2 * math.pi * 392.0 * t)
                          + 0.12 * math.sin(2 * math.pi * 587.3 * t))
        value = int(max(-1.0, min(1.0, sample)) * 20000)
        frames.append(struct.pack("<hh", value, value))
    body = b"".join(frames)
    header = (b"RIFF" + struct.pack("<I", 36 + len(body)) + b"WAVEfmt "
              + struct.pack("<IHHIIHH", 16, 1, 2, rate, rate * 4, 4, 16)
              + b"data" + struct.pack("<I", len(body)))
    return header + body


def seed():
    client = appmod.app.test_client()
    client.post("/signup", data={"name": "Preview Artist",
                                 "email": DEMO_EMAIL,
                                 "password": DEMO_PASSWORD})
    client.post("/login", data={"email": DEMO_EMAIL,
                                "password": DEMO_PASSWORD, "remember": "1"})

    made = []
    for title, artist, kind in (
        ("Signal Fire", "Preview Artist", "stereo_mix_review"),
        ("Cold Water", "Preview Artist", "master_single"),
        ("Long Way Down", "Preview Artist", "stem_mix"),
    ):
        response = client.post("/studio/new", data={
            "title": title, "artist_name": artist, "project_type": kind})
        made.append(response.headers.get("Location", "").rstrip("/").split("/")[-1])

    # Only the first one gets a source, so the preview shows both states: a
    # session waiting for audio and a session with audio in it.
    first = made[0]
    client.post("/studio/session/%s/rights" % first,
                data={"confirmed_by": "Preview Artist"})
    client.post("/studio/session/%s/upload" % first,
                data={"file": (io.BytesIO(_tone_wav()), "signal-fire-mix-3.wav")},
                content_type="multipart/form-data")
    return first


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5066"))
    appmod.app.config["TEMPLATES_AUTO_RELOAD"] = True
    appmod.app.jinja_env.auto_reload = True
    appmod.app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    project_id = seed()
    print("preview on http://localhost:%d" % port)
    print("  sign in: %s / %s" % (DEMO_EMAIL, DEMO_PASSWORD))
    print("  session: /studio/session/%s" % project_id)
    appmod.app.run(port=port, debug=False, use_reloader=False, threaded=True)
