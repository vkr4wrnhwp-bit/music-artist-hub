/**
 * TOOL LIST IMPORT — the document the CAM system already produced
 *
 * A program whose tools are not in the crib gets no engagement bands and no
 * reach check, and the audit gate tells the operator to go type the tools in
 * by hand. They already have the list; this reads it.
 *
 * What it deliberately does NOT do:
 *
 * - It does not create crib records. A CAM tool list is a description of one
 *   job's tooling, not the shop's record of what it owns and has measured.
 *   Entries are context for THIS analysis and are discarded with it.
 * - It does not supply a chipload window. Chipload limits are manufacturer
 *   data about a specific cutter, and no CAM export carries them; inventing
 *   a window would put a feed proposal in front of an operator with nothing
 *   behind it. Tools known only from a list therefore get geometry — a
 *   diameter for engagement, a stickout for reach — and no feed proposal.
 * - It does not guess units. A 6 mm cutter read as 6 inch is a scrapped part
 *   and possibly a broken spindle, and no header convention distinguishes
 *   them reliably. The caller states the units of the document; without that
 *   there is no import.
 * - It does not guess columns. An unidentifiable header is reported as an
 *   unread column rather than positionally assumed.
 */

export type ToolListUnits = "IN" | "MM";

export interface ToolListEntry {
  toolNumber: number;
  description: string;
  /** Inches, converted on the way in. */
  diameter: number;
  flutes: number;
  /** Null when the document does not carry it — never a substituted value. */
  fluteLength: number | null;
  stickout: number | null;
}

export interface ToolListImport {
  entries: ToolListEntry[];
  /** Rows read and rejected, with the reason, so nothing vanishes silently. */
  refusals: { row: number; reason: string }[];
  /** Headers present in the file that this importer does not understand. */
  unreadColumns: string[];
  /** Which header each field was taken from, for the receipt. */
  columns: Partial<Record<keyof ToolListEntry, string>>;
  units: ToolListUnits;
}

/** Header synonyms. Matched case- and punctuation-insensitively. */
const SYNONYMS: Record<keyof ToolListEntry, string[]> = {
  toolNumber: ["tool", "t", "toolnumber", "toolno", "toolnum", "tnumber", "number", "no", "tool#", "t#", "pocket"],
  description: ["description", "comment", "name", "toolname", "tooldescription", "type", "tooltype"],
  diameter: ["diameter", "dia", "d", "cutterdiameter", "tooldiameter", "cuttingdiameter"],
  flutes: ["flutes", "flute", "teeth", "numberofflutes", "flutecount", "nflutes"],
  fluteLength: ["flutelength", "loc", "lengthofcut", "cuttinglength", "cutlength", "fluteln"],
  stickout: ["stickout", "projection", "extension", "gaugelength", "toolprojection", "protrusion"],
};

const norm = (s: string) => s.trim().toLowerCase().replace(/[\s_\-.()"']/g, "");

/**
 * Splits on comma or tab, honouring double quotes. CAM exports are commonly
 * one or the other and a description with a comma in it is ordinary.
 */
function splitRow(line: string, delimiter: string): string[] {
  const out: string[] = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') { cur += '"'; i++; }
      else quoted = !quoted;
    } else if (ch === delimiter && !quoted) { out.push(cur); cur = ""; }
    else cur += ch;
  }
  out.push(cur);
  return out.map((c) => c.trim());
}

function pickDelimiter(header: string): string {
  return header.split("\t").length > header.split(",").length ? "\t" : ",";
}

/** A number, or null. Rejects an empty cell rather than reading it as zero. */
function num(raw: string | undefined): number | null {
  if (raw === undefined) return null;
  const t = raw.trim().replace(/^[ø⌀Ø]/, "").replace(/(mm|in|")$/i, "").trim();
  if (t === "") return null;
  const v = Number(t);
  return Number.isFinite(v) ? v : null;
}

export function parseToolList(text: string, units: ToolListUnits): ToolListImport {
  const scale = units === "MM" ? 1 / 25.4 : 1;
  const refusals: ToolListImport["refusals"] = [];
  const columns: ToolListImport["columns"] = {};
  const lines = text.split(/\r\n|\r|\n/);

  // The header is the first non-blank line that is not a comment. CAM
  // exports commonly precede it with a title line; a header we cannot read
  // is a refusal, not a reason to count columns positionally.
  let headerIndex = -1;
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i].trim();
    if (l === "" || l.startsWith("#") || l.startsWith(";")) continue;
    headerIndex = i;
    break;
  }
  if (headerIndex === -1) {
    return { entries: [], refusals: [{ row: 0, reason: "The file is empty." }], unreadColumns: [], columns, units };
  }

  const delimiter = pickDelimiter(lines[headerIndex]);
  const header = splitRow(lines[headerIndex], delimiter);
  const index: Partial<Record<keyof ToolListEntry, number>> = {};
  const used = new Set<number>();
  // Exact match on the normalized header, never a substring: "Tool Diameter"
  // must not be claimed by the "tool" synonym for tool number. `used` stops
  // one column being read as two fields.
  for (const field of Object.keys(SYNONYMS) as (keyof ToolListEntry)[]) {
    for (const syn of SYNONYMS[field]) {
      const at = header.findIndex((h, i) => !used.has(i) && norm(h) === syn);
      if (at !== -1) { index[field] = at; used.add(at); columns[field] = header[at].trim(); break; }
    }
  }
  const unreadColumns = header.filter((h, i) => h.trim() !== "" && !used.has(i)).map((h) => h.trim());

  const missing = (["toolNumber", "diameter", "flutes"] as const).filter((f) => index[f] === undefined);
  if (missing.length > 0) {
    return {
      entries: [],
      refusals: [{
        row: headerIndex + 1,
        reason: `No column read as ${missing.join(", ")}. Header was: ${header.join(" | ")}. Rename the column or add one — nothing here is taken by position.`,
      }],
      unreadColumns,
      columns,
      units,
    };
  }

  const entries: ToolListEntry[] = [];
  const seen = new Map<number, number>();
  for (let i = headerIndex + 1; i < lines.length; i++) {
    const raw = lines[i];
    if (raw.trim() === "" || raw.trim().startsWith("#") || raw.trim().startsWith(";")) continue;
    const row = i + 1;
    const cells = splitRow(raw, delimiter);

    const tRaw = cells[index.toolNumber!] ?? "";
    const t = num(tRaw.replace(/^t/i, ""));
    if (t === null || !Number.isInteger(t) || t <= 0) {
      refusals.push({ row, reason: `Tool number "${tRaw}" is not a positive whole number.` });
      continue;
    }
    const diameter = num(cells[index.diameter!]);
    if (diameter === null || diameter <= 0) {
      refusals.push({ row, reason: `T${t}: diameter "${cells[index.diameter!] ?? ""}" is not a positive number. Engagement cannot be computed from it.` });
      continue;
    }
    const flutes = num(cells[index.flutes!]);
    if (flutes === null || !Number.isInteger(flutes) || flutes <= 0) {
      refusals.push({ row, reason: `T${t}: flute count "${cells[index.flutes!] ?? ""}" is not a positive whole number.` });
      continue;
    }
    if (seen.has(t)) {
      refusals.push({ row, reason: `T${t} appears again — the first row (line ${seen.get(t)}) is kept. Two tools cannot share one T number in one program.` });
      continue;
    }
    seen.set(t, row);

    const fluteLength = index.fluteLength === undefined ? null : num(cells[index.fluteLength]);
    const stickout = index.stickout === undefined ? null : num(cells[index.stickout]);
    entries.push({
      toolNumber: t,
      description: (index.description === undefined ? "" : (cells[index.description] ?? "").trim()) || `T${t} (from attached list)`,
      diameter: diameter * scale,
      flutes,
      fluteLength: fluteLength === null || fluteLength <= 0 ? null : fluteLength * scale,
      stickout: stickout === null || stickout <= 0 ? null : stickout * scale,
    });
  }

  if (entries.length === 0 && refusals.length === 0) {
    refusals.push({ row: headerIndex + 1, reason: "The file has a readable header and no tool rows under it." });
  }
  return { entries, refusals, unreadColumns, columns, units };
}
