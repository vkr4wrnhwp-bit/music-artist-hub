"""The X32 adapter's place in the system: reachable only as a bench adapter,
labelled UNTESTED wherever it is named, and addressed only by a patch map
the owner typed.
"""
import json
import uuid

import pytest

import advance_store as adv
import app as appmod
import db as store
import passport_store as ps
import stage_adapters as sa
import stage_bridge as sb
import stage_store as st

USER = "x32-wiring"
PASSWORD = "x32-rooms-123"


@pytest.fixture(scope="module", autouse=True)
def schema():
    store.init_db()
    ps.init_passports()
    adv.init_advance()
    st.init_stage()
    sb.init_bridge()


# --- the registry ---------------------------------------------------------------

def test_the_x32_is_not_in_the_default_registry(monkeypatch):
    monkeypatch.delenv("STAGE_BENCH_ADAPTERS", raising=False)
    assert list(sa.ADAPTERS) == ["simulator"]
    assert sa.adapter_class("x32") is None and sa.spec("x32") is None
    assert list(sa.available()) == ["simulator"]


def test_the_bench_flag_makes_it_reachable_but_not_verified(monkeypatch):
    monkeypatch.setenv("STAGE_BENCH_ADAPTERS", "1")
    assert "x32" in sa.available()
    spec = sa.spec("x32")
    assert spec["verified"] is False and spec["simulated"] is False
    assert list(sa.ADAPTERS) == ["simulator"], "the default registry did not change"


def test_the_simulator_is_verified_against_itself():
    assert sa.spec("simulator")["verified"] is True


def test_an_x32_instance_takes_the_devices_config(monkeypatch):
    monkeypatch.setenv("STAGE_BENCH_ADAPTERS", "1")
    inst = sa.instance_for("dev-x32-cfg", "x32",
                           {"host": "192.0.2.9", "patch": {"mixes": {"Mix 1": 7}, "sources": {"Kick": 2}}})
    assert inst.spec()["key"] == "x32"
    assert inst._level_addr("Mix 1", "Kick") == "/ch/02/mix/07/level"
    assert inst.transport.host == "192.0.2.9"
    sa.forget("dev-x32-cfg")


# --- the device -------------------------------------------------------------------

def _device(monkeypatch):
    monkeypatch.setenv("STAGE_BENCH_ADAPTERS", "1")
    show = "x32-" + uuid.uuid4().hex[:8]
    dev, _t = sb.register(USER, show, "FOH laptop", adapter_key="x32")
    return show, dev


def test_registration_refuses_the_x32_without_the_bench_flag(monkeypatch):
    monkeypatch.delenv("STAGE_BENCH_ADAPTERS", raising=False)
    with pytest.raises(ValueError):
        sb.register(USER, "x32-" + uuid.uuid4().hex[:8], "FOH", adapter_key="x32")


def test_the_patch_map_is_validated_and_never_guessed(monkeypatch):
    show, dev = _device(monkeypatch)
    cfg, refused = sb.set_config(dev["id"], USER, host="192.0.2.9",
                                 mixes={"Mix 1": "7", "Mix 2": "17", "": "3"},
                                 sources={"Lead Vox": "1", "Kick": "x", "Bass DI": "40"})
    assert cfg["patch"] == {"mixes": {"Mix 1": 7}, "sources": {"Lead Vox": 1}}
    assert set(refused) == {"Mix 2", "", "Kick", "Bass DI"}
    assert sb.config(sb.get_device(dev["id"]))["host"] == "192.0.2.9"


def test_run_local_refuses_to_drive_the_x32(monkeypatch):
    show, dev = _device(monkeypatch)
    assert "real bridge" in sb.run_local(dev["id"], USER)["error"]


def test_the_mode_says_the_adapter_is_unverified(monkeypatch):
    show, dev = _device(monkeypatch)
    sb.arm(dev["id"], USER)
    sb.heartbeat(sb.get_device(dev["id"]), {"ok": True, "verified": False})
    m = sb.mode(show, USER)
    assert m["mode"] == "connected" and m["verified"] is False and m["simulated"] is False


# --- the rooms -----------------------------------------------------------------------

@pytest.fixture
def room(monkeypatch):
    monkeypatch.setenv("STAGE_BENCH_ADAPTERS", "1")
    application = appmod.app
    email = "x32-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Bench Owner", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    with application.app_context():
        user = store.get_user_by_email(email)
        pid = ps.create_passport(user["id"], artist_name="Prayers")
        ps.add_row("inputs", pid, channel="1", source="Lead Vox", sort=1)
        ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar", safe_start="-20 dB", sort=1)
        ps.publish(pid, user["id"])
        sid = "show-" + uuid.uuid4().hex[:10]
        adv.attach(sid, user["id"], pid)
    return {"client": client, "user": user, "show": sid}


def test_the_bridge_page_names_the_x32_as_untested_and_takes_a_patch_map(room):
    c = room["client"]
    page = c.get("/stage/%s/bridge" % room["show"]).get_data(as_text=True)
    assert "UNTESTED" in page and 'value="x32"' in page
    c.post("/stage/%s/bridge/register" % room["show"], data={"name": "FOH laptop", "adapter": "x32"})
    page = c.get("/stage/%s/bridge" % room["show"]).get_data(as_text=True)
    assert "UNTESTED — bench only" in page and "Patch map" in page
    assert 'name="mix_Mix 1"' in page and 'name="src_Lead Vox"' in page
    r = c.post("/stage/%s/bridge/patch" % room["show"],
               data={"host": "192.0.2.9", "mix_Mix 1": "7", "src_Lead Vox": "1"})
    assert "refused" not in r.headers["Location"]
    page = c.get("/stage/%s/bridge" % room["show"]).get_data(as_text=True)
    assert 'value="192.0.2.9"' in page and 'name="mix_Mix 1" value="7"' in page
    r = c.post("/stage/%s/bridge/patch" % room["show"], data={"mix_Mix 1": "40"})
    assert "Not+patched" in r.headers["Location"]


def test_the_desk_banner_says_untested_adapter_when_connected(room):
    c = room["client"]
    c.post("/stage/%s/bridge/register" % room["show"], data={"name": "FOH laptop", "adapter": "x32"})
    c.post("/stage/%s/bridge/arm" % room["show"])
    with c.application.app_context():
        dev = sb.device_for_show(room["show"], room["user"]["id"])
        sb.heartbeat(dev, {"ok": True})
    desk = c.get("/stage/%s" % room["show"]).get_data(as_text=True)
    assert 'data-mode="connected"' in desk and "UNTESTED ADAPTER" in desk
    # The simulator's pulse button is not offered for a real desk.
    r = c.post("/stage/%s/bridge/heartbeat" % room["show"])
    assert r.status_code == 404
