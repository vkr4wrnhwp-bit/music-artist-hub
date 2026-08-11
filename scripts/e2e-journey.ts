import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { chromium } from "playwright";

/**
 * E2E JOURNEY — STEP file to operation plan, the way a customer part arrives.
 *
 * Upload a synthetic STEP plate (one hole, one rectangular pocket) → accept
 * the recognizer's proposals → define stock (the import deliberately leaves
 * it unknown: the allowance is a machining decision) → pick and approve a
 * machinist approach → confirm the plan exists with real toolpaths.
 *
 * This test exists because the chain broke silently once: every stage worked
 * alone, and an imported part still dead-ended because nothing let a human
 * define stock after intake. Posture checks per stage, no pixel assertions.
 */

const PORT = 3942;
const BASE = `http://localhost:${PORT}`;
const LOCAL_CHROMIUM = "/opt/pw-browsers/chromium";

function fail(msg: string): never {
  console.error(`JOURNEY FAIL: ${msg}`);
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

    /* ---- STEP upload ---- */
    await page.goto(`${BASE}/parts/new`);
    const stepText = readFileSync("tests/fixtures/journey.stp");
    await page.locator('input[accept=".step,.stp"]').setInputFiles({
      name: "journey-plate.stp",
      mimeType: "application/octet-stream",
      buffer: stepText,
    });
    await page.locator('button:has-text("Import STEP")').click();
    await page.waitForURL(/\/proposals$/, { timeout: 30_000 }).catch(() => fail(`upload did not land on proposals: ${page.url()}`));
    const partId = page.url().split("/parts/")[1].split("/")[0];
    console.log("ok: STEP uploaded, proposals pending");

    /* ---- accept proposals ---- */
    const pBody = (await page.textContent("body"))!;
    if (!/RECT_POCKET|pocket/i.test(pBody)) fail("recognizer proposed no pocket");
    if (!/DRILLED_HOLE|hole/i.test(pBody)) fail("recognizer proposed no hole");
    await page.locator('button:has-text("Accept")').first().click();
    await page.waitForLoadState("networkidle");
    console.log("ok: proposals accepted into geometry");

    /* ---- define stock ---- */
    await page.goto(`${BASE}/parts/${partId}`);
    await page.waitForSelector("canvas");
    // The stock panel lives in the right-hand DATA pane.
    await page.locator("button", { hasText: /^DATA$/i }).first().click();
    await page.locator("button", { hasText: /^Stock$/i }).first().click();
    const xInput = page.locator('input[name="x"]');
    await xInput.waitFor({ timeout: 15_000 }).catch(() => fail("stock definition form not reachable"));
    await xInput.fill("4.25");
    await page.locator('input[name="y"]').fill("3.25");
    await page.locator('input[name="z"]').fill("0.625");
    await page.locator('input[name="material"]').fill("Aluminum 6061");
    await page.locator('button:has-text("Define stock")').click();
    // The server action revalidates the route; wait for the form to give way
    // to the recorded values rather than racing the refresh.
    await page
      .locator('input[name="x"]')
      .waitFor({ state: "detached", timeout: 20_000 })
      .catch(() => fail("stock form did not resolve after submit"));
    const sBody = (await page.textContent("body"))!;
    if (!/4\.25 × 3\.25 × 0\.625/.test(sBody)) fail("defined stock did not render");
    console.log("ok: stock defined (4.25 × 3.25 × 0.625 Aluminum 6061)");

    /* ---- machinist approach ---- */
    await page.goto(`${BASE}/parts/${partId}/machinist`);
    const mBody = (await page.textContent("body"))!;
    if (/Stock is not defined/.test(mBody)) fail("machinist still blocked on stock");
    const approve = page.locator('button:has-text("Approve")').first();
    if (!(await approve.count())) fail("no approvable approach offered");
    if (await approve.isDisabled()) fail("approve button disabled — approach has errors");
    await approve.click();
    await page.waitForLoadState("networkidle");
    console.log("ok: machinist approach approved");

    /* ---- plan exists with real toolpaths ---- */
    await page.goto(`${BASE}/parts/${partId}`);
    await page.waitForSelector("canvas");
    const fBody = (await page.textContent("body"))!;
    const opMatch = fBody.match(/OPERATION PLAN\s*(\d+) operations/i);
    if (!opMatch || Number(opMatch[1]) < 1) fail("no operation plan after approval");
    if (!/min cut time/i.test(fBody)) fail("no cycle time — toolpaths missing");
    console.log(`ok: operation plan exists (${opMatch[1]} operations with cycle time)`);

    await browser.close();
    console.log("JOURNEY PASS");
  } finally {
    stopServer();
  }
  process.exit(0);
}

main().catch((e) => fail(String(e)));
