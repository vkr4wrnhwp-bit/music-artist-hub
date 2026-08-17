# Risk register

Ordered by expected cost of being wrong.

| # | Risk | Likelihood | Impact | Mitigation in place | Residual |
|---|---|---|---|---|---|
| 1 | **Google's "per 1 count" pricing unit is per-clip, not per-second** | medium | 8× cost error either way | quotes marked `estimated`; warning surfaced in the UI and in every quote's `raw`; global live-spend cap bounds it | **open** — verify against an invoice before volume |
| 2 | **Provider API drift** (renamed models, changed fields) | high | submissions fail after a shot is planned | capabilities and prices carry `retrievedAt` + `sourceUrl`; live catalogues preferred; contract battery per adapter; static fallbacks labelled `source: 'static'` | ongoing — re-run `masterclip providers contract` on a schedule |
| 3 | **No live provider call has ever been made from this build** | certain | adapters are spec-correct but unproven on the wire | every host was egress-blocked during development; adapters written from vendors' own client source, not memory | **open** — first live run needs a sandbox key and `masterclip providers contract --submit` |
| 4 | **A routing bug spends at scale** | low | unbounded | sandbox default; global `LIVE_SPEND_CAP_USD`; batch-aware authorization; re-authorization at submit; attempt caps | low |
| 5 | **Acceptance-rate learning overfits a tiny sample** | medium | bad routing that looks data-driven | Beta prior with 8 pseudo-observations; confidence reported on every decision; UI says when a ranking rests on priors | low |
| 6 | **Identity misuse** — generating a real person without consent | low | serious | consent recorded at upload; `requireAuthorizedForIdentity` refuses unless explicitly authorized and unexpired; rights changes audited | low |
| 7 | **A vision-QC false negative passes a bad clip** | medium | wasted finishing work | auto-rejection restricted to *demonstrated* technical failures; low confidence routes to a human; nothing auto-promotes | low |
| 8 | **A vision-QC false positive rejects a good clip** | medium | wasted spend | visual hard-failures require ≥0.6 confidence; human review remains the default for anything uncertain | medium |
| 9 | **Provider webhook spoofing** | low | fake completions | HMAC token bound to `(provider, job)`; per-provider signature where offered; dedupe index; state always re-fetched from the provider | low |
| 10 | **MuAPI's image field name varies by model** | high | 422 on submit | runtime recovery loop swaps `image_url` ↔ `images_list` on a field-required 422 | low |
| 11 | **Self-hosting adopted before it pays** | medium | worse cost per approved second plus ops burden | provider refuses to quote without measured GPU rate and compute ratio; `SELF_HOSTED_DRAFT` is not a default profile | low |
| 12 | **S3 driver has never touched a live bucket** | certain | uploads fail in a cloud deployment | SigV4 unit-tested against AWS's published vector; local driver is the default | **open** — run `doctor` with `STORAGE_DRIVER=s3` first |
| 13 | **No API rate limiting** | medium | brute force, upload flooding | documented in `docs/security-model.md`; deploy behind a rate-limiting proxy | **open** |
| 14 | **Long single generations degrade** | high | wasted renders past ~10s | validator warns above 10s and points at chaining via `CONTINUITY` | low |
| 15 | **Queue starvation under load** | low | slow renders block cheap bookkeeping | four separate queues (render, qc, media, maintenance) | low |
| 16 | **Estimate-vs-invoice drift goes unnoticed** | medium | budgets quietly wrong | `estimate` and `charge` are separate ledger entry types; `variance()` reports the delta per job | low |
| 17 | **Ledger corruption via a partial write** | low | wrong spend totals | ledger writes are transactional with the state change they describe; append-only | low |

---

## The three that need a human before production

1. **Confirm the Google pricing unit against a real invoice** (#1).
2. **Run one live sandbox render per provider** and re-run the contract battery
   with `--submit` (#3).
3. **Put a rate limiter in front of the API** (#13).
