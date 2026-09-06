"""Street Banker Signal - provider adapter layer.

The product must never be a wrapper around one data vendor. Every external
source sits behind `MusicIntelligenceProvider`, and the rest of Signal only
ever talks to the interface. Swapping Soundcharts for Chartmetric, or using
one provider for city movement and another for playlists, is a registry
change - not a rewrite.

Phase 1 ships:
  * the interface,
  * a deterministic mock adapter so the whole product works with no
    credentials at all,
  * typed stubs for the real providers that declare their capabilities and
    report `configured=False` until their env vars exist.

Nothing here invents provider fields. A stub that has not been implemented
raises NotImplementedError rather than returning a plausible-looking guess,
because a fabricated distributor or manager is worse than a blank one.

Feature flags (all default off; see .env.example):
    SOUNDCHARTS_ENABLED, CHARTMETRIC_ENABLED, MUSICBRAINZ_ENABLED,
    MLC_ENABLED, SOUNDEXCHANGE_ENABLED, SPOTIFY_METADATA_ENABLED,
    WEB_ENRICHMENT_ENABLED, INTERNAL_REVENUE_ENABLED,
    PRIVATE_AUDIO_ENABLED, AUDIO_INTELLIGENCE_ENABLED
"""
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
import random
from datetime import date, datetime, timedelta, timezone

# --- capabilities -----------------------------------------------------------
# What a provider can answer. The registry picks a provider per capability,
# so no single vendor has to cover the whole product.

CAP_ARTIST = "artist"
CAP_METRICS = "metrics"
CAP_RELEASES = "releases"
CAP_CITIES = "cities"
CAP_PLAYLISTS = "playlists"
CAP_SOCIAL = "social"
CAP_EVENTS = "events"
CAP_DISTRIBUTOR = "distributor"
CAP_LABEL = "label"
CAP_CONTACTS = "contacts"
CAP_RIGHTS = "rights"

ALL_CAPABILITIES = (CAP_ARTIST, CAP_METRICS, CAP_RELEASES, CAP_CITIES,
                    CAP_PLAYLISTS, CAP_SOCIAL, CAP_EVENTS, CAP_DISTRIBUTOR,
                    CAP_LABEL, CAP_CONTACTS, CAP_RIGHTS)

CAPABILITY_LABELS = {
    CAP_ARTIST: "Artist identity",
    CAP_METRICS: "Streaming & audience metrics",
    CAP_RELEASES: "Releases & tracks",
    CAP_CITIES: "City / territory movement",
    CAP_PLAYLISTS: "Playlist activity",
    CAP_SOCIAL: "Social activity",
    CAP_EVENTS: "Live events",
    CAP_DISTRIBUTOR: "Distributor evidence",
    CAP_LABEL: "Label evidence",
    CAP_CONTACTS: "Professional contacts",
    CAP_RIGHTS: "Rights & registration evidence",
}


def _flag(name):
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


class ProviderError(RuntimeError):
    """A provider failed. Callers degrade; they never crash a page."""


class MusicIntelligenceProvider(object):
    """The one interface Signal talks to.

    Subclasses declare `key`, `label` and `capabilities`, and implement only
    the methods their capabilities claim. Anything not claimed must raise
    NotImplementedError - never a fabricated value.
    """

    key = "base"
    label = "Base provider"
    capabilities = ()
    # Cost per request in USD, used by the usage dashboard. 0 for free/mock.
    cost_per_request = 0.0

    def configured(self):
        """True when this provider has what it needs to make real calls."""
        return False

    def health_check(self):
        return {"provider": self.key, "configured": self.configured(),
                "ok": self.configured(), "detail": "not configured",
                "capabilities": list(self.capabilities)}

    def supports(self, capability):
        return capability in self.capabilities

    # Every method below is optional per capability.
    def search_artists(self, query, limit=20):
        raise NotImplementedError

    def get_artist(self, provider_artist_id):
        raise NotImplementedError

    def get_artist_metrics(self, provider_artist_id, start, end):
        raise NotImplementedError

    def get_artist_releases(self, provider_artist_id):
        raise NotImplementedError

    def get_artist_cities(self, provider_artist_id, start, end):
        raise NotImplementedError

    def get_playlist_activity(self, provider_artist_id, start, end):
        raise NotImplementedError

    def get_social_activity(self, provider_artist_id, start, end):
        raise NotImplementedError

    def get_events(self, provider_artist_id):
        raise NotImplementedError

    def get_distributor_evidence(self, provider_release_id):
        raise NotImplementedError

    def get_label_evidence(self, provider_release_id):
        raise NotImplementedError

    def get_contact_evidence(self, provider_artist_id):
        raise NotImplementedError

    def get_rights_evidence(self, isrc=None, title=None, artist=None):
        raise NotImplementedError


# --- real providers: declared, not faked ------------------------------------
# Each declares what it could answer and stays unconfigured until its
# credentials exist. Signal shows them in /signal/admin/data-sources as
# "not configured" rather than pretending they are live.

class _EnvProvider(MusicIntelligenceProvider):
    env_flag = ""
    env_keys = ()

    def configured(self):
        if not _flag(self.env_flag):
            return False
        return all((os.environ.get(k) or "").strip() for k in self.env_keys)

    def health_check(self):
        if not _flag(self.env_flag):
            detail = "disabled (%s is not set)" % self.env_flag
        elif not self.configured():
            missing = [k for k in self.env_keys if not (os.environ.get(k) or "").strip()]
            detail = "enabled but missing credentials: %s" % ", ".join(missing)
        else:
            detail = "configured"
        return {"provider": self.key, "configured": self.configured(),
                "ok": self.configured(), "detail": detail,
                "capabilities": list(self.capabilities)}


class SoundchartsAdapter(_EnvProvider):
    key = "soundcharts"
    label = "Soundcharts"
    env_flag = "SOUNDCHARTS_ENABLED"
    env_keys = ("SOUNDCHARTS_APP_ID", "SOUNDCHARTS_API_KEY")
    capabilities = (CAP_ARTIST, CAP_METRICS, CAP_RELEASES, CAP_CITIES,
                    CAP_PLAYLISTS, CAP_SOCIAL, CAP_EVENTS)


class ChartmetricAdapter(_EnvProvider):
    key = "chartmetric"
    label = "Chartmetric"
    env_flag = "CHARTMETRIC_ENABLED"
    env_keys = ("CHARTMETRIC_REFRESH_TOKEN",)
    capabilities = (CAP_ARTIST, CAP_METRICS, CAP_RELEASES, CAP_CITIES,
                    CAP_PLAYLISTS, CAP_SOCIAL)


class MusicBrainzAdapter(_EnvProvider):
    """The open MusicBrainz database, over its JSON web service.

    Free, no account: their policy asks for a User-Agent that names a
    contact, which is the one thing the environment has to carry, and one
    request per second, which the adapter keeps to itself. What it answers
    is identity and catalogue - who an artist is, where they are from, what
    they have released and on which label. What it does NOT answer is
    listeners, followers, cities or playlists: MusicBrainz measures nothing,
    so those stay "not measured" rather than borrowing the demo's numbers
    (see ProviderRegistry.for_capability).

    Every method returns the same shapes the mock does, so the rest of
    Signal cannot tell which one answered - except that these are true.
    """
    key = "musicbrainz"
    label = "MusicBrainz"
    env_flag = "MUSICBRAINZ_ENABLED"
    env_keys = ("MUSICBRAINZ_CONTACT",)      # their policy requires a UA contact
    capabilities = (CAP_ARTIST, CAP_RELEASES, CAP_LABEL)
    base_url = "https://musicbrainz.org/ws/2"
    min_interval = 1.05                       # seconds between requests, their limit
    release_groups_per_artist = 8             # one extra request each, so bounded

    def __init__(self, fetch=None, sleep=None):
        self._fetch = fetch
        self._sleep = sleep if sleep is not None else time.sleep
        self._last = 0.0

    # -- transport --
    def _get(self, path, **params):
        params.setdefault("fmt", "json")
        url = "%s/%s?%s" % (self.base_url, path.lstrip("/"), urllib.parse.urlencode(params))
        wait = self.min_interval - (time.time() - self._last)
        if wait > 0:
            self._sleep(wait)
        self._last = time.time()
        if self._fetch is not None:
            return self._fetch(url)
        contact = (os.environ.get("MUSICBRAINZ_CONTACT") or "").strip()
        req = urllib.request.Request(url, headers={
            "User-Agent": "StreetBanker/1.0 ( %s )" % contact, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise ProviderError("MusicBrainz: %s" % e)

    # -- shapes --
    @staticmethod
    def _artist_fields(a):
        tags = sorted(a.get("tags") or [], key=lambda t: -(t.get("count") or 0))
        area = a.get("area") or {}
        begin = a.get("begin-area") or {}
        socials = {"instagram": "", "tiktok": "", "youtube": ""}
        website = ""
        for rel in a.get("relations") or []:
            url = (rel.get("url") or {}).get("resource") or ""
            kind = rel.get("type") or ""
            if kind == "official homepage" and not website:
                website = url
            for name in socials:
                if name in url and not socials[name]:
                    socials[name] = url
        return {
            "provider_artist_id": a.get("id") or "",
            "name": a.get("name") or "",
            "genre": (tags[0].get("name") or "").title() if tags else "",
            "country": a.get("country") or "",
            "city": begin.get("name") or "",
            "state": "",
            "region": area.get("name") or "",
            # Not measured here. Left empty on purpose - never a guess.
            "career_stage": "",
            "monthly_listeners": None,
            "image_url": "",
            "website": website,
            "socials": socials,
            "disambiguation": a.get("disambiguation") or "",
        }

    def search_artists(self, query, limit=20):
        q = (query or "").strip()
        if not q:
            # A blank search is how the demo universe is seeded; there is no
            # honest way to pick "some artists" out of a million real ones.
            return []
        data = self._get("artist/", query=q, limit=max(1, min(int(limit or 20), 50)))
        return [self._artist_fields(a) for a in data.get("artists") or []]

    def get_artist(self, provider_artist_id):
        data = self._get("artist/%s" % provider_artist_id, inc="tags+url-rels")
        if not data or not data.get("id"):
            return None
        return self._artist_fields(data)

    def get_artist_releases(self, provider_artist_id):
        data = self._get("release-group/", artist=provider_artist_id,
                         limit=self.release_groups_per_artist)
        out = []
        for rg in data.get("release-groups") or []:
            item = {
                "provider_release_id": rg.get("id") or "",
                "title": rg.get("title") or "",
                "release_type": (rg.get("primary-type") or "Single"),
                "release_date": rg.get("first-release-date") or "",
                "upc": "", "label_text": "", "distributor_name": "",
                "distributor_class": "Unknown", "copyright_line": "", "track_count": 0,
                "provider": self.key,
            }
            # One release per group for its label and barcode; the group
            # alone carries neither.
            try:
                rel = self._get("release/", **{"release-group": rg.get("id") or "",
                                              "inc": "labels+media", "limit": 1})
            except ProviderError:
                rel = {}
            releases = rel.get("releases") or []
            if releases:
                r0 = releases[0]
                labels = [li.get("label") or {} for li in r0.get("label-info") or []]
                item["label_text"] = ", ".join(l.get("name") for l in labels if l.get("name"))
                item["upc"] = r0.get("barcode") or ""
                item["track_count"] = sum(int(m.get("track-count") or 0) for m in r0.get("media") or [])
            out.append(item)
        out.sort(key=lambda x: x["release_date"], reverse=True)
        return out

    def get_label_evidence(self, provider_release_id):
        data = self._get("release/", **{"release-group": provider_release_id,
                                        "inc": "labels", "limit": 1})
        releases = data.get("releases") or []
        if not releases:
            return []
        out = []
        for li in releases[0].get("label-info") or []:
            label = li.get("label") or {}
            if label.get("name"):
                out.append({"label_name": label["name"], "catalog_number": li.get("catalog-number") or "",
                            "source_type": "release_metadata", "source_label": "MusicBrainz release",
                            "source_url": "https://musicbrainz.org/release/%s" % (releases[0].get("id") or ""),
                            "confidence": 0.8})
        return out


class MLCAdapter(_EnvProvider):
    key = "mlc"
    label = "The MLC"
    env_flag = "MLC_ENABLED"
    env_keys = ("MLC_API_KEY",)
    capabilities = (CAP_RIGHTS,)


class SoundExchangeAdapter(_EnvProvider):
    key = "soundexchange"
    label = "SoundExchange"
    env_flag = "SOUNDEXCHANGE_ENABLED"
    env_keys = ("SOUNDEXCHANGE_API_KEY",)
    capabilities = (CAP_RIGHTS,)


class SpotifyMetadataAdapter(_EnvProvider):
    key = "spotify_metadata"
    label = "Spotify metadata"
    env_flag = "SPOTIFY_METADATA_ENABLED"
    env_keys = ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET")
    capabilities = (CAP_ARTIST, CAP_RELEASES)


class PublicWebResearchAdapter(_EnvProvider):
    key = "web_research"
    label = "Public web research"
    env_flag = "WEB_ENRICHMENT_ENABLED"
    env_keys = ()
    capabilities = (CAP_CONTACTS, CAP_LABEL, CAP_DISTRIBUTOR)

    def configured(self):
        return _flag(self.env_flag)


class InternalStreetBankerAdapter(_EnvProvider):
    key = "internal"
    label = "Street Banker internal"
    env_flag = "INTERNAL_REVENUE_ENABLED"
    env_keys = ()
    capabilities = (CAP_DISTRIBUTOR, CAP_RIGHTS)

    def configured(self):
        return _flag(self.env_flag)


# --- mock provider ----------------------------------------------------------

_GENRES = ["Alternative", "Indie Rock", "Hip-Hop", "R&B", "Pop", "Americana",
           "Synthwave", "Latin", "Punk", "Soul"]
_CITIES = [
    ("Atlanta", "GA", "US"), ("Charlotte", "NC", "US"), ("Nashville", "TN", "US"),
    ("Austin", "TX", "US"), ("Seattle", "WA", "US"), ("Portland", "OR", "US"),
    ("Chicago", "IL", "US"), ("Brooklyn", "NY", "US"), ("Los Angeles", "CA", "US"),
    ("Miami", "FL", "US"), ("Denver", "CO", "US"), ("Detroit", "MI", "US"),
]
# Fictional on purpose. Demo mode must never imply a real company's business.
_DISTRIBUTORS = [
    ("Ridgeline Digital", "DIY / Self-Service"),
    ("Foxglove Distribution", "Independent Distributor"),
    ("Northwind Selective", "Selective Indie Services"),
    ("Pelham Row Records", "Independent Label"),
    ("Meridian Supply Co.", "Enterprise Distribution"),
    ("Continental Sound Group", "Major-Affiliated Distribution"),
]
_MGMT = ["Hollow Pine Management", "Rivet & Co.", "Quarter Note Partners",
         "Aldridge Artist Group", "Tin Roof Management"]
_AGENCIES = ["Broadstone Booking", "Cardinal Live", "Fieldhouse Agency"]
_FIRST = ["Marisol", "Devon", "Ivy", "Caleb", "Nadia", "Theo", "Junia", "Rafa",
          "Sloane", "Emory", "Priya", "Kofi", "Lena", "Silas", "Marguerite"]
_LAST = ["Vance", "Okonkwo", "Reyes", "Whitfield", "Barlow", "Nakamura",
         "Delacroix", "Ferraro", "Mbeki", "Sandoval", "Kettering", "Rowe"]


def _rng(*parts):
    """Deterministic RNG: the same mock artist looks the same every run, so
    tests and screenshots are stable."""
    seed = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return random.Random(int(seed[:16], 16))


class MockMusicIntelligenceAdapter(MusicIntelligenceProvider):
    """A believable, entirely fictional universe.

    Deterministic from the artist id, so Breaking Now is stable between
    requests and a test can assert on a specific artist. Every name here is
    invented; nothing maps to a real person or company.
    """

    key = "mock"
    label = "Demo data (no credentials)"
    capabilities = ALL_CAPABILITIES
    cost_per_request = 0.0

    def __init__(self, count=25):
        self.count = count

    def configured(self):
        return True

    def health_check(self):
        return {"provider": self.key, "configured": True, "ok": True,
                "detail": "demo universe of %d artists" % self.count,
                "capabilities": list(self.capabilities)}

    # -- identity
    def _artist_ids(self):
        return ["mock-a%02d" % i for i in range(1, self.count + 1)]

    def search_artists(self, query, limit=20):
        q = (query or "").strip().lower()
        out = []
        for aid in self._artist_ids():
            a = self.get_artist(aid)
            if not q or q in a["name"].lower() or q in a["genre"].lower():
                out.append(a)
            if len(out) >= limit:
                break
        return out

    def get_artist(self, provider_artist_id):
        r = _rng("artist", provider_artist_id)
        city, state, country = r.choice(_CITIES)
        listeners = int(r.choice([1, 1, 1, 2, 5, 12]) * r.randint(3000, 90000))
        return {
            "provider_artist_id": provider_artist_id,
            "name": "%s %s" % (r.choice(_FIRST), r.choice(_LAST)),
            "genre": r.choice(_GENRES),
            "country": country,
            "city": city,
            "state": state,
            "career_stage": ("Emerging" if listeners < 50000 else
                             "Developing" if listeners < 250000 else "Established"),
            "monthly_listeners": listeners,
            "image_url": "",
            "website": "",
            "socials": {"instagram": "", "tiktok": "", "youtube": ""},
        }

    # -- metrics
    def get_artist_metrics(self, provider_artist_id, start, end):
        """Daily listener/follower series. Some artists are deliberately
        accelerating so the discovery boards have something real to find."""
        r = _rng("metrics", provider_artist_id)
        base = self.get_artist(provider_artist_id)["monthly_listeners"]
        # A believable market is mostly ordinary. If every artist were a
        # three-period accelerator the discovery boards would be meaningless
        # and the scoring would look broken - the product exists to separate
        # real movement from noise, so the demo universe has to contain noise.
        shape = r.choices(
            ["flat", "drifting", "accelerating", "spike", "declining", "recovering"],
            weights=[26, 26, 16, 12, 14, 6])[0]
        # each artist has its own intensity, so two accelerators do not land on
        # the same number
        heat = r.uniform(0.25, 1.6)
        days = (end - start).days + 1
        out = []
        value = base * r.uniform(0.72, 0.95)
        spike_at = r.uniform(0.45, 0.9)
        follower_ratio = r.uniform(0.06, 0.34)
        for i in range(days):
            d = start + timedelta(days=i)
            t = i / max(1, days - 1)
            noise = r.uniform(-0.0035, 0.0035)
            if shape == "accelerating":
                growth = 1.0 + (0.002 + 0.010 * t) * heat + noise
            elif shape == "drifting":
                growth = 1.0 + 0.0012 * heat + noise
            elif shape == "spike":
                growth = (1.0 + 0.11 * heat) if abs(t - spike_at) < 0.03 else 1.0 + noise
            elif shape == "declining":
                growth = 1.0 - 0.0035 * heat + noise
            elif shape == "recovering":
                growth = (1.0 - 0.004 * heat + noise) if t < 0.55 else (1.0 + 0.006 * heat + noise)
            else:
                growth = 1.0 + noise
            value = max(50.0, value * growth)
            out.append({"date": d.isoformat(), "metric": "spotify_monthly_listeners",
                        "value": round(value)})
            # followers lag listeners, and on a spike they barely move at all -
            # which is exactly the divergence the anomaly check looks for
            lag = 0.25 if shape == "spike" else 1.0
            out.append({"date": d.isoformat(), "metric": "spotify_followers",
                        "value": round(value * follower_ratio * (1 - (1 - lag) * t))})
        return out

    def get_artist_cities(self, provider_artist_id, start, end):
        r = _rng("cities", provider_artist_id)
        picks = r.sample(_CITIES, r.randint(3, 6))
        out = []
        for city, state, country in picks:
            out.append({"city": city, "region": state, "country": country,
                        "listeners": r.randint(400, 40000),
                        "change_28d_pct": round(r.uniform(-12, 68), 1)})
        return out

    def get_playlist_activity(self, provider_artist_id, start, end):
        r = _rng("playlists", provider_artist_id)
        n = r.randint(2, 7)
        out = []
        for i in range(n):
            out.append({"playlist_name": "Demo Playlist %d" % (i + 1),
                        "editorial": r.random() < 0.35,
                        "followers": r.randint(2000, 900000),
                        "added_on": (end - timedelta(days=r.randint(1, 120))).isoformat(),
                        "estimated_streams": r.randint(500, 250000)})
        return out

    def get_social_activity(self, provider_artist_id, start, end):
        r = _rng("social", provider_artist_id)
        out = []
        for platform in ("tiktok", "instagram", "youtube"):
            out.append({"platform": platform,
                        "followers": r.randint(500, 400000),
                        "change_28d_pct": round(r.uniform(-6, 90), 1)})
        return out

    def get_events(self, provider_artist_id):
        r = _rng("events", provider_artist_id)
        out = []
        for i in range(r.randint(0, 5)):
            city, state, country = r.choice(_CITIES)
            out.append({"date": (date.today() + timedelta(days=r.randint(5, 200))).isoformat(),
                        "city": city, "region": state, "country": country,
                        "venue": "The %s Room" % r.choice(["Ivy", "Copper", "Lantern", "Foundry"])})
        return out

    # -- releases and business evidence
    def get_artist_releases(self, provider_artist_id):
        r = _rng("releases", provider_artist_id)
        dist_name, dist_class = r.choice(_DISTRIBUTORS)
        out = []
        for i in range(r.randint(3, 9)):
            rel_date = date.today() - timedelta(days=r.randint(10, 1500))
            # most artists are consistent; some have a split catalogue
            if r.random() < 0.18:
                d_name, d_class = r.choice(_DISTRIBUTORS)
            else:
                d_name, d_class = dist_name, dist_class
            out.append({
                "provider_release_id": "%s-r%d" % (provider_artist_id, i),
                "title": "%s %s" % (r.choice(["Night", "Paper", "Golden", "Static",
                                              "Cardinal", "Slow", "Riverbed"]),
                                    r.choice(["Hours", "Lines", "Weather", "Signal",
                                              "Machine", "Season", "Talk"])),
                "release_type": r.choice(["Single", "Single", "Single", "EP", "Album"]),
                "release_date": rel_date.isoformat(),
                "upc": "".join(str(r.randint(0, 9)) for _ in range(12)),
                "label_text": d_name if d_class != "DIY / Self-Service" else "",
                "distributor_name": d_name,
                "distributor_class": d_class,
                "copyright_line": "(C) %d %s" % (rel_date.year, d_name),
                "track_count": r.randint(1, 11),
            })
        out.sort(key=lambda x: x["release_date"], reverse=True)
        return out

    def get_distributor_evidence(self, provider_release_id):
        r = _rng("dist", provider_release_id)
        name, cls = r.choice(_DISTRIBUTORS)
        return [{
            "distributor_name": name,
            "classification": cls,
            "source_type": "release_metadata",
            "source_label": "Demo catalogue metadata",
            "source_url": "",
            "excerpt": "℗ %s" % name,
            "confidence": round(r.uniform(0.72, 0.96), 2),
            "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }]

    def get_label_evidence(self, provider_release_id):
        r = _rng("label", provider_release_id)
        name, cls = r.choice(_DISTRIBUTORS)
        return [{"label_name": name, "classification": cls,
                 "source_type": "release_metadata",
                 "source_label": "Demo catalogue metadata",
                 "source_url": "", "excerpt": "© %s" % name,
                 "confidence": round(r.uniform(0.6, 0.95), 2),
                 "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}]

    def get_contact_evidence(self, provider_artist_id):
        """Fictional public professional footprint. Roles and sources only -
        never a personal address or private number."""
        r = _rng("contacts", provider_artist_id)
        out = []
        if r.random() < 0.62:
            person = "%s %s" % (r.choice(_FIRST), r.choice(_LAST))
            company = r.choice(_MGMT)
            out.append({"role": "Manager", "person_name": person, "company_name": company,
                        "email": "management@%s.example" % company.split()[0].lower(),
                        "phone": "", "source_type": "official_site",
                        "source_label": "Demo artist site — Contact",
                        "source_url": "", "excerpt": "Management: %s, %s" % (person, company),
                        "confidence": round(r.uniform(0.78, 0.97), 2)})
        if r.random() < 0.44:
            company = r.choice(_AGENCIES)
            out.append({"role": "Booking Agent",
                        "person_name": "%s %s" % (r.choice(_FIRST), r.choice(_LAST)),
                        "company_name": company,
                        "email": "booking@%s.example" % company.split()[0].lower(),
                        "phone": "", "source_type": "agency_roster",
                        "source_label": "Demo agency roster",
                        "source_url": "", "excerpt": "Roster listing",
                        "confidence": round(r.uniform(0.7, 0.93), 2)})
        if r.random() < 0.3:
            out.append({"role": "Publicist",
                        "person_name": "%s %s" % (r.choice(_FIRST), r.choice(_LAST)),
                        "company_name": "Marlow Press",
                        "email": "press@marlow.example", "phone": "",
                        "source_type": "press_release",
                        "source_label": "Demo press release",
                        "source_url": "", "excerpt": "For press enquiries",
                        "confidence": round(r.uniform(0.55, 0.8), 2)})
        return out

    def get_rights_evidence(self, isrc=None, title=None, artist=None):
        r = _rng("rights", isrc or title or artist or "x")
        work_match = r.random() < 0.55
        return [{
            "source_type": "work_registry",
            "source_label": "Demo work registry",
            "source_url": "",
            "work_match": work_match,
            "writers_complete": work_match and r.random() < 0.7,
            "publisher_detected": work_match and r.random() < 0.65,
            "shares_complete": work_match and r.random() < 0.6,
            "recording_linked": r.random() < 0.6,
            "confidence": round(r.uniform(0.5, 0.95), 2),
            "excerpt": "Demo registry lookup",
        }]


# --- registry ---------------------------------------------------------------

_REAL_ADAPTERS = (SoundchartsAdapter, ChartmetricAdapter, MusicBrainzAdapter,
                  MLCAdapter, SoundExchangeAdapter, SpotifyMetadataAdapter,
                  PublicWebResearchAdapter, InternalStreetBankerAdapter)


class ProviderRegistry(object):
    """Chooses a provider per capability.

    Preference order is explicit and inspectable in the admin screen. The
    mock is always last, so the moment a real provider is configured it
    takes over - and if it later fails, Signal falls back rather than
    showing an empty product.
    """

    def __init__(self, adapters=None, mock=None):
        self.mock = mock or MockMusicIntelligenceAdapter()
        self.adapters = list(adapters) if adapters is not None else [cls() for cls in _REAL_ADAPTERS]

    def all_providers(self):
        return list(self.adapters) + [self.mock]

    def configured_providers(self):
        return [p for p in self.all_providers() if p.configured()]

    def for_capability(self, capability):
        """Preferred provider for a capability.

        The mock answers only while NOTHING real is configured. The moment a
        real provider exists, a capability nobody real covers returns None,
        and the caller shows "not measured" - because a real artist with
        invented listener numbers beside their real name is the fabrication
        this product refuses everywhere else. Demo mode is all-or-nothing.
        """
        for p in self.adapters:
            if p.supports(capability) and p.configured():
                return p
        if self.is_demo():
            return self.mock if self.mock.supports(capability) else None
        return None

    def is_demo(self):
        """True when nothing real is configured - the UI must say so."""
        return not any(p.configured() for p in self.adapters)

    def health(self):
        return [p.health_check() for p in self.all_providers()]


_registry = None


def registry():
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def reset_registry(new=None):
    """Tests swap the registry; production never calls this."""
    global _registry
    _registry = new
    return _registry
