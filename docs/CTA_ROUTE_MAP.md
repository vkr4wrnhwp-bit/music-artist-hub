# CTA route map

Every destination reachable from the Street Banker homepage, and what a
**signed-out** visitor gets when they click it. Verified by walking the
rendered markup and requesting each route with an anonymous test client,
not by reading this file — `tests/test_closing.py::test_no_homepage_link_sends_a_visitor_into_the_login_wall`
fails the build if any of them starts answering with a redirect.

## The rule

A public product-information CTA never lands on a login wall. An account
is asked for at the point where there is something to save, upload,
deliver or claim — never in exchange for finding out what the product is.

## Homepage

| Section | CTA / link | Destination | Anonymous response |
| --- | --- | --- | --- |
| Header | Platform | `/#platform` | 200 (same page) |
| Header | AI Artist Twin | `/#artist-twin-section` | 200 |
| Header | Creative + Rollout | `/#creative-studio` | 200 |
| Header | Royalty Sweep | `/#royalty-sweep` | 200 |
| Header | Product tour | `/product-tour` | 200 |
| Header | For Labels | `/services` | 200 |
| Header | Log in | `/login` | 200 |
| Header | Run a Free Catalog Sweep | `/catalog-sweep` | 200 |
| 2 Hero | Explore Street Banker | `/#platform` | 200 |
| 2 Hero | Run a Royalty Sweep | `/catalog-sweep` | 200 |
| 3 Artist EQ | Build my Street Banker plan | `/plan?<mix>` | 200 |
| 3 Artist EQ | module links | `/plan?<mix>#<slug>` | 200 |
| 4 Departments | AI Artist Twin | `/#artist-twin-section` | 200 |
| 4 Departments | Creative Studio | `/#creative-studio` | 200 |
| 4 Departments | Rollout Engine | `/#rollout-engine` | 200 |
| 4 Departments | Royalty Sweep | `/#royalty-sweep-section` | 200 |
| 4 Departments | Rights | `/#metadata-passport` | 200 |
| 4 Departments | Fan Intelligence | `/product-tour/smart-link#fans` | 200 |
| 5 Artist Twin | Start with the Twin | `/artist-twin/start` | 200 |
| 5 Artist Twin | How we use AI | `/ai` | 200 |
| 6 Lanes | Find my lane / Compare | `/lanes`, `/lanes#<lane>` | 200 |
| 7 Creative Studio | What it does | `/creative-studio` | 200 |
| 8 Rollout Engine | See the plan | `/rollout` | 200 |
| 9 Royalty Sweep | How the sweep works | `/royalty-sweep` | 200 |
| 10 Distribution | What a release needs | `/distribution`, `#guide` | 200 |
| 11 Metadata Passport | The example passport | `/metadata`, `#used` | 200 |
| 11.5 Trust band | Read our artist control policy | `/artist-control` | 200 |
| 12 Closing | Build my Street Banker | `/start` | 200 |
| 12 Closing | Explore the platform | `/product-tour` | 200 |
| Footer · Platform | 8 links | tour, twin, studio, rollout, sweep, distribution, metadata, smart links | 200 |
| Footer · Solutions | 4 links | `/start`, `/lanes`, `/catalog-sweep`, `/services` | 200 |
| Footer · Trust | 4 links | `/artist-control`, `/ai`, `/privacy`, `/terms` | 200 |
| Footer · Company | 2 links | `/services`, `/submit` | 200 |
| Footer · Account | 3 links | `/signup`, `/login`, `/forgot` | 200 |
| Footer · Social | Instagram | instagram.com/summitartsgroup | external |

## What changed in this pass

**Broken destinations repaired.** The footer sent seven of its fifteen
links into the login wall: `/overview`, `/recovery`, `/artist-twin`,
`/roster`, `/audience`, `/capital`, `/network`. All seven are gone,
replaced by the public route that covers the same subject.

**Header hash links.** The public header renders on eleven public pages,
and every hash destination in it was written `#platform` rather than
`/#platform` — so on `/rollout` or `/metadata` the entire nav scrolled to
nothing. All now absolute.

**Department destinations.** Three departments pointed at `#artist-twin`,
`#creative-rollout` and `#tools`, anchors that belonged to the retired
Signature Tools block. They now point at the real section ids, and Fan
Intelligence — which has no homepage section — points at its public
example workspace.

**Generic social URLs removed.** `x.com`, `youtube.com` and
`linkedin.com` were bare domains, not profiles. Only the account that
exists is linked.

**The app rail on public pages.** `/services` and `/services/<slug>`
render the signed-in app shell. A signed-out visitor was being handed a
sidebar of roughly seventy destinations, every one of which answered with
a login redirect. `templates/base.html` now shows the public header
instead when `user_plan` is unset.

## Naming collision worth knowing about

The brief asked for the public tour at `/tour`. That path is the
signed-in touring pipeline (`/tour`, `/tour/add`, `/tour/<id>`,
`/tour/<id>/status`, `/tour-board`) and has been for a long time. The
public tour is at **`/product-tour`** rather than break it.
