"""The Statements page makes a promise about six services.

    "CSV exports from Symphonic, DistroKid, TuneCore, ASCAP, BMI, The MLC,
     and most services work - we auto-detect the columns."

Only Symphonic had ever been tried against it. These are representative
header shapes for the other five, and they exist because a promise on a
page that nothing tests is a promise that quietly stops being true - the
first artist to upload a different export finds out instead.

Writing them found CD Baby: it calls the store "Partner", which matched
no alias, so every row landed under "Unknown source". Income-by-store
would have been empty and the coverage analysis could not have seen a
second store at all, which silently disables the whole recovery feature
for that distributor.

These fixtures are shapes, not captures - no real statement data from
anybody's account is checked in here. The column NAMES are what is under
test, because that is what the auto-detection promise is about.
"""
import pytest

import statements_engine as se

FORMATS = {
    "Symphonic": (
        '"Reporting Period",Label,"Track Title","ISRC Code",'
        '"Digital Service Provider",Territory,Count,"Royalty ($US)"\n'
        'JUN-26,Artist,Hungry Gods,GBWUL2686921,Spotify,US,900,3.41\n'),
    "DistroKid": (
        "Reporting Date,Sale Month,Store,Artist,Title,ISRC,UPC,Quantity,"
        "Country of Sale,Earnings (USD)\n"
        "2026-06-01,2026-04,Spotify,Artist,Hungry Gods,GBWUL2686921,123,900,US,3.41\n"),
    "TuneCore": (
        "Sales Period,Store Name,Artist,Song Title,ISRC,Units,Net Revenue\n"
        "2026-04,Apple Music,Artist,Hungry Gods,GBWUL2686921,120,1.88\n"),
    "CD Baby": (
        "Sale Date,Partner,Track Title,ISRC,Net Payable\n"
        "2026-04-30,Deezer,Hungry Gods,GBWUL2686921,0.42\n"),
    "The MLC": (
        "Work Title,ISWC,DSP,Usage Period,Royalty Amount\n"
        "Hungry Gods,T1234567890,Spotify,2026-Q1,2.15\n"),
    "ASCAP": (
        "Work Title,Performance Period,Source,Amount\n"
        "Hungry Gods,2026-1,Terrestrial Radio,4.10\n"),
    "BMI": (
        "Title,Quarter,Distribution Source,Royalty\n"
        "Hungry Gods,2026Q1,Cable,1.75\n"),
}


@pytest.mark.parametrize("service", sorted(FORMATS))
def test_the_export_parses_at_all(service):
    parsed = se.parse_statement(FORMATS[service])
    assert parsed["error"] is None, parsed["error"]
    assert len(parsed["rows"]) == 1


@pytest.mark.parametrize("service", sorted(FORMATS))
def test_the_money_and_the_title_are_found(service):
    parsed = se.parse_statement(FORMATS[service])
    row = parsed["rows"][0]
    assert row["amount"] > 0, "an amount column is the one hard requirement"
    assert row["title"] == "Hungry Gods", (
        "%s: title column not detected (%r)" % (service, parsed["columns"]))


@pytest.mark.parametrize("service", sorted(FORMATS))
def test_the_store_is_named_and_not_swallowed_as_unknown(service):
    """The defect this file was written to catch.

    With no source column every row becomes "Unknown source". The page
    still shows a total, so nothing looks broken - but income-by-store is
    empty and the coverage analysis cannot see a second store, so the
    recovery feature is silently off for that distributor.
    """
    parsed = se.parse_statement(FORMATS[service])
    assert parsed["columns"]["source"], (
        "%s: no source column matched. Headers: %s"
        % (service, list(FORMATS[service].splitlines()[0].split(","))))
    assert parsed["rows"][0]["source"] != "Unknown source", service


def test_the_isrc_is_kept_where_the_export_carries_one():
    """Needed to check a gap against a store's catalogue. Not every
    format has one - a PRO statement is about works, not recordings -
    and its absence is fine as long as it is not invented."""
    for service in ("Symphonic", "DistroKid", "TuneCore", "CD Baby"):
        row = se.parse_statement(FORMATS[service])["rows"][0]
        assert row["isrc"] == "GBWUL2686921", service
    for service in ("The MLC", "ASCAP", "BMI"):
        row = se.parse_statement(FORMATS[service])["rows"][0]
        assert row["isrc"] == "", "%s has no ISRC and must not invent one" % service


def test_an_export_with_no_amount_column_is_refused_with_its_headers():
    parsed = se.parse_statement("Track,Store,Units\nHungry Gods,Spotify,900\n")
    assert parsed["error"] and "amount" in parsed["error"].lower()
    assert "Units" in parsed["error"], "the refusal names what it saw"


def test_the_artist_is_kept_where_the_export_names_one():
    """A label's export carries every act on the roster in one file
    (2026-09-14). The column is read where it exists and left blank -
    never guessed from the filename or the account - where it does not."""
    for service in ("DistroKid", "TuneCore"):
        row = se.parse_statement(FORMATS[service])["rows"][0]
        assert row["artist"] == "Artist", service
    for service in ("Symphonic", "CD Baby", "The MLC", "ASCAP", "BMI"):
        row = se.parse_statement(FORMATS[service])["rows"][0]
        assert row["artist"] == "", "%s names no artist and must not invent one" % service


def test_a_roster_export_is_read_per_act():
    label = ("Reporting Period,Artist,Track Title,Digital Service Provider,Royalty ($US)\n"
             "JUN-26,Hungry Gods,Narrow,Spotify,60\n"
             "JUN-26,Hungry Gods,Wide,Deezer,40\n"
             "JUN-26,Hellhounds,Howl,Spotify,100\n"
             "JUN-26,,Orphan,Spotify,20\n")
    parsed = se.parse_statement(label)
    assert parsed["columns"]["artist"] == "Artist"
    a = se.analyze(parsed["rows"])
    assert a["artist_count"] == 2
    assert [(x["artist"], x["amount"], x["tracks"]) for x in a["by_artist"]] == [
        ("Hungry Gods", 100.0, 2), ("Hellhounds", 100.0, 1)]
    assert a["by_artist"][0]["share"] == round(100 / 220, 4)
    one = se.analyze(se.parse_statement(FORMATS["Symphonic"])["rows"])
    assert one["artist_count"] == 0 and one["by_artist"] == []
