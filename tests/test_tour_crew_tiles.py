"""TOUR crew, less to read.

The same brief as the rest of TOUR: the categories are counted chips
that filter, one row per person carries the contact beside the name,
and the nine-field person form waits behind a plus once anybody is in
the directory. The redaction is untouched - what a viewer may not see
is still not on the page - and tests/test_tour_os.py keeps holding it.
"""
import re

from tests.test_tour_date_page import _user, _tour, _show, flask_app  # noqa: F401


def _people(client, tid, **args):
    q = "&".join("%s=%s" % kv for kv in args.items())
    r = client.get("/tours/%s/people%s" % (tid, ("?" + q) if q else ""))
    assert r.status_code == 200
    return r.get_data(as_text=True)


def _add(client, tid, **fields):
    data = {"name": "Someone", "role": "", "category": "Crew", "company": "", "email": "", "phone": "", "emergency": ""}
    data.update(fields)
    r = client.post("/tours/%s/people/save" % tid, data=data)
    assert r.status_code in (302, 303)


def test_categories_are_counted_chips_that_filter(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    _add(client, tid, name="Ava Kane", role="Tour manager", category="Tour Management", phone="555 0177")
    _add(client, tid, name="Bo Lee", role="FOH", category="Crew")
    _add(client, tid, name="Cy Ro", role="Driver", category="Drivers")
    html = _people(client, tid)
    chips = re.findall(r'<a class="to-chip-btn( is-on)?" href="([^"]+)">([^<]+)</a>', html.split('id="cats"')[1].split("</div>")[0])
    assert [(c, t) for _on, c, t in chips] == [("?q=", "All · 3"), ("?category=Tour%20Management&amp;q=", "Tour Management · 1"),
                                               ("?category=Crew&amp;q=", "Crew · 1"), ("?category=Drivers&amp;q=", "Drivers · 1")]
    assert chips[0][0] == " is-on", "All is lit until a category is chosen"
    bar = html.split('id="cats"')[0].split("Everyone on the run")[1]
    assert '<select name="category"' not in bar, "the filter select became chips (the form's own stays)"
    only = _people(client, tid, category="Crew")
    assert only.count('class="to-date to-date--person"') == 1 and "Bo Lee" in only and "Ava Kane" not in only
    assert 'class="to-chip-btn is-on" href="?category=Crew' in only
    assert "All · 3" in only, "the counts are over everyone, whatever the filter"


def test_each_person_is_a_row_with_the_contact_beside_the_name(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    _add(client, tid, name="Ava Kane", role="Tour manager", category="Tour Management", company="Rivet & Co.",
         phone="555 0177", email="ava@example.net")
    html = _people(client, tid)
    rows = html.split('id="people"')[1].split("<details")[0]
    assert rows.count('class="to-date to-date--person"') == 1 and "<table" not in rows
    assert "Ava Kane" in rows and "Tour manager · Rivet &amp; Co." in rows
    assert '<span class="to-chip">Tour Management</span>' in rows
    assert 'href="tel:555 0177"' in rows and 'href="mailto:ava@example.net"' in rows
    assert '<span class="to-fig"><span>shows</span><b>all</b></span>' in rows
    assert 'href="?edit=' in rows


def test_the_person_form_waits_behind_a_plus_once_anybody_is_listed(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    html = _people(client, tid)
    assert '<details class="to-add" id="add-person" open>' in html, "an empty directory opens the form"
    assert "Nobody in the directory yet" in html
    _add(client, tid, name="Ava Kane")
    html = _people(client, tid)
    assert '<details class="to-add" id="add-person">' in html and "Add a person</summary>" in html
    assert 'name="name"' in html, "folded, not gone"
    # Editing opens its own form and hides the add fold.
    import tour_store as ts
    pid = ts.list_people(tid)[0]["id"]
    edit = _people(client, tid, edit=pid)
    assert "Edit person" in edit and 'value="%s"' % pid in edit and 'id="add-person"' not in edit


def test_the_sheet_and_the_worker_moved_on():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-date--person" in css and ".to-chip-btn.is-on" in css
    shell = open(os.path.join(here, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 13
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 195
