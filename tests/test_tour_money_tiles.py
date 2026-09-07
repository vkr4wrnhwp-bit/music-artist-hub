"""TOUR money, less to read.

The same brief as the rest of TOUR (2026-09-06: "more meters and images
and less verbiage, more options if they want the options"): the totals
sit in windows that read '—' until a show has numbers, because a zero
would be a claim about money nobody measured; each show is a row whose
figures are small instruments; the eight-field expense form waits
behind a plus once the ledger has an entry. The settled line stays word
for word: straight sums of what you entered, nothing estimated.
"""
import re

from tests.test_tour_date_page import _user, _tour, _show, flask_app  # noqa: F401


def _money(client, tid):
    r = client.get("/tours/%s/money" % tid)
    assert r.status_code == 200
    return r.get_data(as_text=True)


def _lcds(html):
    block = html.split('id="totals"')[1].split("</div>")[0]
    return re.findall(r'<span class="sb-lcd-v">([^<]*)</span>\s*<span class="sb-lcd-cap">([^<]+)</span>', block)


def test_the_windows_stay_blank_until_a_show_has_numbers(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    a = _show(client, tid, "2030-05-02", "Room One")
    _show(client, tid, "2030-05-03", "Room Two")
    html = _money(client, tid)
    caps = [c for _v, c in _lcds(html)]
    assert caps == ["projected net", "projected gross", "guarantees", "expenses", "collected",
                    "outstanding", "deposits due", "unsettled", "avg net / show"]
    blank = [c for v, c in _lcds(html) if v == "—"]
    assert len(blank) == 8 and "unsettled" not in blank, "counts are counts; money waits for numbers"
    assert "Settled: no settlement entered yet" in html
    assert "straight sums of what you entered, nothing estimated" in html
    assert "0 of 2 shows have numbers" in html

    client.post("/tours/%s/shows/%s/money" % (tid, a), data={"deal_type": "flat", "guarantee": "1000"})
    html = _money(client, tid)
    values = dict((c, v) for v, c in _lcds(html))
    assert values["guarantees"] == "1000" and values["projected net"] != "—" and values["deposits due"] == "0"
    assert "1 of 2 shows have numbers" in html


def test_each_show_is_a_row_with_its_figures_as_instruments(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    a = _show(client, tid, "2030-05-02", "Room One")
    b = _show(client, tid, "2030-05-03", "Room Two")
    client.post("/tours/%s/shows/%s/money" % (tid, a), data={"deal_type": "flat", "guarantee": "1000"})
    html = _money(client, tid)
    rows = html.split('id="by-show"')[1].split("</h2>")[0]
    assert rows.count('class="to-date to-date--money"') == 2
    assert 'class="to-date-when" href="/tours/%s/shows/%s?tab=money"' % (tid, a) in rows
    assert "<table" not in rows, "the by-show table is gone"
    figs = re.findall(r'<span class="to-fig(?: is-net)?"><span>([a-z. ]+)</span><b>([^<]+)</b></span>', rows)
    assert [f for f, _ in figs][:6] == ["guarantee", "earned", "merch", "expenses", "est. net", "outstanding"]
    assert ("guarantee", "1000") in figs
    assert rows.count("no numbers entered") == 1, "the show with nothing entered says so, in three words"
    assert 'class="to-chip' in rows, "the settlement state stays a chip"


def test_the_expense_form_waits_behind_a_plus_once_the_ledger_has_an_entry(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    _show(client, tid, "2030-05-02", "Room One")
    html = _money(client, tid)
    assert '<details class="to-add" id="add-expense" open>' in html, "an empty ledger opens the form"
    assert "No expenses logged." in html
    r = client.post("/tours/%s/expenses/add" % tid, data={"vendor": "Backline Co", "category": "other",
                                                          "amount": "250", "spend_date": "2030-05-01"})
    assert r.status_code in (302, 303)
    html = _money(client, tid)
    assert '<details class="to-add" id="add-expense">' in html and "Add expense</summary>" in html
    assert "Backline Co" in html and 'name="vendor"' in html, "folded, not gone"


def test_the_sheet_and_the_worker_moved_on():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-figs" in css and ".to-fig.is-net" in css and ".to-date--money" in css
    shell = open(os.path.join(here, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 12
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 194
