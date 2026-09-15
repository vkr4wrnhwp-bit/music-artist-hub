"""The contract reader: the second half of the renewal reminders.

Owner, 2026-09-14: "it automatically reads the contracts uploaded to
create alarms for you". The first half typed the dates; this half pulls
them out of the file's text and shows them beside the sentence they came
from, for a person to check. Nothing it finds is saved on its own, a
date it did not find is "not found", and a scanned PDF says so.
"""
import io
import uuid
import zipfile

import pytest

import contract_reader as cr
import db as store
from app import create_app

PW = "reader-12345"

AGREEMENT = """DISTRIBUTION AGREEMENT
This Agreement is entered into as of January 15, 2026 (the "Effective Date") between the Label and the Artist.
2. Term. The initial term of this Agreement shall be two (2) years from the Effective Date.
3. Renewal. This Agreement shall automatically renew for successive one (1) year periods unless either party gives written notice of non-renewal at least sixty (60) days prior to the end of the then-current term.
"""


def _pdf(text):
    """A one-page PDF with a real text layer, built by hand."""
    body = b"BT /F1 12 Tf 72 720 Td (" + text.encode("latin-1") + b") Tj ET"
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
            b" /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(body) + body + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return out


def _docx(*paragraphs):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml",
                   "<w:document><w:body>" + "".join(
                       "<w:p><w:r><w:t>%s</w:t></w:r></w:p>" % p for p in paragraphs)
                   + "</w:body></w:document>")
    return buf.getvalue()


def test_the_terms_come_out_with_their_sentences():
    f = cr.find_terms(AGREEMENT)
    assert f["effective_on"]["value"] == "2026-01-15" and f["effective_on"]["how"] == "found"
    assert f["term_months"]["value"] == 24
    assert f["notice_days"]["value"] == 60 and "sixty (60) days" in f["notice_days"]["snippet"]
    assert f["auto_renews"]["value"] is True and "automatically renew" in f["auto_renews"]["snippet"]
    # no end date is stated, so the one offered is derived and says so
    assert f["renews_on"] == {"value": "2028-01-15", "how": "derived",
                              "snippet": f["effective_on"]["snippet"]}
    assert cr.summary(f, "ok") == ("Found an end date worked out from the start date and the term, "
                                   "a 60-day notice period and an automatic renewal clause. "
                                   "Check each against the document before saving.")


def test_a_stated_end_date_beats_a_derived_one_and_a_no_renew_clause_is_read():
    f = cr.find_terms("This Licence commences on 1 March 2026 and shall expire on 31 December 2027. "
                      "This Licence shall not automatically renew. "
                      "Either party may terminate on thirty days' notice.")
    assert f["renews_on"] == {"value": "2027-12-31", "how": "found",
                              "snippet": "This Licence commences on 1 March 2026 and shall expire on 31 December 2027."}
    assert f["auto_renews"]["value"] is False
    assert f["notice_days"]["value"] == 30
    assert "does not renew on its own" in cr.summary(f, "ok")


def test_nothing_found_is_said_not_guessed():
    f = cr.find_terms("Lorem ipsum dolor sit amet, consectetur adipiscing elit.")
    for key in ("renews_on", "effective_on", "term_months", "notice_days", "auto_renews"):
        assert f[key]["how"] == "not_found", key
    assert f["dates"] == []
    assert cr.summary(f, "ok").startswith("Read the text and found no term")
    # a date that is not a date is skipped, not crashed on
    assert cr.find_terms("Expires on 31/02/2027 or 2027-02-30.")["dates"] == []


def test_text_comes_out_of_pdf_docx_and_txt_and_a_scan_says_so():
    text, status = cr.extract_text(_pdf("This Agreement shall expire on 31 December 2027."), "pdf")
    assert status == "ok" and "expire on 31 December 2027" in text
    text, status = cr.extract_text(_docx("Term of twelve (12) months.", "Effective 2026-02-01."), "docx")
    assert status == "ok" and "Term of twelve (12) months.\nEffective 2026-02-01." in text
    assert cr.find_terms(text)["renews_on"] == {"value": "2027-02-01", "how": "derived",
                                                "snippet": "Effective 2026-02-01."}
    assert cr.extract_text(b"Renews on 2027-01-01 unless notice is given.", "txt")[1] == "ok"
    assert cr.extract_text(b"%PDF-1.4 fake", "pdf") == ("", "broken")
    assert cr.extract_text(_pdf(""), "pdf")[1] == "empty"
    assert cr.extract_text(b"anything", "doc") == ("", "unsupported")
    assert cr.extract_text(b"not a zip", "docx") == ("", "broken")
    assert "no readable text" in cr.summary({}, "empty")
    assert "cannot read PDFs yet" in cr.summary({}, "no_reader")


def test_a_pdf_without_the_reader_says_so(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def no_pypdf(name, *a, **k):
        if name == "pypdf":
            raise ImportError("no pypdf here")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_pypdf)
    assert cr.extract_text(_pdf("x"), "pdf") == ("", "no_reader")


@pytest.fixture
def world():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "reader-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "Reader", "email": email, "password": PW})
    client.post("/plan/switch", data={"plan": "pro"})
    return app_obj, client, email


def _upload(app_obj, client, email, data, filename):
    client.post("/vault/documents",
                data={"document": (io.BytesIO(data), filename), "doc_type": "Distribution"},
                content_type="multipart/form-data")
    with app_obj.app_context():
        uid = store.get_user_by_email(email)["id"]
        return uid, store.list_documents(uid)[0]


def test_the_row_reads_the_file_fills_the_form_and_saves_nothing_by_itself(world):
    app_obj, client, email = world
    uid, doc = _upload(app_obj, client, email, AGREEMENT.encode(), "distribution.txt")
    body = client.get("/vault?view=contracts").get_data(as_text=True)
    assert 'action="/vault/documents/%s/read"' % doc["id"] in body and "Read the document" in body
    assert "Found in the document" not in body
    r = client.post("/vault/documents/%s/read" % doc["id"])
    assert r.status_code == 302 and r.headers["Location"].endswith("read=ok#doc-%s" % doc["id"])
    body = client.get("/vault?view=contracts&read=ok").get_data(as_text=True)
    assert "Read the file. Check what it found" in body
    assert "Found in the document, check it" in body
    assert "sixty (60) days prior" in body and "60 days" in body
    assert "2028-01-15" in body and "the start date plus the term" in body
    assert "Read it again" in body
    # the form is filled from the reading, and the row still says whose dates they are
    assert 'name="renews_on" value="2028-01-15"' in body
    assert 'name="notice_days" min="0" max="365" value="60"' in body
    assert 'value="1" selected>Auto-renews' in body
    assert "not a legal opinion" in body
    # nothing reached the terms table: the reminders still have nothing to run on
    with app_obj.app_context():
        assert store.get_document_terms(uid) == {}
    # saving is the person's act, and afterwards the saved dates win over the reading
    client.post("/vault/documents/%s/terms" % doc["id"],
                data={"renews_on": "2028-02-01", "notice_days": "60", "auto_renews": "1"})
    body = client.get("/vault?view=contracts").get_data(as_text=True)
    assert 'name="renews_on" value="2028-02-01"' in body and "Renews 1 Feb 2028 automatically" in body
    assert "These dates are what you save." in body


def test_a_scanned_pdf_and_a_missing_file_say_so_and_a_stranger_gets_nothing(world):
    app_obj, client, email = world
    uid, doc = _upload(app_obj, client, email, _pdf(""), "scan.pdf")
    r = client.post("/vault/documents/%s/read" % doc["id"])
    assert r.headers["Location"].endswith("read=empty#doc-%s" % doc["id"])
    body = client.get("/vault?view=contracts&read=empty").get_data(as_text=True)
    assert "The file could not be read. The row says why." in body
    assert "no readable text" in body and "nobody has read the document" in body
    assert 'name="renews_on" value=""' in body
    # a document whose file is gone from the disk reads as unavailable, not as empty
    with app_obj.app_context():
        with store.get_db() as db:
            db.execute("UPDATE documents SET path = '/uploads/doc_gone.pdf' WHERE id = ?", (doc["id"],))
    r = client.post("/vault/documents/%s/read" % doc["id"])
    assert r.headers["Location"].endswith("read=unavailable#doc-%s" % doc["id"])
    assert "could not be fetched from storage" in client.get("/vault?view=contracts").get_data(as_text=True)
    assert client.post("/vault/documents/nope/read").status_code == 404
    other = app_obj.test_client()
    other.post("/signup", data={"name": "Other", "email": "o-%s@example.net" % uuid.uuid4().hex[:6],
                                "password": PW})
    assert other.post("/vault/documents/%s/read" % doc["id"]).status_code == 404
    # deleting the document takes its reading with it
    client.post("/vault/documents/%s/delete" % doc["id"])
    with app_obj.app_context():
        assert store.get_document_readings(uid) == {}


def test_a_reading_is_wiped_with_the_account(world):
    app_obj, client, email = world
    uid, doc = _upload(app_obj, client, email, b"Term of one (1) year from 2026-01-01.", "deal.txt")
    client.post("/vault/documents/%s/read" % doc["id"])
    with app_obj.app_context():
        assert doc["id"] in store.get_document_readings(uid)
        removed = store.reset_user_data(uid)
        assert removed.get("document_readings") == 1
        assert store.get_document_readings(uid) == {}
