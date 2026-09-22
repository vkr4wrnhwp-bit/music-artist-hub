"""Street Banker Distribution, powered by Symphonic: the application form.

The owner's partnership is with Symphonic, and their sign-up lives on a
HubSpot form at community.symphonic.com/summitarts-1. Sending artists there
meant handing them to somebody else's branded page and losing sight of who
applied (owner, 2026-09-22: "can we lift some information out of it that
they need, make our own, and then once they submit it to ours, it's
submitted to the symphonic sheet").

So this is our form, and it posts into their sheet through HubSpot's public
submission endpoint, which takes no key. Their field names and their exact
option values are below, read from the form's own definition - a value they
do not recognise is a submission they reject.

WHAT THIS IS HONEST ABOUT
-------------------------
  * Symphonic decides, not Street Banker. The page says so, and nothing
    here implies an application has been accepted.
  * An artist's details go to a third party, so a tick says that plainly
    before anything is sent. Same rule as the RoEx consent.
  * We keep our own copy of every application. If HubSpot refuses one, the
    artist is told and the owner can see it - a form that loses an
    application silently is worse than no form.
  * If Symphonic edits their form, our field names drift and submissions
    start bouncing. That shows up as a failure with their message kept,
    not as a success.

WHAT IT DOES NOT DO
-------------------
It does not speak for Symphonic, quote a rate, promise a timeline, or
claim a catalog has been delivered. The distribution guide already says
which parts of the work are the partner's.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

PORTAL_ID = "4245189"
FORM_GUID = "da8b3b69-64fc-480e-ac1f-96381eecb95f"
ENDPOINT = ("https://api.hsforms.com/submissions/v3/integration/submit/%s/%s"
            % (PORTAL_ID, FORM_GUID))
TIMEOUT = 20

# Where their own form sends a person afterwards. Quoted so the page can
# say what happens next in their words rather than ours.
THEIRS = "https://community.symphonic.com/summitarts-1"

WHO = ("Artist", "Distributor", "Label", "Manager",
       "Creator (TikTok/Triller/Etc.)", "Other")

CATALOG = ("Yes", "No", "This is a new artist/label with no previous catalog")

SOCIALS = ("Facebook", "Instagram", "SoundCloud", "Twitter", "YouTube",
           "TikTok", "Other")

SERVICES = ("Marketing Services", "Music Video Distribution",
            "Publishing Administration", "None")

HEARD = (
    "Ari's Take", "Azideia Podcast", "Conference", "Digital Music News",
    "Existing Symphonic Client", "Facebook", "Friend", "Google",
    "Instagram", "Music Business Worldwide", "Symphonic Employee", "Tik Tok",
    "Twitter", "Other",
)

GENRES = (
    "Alternative", "Anime", "Arabic", "Audiobooks",
    "Blues", "Brazilian", "Children's Music", "Chinese",
    "Christian & Gospel", "Classical", "Comedy", "Country",
    "Dance", "Disney", "Easy Listening", "Electronic",
    "Enka", "Fitness & Workout", "Folk", "French Pop",
    "Funk", "German Folk", "German Pop", "Heavy Metal",
    "Hip Hop/Rap", "Holiday", "Indian", "Inspirational",
    "Instrumental", "J-Pop", "Jazz", "Karaoke",
    "Kayokyoku", "Korean", "Latin", "Marching Bands",
    "New Age", "Other/Non Music Related", "Pop", "Punk",
    "R&B/Soul", "Reggaeton", "Reggae", "Rock",
    "Singer/Songwriter", "Soundtrack", "Spoken Word", "Vocal",
    "World",
)

# The field names their form uses. Ours differ only where we already know
# the answer from the account.
FIELDS = (
    ("firstname", True), ("lastname", True), ("email", True),
    ("mobilephone", False),
    ("select_your_home_country", True),
    ("which_of_these_best_describes_you", True),
    ("key_info_about_your_band", True),
    ("transfer_existing_catalog_to_symphonic", True),
    ("primary_genre", True),
    ("artist_label_social_media_links", True),
    ("how_did_you_hear_about_symphonic_", True),
    ("planned_marketing_services", True),
)

# HubSpot takes a multi-select as one value with semicolons between.
MULTI = ("artist_label_social_media_links", "planned_marketing_services")

CHOICES = {
    "which_of_these_best_describes_you": WHO,
    "transfer_existing_catalog_to_symphonic": CATALOG,
    "primary_genre": GENRES,
    "artist_label_social_media_links": SOCIALS,
    "how_did_you_hear_about_symphonic_": HEARD,
    "planned_marketing_services": SERVICES,
}

WORDS = {
    "firstname": "First name",
    "lastname": "Last name",
    "email": "Email",
    "mobilephone": "Mobile phone",
    "select_your_home_country": "Country you live in",
    "which_of_these_best_describes_you": "Which of these describes you",
    "key_info_about_your_band": "About the artist, band or label",
    "transfer_existing_catalog_to_symphonic": "Moving an existing catalog across",
    "primary_genre": "Main genre",
    "artist_label_social_media_links": "Where people follow you",
    "how_did_you_hear_about_symphonic_": "How you heard about Symphonic",
    "planned_marketing_services": "Anything else you are interested in",
}


COUNTRIES = (
    "United States", "Afghanistan", "Albania", "Algeria",
    "Andorra", "Angola", "Antigua & Deps", "Argentina",
    "Armenia", "Australia", "Austria", "Azerbaijan",
    "Bahamas", "Bahrain", "Bangladesh", "Barbados",
    "Belarus", "Belgium", "Belize", "Benin",
    "Bhutan", "Bolivia", "Bosnia Herzegovina", "Botswana",
    "Brazil", "Brunei", "Burkina Faso", "Bulgaria",
    "Burkina", "Burundi", "Cambodia", "Cameroon",
    "Canada", "Cape Verde", "Central African Rep", "Chad",
    "Chile", "China", "Colombia", "Comoros",
    "Congo", "Congo {Democratic Rep}", "Costa Rica", "Croatia",
    "Cuba", "Cyprus", "Czech Republic", "Denmark",
    "Djibouti", "Dominica", "Dominican Republic", "East Timor",
    "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea",
    "Eritrea", "Estonia", "Ethiopia", "Fiji",
    "Finland", "France", "Gabon", "Gambia",
    "Georgia", "Germany", "Ghana", "Greece",
    "Grenada", "Guatemala", "Guinea", "Guinea-Bissau",
    "Guyana", "Haiti", "Honduras", "Hungary",
    "Iceland", "India", "Indonesia", "Iran",
    "Iraq", "Ireland {Republic}", "Israel", "Italy",
    "Ivory Coast", "Jamaica", "Japan", "Jordan",
    "Kazakhstan", "Kenya", "Kiribati", "Korea North",
    "Korea South", "Kosovo", "Kuwait", "Kyrgyzstan",
    "Laos", "Latvia", "Lebanon", "Lesotho",
    "Liberia", "Libya", "Liechtenstein", "Lithuania",
    "Luxembourg", "Macedonia", "Madagascar", "Malawi",
    "Malaysia", "Maldives", "Mali", "Malta",
    "Marshall Islands", "Mauritania", "Mauritius", "Mexico",
    "Micronesia", "Moldova", "Monaco", "Mongolia",
    "Montenegro", "Morocco", "Mozambique", "Myanmar, (Burma)",
    "Namibia", "Nauru", "Nepal", "Netherlands",
    "New Zealand", "Nicaragua", "Niger", "Nigeria",
    "Norway", "Oman", "Pakistan", "Palau",
    "Panama", "Papua New Guinea", "Paraguay", "Peru",
    "Philippines", "Poland", "Portugal", "Puerto Rico",
    "Qatar", "Romania", "Russian Federation", "Rwanda",
    "St Kitts & Nevis", "St Lucia", "Saint Vincent & the Grenadines", "Samoa",
    "San Marino", "Sao Tome & Principe", "Saudi Arabia", "Senegal",
    "Serbia", "Seychelles", "Sierra Leone", "Singapore",
    "Slovakia", "Slovenia", "Solomon Islands", "Somalia",
    "South Africa", "South Sudan", "Spain", "Sri Lanka",
    "Sudan", "Suriname", "Swaziland", "Syria",
    "Sweden", "Switzerland", "Taiwan", "Tasmania",
    "Tajikistan", "Tanzania", "Thailand", "Togo",
    "Tonga", "Trinidad & Tobago", "Tunisia", "Turkey",
    "Turkmenistan", "Tuvalu", "Uganda", "Ukraine",
    "United Arab Emirates", "United Kingdom", "Uruguay", "Uzbekistan",
    "Vanuatu", "Vatican City", "Venezuela", "Vietnam",
    "Yemen", "Zambia", "Zimbabwe", "Martinique",
    "Faroe Islands", "C\u00f4te d'Ivoire", "Ruanda", "Hong Kong",
    "Chipre",
)


def countries():
    """The 205 their form accepts, United States first as theirs has it."""
    return COUNTRIES


def check(form):
    """(values, errors). Nothing is sent until this is clean.

    A value outside their own list is refused here rather than bounced by
    HubSpot, because their refusal is a number and ours is a sentence.
    """
    values, errors = {}, {}
    for name, required in FIELDS:
        if name in MULTI:
            picked = [v for v in form.getlist(name) if v in CHOICES[name]]
            if required and not picked:
                errors[name] = "Pick at least one."
            values[name] = ";".join(picked)
            continue
        raw = (form.get(name) or "").strip()
        if name in CHOICES and raw and raw not in CHOICES[name]:
            errors[name] = "Choose one of the listed options."
            continue
        if name == "select_your_home_country" and raw and raw not in COUNTRIES:
            errors[name] = "Choose a country from the list."
            continue
        if required and not raw:
            errors[name] = "This one is needed."
        if name == "email" and raw and ("@" not in raw or "." not in raw.split("@")[-1]):
            errors[name] = "That does not look like an email address."
        values[name] = raw[:2000]
    return values, errors


def submit(values, page_url="", ip="", opener=None):
    """Send one application to Symphonic. (ok, message).

    `opener` is the seam the tests replace; nothing else here opens a
    socket. A refusal keeps HubSpot's own words, because "it did not work"
    is not something an artist can act on.
    """
    body = {
        "fields": [{"objectTypeId": "0-1", "name": k, "value": v}
                   for k, v in values.items() if v != ""],
        "context": {"pageUri": page_url or THEIRS,
                    "pageName": "Street Banker Distribution"},
    }
    if ip:
        body["context"]["ipAddress"] = ip
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=data, method="POST",
        headers={"Content-Type": "application/json",
                 "User-Agent": "StreetBanker-Distribution/1"})
    try:
        with (opener or urllib.request.urlopen)(req, timeout=TIMEOUT) as resp:
            return 200 <= resp.status < 300, ""
    except urllib.error.HTTPError as exc:
        return False, _their_words(exc)
    except Exception as exc:
        # Their end, or the network. Either way the application is kept.
        return False, "%s" % type(exc).__name__


def _their_words(exc):
    """What HubSpot said, short enough to show and specific enough to act
    on. A changed field name comes back here, which is the one failure
    that will not announce itself any other way."""
    try:
        got = json.loads(exc.read(4000).decode("utf-8", "replace"))
    except Exception:
        return "HTTP %s" % exc.code
    bits = []
    for err in (got.get("errors") or [])[:3]:
        message = err.get("message") or err.get("errorType") or ""
        if message:
            bits.append(str(message)[:160])
    if not bits and got.get("message"):
        bits.append(str(got["message"])[:200])
    return " ".join(bits) or "HTTP %s" % exc.code
