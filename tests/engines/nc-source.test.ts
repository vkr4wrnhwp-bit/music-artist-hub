import { test } from "node:test";
import assert from "node:assert/strict";
import { CONTROLLER_FAMILY_LABEL, inspectSource } from "@/lib/nc/source";
import { parseNC } from "@/lib/nc/parse";

/**
 * What arrived, before anything tries to read it.
 *
 * Seven of the ten upload-provenance facts were recorded. The three that were
 * not are the three that decide whether the program can be read at all: how
 * the bytes decode, how the lines end, and what dialect the file is in.
 */

const enc = (s: string) => new TextEncoder().encode(s);
const PROG = ["%", "O0001", "G20 G17 G90 G54", "G00 X0 Y0", "G01 Z-0.25 F10.", "M30", "%"];

/* ---- line endings, which is where the real damage was ---- */

test("each kind of line ending is named", () => {
  assert.equal(inspectSource(enc(PROG.join("\r\n"))).lineEnding, "CRLF");
  assert.equal(inspectSource(enc(PROG.join("\n"))).lineEnding, "LF");
  assert.equal(inspectSource(enc(PROG.join("\r"))).lineEnding, "CR");
});

test("a file with more than one kind is MIXED, not whichever came first", () => {
  assert.equal(inspectSource(enc("%\r\nO0001\nG00 X0\rM30")).lineEnding, "MIXED");
});

test("a single-line file has no line ending at all", () => {
  assert.equal(inspectSource(enc("G00 X0 Y0")).lineEnding, "NONE");
});

test("the counts are counts, not a guess", () => {
  const s = inspectSource(enc("a\r\nb\nc\rd"));
  assert.deepEqual({ crlf: s.crlf, lf: s.lf, cr: s.cr }, { crlf: 1, lf: 1, cr: 1 });
});

test("a program with bare carriage returns parses like any other", () => {
  // THE BUG. `/\r?\n/` made this ONE line: one segment, zero refusals — a
  // clean report on a program the parser had not read. Clean is what an
  // operator reads as safe.
  const lf = parseNC(PROG.join("\n"));
  const cr = parseNC(PROG.join("\r"));
  const crlf = parseNC(PROG.join("\r\n"));
  assert.equal(cr.lineCount, lf.lineCount, "a CR-only program is read as a different number of lines");
  assert.equal(cr.segments.length, lf.segments.length, "a CR-only program produces different motion");
  assert.equal(crlf.segments.length, lf.segments.length);
  assert.ok(lf.segments.length > 1, "the fixture must produce several segments or this proves nothing");
});

/* ---- encoding ---- */

test("plain ASCII is named as such rather than as UTF-8", () => {
  assert.equal(inspectSource(enc(PROG.join("\n"))).encoding, "US_ASCII");
});

test("a BOM is recognised and removed from the program text", () => {
  // Left in place it becomes the first character of the first block, and the
  // opening line stops parsing.
  const withBom = new Uint8Array([0xef, 0xbb, 0xbf, ...enc(PROG.join("\n"))]);
  const s = inspectSource(withBom);
  assert.equal(s.encoding, "UTF_8_BOM");
  assert.ok(!s.text.startsWith("\uFEFF"), "the BOM is still in the program text");
  assert.equal(s.text.charCodeAt(0), 0x25, "the program no longer starts at %");
  assert.ok(s.text.startsWith("%"), "the program no longer starts where it should");
});

test("a byte that is not valid UTF-8 loses nothing and claims no codepage", () => {
  // 0xB0 is a degree sign in Latin-1 and invalid UTF-8. Decoding as UTF-8
  // anyway substitutes U+FFFD and silently loses what the operator typed.
  const bytes = new Uint8Array([...enc("(FACE TO 20"), 0xb0, ...enc("C)\nM30\n")]);
  const s = inspectSource(bytes);
  assert.equal(s.encoding, "EIGHT_BIT_UNKNOWN");
  assert.ok(!s.text.includes("�"), "a byte was replaced rather than kept");
  assert.equal(s.text.length, bytes.length, "the decode was not lossless");
});

test("UTF-16 is recognised by its byte-order mark", () => {
  const le = new Uint8Array([0xff, 0xfe, 0x25, 0x00]);
  assert.equal(inspectSource(le).encoding, "UTF_16LE");
  const be = new Uint8Array([0xfe, 0xff, 0x00, 0x25]);
  assert.equal(inspectSource(be).encoding, "UTF_16BE");
});

/* ---- dialect ---- */

test("Heidenhain conversational is recognised, with the marker that decided it", () => {
  const s = inspectSource(enc("BEGIN PGM TEST MM\n1 TOOL CALL 5 Z S8000\nEND PGM TEST MM\n"));
  assert.equal(s.controllerFamily, "HEIDENHAIN");
  assert.equal(s.controllerEvidence, "BEGIN PGM");
});

test("Siemens is recognised before word address, not after", () => {
  // A Siemens program contains lines that look like word address; a
  // Fanuc-style file contains none of Siemens' markers.
  const s = inspectSource(enc("N10 G54\nCYCLE81(10,0,2,-15)\nM30\n"));
  assert.equal(s.controllerFamily, "SIEMENS");
  assert.equal(s.controllerEvidence, "CYCLE81(");
});

test("word address is named as a family, never as a vendor", () => {
  const s = inspectSource(enc(PROG.join("\n")));
  assert.equal(s.controllerFamily, "FANUC_STYLE");
  // Haas, Fanuc, Mitsubishi and Brother all emit this and a text file cannot
  // separate them. Naming one would be inventing a fact about the machine.
  for (const label of Object.values(CONTROLLER_FAMILY_LABEL)) {
    assert.ok(!/haas|mitsubishi|brother/i.test(label), `${label} names a vendor the file does not`);
  }
  assert.equal(CONTROLLER_FAMILY_LABEL.FANUC_STYLE, "Fanuc-style word address");
});

test("a file with no distinctive marker gets no family at all", () => {
  // Not a guess, not a default. Null, so nothing downstream reads a dialect
  // that was never established.
  const s = inspectSource(enc("N10 X1.0 Y2.0\nN20 X3.0\n"));
  assert.equal(s.controllerFamily, null);
  assert.equal(s.controllerEvidence, null);
});

test("every family it does claim carries its evidence", () => {
  const samples = [
    "BEGIN PGM A MM\n",
    "CYCLE81(1,2,3,4)\n",
    PROG.join("\n"),
    "g0 x0 y0\ng1 z-0.1 f10\nm30\n",
  ];
  for (const text of samples) {
    const s = inspectSource(enc(text));
    assert.ok(s.controllerFamily, `no family for ${JSON.stringify(text.slice(0, 20))}`);
    assert.ok(s.controllerEvidence, `${s.controllerFamily} claimed with no evidence behind it`);
  }
});
