"""One source of truth: the cross-surface assertions.

Four facts about an account were stored in more than one table and
computed by more than one rule, so two pages could disagree about the
same artist. Each section below picks the surfaces a real person
actually compares - a press kit against a money page, a passport against
a catalog row - and asserts they say the same thing for the same
account.

The per-module rules live with their modules (catalog_value,
artist_identity, db.get_catalog_tracks). This file is where the pages
are held to them.
"""
import io as _io
import uuid

import pytest

from app import create_app

PASSWORD = "one-truth-123"

STATEMENT_CSV = "".join(line + "\n" for line in (
    "Track Title,Store,Net Revenue,Sales Period",
    "Midnight Drive,Spotify,120.50,2026-05",
    "Midnight Drive,Apple Music,80.25,2026-05",
    "Neon Dreams,Spotify,60.00,2026-06",
)).encode()


@pytest.fixture(scope="module")
def application():
    return create_app()


@pytest.fixture
def artist(application):
    """A fresh Pro account. Never the demo showcase: the whole point of
    these assertions is that the numbers belong to one real account."""
    import db as store

    email = "onetruth-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Vera Kane", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    client.post("/plan/switch", data={"plan": "pro"})
    with application.app_context():
        uid = store.get_user_by_email(email)["id"]
    return {"client": client, "uid": uid, "email": email}


def _upload_statements(client):
    r = client.post("/statements",
                    data={"statement": (_io.BytesIO(STATEMENT_CSV), "dist.csv")},
                    content_type="multipart/form-data")
    assert r.status_code == 302


# --- Finding 4: one catalog-value rule ----------------------------------------

def test_the_money_page_the_press_kit_and_benchmark_quote_one_valuation(artist):
    """Same account, same statements, three surfaces, one figure.

    /valuation used 3-5x, the press kit re-derived 3-5x from its own
    copy, and /benchmark applied 8/12/16x to an illustrative trend. A
    label reading the kit and the page saw two catalog values three
    times apart.
    """
    import benchmark_config
    import db as store
    import epk_config
    import valuation_engine

    _upload_statements(artist["client"])
    rows = store.get_statement_rows(artist["uid"])

    money = valuation_engine.build(artist["uid"])
    assert money["has_data"] and money["value"]["mid"] > 0

    kit = epk_config.real_stats(rows, track_count=0)
    kit_value = next(s for s in kit if s["label"] == "Est. Catalog Value")

    bench = benchmark_config.get_benchmark_data(rows)
    bench_value = next(m for m in bench["metrics"]
                       if m["label"] == "Est. catalog value")

    assert kit_value["value"] == "${:,.0f}".format(money["value"]["mid"])
    assert round(bench_value["you"]) == money["value"]["mid"]


def test_every_valuation_multiple_in_the_app_comes_from_one_module():
    """No second copy of the band, and no second opinion about it."""
    import catalog_value
    import royalty_data
    import statements_engine
    import valuation_engine

    assert valuation_engine.MULTIPLES is catalog_value.MULTIPLES
    assert royalty_data.CATALOG_VALUE_MULTIPLES is catalog_value.MULTIPLES
    summary = statements_engine.build_royalty_summary(
        [{"title": "T", "source": "S", "amount": 1000.0, "period": "2026-01"}])
    assert summary["valuation"] == catalog_value.band(12000.0)
    # The band the money pages show, not an average of the three that
    # used to be in the tree.
    assert catalog_value.MULTIPLES == {"low": 3, "mid": 4, "high": 5}


def test_the_valuation_page_renders_the_band_it_computed(artist):
    _upload_statements(artist["client"])
    import valuation_engine
    money = valuation_engine.build(artist["uid"])
    body = artist["client"].get("/valuation").get_data(as_text=True)
    assert "${:,.0f}".format(money["value"]["mid"]) in body
    assert "Catalog signal (mid, 4x)" in body
