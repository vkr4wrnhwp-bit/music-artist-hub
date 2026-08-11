import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { chromium } from "playwright";

/**
 * E2E SMOKE — the checks unit tests cannot make.
 *
 * Boots the built app against the seeded database and walks the demo shop
 * the way a user would: sign in, open the part, hover the readiness gates,
 * open the tablet, open NC output. Assertions are about POSTURE, not pixels:
 * the gate list renders, the tablet never shows a signature over a red gate,
 * the NC page shows its pre-flight. A failure here is a broken page or a
 * broken gate posture that 91 unit tests cannot see.
 *
 * Run: npm run build && npm run db:seed && npm run test:e2e
 * CI installs its own chromium; locally the pre-provisioned build is used.
 */

const PORT = 3941;
const BASE = `http://localhost:${PORT}`;
const LOCAL_CHROMIUM = "/opt/pw-browsers/chromium";

function fail(msg: string): never {
  console.error(`SMOKE FAIL: ${msg}`);
  process.exit(1);
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
  // Detached, own process group: `npx` spawns `next` as a grandchild, and a
  // plain SIGTERM to npx leaves the server orphaned — which keeps a CI step
  // alive forever waiting on its open pipes. Killing the group gets both.
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

    /* ---- sign in ---- */
    await page.goto(`${BASE}/sign-in`);
    await page.fill('input[name="email"]', "demo@canvas.local");
    await page.fill('input[name="password"]', "canvas-demo");
    await page.locator('button[type="submit"]').first().click();
    await page.waitForLoadState("networkidle");
    if (page.url().includes("sign-in")) fail("sign-in did not complete");
    console.log("ok: sign-in");

    /* ---- part workspace ---- */
    await page.goto(`${BASE}/parts`);
    const href = await page.locator('a[href^="/parts/"]:not([href$="/new"])').first().getAttribute("href");
    if (!href) fail("no seeded part in the library");
    await page.goto(BASE + href);
    // First WebGL page after a cold server start can take a while.
    await page.waitForSelector("canvas", { timeout: 60_000 });
    const body = (await page.textContent("body"))!;
    if (!/PART STATUS/i.test(body)) fail("part status module missing");
    if (/\d+\s?% (ready|complete)/i.test(body)) fail("a readiness percentage appeared — gates are not percentages");
    console.log("ok: part workspace renders, no readiness percentage");

    /* ---- readiness gates ---- */
    await page.goto(`${BASE}${href}/readiness`);
    const rBody = (await page.textContent("body"))!;
    if (!/gate/i.test(rBody)) fail("readiness page shows no gates");
    console.log("ok: readiness gates render");

    /* ---- tablet posture ---- */
    await page.goto(`${BASE}${href}/tablet`);
    const tBody = (await page.textContent("body"))!;
    for (const section of ["1 · Setup", "2 · Tools", "3 · Probe", "4 · Run", "5 · Sign-off"]) {
      if (!tBody.includes(section)) fail(`tablet section missing: ${section}`);
    }
    const gatesFailing = /Not ready — \d+ blocking/.test(tBody);
    const signOffered = /Sign off setup/.test(tBody);
    const signBlocked = /no signature line while gates are failing/.test(tBody);
    if (gatesFailing && signOffered) fail("tablet offered a signature over a red gate");
    if (gatesFailing && !signBlocked) fail("tablet failed to explain the withheld signature");
    if (!gatesFailing && !signOffered && !/Signed off/.test(tBody)) fail("gates pass but no sign-off control");
    console.log(`ok: tablet posture (gates ${gatesFailing ? "failing → signature withheld" : "passing → signature available"})`);

    /* ---- NC output gate ---- */
    await page.goto(`${BASE}${href}/nc`);
    const nBody = (await page.textContent("body"))!;
    if (!nBody.includes("Pre-flight check")) fail("NC pre-flight missing");
    if (!/Not certified for production/i.test(nBody)) fail("NC page lost its not-certified notice");
    console.log("ok: NC output gated behind pre-flight");

    /* ---- knowledge page ---- */
    await page.goto(`${BASE}/knowledge`);
    const kBody = (await page.textContent("body"))!;
    if (!/Shop knowledge is not universal knowledge/.test(kBody)) fail("knowledge page scoping notice missing");
    console.log("ok: shop knowledge page");

    await browser.close();
    console.log("SMOKE PASS");
  } finally {
    stopServer();
  }
  // The server's stdio pipes would otherwise keep the event loop alive.
  process.exit(0);
}

main().catch((e) => fail(String(e)));
