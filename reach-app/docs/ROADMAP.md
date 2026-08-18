# REACH — Feature Roadmap and Architecture Notes

This document captures proposed feature modules, what already exists, and —
most importantly — where each proposal has to bend to REACH's non-negotiable
rules before it gets built. Anything here that contradicts a rule in the
"never remove" list (evidence requirements, human approval, UNKNOWN handling,
no fabricated success) is documented with its honest variant, and only the
honest variant will be implemented.

## Already shipped (do not rebuild)

These arrived in response to the first real discovery runs and are live:

| Proposal | Status | Where |
|---|---|---|
| Bot-wall / error-page filter ("Just a moment…", Cloudflare, 5xx) | **Shipped** | `extractor.page_state` classifies BOT_CHALLENGE / ERROR; `pipeline` refuses to mint outlets from them |
| Platform-domain filter (Spotify, YouTube, Wikipedia…) | **Shipped** | `config.PLATFORM_DOMAINS`, applied at search stage and again at resolve |
| Entity resolution / dedup by canonical domain | **Shipped** | `entities` canonicalisation; extra instances marked DUPLICATE, best record kept |
| Mobile card layout, action pills, inline score breakdown | **Shipped** | opportunities templates + `ui.score_breakdown` / `ui.target_actions` |

## Near-term candidates (months, not weeks)

### 1. Placement receipts and stream verification
Poll placed targets' public pages/playlists on a schedule; when the track is
found, record a placement evidence packet (URL, retrieval timestamp, excerpt)
and capture stream deltas against the baseline snapshots `analytics` already
takes.
**Constraints that bind:** a placement still requires evidence — automation
*gathers* the evidence, it never waives it. Polling goes through the existing
hardened fetcher (robots, rate limits, no login walls). Spotify content never
enters an LLM. Stream counts come only from the artist's own reported figures
or provider APIs with explicit policy allowance — never scraped guesses.
**Builds on:** `jobs` (durable queue), `evidence`, `outcomes.record_placement`,
`analytics.capture_baseline`.

### 2. "Call for music" radar
A discovery query family + RSS reader for active submission windows
("looking for synthpop for Friday's update"), surfacing the quoted post inside
the evidence panel with source URL and retrieval date.
**Constraints that bind:** public pages and feeds only — no authenticated or
private interfaces; the quote is an excerpt with a receipt, same as all
evidence. Freshness scoring already exists as a component.
**Builds on:** `pipeline` query families, `evidence`, the Receipt component.

### 3. Public press kit ("verified outreach history")
A read-only public page proving the outreach record: campaigns run, evidence
counts, zero pay-for-play (blocked-outlet stats), placements with their
evidence URLs.
**Constraints that bind:** recipient contact details never appear; the page
publishes *hashes and counts*, not private payloads. Label it what it is —
"attested by REACH's audit log", which is hash-chained and verifiable — not
"verified" by any third party until one actually verifies it.
**Builds on:** the hash-chained `audit` log, `outcomes.placements`.

## Longer-horizon proposals (with corrections)

### Cryptographic outreach audit trail (Merkle attestations)
The audit log is already append-only and hash-chained. The extension is
periodic public roots (publish the chain head) plus inclusion proofs, so a
third party can verify an entry without seeing recipient data. Feasible and
honest; the work is key management and a public verification page.

### Browser companion extension
An extension that autofills the already-prepared "copy-ready field answers"
into SubmitHub/Groover/DSP forms, human in the loop for every submit.
**Correction:** it must not bypass logins, CAPTCHAs, or terms — it is a
faster clipboard, not an automator. The Needs You speed-run view is the
in-app version of this today.

### Outlet persona simulator ("Curator X rejects pitches over 120 words")
**Correction:** only rules derived from *recorded* outcomes and *stated*
submission guidelines (with receipts) may fire. REACH will not invent curator
preferences — an uncorroborated "Curator X prefers…" is fabrication. Honest
v1: lint drafts against the outlet's own stated guidelines captured as
evidence (word limits, link rules, genre restrictions), each warning carrying
its source.

### Cross-campaign fraud telemetry ("global ledger")
REACH is single-tenant today; within the tenant, scam signals already block
outlets outright and the suppression list is global and permanent. The honest
in-tenant extension: when a *reply* demands payment, block that outlet across
all campaigns with the quoted demand stored as evidence. A cross-tenant
network is a privacy design problem first: only domain-level verdicts with
evidence excerpts may ever leave a tenant, never artist or recipient data.

### Visual-first crawler (headless browser inspection)
Text-side bot-challenge detection already gates the pipeline. A rendering
pass could catch JS-only walls, at real cost (Chromium per fetch) and real
risk (it must *detect and drop* challenges, never solve them; robots and
rate limits still bind). Revisit when text-side detection demonstrably
misses real cases — none observed since the page-state gate shipped.

### Inbound response intelligence
Bounce and opt-out parsing already exist (webhook + `sender.looks_like_opt_out`).
The honest extension, rule-based, each action logged with the quoted trigger:
- **Payment demanded in a reply** → block the outlet everywhere, store the
  quoted snippet as evidence, cancel follow-ups.
- **Master/WAV requested** → open a Needs You task with the asset checklist.
- **"We placed it"** → record an ACCEPT response and prompt for the placement
  URL. **Never** auto-transition to PLACED: a placement without evidence is
  the exact thing REACH refuses to fabricate.

### Rights attestation hash in pitches
SHA-256 over the recorded rights attestation + ISRC + split data, shown in
review and optionally in the pitch footer.
**Correction:** the label is **RIGHTS ATTESTED**, not "verified" — REACH
records the artist's attestation; it has not independently verified chain of
title, and saying otherwise would be a fabricated claim.

### Territory pitch adapters
Deterministic per-territory formatting (salutation, structure, citation
style: US/UK/DACH/JP) over the same fact set. Every factual sentence keeps
its source binding — adapters reorder and rephrase framing, never facts.
Language handling already flags untranslatable drafts for review.
