/**
 * CANVAS SMOKE — the built app, actually running.
 *
 * Boots `next start` against the seeded database, mints a session for the
 * demo user directly in SQLite, requests every workspace route, and makes
 * content assertions on the things most recently changed. Unit tests prove
 * the engines; this proves the pages that assemble them still assemble.
 *
 * Run from the repo root, after `next build` and a seed:
 *
 *   node scripts/smoke.mjs
 *
 * Exit code 0 means every route answered 200 with no error boundary and
 * every content assertion held. SQLite only — the session is minted with
 * a direct INSERT, which is a smoke-test liberty, not an API.
 */
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { DatabaseSync } from "node:sqlite";

const PORT = process.env.SMOKE_PORT ?? "3199";
const BASE = `http://localhost:${PORT}`;
const db = new DatabaseSync("prisma/dev.db");

function mintSession() {
  const u = db.prepare("SELECT id FROM User WHERE email = ?").get("demo@canvas.local");
  if (!u) throw new Error("Demo user not found — run the seed first.");
  const token = "smoke-" + randomBytes(12).toString("hex");
  db.prepare("INSERT INTO Session (id, token, userId, expiresAt, createdAt) VALUES (?,?,?,?,?)").run(
    "sess_" + randomBytes(10).toString("hex"),
    token,
    u.id,
    Date.now() + 1800_000,
    Date.now(),
  );
  return token;
}

const server = spawn("npx", ["next", "start", "-p", PORT], { stdio: "ignore", detached: false });
process.on("exit", () => server.kill());

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(fn, tries = 30) {
  for (let i = 0; i < tries; i++) {
    try { if (await fn()) return; } catch { /* not up yet */ }
    await wait(1000);
  }
  throw new Error("Server did not come up.");
}

let failures = 0;
const fail = (msg) => { failures++; console.error(`FAIL ${msg}`); };
const ok = (msg) => console.log(`ok   ${msg}`);

async function get(path, token) {
  const res = await fetch(BASE + path, { headers: { Cookie: `canvas_session=${token}` } });
  return { status: res.status, body: await res.text() };
}

await until(async () => (await fetch(BASE + "/", { redirect: "manual" })).status > 0);
const token = mintSession();

const partId = db.prepare("SELECT id FROM Part WHERE partNumber = ?").get("CNV-001")?.id;
const latheId = db
  .prepare("SELECT p.id AS id FROM Part p JOIN PartRevision r ON r.partId = p.id JOIN RotationalPart rp ON rp.partRevisionId = r.id LIMIT 1")
  .get()?.id;
if (!partId || !latheId) throw new Error("Seed parts not found.");

/* ---- every route answers, no error boundary ---- */
const routes = [
  "/", `/parts/${partId}`, `/parts/${partId}/setups`, `/parts/${partId}/machinist`,
  `/parts/${partId}/readiness`, `/parts/${partId}/tooling`, `/parts/${partId}/cost`,
  `/parts/${partId}/nc`, `/parts/${partId}/soft-jaws`, `/parts/${partId}/nc-analyzer`,
  "/reverse-engineer", "/lathe", `/lathe/${latheId}`, `/lathe/${latheId}/cost`,
  `/lathe/${latheId}/soft-jaws`, `/lathe/${latheId}/nc-review`,
  "/machines", "/tools", "/materials", "/metrology", "/workholding", "/network", "/settings",
];
for (const path of routes) {
  const { status, body } = await get(path, token);
  if (status !== 200) fail(`${path} -> ${status}`);
  else if (/Application error|Something went wrong/.test(body)) fail(`${path} rendered an error boundary`);
  else ok(path);
}

/* ---- content: the assemblies assemble ---- */
const checks = [
  [`/lathe/${latheId}?op=55`, /Chamfer thread entry/i, "seeded chamfer op on the lathe workspace"],
  [`/lathe/${latheId}?op=55`, /uncompensated/i, "nose-radius warning reaches the operator"],
  [`/lathe/${latheId}`, /Turning readiness/i, "worst-gate readiness panel"],
  ["/reverse-engineer", /Declare the units/i, "scan import form with its units declaration"],
  [`/parts/${partId}/setups`, /holding margin/i, "holding margin block on setups"],
];
for (const [path, re, label] of checks) {
  const { body } = await get(path, token);
  if (re.test(body)) ok(label);
  else fail(`${label} — ${path} lacks ${re}`);
}

server.kill();
if (failures > 0) { console.error(`\n${failures} failure(s).`); process.exit(1); }
console.log("\nSmoke clean: every route answered and every assertion held.");
process.exit(0);
