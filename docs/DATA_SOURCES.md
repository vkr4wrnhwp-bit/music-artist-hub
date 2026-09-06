# Data sources — which key lights which page, and which seams are still empty

Every provider is switched on by environment variables in Render's UI
(the owner sets those; keys never pass through chat or the repo). The
pages say "not configured" until then. This file says, honestly, which
adapters are *implemented* and which are only *declared* — a declared
adapter with a key would light a "configured" badge and answer nothing.

## Implemented and live

| Provider | Env | Pages it feeds |
| --- | --- | --- |
| Spotify Web API | `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI` | Artist Pulse, pre-saves, artist search |
| ElevenLabs | `ELEVENLABS_API_KEY` + lane flags (`docs/AUDIO_OPERATIONS.md`) | Audio Studio, Remix Lab plans |
| Resend | `RESEND_API_KEY`, `RESEND_INBOUND_DOMAIN`, `RESEND_WEBHOOK_SECRET`, `EMAIL_FROM` | Mail out, statements in by email |
| Stripe | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Billing |
| Cloudflare R2 | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | Uploads, audio outputs |
| Bandsintown | `BANDSINTOWN_APP_ID` (awaiting their approval) | EPK tour dates |
| MusicBrainz (keyless) | — | Catalog: songwriter and publisher credits by ISRC (`music_apis.musicbrainz_credits`) |
| Google News RSS (keyless) | — | Press finder on the EPK |
| **MusicBrainz for Signal** | `MUSICBRAINZ_ENABLED=1`, `MUSICBRAINZ_CONTACT=<email>` | Signal: artist identity, releases, labels — free, no account. Measures nothing (no listeners, cities or distributor), and says so. |
| **Soundcharts** | `SOUNDCHARTS_ENABLED=1`, `SOUNDCHARTS_APP_ID`, `SOUNDCHARTS_API_KEY` | Signal: identity, Spotify monthly listeners + followers series, city breakdown, playlists, social counts, events, album label/UPC/distributor. Adapter verified against their public sandbox (`tests/test_signal_soundcharts.py`, live test behind `SOUNDCHARTS_SANDBOX_LIVE=1`). |
| **ACRCloud** | `ACRCLOUD_HOST`, `ACRCLOUD_ACCESS_KEY`, `ACRCLOUD_ACCESS_SECRET` | Beats: a fingerprint *check* the producer runs (`POST /beats/<id>/identify`) — a slice of the beat, or a clip they found, against ACRCloud's index of released recordings. Every run is stored; a match becomes a usage case marked `fingerprint` only when they press the button. Not monitoring: nothing crawls or listens on its own. Free tier covers it. |

## Declared only — a key does nothing until the adapter is written

| Provider | Env it expects | Would feed | Status |
| --- | --- | --- | --- |
| Chartmetric | `CHARTMETRIC_ENABLED`, `CHARTMETRIC_REFRESH_TOKEN` | Same family | **Stub.** |
| The MLC | `MLC_ENABLED`, `MLC_API_KEY` | Mechanicals, Clean Release, Recovery | **Stub.** The member API needs a publisher account and a request to The MLC. |
| SoundExchange | `SOUNDEXCHANGE_ENABLED`, `SOUNDEXCHANGE_API_KEY` | Neighboring rights, Recovery | **Stub**, and no public API exists today. |
| Spotify metadata for Signal | `SPOTIFY_METADATA_ENABLED` | Signal identity and releases from Spotify | **Stub** (the Pulse integration is separate and real). |

## The registry rule (`signal_providers.ProviderRegistry`)

The demo provider answers only while nothing real is configured. Once
one real provider exists, any capability no real provider covers returns
*none* and the page reads "not measured". A real artist with invented
listener numbers beside their name would be the fabrication this product
refuses everywhere else, so demo mode is all-or-nothing.

## Order to switch things on

1. `MUSICBRAINZ_ENABLED=1` + `MUSICBRAINZ_CONTACT` — free, immediate, real.
2. `BANDSINTOWN_APP_ID` — when Bandsintown answers the application.
3. Soundcharts — the adapter exists and is sandbox-verified. A plan must
   include: artist search + metadata, current stats, streaming audience
   (listening and local), audience (followers), albums + album metadata,
   playlists, events. Endpoints a plan lacks answer 403 and read "not
   measured"; nothing is guessed. Their public sandbox credentials
   (`soundcharts`/`soundcharts`) run the adapter on two real artists and
   are for development only - never set them on the live service.
4. ACRCloud — the three keys from the console's project page (host is the
   region host, e.g. `identify-us-west-2.acrcloud.com`).
5. The MLC member API — apply as a publisher; adapter after access.

## What no API exists for

Capital (fan passes, crowdfunding, futures — regulated securities),
Funding (advance lenders work by application), Conflicts (no
cross-society conflict feed). These pages are parked; see
`PARKED_PAGES.md`.
