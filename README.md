# music-artist-hub

Four separate products share this repository. They have their own runtimes,
their own tests and their own deployments — the only thing they share is this
repo and `render.yaml`.

A fifth, **MASTERCLIP OS**, used to live here and now has
[its own repository](https://github.com/vkr4wrnhwp-bit/masterclip-os). It is
listed below so this table stays a complete index of the products, but nothing
of it is stored here.

| Product | What it is | Where | State |
|---|---|---|---|
| **[MASTERCLIP OS](https://github.com/vkr4wrnhwp-bit/masterclip-os)** | Cinematic AI-video render factory — define a shot once, generate it across providers, QC every result, track cost per approved second. Also carries audio intelligence, Song Lab and Live Lab. | its own repo | Deployed |
| **[REACH](reach-app/)** | Music discovery and outreach — finds playlists, blogs, radio and sync outlets that fit a track, keeps evidence behind every claim, routes each opportunity to an approved email or a human task. | `reach-app/` | Ready to deploy |
| **[TRACE](mx-lab/)** | Motocross telemetry and tuning platform — sessions, map workflow, race-day ops, an AI race engineer that recommends but never decides, plus a self-hosted team sync server. | `mx-lab/` | Ready to deploy |
| **Royalty Sweep** | Royalty dashboard — platform balances, payout calendar, catalog value, leak alerts, advance eligibility. The app this repo started as. | repo root | Ready to deploy |
| **[Holeshot Tuner](fuel-map-tool/)** | Single-file fuel-map worksheet for motocross bikes. No server, no build step. | `fuel-map-tool/` | Ready to deploy |

**[▶ Deploy all four to Render](https://render.com/deploy?repo=https://github.com/vkr4wrnhwp-bit/music-artist-hub)** — one click; reads `render.yaml`.

**Details, costs and first-run steps: [DEPLOY.md](DEPLOY.md)** — one Blueprint apply brings up
all four, and it lists what each costs and what Render will prompt you for.
MASTERCLIP OS deploys separately, from its own repository's `render.yaml`.

## Honest state

Each product labels what is real and what is not, in its own UI and its own docs:

- **REACH** — real pipeline, compliance engine, suppression list and audit chain.
  Without search/email credentials it runs against a labeled fixture corpus and
  says so on every screen; it never fabricates a result.
- **TRACE** — telemetry is simulated and bannered on every screen, except where a
  real logger CSV has been imported, which is labeled as measured. No ECU write
  path exists anywhere in the build, by design.
- **Royalty Sweep** — every figure is demonstration data defined in
  `royalty_data.py`, labeled on every screen. Not connected to any royalty
  provider.
- **Holeshot Tuner** — a worksheet. It calculates what you type in; it talks to
  no bike.

## Running the root app (Royalty Sweep)

```bash
pip install -r requirements.txt
python app.py            # http://localhost:5000
pytest                   # 169 tests
ruff check .
```

The other three here have their own READMEs and their own commands — start with
the links in the table above. MASTERCLIP OS is in its own repository.

## Repository layout

```
app.py, royalty_data.py, templates/, music_utils/, tests/   Royalty Sweep
reach-app/                                                  REACH
mx-lab/                                                     TRACE
fuel-map-tool/                                              Holeshot Tuner
render.yaml                                                 all four services
DEPLOY.md                                                   how to deploy them
.github/workflows/                                          one workflow per product
```

Each product has its own workflow, filtered to its own paths, so a change to
REACH does not run TRACE's build and cannot fail its pull request. Editing the
fuel-map worksheet runs nothing: it is one HTML file with no build step.

## Why MASTERCLIP OS is not here

It was, until this commit, in a `masterclip-os/` directory that `render.yaml`
deployed from. Because the product's real repository was elsewhere, every
commit reached production only when someone remembered to copy it across. That
went wrong twice. The copy fell six days and seventeen whole packages behind
without anyone noticing (#55), and later a cost-control fix landed in the copy
while the live service kept shipping without it.

One product, one repository. `tests/test_deployment_blueprint.py` fails if the
directory or its service comes back.

### One thing to carry across first: `APPLY-TO-MASTERCLIP-OS.patch`

The second failure above left a real fix stranded. `isSandboxProvider()` read

```ts
return providerId === 'mock' || this.rt.config.isSandbox
```

`sandbox: true` is the flag the cost controller reads to decide **not** to
enforce, so under `MASTERCLIP_MODE=sandbox` — the default, and what the
blueprint deploys — every real-provider request skipped the live-spend cap, the
approval gate and both price denials, and was then ledgered as sandbox so the
cap never counted it afterwards either. It was fixed in the copy that lived
here and never reached the product, which still ships the original line.

That fix, its regression test and the risk-register entries are in
`APPLY-TO-MASTERCLIP-OS.patch` at the repository root. Apply it upstream:

```bash
git clone https://github.com/vkr4wrnhwp-bit/masterclip-os
cd masterclip-os
git checkout -b sandbox-posture
git am /path/to/APPLY-TO-MASTERCLIP-OS.patch
pnpm install && npx vitest run packages/runtime/test/sandbox-posture.test.ts
git push -u origin sandbox-posture
```

It was built against `5ce21aa` and applies cleanly there; the test passes (4/4)
and the whole workspace typechecks. Restoring the old expression fails three of
the four cases, so the regression cannot come back quietly. **Delete this patch
file once it has landed upstream** — it is a hand-off artifact, not part of
this repository.
