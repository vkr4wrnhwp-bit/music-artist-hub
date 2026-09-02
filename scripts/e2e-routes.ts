import { spawn } from "node:child_process";
import { existsSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "playwright";

/**
 * E2E ROUTES — does every page still render?
 *
 * The smoke suite walks one path deeply and says nothing about the other
 * thirty screens. This walks all of them, shallowly: sign in, open every
 * route the navigation offers and every part subroute that exists on disk,
 * and fail on a 4xx/5xx, a Next error boundary, or an uncaught client error.
 *
 * The route list is DISCOVERED, not hand-kept — a hand-kept list is how you
 * end up sweeping a route that was renamed a year ago and missing the four
 * that were added since. Directories under src/app/(app)/parts/[id]/ are the
 * source of truth for part subroutes; a `[param]` directory is skipped
 * because there is no index there to open.
 *
 * Run: npm run build && npm run db:seed && npm run test:e2e:routes
 */

const PORT = 3942;
const BASE = `http://localhost:${PORT}`;
const LOCAL_CHROMIUM = "/opt/pw-browsers/chromium";
const PART_ROUTES = "src/app/(app)/parts/[id]";
const APP_ROUTES = "src/app/(app)";

function fail(msg: string): never {
  console.error(`ROUTES FAIL: ${msg}`);
  process.exit(1);
}

/** Directories that are real, openable routes — not dynamic segments. */
function subroutes(dir: string): string[] {
  return readdirSync(dir)
    .filter((e) => !e.startsWith("[") && statSync(join(dir, e)).isDirectory())
    .filter((e) => existsSync(join(dir, e, "page.tsx")))
    .sort();
}

async function waitForServer(timeoutMs: number): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(BASE, { redirect: "manual" });
      if (res.status > 0) return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  fail(`server did not answer on :${PORT} within ${timeoutMs}ms`);
}

async function main() {
  // Detached, own process group — see the note in e2e-smoke.ts.
  const server = spawn("npx", ["next", "start", "-p", String(PORT)], { stdio: "pipe", detached: true });
  const stopServer = () => {
    try {
      if (server.pid) process.kill(-server.pid, "SIGTERM");
    } catch {
      /* already gone */
    }
  };
  process.on("exit", stopServer);

  try {
    await waitForServer(60_000);
    const browser = await chromium.launch(
      existsSync(LOCAL_CHROMIUM) ? { executablePath: LOCAL_CHROMIUM, args: ["--use-gl=angle"] } : {},
    );
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    page.setDefaultTimeout(30_000);

    const clientErrors: string[] = [];
    page.on("pageerror", (e) => clientErrors.push(`${page.url()} — ${e.message}`));

    await page.goto(`${BASE}/sign-in`);
    await page.fill('input[name="email"]', "demo@canvas.local");
    await page.fill('input[name="password"]', "canvas-demo");
    await page.locator('button[type="submit"]').first().click();
    await page.waitForLoadState("networkidle");
    if (page.url().includes("sign-in")) fail("sign-in did not complete");

    // The demo Bearing Support: the training part has no setups by design and
    // several subroutes would render their empty state rather than the page.
    await page.goto(`${BASE}/parts`);
    const links = page.locator('a[href^="/parts/"]:not([href$="/new"])');
    let part: string | null = null;
    for (let i = 0; i < (await links.count()); i++) {
      if (/Bearing Support/.test((await links.nth(i).textContent()) ?? "")) {
        part = await links.nth(i).getAttribute("href");
        break;
      }
    }
    part = part ?? (await links.first().getAttribute("href"));
    if (!part) fail("no seeded part in the library");

    const top = subroutes(APP_ROUTES).map((r) => `/${r}`);
    const parts = subroutes(PART_ROUTES).map((r) => `${part}/${r}`);
    const routes = ["/", ...top, part, ...parts];

    const broken: string[] = [];
    for (const route of routes) {
      try {
        const res = await page.goto(BASE + route, { waitUntil: "domcontentloaded" });
        const status = res?.status() ?? 0;
        const body = (await page.textContent("body")) ?? "";
        // A Next error boundary answers 200 with an apology on it, so status
        // alone is not enough.
        const errored = /Application error|Internal Server Error|Unhandled Runtime Error/i.test(body);
        if (status >= 400 || errored) {
          broken.push(`${status} ${route}${errored ? " (error boundary)" : ""}`);
          console.log(`FAIL ${status} ${route}`);
        } else if (body.trim().length < 200) {
          broken.push(`${status} ${route} (rendered almost nothing)`);
          console.log(`FAIL ${status} ${route} — ${body.trim().length} chars`);
        } else {
          console.log(`ok   ${status} ${route}`);
        }
      } catch (e) {
        broken.push(`${route}: ${(e as Error).message.slice(0, 120)}`);
        console.log(`FAIL --- ${route}`);
      }
    }

    await browser.close();

    if (clientErrors.length > 0) {
      clientErrors.slice(0, 10).forEach((e) => console.error(`  client error: ${e}`));
      fail(`${clientErrors.length} uncaught client error(s)`);
    }
    if (broken.length > 0) fail(`${broken.length} route(s) did not render:\n  ${broken.join("\n  ")}`);
    console.log(`\nROUTES PASS — ${routes.length} routes rendered`);
  } finally {
    stopServer();
  }
}

void main();
