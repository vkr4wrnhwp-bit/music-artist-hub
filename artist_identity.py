"""The artist's name, resolved once.

SOURCE OF TRUTH: `pulse_profiles.artist_name`.

The account's display name was stored in four places and derived in more
than four:

  users.name                      what was typed into the signup box. Often
                                  a person ("Dee Okafor"), not an act.
  pulse_profiles.artist_name      the act the artist searched for and
                                  confirmed, bound to a provider id - the
                                  only copy that is tied to a thing the
                                  outside world can be asked about.
  tour_store tours.artist_name    per tour, and legitimately so: a tour can
                                  be for a different act.
  signal_artists.canonical_name   the shared A&R roster, org-scoped and not
                                  linked to any account.
  os_tracks passport.artist_name  per track, and legitimately so: a feature
                                  is credited to somebody else.
  ml_campaigns / ro_campaigns /
  sync_packs .artist_name         per object, and legitimately so.

`pulse_profiles.artist_name` wins because it is the one bound to a
provider id: when Signal, YouTube or the metrics provider measures this
account, that is the artist being measured, so it is the name the rest of
the app must agree with. `users.name` is the fallback, because an account
that never connected a profile has nothing better.

The per-object copies stay. What is gone is *deriving* the artist's name
by guessing which table to read: the press desk put `users.name` on every
outgoing pitch and announcement, the release kit signed itself with it,
the artist twin introduced the artist by it, TOUR defaulted a new tour to
it and the public press kit headlined it - so a signed-up person called
"Dee Okafor" who runs an act called "COLD FURNACE" was announced to the
press as Dee Okafor while Pulse, Signal and the metrics provider all said
COLD FURNACE.

Nothing here calls a provider or writes anything.
"""

import db as store


def display_name(user, profile=None, default=""):
    """Resolve from records already in hand. `profile` is the account's
    pulse profile when the caller has it; None means "look it up"."""
    if not user:
        return default
    if profile is None:
        try:
            profile = store.get_pulse_profile(user.get("id") or "")
        except Exception:                  # noqa: BLE001 - a name, never a failure
            profile = None
    name = ((profile or {}).get("artist_name") or "").strip()
    if name:
        return name
    name = ((user.get("name") if hasattr(user, "get") else user["name"]) or "").strip()
    if name:
        return name
    email = (user.get("email") or "").strip() if hasattr(user, "get") else ""
    return email.split("@")[0] if email else default


def name_for(user_id, default=""):
    """The display name for one account id."""
    if not user_id:
        return default
    try:
        user = store.get_user(user_id)
    except Exception:                      # noqa: BLE001
        return default
    return display_name(dict(user) if user else None, default=default)
