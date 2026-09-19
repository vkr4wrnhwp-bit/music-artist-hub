"""What support knows, and what it admits it does not.

Owner, 2026-09-17: an AI support chat is one of two things that must exist
before sign-up reopens. Strangers ask different questions from people the
owner knows personally.

This is the layer underneath that chat, and it is built first on purpose.
It holds written answers and finds the one that fits. It has no model in
it, so it cannot invent an answer, and it works on a deployment with no
API key at all. When a model is added later it chooses among THESE
entries rather than writing prose of its own, which is what keeps the
whole feature honest: every sentence a person reads was written here and
can be corrected here.

The important behaviour is the refusal. A question this does not cover
returns nothing, and nothing means the question goes to the owner with the
page the person was on. A support answer that is confidently wrong about
somebody's royalties is worse than no answer, and an artist who is told
something wrong about their money does not come back.
"""

import re

# What a real question is made of once the noise is gone.
_STOP = {
    "a", "an", "the", "is", "are", "was", "do", "does", "did", "i", "my", "me",
    "we", "you", "your", "it", "its", "to", "of", "in", "on", "for", "and", "or",
    "can", "how", "what", "why", "when", "where", "who", "should", "would",
    "there", "this", "that", "with", "at", "be", "have", "has", "get", "got",
    "am", "if", "so", "but", "not", "no", "yes", "please", "help", "just",
}

# Each entry: id, the question in the artist's words, the answer, where to
# go, and the words that should find it. Answers say what the app actually
# does today; where something is not built, the answer says so.
ENTRIES = [
    {
        "id": "what-is-royalty-sweep",
        "question": "What is the Royalty Sweep?",
        "answer": ("It reads the statements you upload and shows what each platform "
                   "actually paid you, line by line. It also shows where a recording "
                   "is earning on some platforms but not others, which is usually "
                   "where money goes missing. Figures taken straight from a statement "
                   "are shown as measured. Anything worked out from them is labelled "
                   "an estimate, and it never promises you will recover anything."),
        "where": [("Royalty Sweep", "/royalties"), ("Upload a statement", "/statements")],
        "tags": "royalty sweep royalties money earnings statements missing owed gaps coverage",
    },
    {
        "id": "upload-statement",
        "question": "How do I upload a royalty statement?",
        "answer": ("Go to Statements and upload the file your distributor gives you. "
                   "CSV and the usual spreadsheet exports work. Once it is read, the "
                   "recordings and platforms in it appear across the money pages."),
        "where": [("Statements", "/statements")],
        "tags": "upload statement statements csv distributor import royalty file",
    },
    {
        "id": "not-measured",
        "question": "Why does something say Not measured instead of a number?",
        "answer": ("Because it has not been measured. Street Banker will not print a "
                   "zero for something it does not know, because a zero reads as a "
                   "real answer and would be a lie. Not measured means the app needs "
                   "something it does not have yet, usually a statement or a "
                   "connection."),
        "where": [],
        "tags": "not measured zero blank empty missing number unknown estimate",
    },
    {
        "id": "memberships",
        "question": "What do the memberships include?",
        "answer": ("Artist at $29 a month is Street Banker, Royalty Sweep and "
                   "Artifacts. Pro at $79 adds REACH, Tour and Company. Label at $199 "
                   "opens everything, including The Room, Noise Lab and Motion, and "
                   "includes credits every month. Artifacts and Company are marked "
                   "coming soon and open at no extra cost when they land."),
        "where": [("Plans", "/plan"), ("Billing", "/billing")],
        "tags": "membership plan plans price pricing cost tier artist pro label upgrade subscription",
    },
    {
        "id": "credits",
        "question": "How do credits work?",
        "answer": ("The Room and Motion cost real computing time every time they make "
                   "something, so they run on credits instead of being folded into a "
                   "flat price. A Label membership includes credits each month, and "
                   "those lapse when the next month's arrive. Credit packs are not on "
                   "sale yet. Noise Lab is coming soon."),
        "where": [("Credits", "/billing#credits")],
        "tags": "credits credit pack wallet balance run out spend the room noise lab motion",
    },
    {
        "id": "suite-locked",
        "question": "Why can I not open one of the suites?",
        "answer": ("Each suite opens with a particular membership. REACH, Tour and "
                   "Company need Pro. The Room, Noise Lab and Motion spend credits, so "
                   "they open on a Label membership or for anyone holding credits. The "
                   "tag beside a locked suite says which one it is."),
        "where": [("Plans", "/plan"), ("Credits", "/billing#credits")],
        "tags": "locked suite cannot open reach tour company room noise lab motion pro credits access denied",
    },
    {
        "id": "cover-rejected",
        "question": "Why was my cover art rejected by the stores?",
        "answer": ("Almost always something measurable. The most common causes are art "
                   "under 3000 pixels square, a file that is not square at all, CMYK "
                   "from a print designer instead of RGB, a transparent background, or "
                   "an image enlarged from a smaller one until it is soft. Text on the "
                   "cover that does not match your release title exactly is the other "
                   "common one."),
        "where": [("Cover Art", "/artwork")],
        "tags": "cover art artwork rejected refused declined store spotify apple size square cmyk blurry",
    },
    {
        "id": "smart-link",
        "question": "What is a smart link?",
        "answer": ("One address for a release that sends each listener to the platform "
                   "they actually use, and lets you capture the fan on the way through "
                   "if they agree to it. You make one from Smart Links."),
        "where": [("Smart Links", "/links")],
        "tags": "smart link links presave pre-save release share url landing fans capture",
    },
    {
        "id": "add-track",
        "question": "How do I add a song?",
        "answer": ("Add it in the Catalog, where each song gets a passport holding its "
                   "ISRC, credits, splits and the rest. If you have already uploaded "
                   "statements, the songs named in them are known to the app without "
                   "you adding them again."),
        "where": [("Catalog", "/catalog")],
        "tags": "add track song catalog passport isrc upload recording new release metadata",
    },
    {
        "id": "splits",
        "question": "How do I record who gets paid what?",
        "answer": ("Splits live on the song's passport in the Catalog, beside its "
                   "credits and identifiers. Getting them written down before a release "
                   "goes out is what prevents most of the arguments later."),
        "where": [("Catalog", "/catalog")],
        "tags": "split splits songwriter producer percentage share credits collaborator publishing who gets paid",
    },
    {
        "id": "invite-team",
        "question": "How do I give my manager access?",
        "answer": ("Settings has a Team section. Invite them by email and choose what "
                   "they can see. They get their own sign-in rather than using yours."),
        "where": [("Team", "/team"), ("Settings", "/settings")],
        "tags": "team manager invite access share account collaborator accountant lawyer permission",
    },
    {
        "id": "cannot-sign-in",
        "question": "I cannot sign in.",
        "answer": ("Use Forgot password on the sign-in page to set a new one. If it "
                   "says your access has ended or the account is locked, that is "
                   "Street Banker's own switch rather than anything you did, and "
                   "writing to us is the way through."),
        "where": [("Sign in", "/login"), ("Forgot password", "/forgot")],
        "tags": "sign in login cannot password locked reset forgot access ended blocked out",
    },
    {
        "id": "cancel",
        "question": "How do I cancel?",
        "answer": ("Billing, then Manage Billing, which opens Stripe's own portal where "
                   "you can cancel or change the card. Cancelling does not delete "
                   "anything you have built; the pages above your plan simply close."),
        "where": [("Billing", "/billing")],
        "tags": "cancel cancelling refund stop subscription unsubscribe downgrade billing card",
    },
    {
        "id": "my-data",
        "question": "Who can see my data?",
        "answer": ("You, and anyone you invite. Street Banker's owner can see account "
                   "records for support, and nobody else's account can reach yours. "
                   "Card details never touch this server: payments run entirely on "
                   "Stripe."),
        "where": [("Privacy", "/privacy"), ("Settings", "/settings")],
        "tags": "data privacy private secure security see who access gdpr delete card safe",
    },
    {
        "id": "delete-account",
        "question": "How do I delete my account?",
        "answer": ("Settings has it, at the bottom. It removes the account and "
                   "everything in it, and it cannot be undone, so take a backup first "
                   "if you want to keep anything."),
        "where": [("Settings", "/settings")],
        "tags": "delete account remove close erase wipe leave gdpr",
    },
    {
        "id": "artist-eq",
        "question": "What is the Artist EQ?",
        "answer": ("Six faders for release, creative, audience, rights, revenue and "
                   "growth. Set them to where your priorities actually are and Street "
                   "Banker builds a plan from them: which tools to open first and what "
                   "to do this week."),
        "where": [("Artist EQ", "/#artist-eq")],
        "tags": "artist eq faders priorities plan readiness score tune sliders",
    },
    {
        "id": "artist-twin",
        "question": "What is the Artist Twin?",
        "answer": ("It learns your music, visuals, audience, catalog and goals, then "
                   "helps you judge a release, a cover or a campaign before you commit "
                   "to it. It supports your decision. It does not make it for you."),
        "where": [("Artist Twin", "/artist-twin")],
        "tags": "artist twin ai assessment evaluate readiness brand alignment recommend",
    },
    {
        "id": "invitation-only",
        "question": "How do I get an account?",
        "answer": ("Street Banker is opening by invitation while the first partners are "
                   "brought on by hand. Write to us with who you are and what you are "
                   "working on, and we will set the account up with you."),
        "where": [("Contact", "/contact")],
        "tags": "account sign up signup join invitation invite register new create waiting list",
    },
    {
        "id": "white-label",
        "question": "Can I run this under my own label's brand?",
        "answer": ("Yes. Your brand, your domain, your artists on seats you control and "
                   "your own pricing to them. It is $499 a month plus every seat at 40 "
                   "per cent off the public price of its membership. Write to us and we "
                   "will set it up."),
        "where": [("Contact", "/contact")],
        "tags": "white label reseller brand own label partner seats distributor agency rebrand",
    },
    {
        "id": "tour",
        "question": "What does Tour do?",
        "answer": ("Routing, advancing, the day of show and settling, in one place. A "
                   "new account opens onto a Mock Up Tour, a full example routing you "
                   "can click through. It is marked as a demonstration and is not a "
                   "booking of yours."),
        "where": [("Tour", "/tours")],
        "tags": "tour touring shows dates routing advance settle venue road mock up demo gig",
    },
]

# Below this the match is not good enough to answer with. Chosen so that a
# question sharing one ordinary word with an entry never triggers it.
CONFIDENCE = 0.34


def _words(text):
    return [w for w in re.findall(r"[a-z0-9']+", (text or "").lower())
            if w not in _STOP and len(w) > 1]


def _score(query_words, entry):
    if not query_words:
        return 0.0
    hay = set(_words(entry["tags"])) | set(_words(entry["question"]))
    hits = sum(1 for w in set(query_words) if w in hay)
    # Against the question asked, not the entry, so a long entry with many
    # tags cannot win by sheer size.
    return hits / float(len(set(query_words)))


def search(query, limit=3):
    """Every entry that fits, best first. Scores are included so a caller
    can see how close the runner-up was."""
    qw = _words(query)
    scored = [(round(_score(qw, e), 3), e) for e in ENTRIES]
    scored = [(s, e) for s, e in scored if s > 0]
    scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    return [{"score": s, **e} for s, e in scored[:limit]]


def answer(query):
    """The one written answer that fits, or None.

    None is the important half. It means nobody here knows, and the caller
    must send the question to a person rather than improvising.
    """
    hits = search(query, limit=2)
    if not hits or hits[0]["score"] < CONFIDENCE:
        return None
    # Two entries fitting equally well is not confidence, it is ambiguity.
    if len(hits) > 1 and abs(hits[0]["score"] - hits[1]["score"]) < 0.001:
        return None
    return hits[0]


UNKNOWN = ("I do not know that one, so I have not guessed. Your question has "
           "gone to Street Banker with the page you were on, and someone will "
           "come back to you.")


def escalation(query, page="", account=""):
    """What gets sent to the owner when nothing here fits. The near misses go
    with it, because a question that nearly matched twice is usually an
    answer that needs writing."""
    return {
        "question": (query or "").strip()[:2000],
        "page": page,
        "account": account,
        "near_misses": [{"id": h["id"], "score": h["score"]} for h in search(query, limit=3)],
        "reply": UNKNOWN,
    }
