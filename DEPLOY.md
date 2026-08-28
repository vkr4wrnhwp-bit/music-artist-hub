# Deploying everything in this repo

Three apps ship from this repository. `render.yaml` deploys all of them in
one Blueprint apply.

| Service | What it is | Render type | Cost |
|---|---|---|---|
| `trace` | TRACE telemetry & tuning platform — app **and** team sync server on one origin | Node web service | paid (persistent disk) or free without the disk |
| `royalty-sweep` | Royalty Sweep royalty dashboard (Flask) | Python web service | free tier |
| `holeshot-tuner` | Holeshot Tuner fuel-map tool, single HTML file | Static site | free |

## Deploy (desktop, ~5 minutes)

1. [dashboard.render.com](https://dashboard.render.com) → **New → Blueprint**.
2. Connect this GitHub repository. Render reads `render.yaml` and lists the
   three services.
3. **Apply.** First build takes a few minutes (npm install + Vite build for
   TRACE; pip install for the Flask app; the static site is instant).
4. Each service gets its own `https://<name>-xxxx.onrender.com` URL, listed
   on the Render dashboard. That's what you share.

### Free-plan option
The `trace` service asks for a 1 GB persistent disk, which needs Render's
cheapest paid instance. To trial everything at zero cost, delete the `disk:`
block **and** the `plan: starter` line from `render.yaml` before applying.
Everything runs; only server-side TRACE data (passwords, invites, org
snapshots, telemetry chunks) resets on each deploy or restart — browsers keep
their local databases and re-push on the next sync.

Free instances also sleep when idle: the first request after a quiet period
takes ~30–60 seconds to wake. Normal, not a fault.

## First run of TRACE (do this in one sitting)

1. Open the `trace` URL. The page **is** the app.
2. Sign in as an admin or manager (Alex Ferro / Sam Calloway). The first
   sign-in **sets that account's password** and claims the organization.
3. **More → Team Sync** — the server URL is prefilled with the site's own
   origin. Enter the password, **Sign in to server**, then **Sync now**.
   The footer showing `synced to team server (rev 1)` means it worked.
4. From then on the bootstrap door is closed: new accounts need one-time
   invite codes from **More → Team & roles → Invite**. External tuners never
   get accounts — mint a grant token on the Remote Tuner Access screen and
   send them the URL / org id / token trio for `#/grantview`.

## Smoke test after deploy

- `https://<trace>/` renders the app (dark UI, circuit logo, SIMULATED banner).
- `https://<trace>/orgs/x/db` returns a JSON 401 — the API is gated.
- `https://<royalty-sweep>/` redirects to `/dashboard` and renders.
- `https://<holeshot-tuner>/` renders the tuner.

## After deploy

Auto-deploy is on: every push to `main` rebuilds the affected services.
TLS is automatic on all three, which is what TRACE's bearer tokens need.
Custom domains, backups, and the account lifecycle are covered in
`mx-lab/docs/architecture/deployment.md`.
