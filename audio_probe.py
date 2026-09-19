"""What an uploaded audio file is, read from its own header.

Release-Ready refuses a file before anything is stored or sent to RoEx
when it is the wrong format, too long, too short, or at a sample rate
RoEx's own examples refuse. RoEx documents no error code for any of
those, so the only honest place to catch them is here, on our side.

WAV (RIFF/WAVE, including WAVE_FORMAT_EXTENSIBLE and 24-bit) and FLAC
(the STREAMINFO block) are read in pure Python from the first bytes of
the file. MP3 length comes from its Xing/Info/VBRI header when there is
one, which gives an exact frame count; otherwise from ffmpeg when the
server has it; otherwise it is unknown, and an unknown length is refused
with a plain message rather than guessed.

A WAV header that promises more audio than the file holds is broken, and
is refused as unreadable: the length it states is not the length RoEx
would get.
"""
import os
import re
import shutil
import struct
import subprocess

MIN_SECONDS = 10
MAX_SECONDS = 600                      # RoEx: 10 minutes per file
MAX_BYTES = 200 * 1024 * 1024
SAMPLE_RATES = (44100, 48000)
EXTS = (".wav", ".flac", ".mp3")
MIME = {".wav": "audio/wav", ".flac": "audio/flac", ".mp3": "audio/mpeg"}

_WAVE_FORMAT_PCM = 1
_WAVE_FORMAT_FLOAT = 3
_WAVE_FORMAT_EXTENSIBLE = 0xFFFE


def _ext(name):
    name = (name or "").lower()
    return os.path.splitext(name)[1] if "." in name else ""


def sniff(head):
    """The format the bytes say they are, or None."""
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return ".wav"
    body = head
    if head[:3] == b"ID3" and len(head) >= 10:
        size = _synchsafe(head[6:10])
        body = head[10 + size:]
        if body[:4] == b"fLaC":
            return ".flac"
        return ".mp3"
    if head[:4] == b"fLaC":
        return ".flac"
    if len(body) >= 2 and body[0] == 0xFF and (body[1] & 0xE0) == 0xE0:
        return ".mp3"
    return None


def _synchsafe(b):
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def probe(path, filename):
    """{ok: True, format, duration_s, sample_rate, channels, bit_depth}
    or {ok: False, reason, ...}. Reasons: unsupported_format, too_big,
    unreadable, too_short, too_long, sample_rate."""
    ext = _ext(filename)
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            head = fh.read(65536)
    except OSError:
        return {"ok": False, "reason": "unreadable"}
    if ext not in EXTS or sniff(head) != ext:
        return {"ok": False, "reason": "unsupported_format"}
    if size > MAX_BYTES:
        return {"ok": False, "reason": "too_big", "bytes": size}
    try:
        if ext == ".wav":
            info = _wav(path, size)
        elif ext == ".flac":
            info = _flac(path)
        else:
            info = _mp3(path, size)
    except (OSError, struct.error, ValueError, IndexError):
        info = None
    if not info or not info.get("duration_s"):
        return {"ok": False, "reason": "unreadable"}
    info["format"] = ext[1:]
    info["mime_type"] = MIME[ext]
    dur = info["duration_s"]
    if dur < MIN_SECONDS:
        return dict(info, ok=False, reason="too_short")
    if dur > MAX_SECONDS:
        return dict(info, ok=False, reason="too_long")
    if info.get("sample_rate") and info["sample_rate"] not in SAMPLE_RATES:
        return dict(info, ok=False, reason="sample_rate")
    return dict(info, ok=True)


def wav_facts(path):
    """A WAV's own header, with none of the upload limits: {sample_rate,
    bit_depth, channels, duration_s}, or None when it is not a readable
    WAV. Release-Ready reads a stored master with this, so the format line
    on the page is what the file holds, not what we expected it to hold."""
    try:
        info = _wav(path, os.path.getsize(path))
    except (OSError, struct.error, ValueError, IndexError):
        return None
    return info or None


def mmss(seconds):
    s = int(round(seconds or 0))
    return "%d:%02d" % (s // 60, s % 60)


# --- WAV ------------------------------------------------------------------------

def _wav(path, size):
    with open(path, "rb") as fh:
        head = fh.read(12)
        if len(head) < 12 or head[:4] != b"RIFF" or head[8:12] != b"WAVE":
            return None
        fmt = None
        while True:
            hdr = fh.read(8)
            if len(hdr) < 8:
                return None
            cid, csize = hdr[:4], struct.unpack("<I", hdr[4:])[0]
            if cid == b"fmt ":
                raw = fh.read(csize)
                if len(raw) < 16:
                    return None
                tag, channels, rate, byte_rate, align, bits = struct.unpack("<HHIIHH", raw[:16])
                if tag == _WAVE_FORMAT_EXTENSIBLE and len(raw) >= 40:
                    valid_bits = struct.unpack("<H", raw[18:20])[0]
                    tag = struct.unpack("<H", raw[24:26])[0]      # the subformat GUID
                    bits = valid_bits or bits
                if tag not in (_WAVE_FORMAT_PCM, _WAVE_FORMAT_FLOAT):
                    return None
                fmt = {"channels": channels, "sample_rate": rate, "bit_depth": bits,
                       "byte_rate": byte_rate or rate * align}
                if csize % 2:
                    fh.seek(1, os.SEEK_CUR)
                continue
            if cid == b"data":
                if not fmt or not fmt["byte_rate"]:
                    return None
                start = fh.tell()
                available = size - start
                if csize in (0, 0xFFFFFFFF):
                    csize = available             # a streamed header that never came back
                elif csize > available + 1:
                    return None                   # the header promises audio the file lacks
                return {"channels": fmt["channels"], "sample_rate": fmt["sample_rate"],
                        "bit_depth": fmt["bit_depth"],
                        "duration_s": round(csize / float(fmt["byte_rate"]), 3)}
            fh.seek(csize + (csize % 2), os.SEEK_CUR)


# --- FLAC -----------------------------------------------------------------------

def _flac(path):
    with open(path, "rb") as fh:
        head = fh.read(10)
        if head[:3] == b"ID3":
            fh.seek(10 + _synchsafe(head[6:10]))
        else:
            fh.seek(0)
        if fh.read(4) != b"fLaC":
            return None
        block = fh.read(4)
        if len(block) < 4 or (block[0] & 0x7F) != 0:        # STREAMINFO comes first
            return None
        info = fh.read(34)
        if len(info) < 34:
            return None
    bits = int.from_bytes(info[10:18], "big")
    rate = bits >> 44
    channels = ((bits >> 41) & 0x7) + 1
    depth = ((bits >> 36) & 0x1F) + 1
    total = bits & 0xFFFFFFFFF
    if not rate or not total:
        return None
    return {"channels": channels, "sample_rate": rate, "bit_depth": depth,
            "duration_s": round(total / float(rate), 3)}


# --- MP3 --------------------------------------------------------------------------

_RATES = {1: (44100, 48000, 32000), 2: (22050, 24000, 16000), 25: (11025, 12000, 8000)}


def _mp3(path, size):
    with open(path, "rb") as fh:
        data = fh.read(131072)
    off = 0
    if data[:3] == b"ID3" and len(data) >= 10:
        off = 10 + _synchsafe(data[6:10])
        if off >= len(data):
            with open(path, "rb") as fh:
                fh.seek(off)
                data = fh.read(131072)
            off = 0
    # the first frame sync
    i = off
    while i + 4 <= len(data):
        if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
            hdr = _frame_header(data[i:i + 4])
            if hdr:
                break
        i += 1
    else:
        return _mp3_ffmpeg(path)
    version, layer, rate, channels = hdr
    samples_per_frame = 1152 if version == 1 else 576
    side = (32 if channels == 2 else 17) if version == 1 else (17 if channels == 2 else 9)
    for tag_off in (i + 4 + side, i + 36):
        tag = data[tag_off:tag_off + 4]
        if tag in (b"Xing", b"Info"):
            flags = struct.unpack(">I", data[tag_off + 4:tag_off + 8])[0]
            if flags & 1:
                frames = struct.unpack(">I", data[tag_off + 8:tag_off + 12])[0]
                if frames:
                    return {"channels": channels, "sample_rate": rate, "bit_depth": None,
                            "duration_s": round(frames * samples_per_frame / float(rate), 3)}
        if tag == b"VBRI":
            frames = struct.unpack(">I", data[tag_off + 14:tag_off + 18])[0]
            if frames:
                return {"channels": channels, "sample_rate": rate, "bit_depth": None,
                        "duration_s": round(frames * samples_per_frame / float(rate), 3)}
    got = _mp3_ffmpeg(path)
    if got:
        got.setdefault("sample_rate", rate)
        got.setdefault("channels", channels)
    return got


def _frame_header(b):
    ver_bits = (b[1] >> 3) & 0x3
    layer_bits = (b[1] >> 1) & 0x3
    if ver_bits == 1 or layer_bits != 1:          # reserved version; Layer III only
        return None
    version = {3: 1, 2: 2, 0: 25}[ver_bits]
    rate_idx = (b[2] >> 2) & 0x3
    br_idx = (b[2] >> 4) & 0xF
    if rate_idx == 3 or br_idx in (0, 15):
        return None
    rate = _RATES[version][rate_idx]
    channels = 1 if ((b[3] >> 6) & 0x3) == 3 else 2
    return version, 3, rate, channels


def _ffmpeg_path():
    return shutil.which("ffmpeg")


_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def _mp3_ffmpeg(path):
    exe = _ffmpeg_path()
    if not exe:
        return None
    try:
        run = subprocess.run([exe, "-hide_banner", "-nostdin", "-i", path],
                             capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    m = _DURATION.search(run.stderr.decode("utf-8", "replace"))
    if not m:
        return None
    h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return {"channels": None, "sample_rate": None, "bit_depth": None,
            "duration_s": round(h * 3600 + mi * 60 + s, 3)}
