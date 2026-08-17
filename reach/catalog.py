"""Canonical music identity over the host catalog.

REACH does not create a second release catalog. ``royalty_data`` stays the
source of truth for the artist's songs; this module mirrors each song into a
``recording`` row so campaigns, evidence and placements have a stable foreign
key, and adds the identity fields the host catalog does not model (version
type, mix/edit name, MusicBrainz ids, platform assets).

Different remixes, edits, remasters, clean versions and instrumentals are
distinct recordings. An ISRC identifies a recording; it never proves ownership,
which is why :func:`attest_rights` exists separately.
"""

import json

import royalty_data

from . import audit, clock, db, rbac
from .errors import ValidationError

ORIGINAL = "ORIGINAL"
VERSION_TYPES = [
    ORIGINAL, "RADIO_EDIT", "EXTENDED_MIX", "REMIX", "REMASTER",
    "INSTRUMENTAL", "CLEAN", "ACOUSTIC", "LIVE", "VIDEO",
]

RIGHTS_SCOPE = [
    "master_recording", "artwork", "photographs", "biography",
    "video", "epk_assets", "names_and_likenesses", "submission_materials",
]


def _artist_id(tenant_id, name):
    row = db.query_one(
        "SELECT id FROM artist WHERE tenant_id = ? AND name = ?", (tenant_id, name)
    )
    if row:
        return row["id"]
    artist_id = db.new_id("art")
    db.insert("artist", {
        "id": artist_id,
        "tenant_id": tenant_id,
        "name": name,
        "created_at": clock.now_iso(),
    })
    return artist_id


def sync_from_host(tenant_id=None):
    """Mirror every host song into a recording row. Idempotent."""
    tenant_id = tenant_id or rbac.current_principal().tenant_id
    rbac.ensure_default_tenant()
    created = []
    for song in royalty_data.get_songs():
        artist_id = _artist_id(tenant_id, song.master_owner or "Unknown Artist")
        row = db.query_one(
            "SELECT id FROM recording WHERE tenant_id = ? AND host_song_id = ? "
            "AND version_type = ? AND mix_name IS NULL AND edit_name IS NULL",
            (tenant_id, song.id, ORIGINAL),
        )
        if row:
            db.update("recording", row["id"], {
                "title": song.title,
                "isrc": song.isrc,
                "iswc": song.iswc,
                "upc": song.upc,
            })
            continue
        recording_id = db.new_id("rec")
        db.insert("recording", {
            "id": recording_id,
            "tenant_id": tenant_id,
            "artist_id": artist_id,
            "release_id": None,
            "host_song_id": song.id,
            "title": song.title,
            "isrc": song.isrc,
            "iswc": song.iswc,
            "upc": song.upc,
            "musicbrainz_recording_id": None,
            "version_type": ORIGINAL,
            "mix_name": None,
            "edit_name": None,
            "explicit": None,
            "duration_seconds": None,
            "master_version": 1,
            "release_territory": None,
            "release_date": None,
            "created_at": clock.now_iso(),
        })
        created.append(recording_id)
    return created


def recordings(tenant_id=None):
    tenant_id = tenant_id or rbac.current_principal().tenant_id
    sync_from_host(tenant_id)
    return db.query(
        "SELECT r.*, a.name AS artist_name FROM recording r "
        "JOIN artist a ON a.id = r.artist_id WHERE r.tenant_id = ? ORDER BY r.title",
        (tenant_id,),
    )


def get_recording(recording_id):
    return db.query_one(
        "SELECT r.*, a.name AS artist_name FROM recording r "
        "JOIN artist a ON a.id = r.artist_id WHERE r.id = ?",
        (recording_id,),
    )


def recording_for_host_song(host_song_id, tenant_id=None):
    tenant_id = tenant_id or rbac.current_principal().tenant_id
    sync_from_host(tenant_id)
    return db.query_one(
        "SELECT r.*, a.name AS artist_name FROM recording r "
        "JOIN artist a ON a.id = r.artist_id "
        "WHERE r.tenant_id = ? AND r.host_song_id = ? AND r.version_type = ?",
        (tenant_id, host_song_id, ORIGINAL),
    )


def host_song(recording_row):
    if recording_row is None or not recording_row["host_song_id"]:
        return None
    song = royalty_data.get_song(recording_row["host_song_id"])
    return royalty_data.live_song(song) if song else None


def add_version(source_recording_id, version_type, mix_name=None, edit_name=None,
                isrc=None, explicit=None):
    """Register a distinct recording entity for a remix/edit/version."""
    if version_type not in VERSION_TYPES:
        raise ValidationError(f"Unknown version type: {version_type}")
    source = get_recording(source_recording_id)
    if source is None:
        raise ValidationError("Unknown source recording")
    recording_id = db.new_id("rec")
    db.insert("recording", {
        "id": recording_id,
        "tenant_id": source["tenant_id"],
        "artist_id": source["artist_id"],
        "release_id": source["release_id"],
        "host_song_id": source["host_song_id"],
        "title": source["title"],
        "isrc": isrc,
        "iswc": source["iswc"],
        "upc": source["upc"],
        "musicbrainz_recording_id": None,
        "version_type": version_type,
        "mix_name": mix_name,
        "edit_name": edit_name,
        "explicit": explicit,
        "duration_seconds": None,
        "master_version": 0,
        "release_territory": source["release_territory"],
        "release_date": source["release_date"],
        "created_at": clock.now_iso(),
    })
    audit.record("catalog.version_added", entity_type="recording", entity_id=recording_id,
                 payload={"version_type": version_type, "source": source_recording_id})
    return recording_id


def add_platform_asset(recording_id, provider, external_id=None, url=None):
    asset_id = db.new_id("asset")
    db.insert("platform_asset", {
        "id": asset_id,
        "recording_id": recording_id,
        "provider": provider,
        "external_id": external_id,
        "url": url,
        "created_at": clock.now_iso(),
    })
    return asset_id


def platform_assets(recording_id):
    return db.query(
        "SELECT * FROM platform_asset WHERE recording_id = ? ORDER BY provider",
        (recording_id,),
    )


def identifiers(recording_id):
    """Everything REACH knows that identifies this recording. UNKNOWN stays
    UNKNOWN — no value is inferred to fill a gap."""
    row = get_recording(recording_id)
    if row is None:
        return {}
    assets = platform_assets(recording_id)
    return {
        "internal_recording_id": row["id"],
        "internal_track_id": row["host_song_id"],
        "isrc": row["isrc"],
        "iswc": row["iswc"],
        "upc": row["upc"],
        "musicbrainz_recording_id": row["musicbrainz_recording_id"],
        "musicbrainz_release_id": None,
        "version_type": row["version_type"],
        "mix_name": row["mix_name"],
        "edit_name": row["edit_name"],
        "explicit": row["explicit"],
        "master_version": bool(row["master_version"]),
        "release_territory": row["release_territory"],
        "release_date": row["release_date"],
        "platform_assets": [dict(a) for a in assets],
    }


# --------------------------------------------------------------------------
# rights attestation
# --------------------------------------------------------------------------

ATTESTATION_STATEMENT = (
    "I confirm that the campaign owner holds or controls the rights necessary to use the "
    "master recording, artwork, photographs, biography, video, EPK assets, names and "
    "likenesses, and submission materials for this recording in promotional outreach."
)


def attest_rights(recording_id, scope=None, attested_by=None):
    """Record a rights attestation. A campaign cannot launch without one."""
    principal = rbac.require("campaign.create")
    scope = scope or list(RIGHTS_SCOPE)
    unknown = [item for item in scope if item not in RIGHTS_SCOPE]
    if unknown:
        raise ValidationError(f"Unknown rights scope: {', '.join(unknown)}")
    attestation_id = db.new_id("rights")
    db.insert("rights_attestation", {
        "id": attestation_id,
        "tenant_id": principal.tenant_id,
        "recording_id": recording_id,
        "attested_by": attested_by or principal.email,
        "scope_json": json.dumps(sorted(scope)),
        "statement": ATTESTATION_STATEMENT,
        "attested_at": clock.now_iso(),
        "revoked_at": None,
    })
    audit.record("rights.attested", entity_type="recording", entity_id=recording_id,
                 payload={"scope": sorted(scope)}, actor_kind=audit.ACTOR_USER,
                 actor_id=principal.id)
    return attestation_id


def active_attestation(recording_id):
    return db.query_one(
        "SELECT * FROM rights_attestation WHERE recording_id = ? AND revoked_at IS NULL "
        "ORDER BY attested_at DESC LIMIT 1",
        (recording_id,),
    )


def has_rights_attestation(recording_id):
    return active_attestation(recording_id) is not None


# --------------------------------------------------------------------------
# release readiness
# --------------------------------------------------------------------------

def release_readiness(recording_id):
    """Checks that gate what a campaign can actually do. Each item states the
    consequence, because a missing ISRC blocks different routes than missing
    artwork does."""
    row = get_recording(recording_id)
    song = host_song(row)
    checks = []

    def add(key, label, ok, consequence):
        checks.append({"key": key, "label": label, "ok": bool(ok), "consequence": consequence})

    add("isrc", "ISRC on file", bool(row["isrc"]),
        "Placement monitoring and several submission forms require an ISRC.")
    add("upc", "UPC on file", bool(row["upc"]),
        "Release-level pitches (Amazon, Pandora) require a UPC.")
    add("distribution", "Delivered through a distributor",
        bool(song and song.registrations.get("distribution")),
        "DSP editorial pitches require the release to be delivered.")
    add("rights", "Rights attestation recorded", has_rights_attestation(recording_id),
        "No campaign may launch without one.")
    add("writers", "Writers on file", bool(song and song.writers),
        "Credits are required by most editorial and radio submission forms.")
    add("publisher", "Publisher on file", bool(song and song.publisher),
        "Some publications ask for publishing information.")
    add("splits", "Splits confirmed",
        bool(song and royalty_data.splits_fully_confirmed(song)),
        "Unconfirmed splits put placement revenue at risk.")

    passed = sum(1 for c in checks if c["ok"])
    return {
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "score": round(passed / len(checks) * 100) if checks else 0,
        "blocking": [c for c in checks if not c["ok"] and c["key"] == "rights"],
    }
