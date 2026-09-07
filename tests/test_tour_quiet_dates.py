"""Quiet dates fold.

Read on the live 36-date run after the tile pass shipped: Guests,
Marketing and Money each drew 36 identical empty rows, and the home's
attention list said the same two dates ten times. Now a run-wide page
shows the dates that hold something and folds the rest behind one
count; when nothing holds anything the first three stay out so the page
still shows where to start; the home says one line per date with a
count and the items behind it.
"""
import re

from tests.test_tour_date_page import _user, _tour, _show, flask_app  # noqa: F401

DATES = ["2030-05-0%d" % d for d in range(2, 8)]


def _six(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sids = [_show(client, tid, d, "Room %d" % i) for i, d in enumerate(DATES)]
    return client, owner, tid, sids


def _grid(html, anchor):
    return html.split('id="%s"' % anchor)[1]


def _visible_and_folded(html, anchor, row_class):
    grid = _grid(html, anchor)
    fold = grid.split('<details class="to-fold to-quiet">')
    visible = fold[0].count('class="%s"' % row_class)
    folded = fold[1].split("</details>")[0].count('class="%s"' % row_class) if len(fold) > 1 else 0
    summary = re.search(r"<summary>([^<]+)</summary>", fold[1]).group(1) if len(fold) > 1 else ""
    return visible, folded, summary


def test_guests_marketing_and_money_fold_the_dates_that_hold_nothing(flask_app):
    client, owner, tid, sids = _six(flask_app)
    for path, anchor, row in (("guests", "guest-shows", "to-date to-date--money"),
                              ("marketing", "markets", "to-date to-date--market"),
                              ("money", "by-show", "to-date to-date--money")):
        html = client.get("/tours/%s/%s" % (tid, path)).get_data(as_text=True)
        assert _visible_and_folded(html, anchor, row) == (3, 3, "3 dates with nothing entered yet"), path
    # One date gets something: it is the only one out; the other five fold.
    client.post("/tours/%s/shows/%s/ext" % (tid, sids[4]), data={"guest_allocation": "4"})
    client.post("/tours/%s/shows/%s/marketing" % (tid, sids[4]), data={"ticket_url": "https://tickets.example/x"})
    client.post("/tours/%s/shows/%s/money" % (tid, sids[4]), data={"guarantee": "1500", "deal_type": "flat"})
    for path, anchor, row in (("guests", "guest-shows", "to-date to-date--money"),
                              ("marketing", "markets", "to-date to-date--market"),
                              ("money", "by-show", "to-date to-date--money")):
        html = client.get("/tours/%s/%s" % (tid, path)).get_data(as_text=True)
        visible, folded, summary = _visible_and_folded(html, anchor, row)
        assert (visible, folded, summary) == (1, 5, "5 dates with nothing entered yet"), path
        assert ("/shows/%s?tab=" % sids[4]) in _grid(html, anchor).split('<details class="to-fold to-quiet">')[0], path


def test_the_home_says_one_line_per_date_with_a_count(flask_app):
    client, owner, tid, sids = _six(flask_app)
    html = client.get("/tours/%s" % tid).get_data(as_text=True)
    board = html.split("Needs attention</h2>")[1].split("<h2")[0]
    assert len(re.findall(r'sb-lamp sb-lamp--crit">\d+ open</span>', board)) == 5, "five dates shown, one line each"
    assert board.count('<details class="to-date-missing"><summary>what</summary>') == 5
    assert "1 more date with open items" in board
    assert ('/shows/%s"' % sids[0]) in board and ('/shows/%s"' % sids[5]) not in board
    assert "Nashville, TN contract" not in board, "the city is not repeated on every item"


def test_the_person_form_folds_its_show_list(flask_app):
    client, owner, tid, sids = _six(flask_app)
    html = client.get("/tours/%s/people" % tid).get_data(as_text=True)
    assert "<summary>Shows (none ticked = every show)</summary>" in html
    assert html.count('name="shows"') == 6


def test_the_sheet_moved_on():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-quiet" in css
    shell = open(os.path.join(here, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 21
