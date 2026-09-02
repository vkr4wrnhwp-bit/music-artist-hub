import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { chromium } from "playwright";

const PORT = 3943;
const BASE = `http://localhost:${PORT}`;
const LOCAL_CHROMIUM = "/opt/pw-browsers/chromium";

function fail(msg: string): never { console.error(`FAIL: ${msg}`); process.exit(1); }

async function waitForServer(t: number) {
  const s = Date.now();
  while (Date.now() - s < t) {
    try { const r = await fetch(BASE, { redirect: "manual" }); if (r.status > 0) return; } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }
  fail("server never came up");
}

async function main() {
  const server = spawn("npx", ["next", "start", "-p", String(PORT)], { stdio: "pipe", detached: true });
  process.on("exit", () => { try { if (server.pid) process.kill(-server.pid, "SIGTERM"); } catch {} });
  await waitForServer(60_000);
  const browser = await chromium.launch(existsSync(LOCAL_CHROMIUM) ? { executablePath: LOCAL_CHROMIUM, args: ["--use-gl=angle"] } : {});
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.setDefaultTimeout(30_000);

  await page.addInitScript(() => { try { window.localStorage.setItem("canvas.guideCard", "closed"); } catch {} });
  await page.goto(`${BASE}/sign-in`);
  await page.fill('input[name="email"]', "demo@canvas.local");
  await page.fill('input[name="password"]', "canvas-demo");
  await page.locator('button[type="submit"]').first().click();
  await page.waitForLoadState("networkidle");
  if (page.url().includes("sign-in")) fail("sign-in did not complete");
  console.log("ok: signed in");

  // ---- create a NEW PART from the command bar (STEP import) ----
  await page.goto(`${BASE}/parts/new`);
  await page.locator('input[accept=".step,.stp"]').setInputFiles({
    name: "journey-plate.stp", mimeType: "application/octet-stream",
    buffer: readFileSync("tests/fixtures/journey.stp"),
  });
  await page.locator('button:has-text("Import STEP")').click();
  await page.waitForURL(/\/proposals$/, { timeout: 30_000 }).catch(() => fail("no proposals"));
  const partId = page.url().split("/parts/")[1].split("/")[0];
  console.log(`ok: NEW PART created from IMPORT CAD -> ${partId}`);

  await page.locator('button:has-text("Accept")').first().click();
  await page.waitForLoadState("networkidle");
  console.log("ok: proposals accepted into geometry");

  // ---- define stock (dismiss the guide overlay that blocks clicks) ----
  await page.goto(`${BASE}/parts/${partId}`);
  await page.waitForSelector("canvas");
  const collapse = page.locator('button[aria-label="Collapse the guide sheet"]');
  if (await collapse.count()) await collapse.click().catch(() => {});
  const dataBtn = page.locator("button", { hasText: /^DATA$/i }).first();
  if (!(await dataBtn.isVisible())) {
    const expand = page.locator('button[aria-label="Expand the feature panel"]');
    if (await expand.count()) await expand.click({ force: true });
    await dataBtn.waitFor({ state: "visible", timeout: 15_000 }).catch(() => fail("feature panel never expanded"));
  }
  await dataBtn.click({ force: true });
  await page.locator("button", { hasText: /^Stock$/i }).first().click({ force: true });
  await page.locator('input[name="x"]').waitFor({ timeout: 15_000 }).catch(() => fail("stock form unreachable"));
  await page.locator('input[name="x"]').fill("4.25");
  await page.locator('input[name="y"]').fill("3.25");
  await page.locator('input[name="z"]').fill("0.625");
  await page.locator('input[name="material"]').fill("Aluminum 6061");
  await page.locator('button:has-text("Define stock")').click({ force: true });
  await page.locator('input[name="x"]').waitFor({ state: "detached", timeout: 20_000 }).catch(() => fail("stock did not save"));
  console.log("ok: stock defined");

  // ---- THE CLAIMED DEAD END ----
  await page.goto(`${BASE}/parts/${partId}/machinist`);
  const body1 = (await page.textContent("body"))!;
  if (/No machine is available/.test(body1)) fail("DEAD END CONFIRMED: 'No machine is available'");
  const chooser = /Which machine will run this part\?/.test(body1);
  console.log(`machine chooser rendered: ${chooser}`);
  if (!chooser) fail("no chooser and no assignment — unexpected state");

  // pick the machine
  const pick = page.locator('a[href*="/machinist?machine="]').first();
  if (!(await pick.count())) fail("chooser lists no machines");
  const href = await pick.getAttribute("href");
  console.log(`ok: chooser offers a machine -> ${href}`);
  await pick.click();
  await page.waitForLoadState("networkidle");

  const body2 = (await page.textContent("body"))!;
  const approve = page.locator('button:has-text("Approve")').first();
  if (!(await approve.count())) fail("no approvable approach offered after choosing a machine");
  if (await approve.isDisabled()) fail("approve disabled after choosing a machine");
  console.log("ok: approaches scored and an Approve button is live");
  await approve.click({ force: true });
  await page.waitForLoadState("networkidle");
  console.log("ok: approach APPROVED");

  // ---- did a Setup actually get written with a machineId? ----
  await page.goto(`${BASE}/parts/${partId}`);
  await page.waitForSelector("canvas");
  const fBody = (await page.textContent("body"))!;
  const opMatch = fBody.match(/OPERATION PLAN\s*[▾▸]?\s*(\d+) operations/i);
  console.log("operation plan on part page:", opMatch ? opMatch[0] : "NOT FOUND");
  console.log(`PARTID=${partId}`);
  await browser.close();
  process.exit(0);
}
main();
