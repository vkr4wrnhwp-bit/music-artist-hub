"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui";

/**
 * STEP IMPORT — the other way into CANVAS.
 *
 * Upload a single-part STEP file; the deterministic recognizer proposes
 * features and the proposals screen asks for acceptance. What the recognizer
 * cannot identify it says it cannot identify — the report travels with the
 * part.
 */
export function StepImport() {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<{ busy: boolean; error: string | null }>({ busy: false, error: null });

  async function submit() {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setState({ busy: false, error: "Choose a .step / .stp file first." });
      return;
    }
    setState({ busy: true, error: null });
    const body = new FormData();
    body.append("file", file);
    const res = await fetch("/api/parts/step", { method: "POST", body });
    const json = await res.json().catch(() => null);
    if (!res.ok || !json?.partId) {
      setState({ busy: false, error: json?.error ?? "Import failed." });
      return;
    }
    router.push(json.suggestions > 0 ? `/parts/${json.partId}/proposals` : `/parts/${json.partId}`);
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={fileRef}
          type="file"
          accept=".step,.stp"
          className="text-[12px] text-muted file:mr-3 file:border file:border-line-strong file:bg-surface file:px-3 file:py-1.5 file:text-[11px] file:font-semibold file:uppercase file:tracking-[0.12em] file:text-platinum-dim hover:file:bg-raised"
        />
        <Button onClick={submit} disabled={state.busy}>
          {state.busy ? "Reading geometry…" : "Import STEP"}
        </Button>
      </div>
      {state.error && <p className="text-[12px] leading-relaxed text-risk">{state.error}</p>}
      <p className="text-[11px] leading-relaxed text-muted">
        Single parts only, 2.5D recognition: top-down holes, pocket and slot floors, and the envelope. Everything
        else is reported as unrecognized, not approximated. Recognized features are proposals — nothing becomes
        geometry until you accept it.
      </p>
    </div>
  );
}
