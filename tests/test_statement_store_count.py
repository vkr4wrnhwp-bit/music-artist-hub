"""49 report lines are not 49 stores.

Symphonic's statement names YouTube four ways - Streaming, Shorts,
Content ID, Audio Tier - and the Statements tile read "49 sources",
which an artist reads as 49 shops. The tile says both numbers now,
the stores counted through store_identity, the same way the recovery
findings already count them.
"""
import io
import uuid

import pytest

import statements_engine as se
from app import create_app

CSV = ("Reporting Period,Track Title,ISRC Code,Digital Service Provider,Royalty\n"
       "JUN-26,Hungry Gods,GBWUL2686921,Spotify,100.00\n"
       "JUN-26,Hungry Gods,GBWUL2686921,YouTube Streaming,5.00\n"
       "JUN-26,Hungry Gods,GBWUL2686921,YouTube Shorts,1.00\n"
       "JUN-26,Hungry Gods,GBWUL2686921,YouTube Content ID,2.00\n")


def test_the_analysis_counts_stores_beside_lines():
    parsed = se.parse_statement(CSV.encode(), "jun.csv")
    rows = parsed["rows"] if isinstance(parsed, dict) else parsed
    a = se.analyze(rows)
    assert a["source_count"] == 4
    assert a["store_count"] == 2, "Spotify, and YouTube once"


def test_the_tile_says_both_numbers():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "lines-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "L", "email": email, "password": "lines-pass-12345"})
    client.post("/plan/switch", data={"plan": "pro"})
    client.post("/statements", data={"statement": (io.BytesIO(CSV.encode()), "jun.csv")},
                content_type="multipart/form-data")
    body = client.get("/statements").get_data(as_text=True)
    assert "2 stores across 4 payee lines" in body
    assert "4 sources" not in body
    track_line = body[body.index("Hungry Gods"):][:400]
    assert "2 stores" in track_line, "the per-track count is stores too"
