# CANVAS

**Precision Manufacturing Intelligence**

_From concept to cut._

PLAN │ MACHINE │ DELIVER

---

CANVAS is not AI CAM software. It is the beginning of an AI manufacturing
operating system whose job is to answer:

> "I need this made. Figure everything else out."

It answers three questions, in this order:

**Can I make it?** — Can these machines, tools, workholding and materials
produce this component safely and accurately?

**Should I make it?** — Is CNC machining actually the right method, or should
this be purchased, cast, forged, formed, cut, printed, molded or turned?
CANVAS is allowed to say *"you should not machine this."*

**Who should make it?** — This machine, another machine, an outside supplier,
or someone who already makes it at a hundred times the volume?

The initial wedge is 3-axis milling in a real job shop. Everything is
architected so CNC is one process among many.

## Running it

```bash
cp .env.example .env
npm install                 # also generates the Prisma client
npm run db:migrate          # creates prisma/dev.db
npm run db:seed             # demo shop + TEST PART 001
npm run dev
```

Sign in at `http://localhost:3000/sign-in`:

```
demo@canvas.local / canvas-demo
```

No API key, no external services, no network. The intake parser is a real
grammar, not a stub — CANVAS is fully usable out of the box. To enable the full
copilot, set `CANVAS_AI_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` server-side.

## Deploying it

CANVAS runs on three database homes from one codebase and one schema — local
SQLite, Turso, or PostgreSQL — with the driver chosen from the connection
string. The smallest live deployment is Vercel plus a free Turso database:
because Turso is SQLite over the network, the committed migrations apply to it
unchanged. Import the repo, set `DATABASE_URL`, deploy; the build migrates and
seeds itself.

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the steps, what is verified,
and the real limitations of a serverless deployment.

## The five-minute demo

Open **CANVAS Bearing Support** from the part library.

1. **Part** — the Part Intent Model, every field showing its source and whether
   a human confirmed it. Load bearing, safety critical and failure consequence
   are deliberately unanswered; the panel says so and blocks process advice.
2. **Workholding** — Setup 2 grips 0.080" where the model wants 0.140". It is
   flagged `HIGH RISK` with the reason, the estimated cutting load, and four
   concrete actions. A real job (J-1042) already failed exactly this way.
3. **Soft jaws** — generate a jaw pair with a machined seat and the eight-step
   process to cut them. Saving updates the grip and re-runs the assessment.
4. **Reverse engineer** — a bore measured at 1.5744" with a bore gauge. CANVAS
   recognises 40 mm (1.5748") at ~97% confidence, shows the deviation and the
   basis, and offers **Accept 40 mm** / **Keep measured value** / **Investigate**.
   It will not change a critical dimension for you.
5. **NC output** — a real Haas program from the deterministic engine. Export is
   disabled because the workholding gate fails. That is the product working.
6. **Cost** — unit cost from the actual generated cycle time, quantity breaks,
   and a make-vs-buy panel that refuses to invent a supplier price.

## What is real, and what is not

Everything under `src/lib/engines/` is real, deterministic and testable in
isolation: the toolpath engine, the workholding model, nominal reasoning, the
readiness gates, the cost engine, the process advisor, the post processors.

Where a capability is not implemented, the interface says so — `DEVELOPMENT`,
`SIMULATION ONLY`, `NOT IMPLEMENTED`, `SHELL`. There are no buttons that appear
to run a collision check and merely play an animation.

`docs/BUILD_STATUS.md` is the authoritative list.

## Non-negotiables

An LLM never emits machine motion. The AI layer never invents a machine, tool or
material you do not own. Responsibility is asked, never inferred. Every
significant value carries its source and confidence, and AI inference never
satisfies an engineering gate. Nothing exports without a named human.

`docs/MANUFACTURING_SAFETY.md` is the document the rest of the system obeys.

## Documentation

| | |
|---|---|
| [ARCHITECTURE](docs/ARCHITECTURE.md) | Stack, layering, data flow, extension seams |
| [MANUFACTURING_SAFETY](docs/MANUFACTURING_SAFETY.md) | Provenance, hard rules, critical applications |
| [CAM_ENGINE](docs/CAM_ENGINE.md) | The pipeline, what is implemented, known limits |
| [REVERSE_ENGINEERING](docs/REVERSE_ENGINEERING.md) | Photo sets, metrology, nominal reasoning |
| [NETWORK_PRIVACY](docs/NETWORK_PRIVACY.md) | Sharing levels, the fingerprint, what never leaves |
| [FUTURE_MANUFACTURING](docs/FUTURE_MANUFACTURING.md) | Processes beyond CNC, volume crossovers |
| [CANVAS_ROADMAP](docs/CANVAS_ROADMAP.md) | Phases 2–6 and the decisions taken |
| [BUILD_STATUS](docs/BUILD_STATUS.md) | Done / in progress / next / blocked |
| [DEPLOYMENT](docs/DEPLOYMENT.md) | Vercel + Postgres, dual-provider schema, known limits |

## Stack

Next.js 16 · TypeScript · React 19 · Tailwind v4 · Three.js (R3F) · Prisma 7 ·
SQLite in development, PostgreSQL-ready.
