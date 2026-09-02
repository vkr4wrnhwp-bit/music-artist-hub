import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

/**
 * What a dimension was measured FROM.
 *
 * `Measurement.datumId` has been in the schema since it was written, with the
 * sentence explaining why it matters sitting right above it: a number without
 * it is not reproducible, because the next person measures from a different
 * edge and gets a different answer that is equally defensible. Nothing ever
 * wrote it. Every measurement in the system was an isolated number, and the
 * schema comment was the only place the rule existed.
 */

const API = "src/app/api/measurements/route.ts";
const FORM = "src/components/reverse/guided-measurement.tsx";
const PAGE = "src/app/(app)/reverse-engineer/[id]/page.tsx";

test("the schema still states the rule", () => {
  const schema = readFileSync("prisma/schema.prisma", "utf8");
  assert.ok(/datumId\s+String\?/.test(schema), "Measurement.datumId is gone");
  assert.ok(/A number without this is not\s*\n?\s*\/\/ reproducible/.test(schema), "the reason was removed from the schema");
});

test("the measurement API accepts and stores a datum", () => {
  const src = readFileSync(API, "utf8");
  assert.ok(/datumId: z\.string\(\)/.test(src), "the API does not accept a datum");
  assert.ok(/datumId: datum\?\.id \?\? null/.test(src), "the API accepts a datum and then does not store it");
});

test("the datum is resolved against this revision, never trusted", () => {
  const src = readFileSync(API, "utf8");
  // A submitted id must not be able to name another part's datum, or another
  // shop's. The session's own revision is the only scope.
  assert.ok(
    /partRevisionId: session\.partRevisionId/.test(src),
    "the submitted datum id is not scoped to the session's revision",
  );
  assert.ok(!/datumId: input\.datumId/.test(src), "the API writes the submitted id straight onto the measurement");
});

test("only an established datum can be measured from", () => {
  const src = readFileSync(API, "utf8");
  // Accepting a datum is a human act. Measuring from a proposal nobody has
  // agreed to records a reference that does not exist yet.
  assert.ok(/acceptedByUser: true/.test(src), "an unaccepted datum proposal can be measured from");
  // Scoped to the datum refusal — the route has other 400s.
  assert.ok(
    /not an established datum on this revision\."\s*\},\s*\{ status: 400 \}/.test(src),
    "a datum that does not qualify is silently dropped rather than refused with a status",
  );
});

test("the form offers established datums and only those", () => {
  const form = readFileSync(FORM, "utf8");
  const page = readFileSync(PAGE, "utf8");
  assert.ok(/name="datumId"/.test(form), "there is no way to say what a reading was measured from");
  assert.ok(/datumId: String\(formData\.get\("datumId"\)\)/.test(form), "the form collects a datum and never sends it");
  // Scoped to the prop handed to the form — the page filters accepted datums
  // elsewhere too, and matching that one proves nothing about this one.
  const prop = /datums=\{([\s\S]{0,240}?)\}\n/.exec(page);
  assert.ok(prop, "the form is not handed any datums");
  assert.ok(
    /\.filter\(\(d\) => d\.acceptedByUser\)/.test(prop![1]),
    "the form is handed datum proposals that nobody has accepted",
  );
});

test("a reading with no datum says so rather than reading as reproducible", () => {
  const form = readFileSync(FORM, "utf8");
  // The failure to avoid is a bare number that looks as trustworthy as one
  // with a reference behind it.
  assert.ok(/no datum recorded/.test(form), "a measurement without a datum is presented as if it were reproducible");
  assert.ok(
    /this reading is not reproducible/.test(form),
    "the empty option does not say what leaving it empty costs",
  );
});
