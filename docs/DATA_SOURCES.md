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
| Stripe | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Billing; fan-club memberships; TOUR VIP packages sold through a date's public link (`/vip/<token>`, one-time Checkout tagged `kind=tour_vip`, claimed by the webhook or the success redirect, never twice). `VIP_PLATFORM_FEE_PCT` (default 15) is Street Banker's cut, recorded per sale; payouts to the artist are settled outside the app and the ledger says so. |
| Cloudflare R2 | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | Uploads, audio outputs |
| Shopify Admin | `SHOPIFY_DOMAIN` + `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET` from the app's settings in Shopify's Dev Dashboard (the app mints its own 24-hour Admin token by the client credentials grant, and its own permanent Storefront token once; the app's released version must carry `read_customers` and the `unauthenticated_read_product_listings` / `unauthenticated_write_checkouts` scopes, and the app and store must be in the same Shopify organization). Legacy `SHOPIFY_ADMIN_TOKEN` / `SHOPIFY_STOREFRONT_TOKEN` still win when set. | Fan CRM: import the store's customers whose email-marketing consent is *subscribed* (`POST /links/fans/import/shopify`, `shopify_customers.py`); others are counted and skipped. The Buy Buttons use the Storefront token, a separate key. |
| Bandsintown | `BANDSINTOWN_APP_ID` | Bandsintown declined to issue an app_id (2026-09-07); dormant. `bandsintown_provider.py` and `BandsintownAdapter` stay in the code unchanged and inert. EPK and Signal dates come from TOUR (`tour_dates.py`). |
| TOUR itself (first-party) | — | EPK tour dates and Signal live dates: the artist's confirmed and advanced shows (`tour_dates.upcoming`; holds never, past dates never). Signal's `TourDatesAdapter` answers only for the signed-in owner's own act, matched to the tour's artist name. It is a real adapter under the registry's all-or-nothing rule: for a viewer with a confirmed date the mock stands down for every capability and anything no real source covers is "not measured". Rows the mock ingested earlier stay fictional, so the Signal shell keeps its demo banner while any mock-seeded artist is still on screen (`signal_store.seeded_by`). No display cap: the EPK lists and counts every upcoming date. "Today" is the tour's home_tz day, the clock TOUR keeps, not the server's. |
| MusicBrainz (keyless) | — | Catalog: songwriter and publisher credits by ISRC (`music_apis.musicbrainz_credits`) |
| Google News RSS (keyless) | — | Press finder on the EPK |
| **MusicBrainz for Signal** | `MUSICBRAINZ_ENABLED=1`, `MUSICBRAINZ_CONTACT=<email>` | Signal: artist identity, releases, labels — free, no account. Measures nothing (no listeners, cities or distributor), and says so. |
| **Soundcharts** | `SOUNDCHARTS_ENABLED=1` plus `SOUNDCHARTS_CLIENT_ID` + `SOUNDCHARTS_CLIENT_SECRET` (OAuth client credentials, optional `SOUNDCHARTS_TEAM_ID`; the bearer token is minted at `account.soundcharts.com/oauth/token`, kept in the key/value store and re-minted on expiry or a 401). `SOUNDCHARTS_APP_ID` + `SOUNDCHARTS_API_KEY` still work for integrations that were issued them; the client pair wins when both are set. | Signal: identity, Spotify monthly listeners + followers series, city breakdown, playlists, social counts, events, album label/UPC/distributor. Adapter verified against their public sandbox (`tests/test_signal_soundcharts.py`, live test behind `SOUNDCHARTS_SANDBOX_LIVE=1`); every 200 answer is cached in the app's key/value store for six hours (`SOUNDCHARTS_CACHE_S` overrides, `0` disables; errors are never cached). |
| **The MLC** | `MLC_ENABLED=1`, `MLC_USERNAME`, `MLC_PASSWORD` | Signal rights evidence (work match by ISRC or title + artist, writers with IPIs, publishers and whether collection shares total 100). Track Passports (`/tracks/<id>`) have a check button (`POST /tracks/<id>/mlc`) that runs `MLCAdapter.lookup()` on the ISRC, or the title + artist name, keeps every answer, and can fill EMPTY passport fields from a match; `MLC registration` is filled only from a match by ISRC. Recovery (`/recovery`) sweeps every passport ISRC (`POST /recovery/mlc`, `recovery_mlc.py`, table `recovery_mlc_sweeps`, 25 a run) and offers a case on every gap; Mechanicals (`/mechanicals`) shows the same sweep beside the income, each row crossed with what that title earned in the stream. Access: register for the Public Search API at the form linked from themlc.com/dataprograms (publicapi@themlc.com); OpenAPI at `https://public-api.themlc.com/api/doc`. |
| **ACRCloud** | `ACRCLOUD_HOST`, `ACRCLOUD_ACCESS_KEY`, `ACRCLOUD_ACCESS_SECRET` | Beats: a fingerprint *check* the producer runs (`POST /beats/<id>/identify`) — a slice of the beat, or a clip they found, against ACRCloud's index of released recordings. Every run is stored; a match becomes a usage case marked `fingerprint` only when they press the button. Not monitoring: nothing crawls or listens on its own. Free tier covers it. |
| **Eventbrite** | `EVENTBRITE_TOKEN` (a private token from eventbrite.com/platform/api-keys, sent as `Authorization: Bearer`) | TOUR: a date's ticket fields from the event that sells it (`eventbrite_provider.py`, matching in `tour_tickets.py`). Sync ticket sales on the tour home walks `/users/me/organizations/` then `/organizations/{id}/events/?status=live,started,ended&expand=venue,ticket_availability` (paged by `pagination.continuation`, 200 events a run) and reads `/events/{id}/ticket_classes/` for `quantity_sold` + `quantity_total`. A show matches an event only on the same local date AND either a shared word in the room's name (`venue_photos.same_room`) or the artist billed in the same city; zero or several candidates is listed as unmatched with the events' names, and one press links the right one for good (`eventbrite_event_id` on `tour_show_ext`). It writes `tickets_sold`, `ticket_status` (on sale / sold out / ended), `capacity` only when empty, and `ticket_url` only over an empty field or another Eventbrite link — a URL typed to another ticketer is never overwritten. A synced count says when it was read; a typed one is labelled typed. Each request spends at most `TICKETS_BUDGET_S` (30s) asking. Without the token the tour home says so and names the variable. |
| **Google Geocoding + Time Zone** (+ Routes, if enabled) | `GOOGLE_MAPS_API_KEY` — the *same* key as Places below; three more APIs switched on for its project (Geocoding API and Time Zone API are on as of 2026-09-09, Routes API is **not**) | TOUR: where each room is (`venue_geo.py`). **Fetch coordinates** on the tour home walks the venue records the dates point at and geocodes each one once — `GET /maps/api/geocode/json?place_id=…` when the Places lookup already matched an exact record, else `?address=<street, city, region, country>` — writing `lat`, `lng`, `geocoded_at` and the address Google matched (`geo_address`) onto `tour_venues`. A record with only a name is skipped, never geocoded: the best match for a bare venue name is anywhere in the world. A hand-typed lat/lng is never replaced. The point is then sent to `GET /maps/api/timezone/json?location=&timestamp=` for the room's IANA zone, and any date whose own zone is blank takes it (`tz_source='venue'` on `tour_show_ext`, so the date page can say "time zone from the venue's location" and a zone somebody typed is never credited to Google or overwritten). The filled zone is what the day sheet, My Day and the `.ics` export print. Statuses read from the body, not the HTTP code: `OK` / `ZERO_RESULTS` (Google does not know the address — "not found", not an error) / `REQUEST_DENIED`, `OVER_QUERY_LIMIT`, `OVER_DAILY_LIMIT`, `INVALID_REQUEST` (kept as a refusal with Google's own `error_message` and reported instead of calling the rooms not found) / `UNKNOWN_ERROR` (retryable; a quiet None). The route page (`/tours/<id>/map`) then labels every leg: **driving, Google Routes** when `POST routes.googleapis.com/directions/v2:computeRoutes` (headers `X-Goog-Api-Key` + `X-Goog-FieldMask: routes.distanceMeters,routes.duration`) measured one, **straight line** — haversine, no duration — when it did not. Routes is a separate API on the same key: the first refusal switches it off for the process and the report says what to enable. Measured drives are cached in `app_kv` by coordinate pair, so a page render never calls Google. An overnight is flagged only when a *measured* duration plus an entered bus call/curfew and load-in show the arrival landing after load-in; no duration is ever inferred from a distance. Each request spends at most `GEO_BUDGET_S` (30s) asking, and the run reports what it did not reach. Without the key the tour home and the route page say so. |
| **ACRCloud Console API** | `ACRCLOUD_CONSOLE_TOKEN` (a console token, minted in the ACRCloud console, beside the identify key/secret above - a different credential on a different host) | The ACRCloud registry (`/fingerprints`, `acr_console.py` + `acr_desk.py`). Three scopes, one job each: **`read-buckets`** lists the account's custom buckets and file-scanning containers (`GET /api/buckets`, `GET /api/fs-containers` on `api-v2.acrcloud.com`) so the page can name a real bucket instead of guessing one; **`write-audios`** registers one of the owner's own Vault masters into a bucket (`POST /api/buckets/:bucket_id/files`, multipart `file` + `title` + `data_type=audio` + `user_defined`, on the region host `api-<region>.acrcloud.com`), which is what makes that recording findable at all; **`read-filescanning`** starts and reads a scan of a long recording - a DJ set, a livestream rip, a podcast (`POST` then `GET /api/fs-containers/:container_id/files/:file_ids`, whose answer carries both the state and, once state is 1, `results.music[]` with `db_begin_time_offset_ms`, `db_end_time_offset_ms` and `score`). Tables `acr_registrations` (UNIQUE on user + vault file, so a master is never sent twice), `acr_scans`, `acr_scan_hits`. A detection whose acrid matches one of this account's registrations lights a lamp and offers a usage case at amount 0 carrying the file, the timestamp, the confidence and the ISRC as evidence. Nothing polls: a scan advances when somebody presses Check again. No bucket or container is ever created for you - the page says what to make in your own console. |
| **Google Places (New)** | `GOOGLE_MAPS_API_KEY` | TOUR: a venue's photo beside its date, looked up by venue name + city when a show is created or on Fetch venue photos; credit shown wherever the photo is, as Google requires (`venue_photos.py`; the top hit is kept only when its name shares a word with the venue's, and the matched name + address are shown beside the credit so the owner can check it is the room; a same-named venue in another city is its own record; an owner's upload is never replaced; each request spends at most `PHOTO_BUDGET_S` (30s) asking, and Fetch venue photos reports what it did not reach; without the key the page says so and draws the monogram). |

## Declared only — a key does nothing until the adapter is written

| Provider | Env it expects | Would feed | Status |
| --- | --- | --- | --- |
| Chartmetric | `CHARTMETRIC_ENABLED`, `CHARTMETRIC_REFRESH_TOKEN` | Same family | **Stub.** |
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
2. ~~`BANDSINTOWN_APP_ID`~~ — Bandsintown declined the application (2026-09-07); TOUR is the dates source instead.
3. Soundcharts — the adapter exists and is sandbox-verified. A plan must
   include: artist search + metadata, current stats, streaming audience
   (listening and local), audience (followers), albums + album metadata,
   playlists, events. Endpoints a plan lacks answer 403 and read "not
   measured"; nothing is guessed. Their public sandbox credentials
   (`soundcharts`/`soundcharts`) run the adapter on two real artists and
   are for development only - never set them on the live service.
4. ACRCloud — the three keys from the console's project page (host is the
   region host, e.g. `identify-us-west-2.acrcloud.com`).
5. The MLC — the adapter exists; it needs the Public Search API login
   The MLC issues after registration (the portal login is not it).
6. `GOOGLE_MAPS_API_KEY` — a Google Cloud key with Places API (New)
   enabled; TOUR then fetches a photo of each room as its dates are made.
7. `EVENTBRITE_TOKEN` — the private token on the account's API Keys
   page. Read-only here: TOUR never creates, edits or cancels an event.

## What no API exists for

Capital (fan passes, crowdfunding, futures — regulated securities),
Funding (advance lenders work by application), Conflicts (no
cross-society conflict feed). These pages are parked; see
`PARKED_PAGES.md`.
