"""Server-side conversion.

Most of these read the command rather than running it. That is
deliberate: the thing worth proving is that no value a user typed ever
reaches ffmpeg unchecked, and running the binary would prove the opposite
of nothing about it.
"""
import convert_engine as ce


def args_for(**kw):
    kw.setdefault("fmt", "mp3")
    return ce.build_args("in.wav", "out.x", kw.pop("fmt"), **kw)


# --- nothing user-typed reaches the command line ------------------------

def test_bitrate_outside_the_table_falls_back():
    # 999 is not on offer; the encoder must not be told to try it.
    args = args_for(bitrate=999)
    assert "-b:a" in args
    assert args[args.index("-b:a") + 1] == "320k"     # the format default


def test_rate_outside_the_table_is_dropped_entirely():
    assert "-ar" not in args_for(rate=7)


def test_channel_count_outside_the_table_is_dropped():
    assert "-ac" not in args_for(channels=9)


def test_every_argument_is_its_own_argv_entry():
    args = args_for(bitrate=320, rate=48000, channels=2)
    assert all(" " not in a for a in args if not a.endswith((".wav", ".x")))


def test_the_shell_is_never_asked_to_parse_anything():
    src = "in; rm -rf /.wav"
    args = ce.build_args(src, "out.mp3", "mp3")
    # The path travels as one argv entry, so the semicolon is just a
    # character in a filename rather than a command separator.
    assert src in args


# --- format behaviour ----------------------------------------------------

def test_lossless_formats_carry_no_bitrate():
    for fmt in ("flac", "alac", "wav", "aiff"):
        assert "-b:a" not in ce.build_args("i", "o", fmt), fmt


def test_bit_depth_only_applies_to_pcm():
    wav = ce.build_args("i", "o", "wav", depth=16)
    assert "pcm_s16le" in wav
    aiff = ce.build_args("i", "o", "aiff", depth=32)
    assert "pcm_f32be" in aiff          # AIFF is big-endian
    # A depth on a compressed format is meaningless and must be ignored.
    assert "-c:a" in ce.build_args("i", "o", "mp3", depth=16)
    assert "libmp3lame" in ce.build_args("i", "o", "mp3", depth=16)


def test_unknown_depth_leaves_the_format_default():
    assert "pcm_s24le" in ce.build_args("i", "o", "wav", depth=7)


def test_video_streams_are_dropped():
    # An m4a or webm input can carry cover art or video; -vn keeps it out
    # of an audio render.
    assert "-vn" in ce.build_args("i", "o", "mp3")


# --- the menu ------------------------------------------------------------

def test_lossless_formats_come_first():
    vals = [f["value"] for f in ce.format_list()]
    lossy = [i for i, f in enumerate(ce.format_list()) if f["lossy"]]
    lossless = [i for i, f in enumerate(ce.format_list()) if not f["lossy"]]
    assert max(lossless) < min(lossy)
    assert "mp3" in vals and "flac" in vals


def test_every_format_has_a_note_and_an_extension():
    for f in ce.format_list():
        assert f["note"] and f["ext"]
        assert f["lossy"] == ce.FORMATS[f["value"]]["lossy"]


def test_lossy_formats_offer_bitrates_and_lossless_do_not():
    for f in ce.format_list():
        assert bool(f["bitrates"]) == f["lossy"], f["value"]


# --- refusals ------------------------------------------------------------

def test_unknown_format_is_refused():
    out, name, err = ce.convert(b"x", "a.wav", "mp4v")
    assert out is None and "unknown format" in err


def test_empty_input_is_refused():
    out, name, err = ce.convert(b"", "a.wav", "mp3")
    assert out is None and err


def test_oversized_input_is_refused_before_any_work():
    big = b"\0" * (ce.MAX_BYTES + 1)
    out, name, err = ce.convert(big, "a.wav", "mp3")
    assert out is None and "MB" in err


def test_missing_encoder_is_reported_not_hidden(monkeypatch):
    monkeypatch.setattr(ce, "available", lambda: False)
    out, name, err = ce.convert(b"x", "a.wav", "mp3")
    assert out is None and "no encoder" in err


# --- what the rack page says depends on what the box can do -------------

def _rack_page(monkeypatch, has_encoder):
    """Render /rack with the encoder present or absent."""
    import app as app_mod
    import convert_engine
    monkeypatch.setattr(convert_engine, "available", lambda: has_encoder)
    application = app_mod.create_app()
    client = application.test_client()
    client.post("/login", data={"email": "demo@streetbanker.io",
                                "password": "sweep"})
    return client.get("/rack").get_data(as_text=True)


def test_without_an_encoder_the_page_promises_nothing_uploads(monkeypatch):
    page = _rack_page(monkeypatch, False)
    assert "Everything here runs in this tab; nothing uploads." in page
    # And it must not dangle formats it cannot produce.
    assert 'value="mp3"' not in page
    assert 'id="rk-cnv-brwrap"' not in page


def test_with_an_encoder_the_page_says_where_each_format_happens(monkeypatch):
    page = _rack_page(monkeypatch, True)
    assert "no browser gives a web page an MP3, FLAC or AAC encoder" in page
    assert "WAV and AIFF are written in this tab and never leave it" in page
    # The upload is disclosed before the button, not after.
    assert 'id="rk-cnv-where"' in page and 'id="rk-cnv-brwrap"' in page
    for fmt in ("mp3", "flac", "alac", "aac", "opus", "vorbis"):
        assert 'value="%s"' % fmt in page, fmt
