# REACH — Integration Setup

REACH runs with **no configuration at all**: discovery falls back to the built-in
fixture corpus and every screen labels it as such. Each variable below unlocks a
real capability. Nothing here is committed to the repository, and no secret is
ever rendered to the browser — templates receive booleans and the *names* of
missing variables.

## Quick start

```bash
pip install -r requirements.txt
python app.py
# open http://127.0.0.1:5000/reach
```

## Core

| Variable | Default | Purpose |
| --- | --- | --- |
| `REACH_DB_PATH` | `reach.db` beside `app.py` | SQLite path, or `:memory:` |
| `REACH_ENCRYPTION_KEY` | ephemeral per process | Fernet key for contact values at rest. **Set this in production** — without it, stored contacts cannot be decrypted after a restart, and Provider Health says so |
| `REACH_PRINCIPAL_EMAIL` | `owner@streetbanker.local` | Acting principal until REACH has sessions |
| `REACH_PRINCIPAL_ROLE` | `OWNER` | One of `OWNER`, `ADMIN`, `CAMPAIGN_MANAGER`, `REVIEWER`, `ANALYST`, `VIEW_ONLY` |

Generate a key:

```python
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Open-web search

| Variable | Purpose |
| --- | --- |
| `REACH_SEARCH_API_KEY` | Brave Search API key, or Google Programmable Search API key |
| `REACH_SEARCH_BACKEND` | `brave` (default) or `google_cse` |
| `REACH_SEARCH_CSE_ID` | Required for `google_cse` |

Without this, discovery uses the fixture corpus and every result is tagged
`FIXTURE`. **External requirement:** a paid search API subscription.

## YouTube Data API

| Variable | Purpose |
| --- | --- |
| `REACH_YOUTUBE_API_KEY` | API key from a Google Cloud project with YouTube Data API v3 enabled |

Quota is accounted per request (search = 100 units, list = 1, of 10,000/day).
**External requirement:** a Google Cloud project; a quota increase needs an
audit request to Google.

## SoundCloud

| Variable | Purpose |
| --- | --- |
| `REACH_SOUNDCLOUD_CLIENT_ID` | OAuth client id |
| `REACH_SOUNDCLOUD_CLIENT_SECRET` | OAuth client secret |

**External requirement:** SoundCloud API application approval. Registration has
been intermittently closed; confirm current availability.

## Mixcloud

| Variable | Purpose |
| --- | --- |
| `REACH_MIXCLOUD_CLIENT_ID` / `REACH_MIXCLOUD_CLIENT_SECRET` | OAuth application |

## MusicBrainz and ListenBrainz

No credential required. MusicBrainz needs the identifying User-Agent REACH
already sends and is throttled to one request per second. ListenBrainz uses
public endpoints only in Phase One.

## Spotify

| Variable | Purpose |
| --- | --- |
| `REACH_SPOTIFY_CLIENT_ID` / `REACH_SPOTIFY_CLIENT_SECRET` | Web API application |
| `REACH_SPOTIFY_QUOTA_MODE` | `DEVELOPMENT_MODE` (default) or `EXTENDED_QUOTA` — displayed verbatim |

**External requirement:** a Spotify developer application; Extended Quota Mode
requires a separate application to Spotify. Read the hard restrictions in
`PROVIDER_POLICY_MATRIX.md` before enabling — they are enforced in code and will
raise rather than bend.

## Email delivery and sender health

| Variable | Purpose |
| --- | --- |
| `REACH_EMAIL_API_KEY` | Transactional provider API key |
| `REACH_EMAIL_API_URL` | Provider endpoint (defaults to a Resend-shaped API) |
| `REACH_EMAIL_WEBHOOK_SECRET` | Shared secret for `X-Reach-Signature` on `/reach/webhooks/email` |
| `REACH_SENDER_FROM` | From address, e.g. `reach@outreach.yourdomain.com` |
| `REACH_SENDER_NAME` | Display name |
| `REACH_SENDER_POSTAL_ADDRESS` | **Required.** Physical address in every message |
| `REACH_SENDER_COUNTRY` | Sender country code, default `US` |
| `REACH_SENDER_DKIM_SELECTOR` | **Required for DKIM.** The selector your provider issued, e.g. `resend` — REACH looks up `<selector>._domainkey.<domain>` |
| `REACH_SENDER_SPF_VERIFIED` | Fallback only, used when the DNS lookup itself fails |
| `REACH_SENDER_DKIM_VERIFIED` | Fallback only, same condition |
| `REACH_SENDER_DMARC_VERIFIED` | Fallback only, same condition |
| `REACH_SENDER_DOMAIN_VERIFIED` | Declared when DNS lookups are unavailable in the environment |

**External requirements before any outreach:**

1. A dedicated outreach subdomain (keeps reputation off transactional mail).
2. SPF, DKIM and DMARC published and verified for that subdomain.
3. A transactional provider account with bounce and complaint webhooks pointed
   at `/reach/webhooks/email`.
4. A real physical postal address.

**REACH now verifies SPF, DKIM and DMARC itself** by querying DNS
(`reach/dns_checks.py`, via `dnspython`). Three outcomes are kept distinct:

* the record was found — PASS, and the check quotes what was actually read;
* the lookup succeeded and the record is absent — **FAIL**, because you have not
  published it;
* the lookup itself failed (no resolver, timeout, SERVFAIL) — UNKNOWN.

The `*_VERIFIED` variables are now a fallback for the third case only. Setting
one turns an UNRESOLVED check into a PASS whose detail reads *"declared, not
checked by REACH"* — it cannot mask a record that is genuinely missing.

DMARC alignment additionally requires an **enforcing** policy: `p=none`
publishes intent without asking receivers to act, so it reports UNKNOWN with
that reason stated rather than passing.

## Optional

| Variable | Purpose |
| --- | --- |
| `REACH_EPK_BASE_URL` | Base URL for the single listening/EPK link in pitches |
| `REACH_LLM_API_KEY` | Reserved. The language-model provider is `DISABLED` in Phase One; pitch generation is deterministic |
| `REACH_FLAG_<FLAG_NAME>` | Overrides a feature flag, e.g. `REACH_FLAG_REACH_COPILOT_EMAIL=false` |

## Approval and authorization still required (not configuration)

| Provider | What is needed |
| --- | --- |
| Apple Music | Distributor or label editorial relationship. No automated pitch API exists |
| Amazon Music | Artist-account access; broader Web API access needs granted approval |
| Pandora AMP | Distribution to Pandora, U.S. rights, a claimed artist account |
| Audiomack | Creator account |
| TIDAL | Developer access granted in writing |
| Deezer | Commercial-use permission |
| TikTok | Creator Marketplace, business product or research access, after app review |
| Instagram / Meta | Business/professional product access, after app review |
| Chartmetric, Soundcharts, Viberate, Songstats | A licensed data agreement |
| SubmitHub, Groover, Playlist Push, SoundCampaign | A commercial arrangement; these are paid-consideration platforms |
| DJ pools, college-radio and sync databases | A licensed or contractual arrangement |

Until each of these exists, the corresponding provider stays `MANUAL_ONLY` or
`APPROVAL_REQUIRED`, `require_capability` refuses every call, and the work
appears in the NEEDS YOU queue with the reason stated.

## Deployment notes

* SQLite suits a single-process deployment. For multiple workers, move to
  PostgreSQL — the SQL is portable and the job runner already claims rows with a
  conditional update.
* Start the background job worker with `reach.jobs.start_worker()` in a
  long-running process. The web `Run discovery` action drains the queue
  synchronously, which is fine for the fixture corpus and small live runs.
* **Deploying REACH.** `reach-app/render.yaml` is REACH's own Render blueprint,
  separate from the TRACE blueprint at the repository root — neither deploys the
  other. `reach-app/Dockerfile` is the container equivalent. Both need
  `REACH_DB_PATH` pointing at a mounted disk so the SQLite store survives a
  restart; without one REACH still runs, but its data resets on every deploy.
* **`REACH_ENCRYPTION_KEY` is not optional in production.** Without it the
  process encrypts with an ephemeral key, which means contact records written
  before a restart cannot be read after one. Provider Health says so on screen.
  Generate it once and keep it: rotating it makes existing rows unreadable.
