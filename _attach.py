# -*- coding: utf-8 -*-
"""A roster nothing could put anybody on.

attach_user and detach_user had no caller anywhere, and nothing else in
the app writes users.partner_id. So a reseller got a console whose roster
reads `WHERE partner_id = ?` and is therefore empty for ever - the
white-label product still could not be sold after the back office was
built, because there was no way to seat a single artist.

Attaching is done from the OWNER's back office rather than the reseller's
console, deliberately. Attaching by email means learning whether an
account exists at that address, and handing that to every reseller is an
account-enumeration oracle over the whole platform. The owner already
knows who is on the platform.
"""
import io

P = "app.py"
s = io.open(P, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"


def swap(old, new, label):
    global s
    o, n = old.replace("\n", nl), new.replace("\n", nl)
    assert s.count(o) == 1, "%s: found %d" % (label, s.count(o))
    s = s.replace(o, n)


swap('''            rows.append(dict(
                p,
                seats_used=partner_store.seats_used(p["id"]),
                seat_limit=partner_store.seat_limit(p["id"]),
                members=partner_store.list_members(p["id"]),
            ))''',
     '''            rows.append(dict(
                p,
                seats_used=partner_store.seats_used(p["id"]),
                seat_limit=partner_store.seat_limit(p["id"]),
                members=partner_store.list_members(p["id"]),
                roster=partner_store.roster_detail(p["id"]),
            ))''', "roster in the view")

swap('''    @app.route("/partners/<pid>/status", methods=["POST"])''',
     '''    @app.route("/partners/<pid>/artists", methods=["POST"])
    def partners_attach(pid):
        """Put an existing account on a reseller's roster.

        Owner-only on purpose. Attaching by email means learning whether
        an account exists at that address, and giving every reseller that
        would be an enumeration oracle over the whole platform.
        """
        _user, bounce = _owner_or_404()
        if bounce:
            return bounce
        if partner_store.get_partner(pid) is None:
            abort(404)
        email = (request.form.get("email") or "").strip().lower()
        if not email:
            return _partners_view("Which account? An email address, please.")
        artist = store.get_user_by_email(email)
        if artist is None:
            return _partners_view(
                "No account here uses %s. They have to sign up before they "
                "can be put on a roster - an account is not invented for "
                "them." % email)
        current = artist.get("partner_id")
        if current and current != pid:
            other = partner_store.get_partner(current)
            return _partners_view(
                "That account already belongs to %s. Moving it is a transfer, "
                "and a transfer is a deliberate two-step: take it off that "
                "roster first."
                % ((other or {}).get("name") or "another reseller"))
        if not partner_store.attach_user(pid, artist["id"]):
            return _partners_view(
                "That roster is at its seat cap. Raise the cap or take "
                "somebody off before adding another.")
        return redirect("/partners")

    @app.route("/partners/<pid>/artists/<uid>/remove", methods=["POST"])
    def partners_detach(pid, uid):
        """Take an account off a roster. The account and its work survive:
        it goes back to being an ordinary Street Banker account."""
        _user, bounce = _owner_or_404()
        if bounce:
            return bounce
        if partner_store.get_partner(pid) is None:
            abort(404)
        partner_store.detach_user(pid, uid)
        return redirect("/partners")

    @app.route("/partners/<pid>/status", methods=["POST"])''',
     "attach and detach routes")

io.open(P, "w", encoding="utf-8", newline="").write(s)
print("attach/detach routed")
