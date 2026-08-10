/**
 * ISO 10303-21 (STEP Part 21) PARSER — deterministic, dependency-free
 *
 * Parses the DATA section of a STEP physical file into an entity graph:
 * `#12 = CYLINDRICAL_SURFACE('', #10, 20.0);` becomes
 * `{ id: 12, type: "CYLINDRICAL_SURFACE", args: ["", ref(10), 20] }`.
 *
 * This is a *syntax* parser. It knows nothing about geometry; the recognizer
 * on top of it does, and only for the entity types it explicitly handles.
 * There is no model call anywhere in this pipeline — a STEP file is the
 * design authority, and reading it is arithmetic, not inference.
 *
 * Scope honestly stated: single-result entities. Complex (multi-record)
 * instances — `#5 = (A(...) B(...));`, used by some AP214 unit definitions —
 * are captured with type "COMPLEX" and their raw text, enough for the unit
 * sniffing the recognizer does, not full semantics.
 */

export type StepArg =
  | { kind: "REF"; id: number }
  | { kind: "STR"; value: string }
  | { kind: "NUM"; value: number }
  | { kind: "ENUM"; value: string }
  | { kind: "LIST"; items: StepArg[] }
  | { kind: "NULL" }        // $
  | { kind: "DERIVED" };    // *

export interface StepEntity {
  id: number;
  type: string;
  args: StepArg[];
  /** Raw text for COMPLEX instances, otherwise absent. */
  raw?: string;
}

export interface StepFile {
  entities: Map<number, StepEntity>;
  /** HEADER section raw text — FILE_SCHEMA etc. */
  header: string;
  warnings: string[];
}

export function parseStep(text: string): StepFile {
  const warnings: string[] = [];
  const headerMatch = /HEADER;([\s\S]*?)ENDSEC;/.exec(text);
  const dataMatch = /DATA;([\s\S]*?)ENDSEC;/.exec(text);
  if (!dataMatch) {
    return { entities: new Map(), header: headerMatch?.[1] ?? "", warnings: ["No DATA section found — not a STEP Part 21 file?"] };
  }

  const entities = new Map<number, StepEntity>();
  // Statements end with ";" — but strings may contain semicolons, so split
  // with a scanner rather than a naive regex.
  const data = dataMatch[1];
  let i = 0;
  const n = data.length;
  while (i < n) {
    // find start of a statement: '#'
    while (i < n && data[i] !== "#") i++;
    if (i >= n) break;
    const start = i;
    // scan to the terminating ';' outside of any string literal
    let inStr = false;
    while (i < n) {
      const ch = data[i];
      if (inStr) {
        if (ch === "'") {
          if (data[i + 1] === "'") i++; // escaped quote
          else inStr = false;
        }
      } else if (ch === "'") inStr = true;
      else if (ch === ";") break;
      i++;
    }
    const stmt = data.slice(start, i);
    i++; // past ';'

    const m = /^#(\d+)\s*=\s*([\s\S]+)$/.exec(stmt.trim());
    if (!m) continue;
    const id = parseInt(m[1], 10);
    const body = m[2].trim();

    if (body.startsWith("(")) {
      // Complex instance. Keep raw for the unit sniffer.
      entities.set(id, { id, type: "COMPLEX", args: [], raw: body });
      continue;
    }
    const tm = /^([A-Z0-9_]+)\s*\(([\s\S]*)\)$/.exec(body);
    if (!tm) {
      warnings.push(`Unparseable entity #${id}`);
      continue;
    }
    entities.set(id, { id, type: tm[1], args: parseArgs(tm[2]) });
  }

  return { entities, header: headerMatch?.[1] ?? "", warnings };
}

function parseArgs(s: string): StepArg[] {
  const args: StepArg[] = [];
  let i = 0;
  const n = s.length;

  const skipWs = () => {
    while (i < n && /\s/.test(s[i])) i++;
  };

  function parseOne(): StepArg {
    skipWs();
    const ch = s[i];
    if (ch === "#") {
      let j = ++i;
      while (i < n && /\d/.test(s[i])) i++;
      return { kind: "REF", id: parseInt(s.slice(j, i), 10) };
    }
    if (ch === "'") {
      i++;
      let out = "";
      while (i < n) {
        if (s[i] === "'") {
          if (s[i + 1] === "'") { out += "'"; i += 2; continue; }
          i++;
          break;
        }
        out += s[i++];
      }
      return { kind: "STR", value: out };
    }
    if (ch === "(") {
      i++;
      const items: StepArg[] = [];
      skipWs();
      if (s[i] === ")") { i++; return { kind: "LIST", items }; }
      for (;;) {
        items.push(parseOne());
        skipWs();
        if (s[i] === ",") { i++; continue; }
        if (s[i] === ")") { i++; break; }
        break; // malformed; bail without looping forever
      }
      return { kind: "LIST", items };
    }
    if (ch === ".") {
      let j = ++i;
      while (i < n && s[i] !== ".") i++;
      const v = s.slice(j, i);
      i++;
      return { kind: "ENUM", value: v };
    }
    if (ch === "$") { i++; return { kind: "NULL" }; }
    if (ch === "*") { i++; return { kind: "DERIVED" }; }
    // number or bare token (typed parameter like CYLINDRICAL_SURFACE(...) is
    // not expected at arg level in single instances)
    let j = i;
    while (i < n && !",()".includes(s[i])) i++;
    const tok = s.slice(j, i).trim();
    const num = Number(tok);
    if (tok !== "" && Number.isFinite(num)) return { kind: "NUM", value: num };
    return { kind: "STR", value: tok };
  }

  skipWs();
  if (i >= n) return args;
  for (;;) {
    args.push(parseOne());
    skipWs();
    if (i < n && s[i] === ",") { i++; continue; }
    break;
  }
  return args;
}

/* ---------------- accessors ---------------- */

export const asRef = (a: StepArg | undefined): number | null => (a?.kind === "REF" ? a.id : null);
export const asNum = (a: StepArg | undefined): number | null => (a?.kind === "NUM" ? a.value : null);
export const asList = (a: StepArg | undefined): StepArg[] => (a?.kind === "LIST" ? a.items : []);
