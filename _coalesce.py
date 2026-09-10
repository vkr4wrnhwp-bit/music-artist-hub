import io
P = "db.py"
s = io.open(P, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"

old = ('''                "ON CONFLICT(user_id, day, provider) DO UPDATE SET followers=excluded.followers, "
                "popularity=excluded.popularity, deezer_fans=excluded.deezer_fans, "
                "monthly_listeners=COALESCE(excluded.monthly_listeners, pulse_snapshots.monthly_listeners)",''').replace("\n", nl)
new = ('''                "ON CONFLICT(user_id, day, provider) DO UPDATE SET "
                # Every measure coalesces. A later write that did not
                # measure something must not erase what an earlier one did:
                # once these columns could hold NULL, "I have no figure for
                # this" and "the figure is gone" became the same UPDATE, and
                # a provider reporting monthly listeners alone would wipe
                # the follower count recorded beside it that morning.
                "followers=COALESCE(excluded.followers, pulse_snapshots.followers), "
                "popularity=COALESCE(excluded.popularity, pulse_snapshots.popularity), "
                "deezer_fans=COALESCE(excluded.deezer_fans, pulse_snapshots.deezer_fans), "
                "monthly_listeners=COALESCE(excluded.monthly_listeners, pulse_snapshots.monthly_listeners)",''').replace("\n", nl)
assert s.count(old) == 1, s.count(old)
io.open(P, "w", encoding="utf-8", newline="").write(s.replace(old, new))
print("a silence no longer erases a reading")
