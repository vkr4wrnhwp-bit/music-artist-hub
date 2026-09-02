import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { STOCK_BOTTOM_Z, sceneZ, stockTopZ } from "@/components/viewport/part-frame";

/**
 * Where a toolpath is drawn relative to the part it cuts.
 *
 * The scene put the solid's top face at local `stock.z` and the toolpath's
 * Z-zero plane at local `stock.z / 2`, so everything drawn in tool coordinates
 * sat half a stock height inside the material. Clearance is the single thing a
 * machinist looks at a toolpath view to check.
 */

const PLATE = 0.75; // the seeded Bearing Support stock thickness

test("part Z zero is the top face of the stock", () => {
  assert.equal(sceneZ(PLATE, 0), stockTopZ(PLATE));
});

test("a cut goes into the material, never out the bottom of it", () => {
  const cut = sceneZ(PLATE, -0.25);
  assert.ok(cut < stockTopZ(PLATE), "a negative Z must be below the top face");
  assert.ok(cut > STOCK_BOTTOM_Z, "a 0.25 cut in a 0.75 plate must stay inside the stock");
  assert.equal(cut, 0.5);
});

test("clearance is drawn ABOVE the part, which is the whole point of looking", () => {
  // The bug: at zTop = stock.z / 2 a rapid 0.100 above the part rendered at
  // 0.475 while the top face was at 0.750 — a quarter inch INSIDE the solid.
  const rapid = sceneZ(PLATE, 0.1);
  assert.ok(rapid > stockTopZ(PLATE), "a positive Z must clear the top face");
  assert.equal(Math.round(rapid * 1000) / 1000, 0.85);
});

test("a through cut reaches the bottom of the stock exactly", () => {
  assert.equal(sceneZ(PLATE, -PLATE), STOCK_BOTTOM_Z);
});

test("nothing draws in the part frame with its own half-stock offset", () => {
  // The offset that centres the part is carried once, by the enclosing group.
  // Any component that adds `stock.z / 2` again is drawing in a second frame.
  for (const file of ["src/components/viewport/scene.tsx", "src/components/viewport/sim-view.tsx"]) {
    const src = readFileSync(file, "utf8");
    assert.ok(
      !/zTop=\{stock\.z \/ 2\}/.test(src),
      `${file}: the toolpath's Z-zero plane is half a stock height below the top face`,
    );
    assert.ok(
      !/const zOff = stock\.z \/ 2;/.test(src),
      `${file}: the simulation rig re-centres a part the group has already centred`,
    );
  }
});

test("the toolpath and the simulation both take the frame from one place", () => {
  const scene = readFileSync("src/components/viewport/scene.tsx", "utf8");
  const sim = readFileSync("src/components/viewport/sim-view.tsx", "utf8");
  assert.ok(/part-frame/.test(scene), "scene.tsx does not use the shared part frame");
  assert.ok(/part-frame/.test(sim), "sim-view.tsx does not use the shared part frame");
});
