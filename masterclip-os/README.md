# MASTERCLIP OS

A cinematic AI-video render factory. Define shots once, generate them across many
providers, measure every result, keep what a human approves — and track the only
number that matters: **cost per approved second**.

Not an explainer generator. Not a single-provider wrapper.

---

## Run it

```bash
cd masterclip-os
pnpm install
pnpm seed          # demo project: 3 shots, a character bible, a world bible
pnpm dev           # API :4310 · web :4311 · worker
```

Open <http://127.0.0.1:4311> and sign in with the credentials `pnpm seed` prints.

**A clean checkout needs nothing installed except Node 22.5+ and ffmpeg.**
It runs on SQLite, local file storage, and a mock provider that renders real
MP4s with ffmpeg — so the whole factory is exercisable at zero cost before any
credential exists.

```bash
pnpm masterclip doctor      # ffmpeg, database, queue, storage, providers, spend allowance
```

### Requirements

| | |
|---|---|
| Node | ≥ 22.5 (`node:sqlite`) |
| ffmpeg + ffprobe | on `PATH`, or set `FFMPEG_PATH` / `FFPROBE_PATH`. Debian/Ubuntu: `apt-get install ffmpeg` |
| Everything else | optional — see below |

### Optional services

```bash
pnpm docker:up     # PostgreSQL + MinIO
```

Then set `DB_DRIVER=postgres` with `DATABASE_URL`, and/or `STORAGE_DRIVER=s3`
with the `S3_*` variables. The same migrations run on both dialects.

---

## The first thing to understand: sandbox mode

`MASTERCLIP_MODE=sandbox` is the default and it **refuses every billable
submission**, independent of budgets. Renders go to the local ffmpeg mock
provider, which returns genuine video files — including deliberately defective
ones, so QC's failure detection is demonstrable rather than assumed.

Going live is a deliberate act:

```bash
MASTERCLIP_MODE=live LIVE_SPEND_CAP_USD=2 FAL_KEY=... pnpm dev
```

`LIVE_SPEND_CAP_USD` is a hard global ceiling across every org and project,
checked separately from budgets, precisely so a bug in routing cannot spend at
scale. The banner at the top of every screen says which mode you are in.

---

## What it does

**Define a shot once, provider-agnostically.** A canonical spec covering subject,
identity/wardrobe/prop locks, environment, action, performance, blocking, camera
position and movement, lens and aperture, a motivated light source, materials,
physics, continuity, audio, negative constraints, routing intent, and a cost
ceiling. Validated by schema *and* by semantic rules — a `first_last_frame` shot
with no last frame is rejected before a provider charges you to find out.

**Route by expected cost per approved second.** Not by sticker price. A model
that costs 3× more but lands twice as often is cheaper per usable second, and the
router learns each model's acceptance rate *for your project, per shot category*
— starting from a conservative prior and telling you when it is still guessing.

**Generate in batches, priced before they are queued.** Build a matrix across
models, seeds, variations, aspect ratios, and durations; see the candidate count
and the real total; prune the expensive branches; then submit.

**Reject failures automatically, for free.** ffprobe, blackdetect, freezedetect
and a full decode pass catch frozen clips, black clips, wrong durations,
truncated downloads, unusable bitrates, and byte-identical duplicates before a
vision model or a person is involved. Only what survives goes to visual QC.

**Never auto-approve.** QC can reject; only a person promotes a master.

**Finish and deliver with provenance.** H.264/H.265/ProRes deliveries, alternate
aspect ratios (with an explicit crop-or-pad choice, because both lose something),
EDL and FCPXML, and a provenance sidecar recording the provider, model, prompt,
seed, shot version, QC verdicts, reviews, and cost. Transcoding never claims to
add detail, and nothing upscales or interpolates by default.

---

## Providers

Implemented adapters: **mock** (local ffmpeg), **MuAPI**, **Google Gemini (Veo)**,
**fal.ai**, **Runway**, **Luma**, **Replicate**, **self-hosted ComfyUI**.

Every endpoint, header, status enum, and price was verified on 2026-08-17 against
each vendor's own client library or machine-readable spec — see
[`docs/provider-matrix.md`](docs/provider-matrix.md).

> **No live provider call has been made from this build.** Every vendor host was
> blocked by the development environment's egress policy, so the adapters are
> spec-correct but unproven on the wire. Run
> `pnpm masterclip providers contract --provider <id> --submit` with a sandbox
> key before trusting one. This is tracked as risk #3 in
> [`docs/risk-register.md`](docs/risk-register.md).

---

## Commands

```bash
pnpm dev              # API + worker + web, one log stream
pnpm test             # 165 unit + integration tests
pnpm test:e2e         # 10 Playwright browser tests
pnpm typecheck        # tsc --noEmit across 27 packages
pnpm lint             # secret scan + shell/SQL guards + typecheck
pnpm build            # esbuild bundles + the web build
pnpm seed             # demo project
pnpm docker:up        # PostgreSQL + MinIO
```

### CLI

```bash
pnpm masterclip doctor
pnpm masterclip providers list | health | contract --provider mock --submit
pnpm masterclip models refresh
pnpm masterclip project create --name "Neon Rain"
pnpm masterclip shots import --project <id> --file shots.csv --dry-run
pnpm masterclip shots template --out shots.csv
pnpm masterclip render submit --shot <id> --count 6
pnpm masterclip queue work            # drain inline, no long-running worker
pnpm masterclip costs report --project <id>
pnpm masterclip masters package --master <id>
```

Every command takes `--json`. Exit codes: `0` ok · `1` error · `2` usage ·
`3` checks ran and reported failures.

---

## Where things live

```
apps/       api (Fastify) · worker · web (React) · cli
packages/   shared · shot-schema · domain · database · queue · asset-storage
            auth · provider-core · provider-{mock,muapi,google,fal,runway,
            luma,replicate,selfhosted} · media-tools · qc-engine · cost-engine
            model-router · prompt-compiler · agents · runtime
docs/       architecture · provider-matrix · current-pricing-snapshot
            model-capabilities · licensing-inventory · security-model
            cost-strategy · cinematic-standard · risk-register · build-audit
```

---

## Documentation

| Document | Read it when |
|---|---|
| [architecture](docs/architecture.md) | you want to know why it is shaped this way |
| [cost-strategy](docs/cost-strategy.md) | before spending anything real |
| [provider-matrix](docs/provider-matrix.md) | adding or debugging an adapter |
| [current-pricing-snapshot](docs/current-pricing-snapshot.md) | budgeting — **read the caveats** |
| [model-capabilities](docs/model-capabilities.md) | choosing a model for a shot |
| [cinematic-standard](docs/cinematic-standard.md) | the default visual standard and how it is enforced |
| [security-model](docs/security-model.md) | before exposing this to a network |
| [licensing-inventory](docs/licensing-inventory.md) | before shipping commercially |
| [risk-register](docs/risk-register.md) | before production |
| [build-audit](docs/build-audit.md) | what is real, what is not |

---

## Status

First production-capable release. Every feature's actual state — REAL,
DEV-LABELED, PARTIAL, or NOT BUILT — is itemised in
[`docs/build-audit.md`](docs/build-audit.md), including what still needs
credentials and what has never been run against a live provider.
