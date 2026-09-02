import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { selectPrimaryMachine } from "@/lib/package-selectors";

/**
 * A part created in the app must be able to reach a plan.
 *
 * The deadlock this pins: `selectPrimaryMachine` reads the machine off an
 * existing setup, and setups are only written when a plan is approved, which
 * needed a machine. A new part had no setup, so no machine, so the planner
 * refused, so no setup ever got written. Only seeded parts — which arrive
 * with setups — worked, which is why it survived every test in this suite.
 */

const PAGE = "src/app/(app)/parts/[id]/machinist/page.tsx";

test("a part with no setups has no assigned machine — that much is correct", () => {
  const machines = [{ id: "m1" }, { id: "m2" }];
  assert.equal(selectPrimaryMachine([], machines), null);
  assert.equal(selectPrimaryMachine([{ machineId: null }], machines), null);
});

test("the assignment is read off the setup, never guessed from the crib", () => {
  const machines = [{ id: "m1" }, { id: "m2" }];
  assert.equal(selectPrimaryMachine([{ machineId: "m2" }], machines)?.id, "m2");
  // A setup naming equipment the shop no longer owns resolves to nothing
  // rather than to the first machine on the list.
  assert.equal(selectPrimaryMachine([{ machineId: "gone" }], machines), null);
});

test("an unassigned part is offered the choice instead of being refused", () => {
  const src = readFileSync(PAGE, "utf8");
  assert.ok(
    !/!pkg\.primaryMachine\s*\n?\s*\?\s*"No machine is available/.test(src),
    "the planner still dead-ends a part that has no setup yet",
  );
  // Declared AND rendered — a flag nothing branches on is not a way in.
  assert.ok(
    /const needsMachineChoice = [^\n]*pkg\.machines\.length > 0/.test(src),
    "the chooser is not offered when the shop has machines but the part has no setup",
  );
  assert.ok(
    /\) : needsMachineChoice \? \(/.test(src),
    "nothing renders the machine chooser",
  );
  assert.ok(
    /href=\{`\/parts\/\$\{id\}\/machinist\?machine=\$\{m\.id\}`\}/.test(src),
    "the chooser lists no machines to choose from",
  );
  assert.ok(
    /pkg\.machines\.length === 0/.test(src),
    "the only honest block is a shop with no machines on file at all",
  );
});

test("the choice is resolved against the shop's own machines, not trusted", () => {
  const src = readFileSync(PAGE, "utf8");
  // Organisation comes from the session; a request parameter may only ever
  // select among what that organisation owns.
  assert.ok(
    /pkg\.machines\.find\(\(m\) => m\.id === machine\)/.test(src),
    "the machine search param is not matched against the organisation's machines",
  );
  assert.ok(
    /fresh\.machines\.find\(\(m\) => m\.id === chosenId\)/.test(src),
    "the approve action does not resolve the submitted machine id against the organisation's machines",
  );
  assert.ok(
    !/machineId: chosenId/.test(src),
    "the approve action writes a submitted id straight onto a setup",
  );
});

test("no fallback to the first machine in the crib was reintroduced", () => {
  // Planning against equipment nobody chose is an invented input: the
  // approach scoring is a property of the machine's travels, spindle, rapid
  // and feed limits, so the wrong machine produces confident wrong answers.
  for (const file of [PAGE, "src/lib/package.ts", "src/lib/package-selectors.ts"]) {
    const src = readFileSync(file, "utf8");
    assert.ok(
      !/machines\[0\]/.test(src.replace(/^\s*(\/\/|\*).*$/gm, "")),
      `${file} falls back to the first machine in the crib`,
    );
  }
});
