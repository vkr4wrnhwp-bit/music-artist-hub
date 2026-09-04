"use client";

import { useState, useTransition } from "react";
import { Button, Field, inputClass } from "@/components/ui";
import { ProfileSketch } from "./profile-sketch";

type Result = { error: string } | { ok: true; proposalId: string; summary: string };

/**
 * THE PART'S OUTSIDE SHAPE, THE TWO WAYS A SHOP HAS IT.
 *
 * `Feature.chain` was read by the contour engine and written by nothing, so
 * every profile CANVAS posted was a rounded rectangle from three numbers —
 * an L-bracket came out a rectangle and nothing said so.
 *
 * A shop with CAD exports a DXF. A shop working from a napkin, a sample or a
 * phone photo draws it. Both go through the same assembly and the same
 * refusals, and both arrive as a PROPOSAL: geometry a person accepts, never
 * geometry that appeared.
 */
export function ProfileInput({
  importDxf,
  saveDrawn,
  proposalsHref,
}: {
  importDxf: (formData: FormData) => Promise<Result>;
  saveDrawn: (formData: FormData) => Promise<Result>;
  proposalsHref: string;
}) {
  const [mode, setMode] = useState<"NONE" | "DXF" | "DRAW">("NONE");
  const [problem, setProblem] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [pending, start] = useTransition();

  const handle = (r: Result) => {
    if ("error" in r) {
      setProblem(r.error);
      setDone(null);
      return;
    }
    setProblem(null);
    setDone(r.summary);
  };

  return (
    <div className="border border-line bg-raised">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-platinum">Outside profile</p>
          <p className="mt-1 text-[12px] leading-relaxed text-muted">
            The shape of the part, as lines and arcs. Without one, a profile is cut as a rectangle from its width and
            length — which is right for a plate and wrong for everything else.
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button type="button" size="sm" variant={mode === "DXF" ? "primary" : "default"} onClick={() => setMode(mode === "DXF" ? "NONE" : "DXF")}>
            Import DXF
          </Button>
          <Button type="button" size="sm" variant={mode === "DRAW" ? "primary" : "default"} onClick={() => setMode(mode === "DRAW" ? "NONE" : "DRAW")}>
            Draw it
          </Button>
        </div>
      </div>

      {mode !== "NONE" && (
        <div className="px-4 py-4">
          {mode === "DXF" && (
            <form
              action={(fd) => start(async () => handle(await importDxf(fd)))}
              className="flex flex-wrap items-end gap-3"
            >
              <div className="min-w-[16rem] flex-1">
                <Field label="DXF file" required>
                  <input type="file" name="file" accept=".dxf,text/plain" className={inputClass} required />
                </Field>
              </div>
              <div className="w-36">
                <Field label="Profile depth" required hint="A 2D drawing does not say.">
                  <input name="depth" className={inputClass} inputMode="decimal" placeholder="0.750" required />
                </Field>
              </div>
              <div className="w-40">
                <Field label="Units" hint="Only used when the file does not say.">
                  <select name="units" className={inputClass} defaultValue="">
                    <option value="">From the file</option>
                    <option value="IN">Inches</option>
                    <option value="MM">Millimetres</option>
                  </select>
                </Field>
              </div>
              <Button type="submit" variant="primary" size="sm" disabled={pending}>
                {pending ? "Reading…" : "Read the outline"}
              </Button>
              <p className="w-full text-[11px] leading-relaxed text-muted">
                LINE, ARC, CIRCLE and polylines, in model space. Splines and ellipses are named rather than flattened
                into chords — approximating one would cut a shape that is not the drawing.
              </p>
            </form>
          )}

          {mode === "DRAW" && (
            <ProfileSketch
              saving={pending}
              problem={null}
              onSave={(segments, depth) =>
                start(async () => {
                  const fd = new FormData();
                  fd.set("segments", JSON.stringify(segments));
                  fd.set("depth", depth);
                  handle(await saveDrawn(fd));
                })
              }
            />
          )}

          {problem && (
            <p className="mt-3 border border-line border-l-2 border-l-risk bg-void px-3 py-2 text-[12px] leading-relaxed text-platinum">
              {problem}
            </p>
          )}
          {done && (
            <p className="mt-3 border border-line border-l-2 border-l-precision bg-void px-3 py-2 text-[12px] leading-relaxed text-platinum">
              Outline read — {done}. It is a proposal until somebody accepts it:{" "}
              <a href={proposalsHref} className="underline decoration-dotted">
                review it
              </a>
              .
            </p>
          )}
        </div>
      )}
    </div>
  );
}
