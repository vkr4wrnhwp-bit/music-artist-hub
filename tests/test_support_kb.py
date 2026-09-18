"""Support answers what it knows and says nothing when it does not.

Owner, 2026-09-17: an AI support chat is one of two gates before sign-up
reopens. This is the layer underneath it, built first so that the feature
can never invent an answer: a model added later chooses among these
written entries rather than writing prose of its own.

The refusal is the behaviour under test. An artist told something
confidently wrong about their royalties does not come back.
"""
import support_kb as kb


def _id(query):
    a = kb.answer(query)
    return a["id"] if a else None


def test_the_questions_artists_actually_ask_are_answered():
    asked = {
        "where is my money": "what-is-royalty-sweep",
        "how do i upload a royalty statement": "upload-statement",
        "why does it say not measured": "not-measured",
        "how much does it cost": "memberships",
        "how do credits work": "credits",
        "why was my cover art rejected": "cover-rejected",
        "what is a smart link": "smart-link",
        "how do i give my manager access": "invite-team",
        "i cannot sign in": "cannot-sign-in",
        "how do i cancel my subscription": "cancel",
        "how do i delete my account": "delete-account",
        "can i run this under my own brand": "white-label",
    }
    wrong = {q: (_id(q), want) for q, want in asked.items() if _id(q) != want}
    assert not wrong, wrong


def test_a_question_nobody_wrote_an_answer_for_gets_nothing():
    for q in ("what is the capital of france",
              "can you write my album for me",
              "do you integrate with my bank",
              "what time is it",
              "asdfgh"):
        assert kb.answer(q) is None, q


def test_an_empty_or_useless_question_is_not_answered():
    for q in ("", "   ", "hi", "hello", "please help", "the a is"):
        assert kb.answer(q) is None, repr(q)


def test_two_entries_fitting_equally_well_is_ambiguity_not_confidence():
    """A tie is not an answer. The question goes to a person instead."""
    hits = kb.search("credits")
    if len(hits) > 1 and abs(hits[0]["score"] - hits[1]["score"]) < 0.001:
        assert kb.answer("credits") is None


def test_every_answer_carries_somewhere_to_go_or_deliberately_does_not():
    for e in kb.ENTRIES:
        assert e["question"].endswith("?") or e["question"].endswith("."), e["id"]
        assert len(e["answer"]) > 60, e["id"]
        assert e["tags"].strip(), e["id"]
        for label, href in e["where"]:
            assert label and href.startswith(("/", "#")), e["id"]


def test_no_answer_promises_money_or_a_recovery():
    """The honesty rule, in the place a stranger reads first."""
    for e in kb.ENTRIES:
        low = e["answer"].lower()
        for phrase in ("we will recover", "guarantee", "guaranteed",
                       "you will get back", "we recover your"):
            assert phrase not in low, (e["id"], phrase)


def test_the_royalty_answer_says_measured_and_estimated_are_different():
    a = kb.answer("what is the royalty sweep")
    assert a and "estimate" in a["answer"].lower() and "measured" in a["answer"].lower()


def test_what_goes_to_the_owner_when_nobody_knows():
    e = kb.escalation("does this work with my bank", page="/billing", account="a@b.co")
    assert e["question"] == "does this work with my bank"
    assert e["page"] == "/billing" and e["account"] == "a@b.co"
    assert e["reply"] == kb.UNKNOWN
    assert "not guessed" in e["reply"]
    # The near misses travel with it: a question that nearly matched twice is
    # usually an answer that needs writing.
    assert isinstance(e["near_misses"], list)
    for miss in e["near_misses"]:
        assert miss["id"] and 0 < miss["score"] <= 1


def test_a_very_long_question_is_trimmed_rather_than_refused():
    e = kb.escalation("why " * 3000)
    assert len(e["question"]) <= 2000


def test_search_puts_the_best_fit_first_and_shows_its_working():
    hits = kb.search("cover art rejected by spotify")
    assert hits and hits[0]["id"] == "cover-rejected"
    assert hits[0]["score"] >= (hits[1]["score"] if len(hits) > 1 else 0)
    assert all(0 < h["score"] <= 1 for h in hits)


def test_the_entries_have_no_duplicate_ids():
    ids = [e["id"] for e in kb.ENTRIES]
    assert len(ids) == len(set(ids))
