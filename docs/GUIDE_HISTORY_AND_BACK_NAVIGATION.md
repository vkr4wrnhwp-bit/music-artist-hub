# Guide history and BACK ONE STEP

GuideSession.history is the actual visited path, in order. BACK ONE
STEP (`back()`, Alt+←) pops it — never `order - 1`, never browser
history — so branches are walked backwards exactly as travelled
(pinned by test: features → proposals-branch → stock backs to
proposals, not to whatever order-minus-one would name).

Back is disabled at the first step (`canGoBack`), is a pure function of
the session, and can change nothing but which card is shown: the engine
has no write access to project state, so backing past an applied change
shows the earlier card with the CURRENT real value. Reversing an
applied manufacturing change is a different action that goes through
the auditable mutation flows (proposals, disagreements, stock/setup
edits) — the Guide never silently rolls anything back.
