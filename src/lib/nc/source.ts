/**
 * WHAT ARRIVED, BEFORE ANYTHING TRIES TO READ IT.
 *
 * An uploaded program is bytes off somebody's flash drive. Seven facts about
 * where it came from were already recorded — the file, its sha256, when, who,
 * the filename, the byte count — and three were not: how the bytes decode,
 * how the lines end, and what dialect the file is in.
 *
 * The line endings were the reason this mattered. `parse.ts` split on
 * `/\r?\n/`, so a program with bare carriage returns became ONE line: one
 * segment, no refusals, a clean report on a program nothing had read.
 *
 * Nothing here is inferred. Encoding and line endings are counts of bytes.
 * The controller family is null unless a literal marker matched, and the
 * marker travels with the answer so the claim can be checked.
 */

export type SourceEncoding = "US_ASCII" | "UTF_8" | "UTF_8_BOM" | "UTF_16LE" | "UTF_16BE" | "EIGHT_BIT_UNKNOWN";
export type LineEnding = "CRLF" | "LF" | "CR" | "MIXED" | "NONE";

/**
 * A FAMILY, never a vendor.
 *
 * Haas, Fanuc, Mitsubishi, Brother and others all emit `%` + `O1234` +
 * word-address blocks, and a text file cannot tell them apart. Claiming HAAS
 * from a file that says nothing about Haas would be inventing a fact about
 * somebody's machine.
 */
export type ControllerFamily = "FANUC_STYLE" | "SIEMENS" | "HEIDENHAIN" | "GRBL_LINUXCNC";

export const CONTROLLER_FAMILY_LABEL: Record<ControllerFamily, string> = {
  FANUC_STYLE: "Fanuc-style word address",
  SIEMENS: "Siemens",
  HEIDENHAIN: "Heidenhain conversational",
  GRBL_LINUXCNC: "GRBL / LinuxCNC",
};

export const ENCODING_LABEL: Record<SourceEncoding, string> = {
  US_ASCII: "US-ASCII",
  UTF_8: "UTF-8",
  UTF_8_BOM: "UTF-8 with BOM",
  UTF_16LE: "UTF-16 LE",
  UTF_16BE: "UTF-16 BE",
  EIGHT_BIT_UNKNOWN: "8-bit, codepage not declared",
};

export interface SourceInspection {
  /** The decoded program. Never lossy: see EIGHT_BIT_UNKNOWN below. */
  text: string;
  encoding: SourceEncoding;
  lineEnding: LineEnding;
  crlf: number;
  lf: number;
  cr: number;
  /** Null when the file carries no marker that names a dialect. */
  controllerFamily: ControllerFamily | null;
  /** The literal text that decided the family, so the claim is inspectable. */
  controllerEvidence: string | null;
}

function decodeLatin1(bytes: Uint8Array): string {
  let out = "";
  for (const b of bytes) out += String.fromCharCode(b);
  return out;
}

function readEncoding(bytes: Uint8Array): { text: string; encoding: SourceEncoding } {
  if (bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) {
    // TextDecoder strips the BOM itself unless asked not to, and that is the
    // behaviour we want: left in place it becomes the first character of the
    // first block and the program's opening line stops parsing. Recorded as a
    // distinct encoding because it is a fact about the file, not a detail of
    // how it was read.
    return { text: new TextDecoder("utf-8").decode(bytes), encoding: "UTF_8_BOM" };
  }
  if (bytes.length >= 2 && bytes[0] === 0xff && bytes[1] === 0xfe) {
    return { text: new TextDecoder("utf-16le").decode(bytes.subarray(2)), encoding: "UTF_16LE" };
  }
  if (bytes.length >= 2 && bytes[0] === 0xfe && bytes[1] === 0xff) {
    return { text: new TextDecoder("utf-16be").decode(bytes.subarray(2)), encoding: "UTF_16BE" };
  }
  if (bytes.every((b) => b < 0x80)) {
    return { text: new TextDecoder("utf-8").decode(bytes), encoding: "US_ASCII" };
  }
  try {
    return { text: new TextDecoder("utf-8", { fatal: true }).decode(bytes), encoding: "UTF_8" };
  } catch {
    // High bytes that are not valid UTF-8. Decoding them as UTF-8 anyway
    // substitutes U+FFFD, which silently loses a byte the operator typed —
    // usually a degree sign or an accented name in a comment. Latin-1 loses
    // nothing, and the encoding field says plainly that no codepage was
    // declared, so nobody reads the comment as certain.
    return { text: decodeLatin1(bytes), encoding: "EIGHT_BIT_UNKNOWN" };
  }
}

function readLineEndings(text: string): { lineEnding: LineEnding; crlf: number; lf: number; cr: number } {
  const crlf = (text.match(/\r\n/g) ?? []).length;
  const lf = (text.match(/(?<!\r)\n/g) ?? []).length;
  const cr = (text.match(/\r(?!\n)/g) ?? []).length;
  const kinds = [crlf, lf, cr].filter((n) => n > 0).length;
  const lineEnding: LineEnding =
    kinds === 0 ? "NONE" : kinds > 1 ? "MIXED" : crlf > 0 ? "CRLF" : lf > 0 ? "LF" : "CR";
  return { lineEnding, crlf, lf, cr };
}

/**
 * The dialect, or null.
 *
 * Ordered deliberately: Heidenhain and Siemens are tested first because a
 * Siemens program can contain lines that look like word address, while a
 * genuine Fanuc-style file contains none of their markers.
 */
function readControllerFamily(text: string): { family: ControllerFamily | null; evidence: string | null } {
  const heidenhain = /^\s*BEGIN PGM\b/m.exec(text) ?? /^\s*\d+\s+(TOOL CALL|CYCL DEF)\b/m.exec(text);
  if (heidenhain) return { family: "HEIDENHAIN", evidence: heidenhain[0].trim() };

  const siemens = /\bCYCLE\d{2,3}\s*\(/.exec(text) ?? /^\s*MSG\s*\(/m.exec(text) ?? /\b(TRANS|SPOS)\b/.exec(text);
  if (siemens) return { family: "SIEMENS", evidence: siemens[0].trim() };

  const fanuc = /^%/.test(text.trimStart()) && /^O\d{1,5}/m.exec(text);
  if (fanuc) return { family: "FANUC_STYLE", evidence: `% / ${fanuc[0]}` };

  // No leading %, no O-number, lowercase words: the shape a hobby or
  // open-source post emits. Weaker evidence than the others, and it says so.
  if (!/^%/.test(text.trimStart()) && !/^O\d{1,5}/m.test(text) && /^\s*[gm]\d/m.test(text)) {
    return { family: "GRBL_LINUXCNC", evidence: "no % or O-number, lowercase word address" };
  }
  return { family: null, evidence: null };
}

export function inspectSource(bytes: Uint8Array): SourceInspection {
  const { text, encoding } = readEncoding(bytes);
  const { lineEnding, crlf, lf, cr } = readLineEndings(text);
  const { family, evidence } = readControllerFamily(text);
  return { text, encoding, lineEnding, crlf, lf, cr, controllerFamily: family, controllerEvidence: evidence };
}
