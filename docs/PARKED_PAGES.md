# Parked pages

Pages taken off the sidebar on 2026-09-06 (the sidebar audit) and **kept
whole** — routes, templates, config modules and tests — for the day a real
provider is connected. Each still answers at its address and says at the
top that it is parked. Nothing links to them.

The owner's instruction: *"Keep all of the A information for after we
correctly get APIs to utilize them."*

| Page | Why it is parked | What would un-park it |
| --- | --- | --- |
| `/capital` — Capital | `capital_config.py`: "every one of these is a SIMULATED DEMO" — Fan Royalty Passes, crowdfunding, a futures marketplace, staking, a dice game. No money moves. | A real financing or fan-investment provider, with the product's own terms, and the honesty doctrine's measured/not-measured labelling. |
| `/benchmark` — Benchmark | Your numbers are real; the peer averages are illustrative. A meter against an invented peer lends the invented half the real half's credibility. | A data source for peer catalogs at a similar stage, with the sample size shown. |
| `/funding` — Funding | The eligibility range is computed from your statements (`capital_engine.advance_eligibility`); the offers, terms and providers around it are illustrative and "request" records interest only. | A lender integration whose offers are the lender's own. The eligibility figure already shows on `/valuation`. |
| `/fan-label` — Fan Label | `community_config.py`: the fund, the backer count and the demo votes are placeholders; no money has been raised and no fan has backed anything. | A real fan-funding provider with the product's own terms. The real fan work is Fans (`/fans`), the Fan CRM and the Fan Club. |
| `/network` — Network | `network_config.py`: the directory, playlists, shows and moments are sample profiles, not real people. The outreach tracker on it is real and moved to `/tour-board/outreach`; the old page still shows it. | A real directory source, or nothing: the Team-Up Board is where real accounts find each other. |
| `/conflicts` — Conflicts | A static illustration of a rights-conflict centre. The real thing is **Disputes** (`/disputes`), which logs and tracks your own conflicts. | Probably never: fold anything worth keeping into Disputes instead. |

## How to un-park one

1. Remove the `{% include "_parked.html" %}` line from the template.
2. Add its sidebar entry back to `hubs.HUBS` and, once it shows real data,
   its key to `hubs._BASE_LIVE`.
3. Update `tests/test_sidebar_fold.py` (the entry count and the parked
   list) and `tests/test_demo_data_guard.py` if the config module changes
   class.

## What was folded the same day (not parked — one tap away)

| Front (sidebar entry) | Tabs |
| --- | --- |
| Income by type (`/publishing`) | Publishing · Mechanicals · Neighboring rights · By market |
| Royalty Lanes | Lanes · Queue (`/money-queue`) |
| Scores (`/qualification`) | Growth · Trust (`/trust-score`) · Insights (`/insights`) |
| Deals (`/deal-room`) | Deal Room · Simulator · Sync packs |
| Press (`/press-desk`) | Desk · Media list · Announcements · Coverage · Press kit (`/epk`) · One-sheet (`/artist-profile`) |
| Settings | Data & Connections (`/connections`) — it was never money |
| Releases (`/releases/autopilot`) | Autopilot · Calendar (`/releases`) |
| Vault | Files · Contracts & licences (`/documents`) |
| Catalog | Catalog · Track Passports (`/tracks`) — two song tables still; unifying the data is a separate job |
| Fans (`/fans`) | Dashboard · Fan CRM (`/links/fans`) · Fan Club (`/fan-club`) — 2026-09-06 |

Every folded URL is unchanged.
