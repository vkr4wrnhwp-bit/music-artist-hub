# music-artist-hub

Five separate products share this repository. They have their own runtimes,
their own tests and their own deployments — the only thing they share is this
repo and `render.yaml`.

| Product | What it is | Where | State |
|---|---|---|---|
| **[MASTERCLIP OS](masterclip-os/)** | Cinematic AI-video render factory — define a shot once, generate it across providers, QC every result, track cost per approved second. Also carries audio intelligence, Song Lab and Live Lab. | `masterclip-os/` | Deployed |
| **[REACH](reach-app/)** | Music discovery and outreach — finds playlists, blogs, radio and sync outlets that fit a track, keeps evidence behind every claim, routes each opportunity to an approved email or a human task. | `reach-app/` | Ready to deploy |
| **[TRACE](mx-lab/)** | Motocross telemetry and tuning platform — sessions, map workflow, race-day ops, an AI race engineer that recommends but never decides, plus a self-hosted team sync server. | `mx-lab/` | Ready to deploy |
| **Royalty Sweep** | Royalty dashboard — platform balances, payout calendar, catalog value, leak alerts, advance eligibility. The app this repo started as. | repo root | Ready to deploy |
| **[Holeshot Tuner](fuel-map-tool/)** | Single-file fuel-map worksheet for motocross bikes. No server, no build step. | `fuel-map-tool/` | Ready to deploy |

**[▶ Deploy all five to Render](https://render.com/deploy?repo=https://github.com/vkr4wrnhwp-bit/music-artist-hub)** — one click; reads `render.yaml`.

**Details, costs and first-run steps: [DEPLOY.md](DEPLOY.md)** — one Blueprint apply brings up
all five, and it lists what each costs and what Render will prompt you for.

## Honest state

Each product labels what is real and what is not, in its own UI and its own docs:

- **MASTERCLIP OS** — the render pipeline, ffmpeg-based QC, budgets and approval
  gates are real. Its seven vendor adapters are written against real specs and are
  callable, but no live provider call has been made from this build; they are
  labeled `DEV-LABELED — no live call` and total spend is $0.00.
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
pytest                   # 111 tests
ruff check .
```

The other four have their own READMEs and their own commands — start with the
links in the table above.

## Repository layout

```
app.py, royalty_data.py, templates/, music_utils/, tests/   Royalty Sweep
masterclip-os/                                              MASTERCLIP OS
reach-app/                                                  REACH
mx-lab/                                                     TRACE
fuel-map-tool/                                              Holeshot Tuner
render.yaml                                                 all five services
DEPLOY.md                                                   how to deploy them
.github/workflows/ci.yml                                    one job per product
```

CI runs a separate job per product on every pull request; a change in one
product does not rebuild or block the others.
