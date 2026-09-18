"""A fan list comes in from whatever tool it lives in, and nothing is lost.

Owner, 2026-09-17: the Fans page offered one connected Shopify store and
nothing else, so an artist whose list is in Mailchimp or on a spreadsheet
could not bring it. Every tool exports a CSV and they all disagree about
the column names, so the columns are read rather than demanded.

The two rules under test: consent is never invented, and no row is ever
dropped without being counted under a reason.
"""
import fan_list_import as fli

MAILCHIMP = (
    "Email Address,First Name,Last Name,Status\n"
    "ada@example.com,Ada,Lovelace,subscribed\n"
    "grace@example.com,Grace,Hopper,subscribed\n"
    "left@example.com,Someone,Gone,unsubscribed\n"
    "bounced@example.com,Bad,Address,cleaned\n"
)
KLAVIYO = (
    "Email,First Name,Last Name,Email Marketing Consent\n"
    "ada@example.com,Ada,Lovelace,SUBSCRIBED\n"
    "never@example.com,No,Thanks,NEVER_SUBSCRIBED\n"
)
SHOPIFY = (
    "First Name,Last Name,Email,Accepts Email Marketing\n"
    "Ada,Lovelace,ada@example.com,yes\n"
    "Alan,Turing,alan@example.com,no\n"
)
BANDCAMP = "email,name\nada@example.com,Ada Lovelace\nalan@example.com,Alan Turing\n"
BARE = "ada@example.com\nalan@example.com\n"


def test_it_reads_the_column_names_every_tool_uses():
    for text, label in ((MAILCHIMP, "mailchimp"), (KLAVIYO, "klaviyo"),
                        (SHOPIFY, "shopify"), (BANDCAMP, "bandcamp")):
        cols = fli.read_columns(text)
        assert cols["email"] is not None, label
        assert cols["status"] is not None or label == "bandcamp", label


def test_a_mailchimp_export_brings_the_subscribed_and_leaves_the_rest():
    p = fli.parse(MAILCHIMP)
    assert [r["email"] for r in p["rows"]] == ["ada@example.com", "grace@example.com"]
    assert p["rows"][0]["name"] == "Ada Lovelace"
    whys = {s["why"] for s in p["skipped"]}
    assert whys == {"their list says unsubscribed"}
    assert len(p["skipped"]) == 2, "unsubscribed AND cleaned, both left out"


def test_the_words_each_tool_uses_for_no_are_all_understood():
    assert [r["email"] for r in fli.parse(KLAVIYO)["rows"]] == ["ada@example.com"]
    assert [r["email"] for r in fli.parse(SHOPIFY)["rows"]] == ["ada@example.com"]


def test_a_list_with_no_consent_column_is_not_read_as_permission():
    p = fli.parse(BANDCAMP)
    assert len(p["rows"]) == 2
    assert p["has_status_column"] is False
    note = fli.consent_note("Bandcamp", "2026-09-17", p["has_status_column"])
    assert "the artist's word is the only record" in note


def test_the_consent_record_says_where_it_came_from_and_who_vouched():
    note = fli.consent_note("Mailchimp", "2026-09-17", True)
    assert "Imported from Mailchimp" in note
    assert "The artist confirmed on 2026-09-17" in note
    # It must never read as though the fan agreed inside Street Banker.
    assert "signed up" not in note.lower() and "opted in here" not in note.lower()


def test_a_bare_column_of_addresses_still_works():
    p = fli.parse(BARE)
    assert [r["email"] for r in p["rows"]] == ["ada@example.com", "alan@example.com"]
    assert p["had_header"] is False


def test_semicolons_and_tabs_are_read_too():
    assert len(fli.parse("Email;Name\na@b.co;A\nc@d.co;C\n")["rows"]) == 2
    assert len(fli.parse("Email\tName\na@b.co\tA\n")["rows"]) == 1


def test_rubbish_rows_are_counted_not_dropped():
    p = fli.parse("Email,Name\n,Nobody\nnot-an-address,Who\nada@example.com,Ada\n"
                  "ada@example.com,Ada Again\n")
    assert [r["email"] for r in p["rows"]] == ["ada@example.com"]
    whys = sorted(s["why"] for s in p["skipped"])
    assert whys == ["no email address", "not a readable email address",
                    "the same address twice in this file"]


def test_the_preview_adds_up_to_the_rows_read():
    p = fli.parse(MAILCHIMP)
    view = fli.preview(p, known_emails=["grace@example.com"])
    assert view["read"] == 4
    assert view["new"] == 1 and view["already_here"] == 1 and view["skipped"] == 2
    assert view["adds_up"] is True
    assert view["reasons"] == {"their list says unsubscribed": 2}
    assert view["sample"] == ["ada@example.com"]


def test_a_file_with_no_address_column_is_refused_rather_than_guessed_at():
    p = fli.parse("Name,Phone\nAda,555\n")
    assert p["rows"] == [] and p["columns"]["email"] is None


def test_a_very_long_list_stops_and_says_so_rather_than_truncating_quietly():
    text = "Email\n" + "".join("a%d@example.com\n" % i for i in range(60))
    p = fli.parse(text, limit=25)
    assert p["read"] == 25 and p["truncated"] is True
    assert fli.preview(p)["truncated"] is True


def test_an_empty_file_is_empty_and_not_an_error():
    for text in ("", "\n", "   "):
        p = fli.parse(text)
        assert p["rows"] == [] and p["read"] == 0
