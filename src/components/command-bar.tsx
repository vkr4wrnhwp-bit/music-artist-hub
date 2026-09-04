"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { buttonClass } from "./ui";

/**
 * The intelligent command bar. It accepts a description, files, or a hand-off
 * to reverse engineering — but everything it produces goes through the intake
 * pipeline, not straight into a part.
 */

const ACCEPTS: Record<string, string> = {
  photo: "image/*",
  drawing: "application/pdf,image/*",
  cad: ".step,.stp,.stl,.dxf,.svg,.iges,.igs,.x_t,.sldprt",
};

export function CommandBar() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [pending, start] = useTransition();
  const [uploadMode, setUploadMode] = useState<string | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);

  const describe = () => {
    if (!prompt.trim()) return;
    setError(null);
    start(async () => {
      const res = await fetch("/api/parts/intake", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      if (!res.ok) {
        setError("Intake failed. The description was not converted into a part.");
        return;
      }
      const { partId } = await res.json();
      router.push(`/parts/${partId}?intake=1`);
    });
  };

  return (
    <div className="space-y-3">
      <div className="datum-frame border border-line-strong bg-surface focus-within:border-precision/60">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) describe();
          }}
          rows={3}
          placeholder={`Make a 6 x 4 x .500 aluminum plate with four 1/4-20 holes, rounded corners, a .125 deep center pocket and engraved text.`}
          className="w-full resize-none bg-transparent px-4 py-3.5 text-[13px] leading-relaxed text-platinum placeholder:text-muted/70 focus:outline-none"
        />
        <div className="flex items-center justify-between border-t border-line px-3 py-2">
          <span className="tech-label">{prompt.length > 0 ? `${prompt.length} characters` : "⌘↵ to submit"}</span>
          <button onClick={describe} disabled={pending || !prompt.trim()} className={buttonClass("primary", "sm")}>
            {pending ? "Parsing…" : "Describe"}
          </button>
        </div>
      </div>

      {/*
        FOUR WAYS IN, EACH SAYING WHAT IT ACTUALLY DOES.

        These were four identical small outline buttons. A shop with a part
        in one hand and no drawing could not tell from "Import CAD" that
        nothing reads the model, or from "Upload photo" that the photograph
        becomes an order of work rather than a set of dimensions. The second
        line on each card is the honest one, and it is the reason they are
        cards: a label alone has nowhere to put it.
      */}
      <div className="grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
        <UploadCard
          label="Upload photo"
          note="CANVAS marks up what to measure, in order. It reads no dimensions from a photograph."
          mode="photo"
          active={uploadMode}
          setActive={setUploadMode}
          setFiles={setFiles}
        />
        <UploadCard
          label="Upload drawing"
          note="Stored against the revision. Nothing is read off the sheet until you enter it."
          mode="drawing"
          active={uploadMode}
          setActive={setUploadMode}
          setFiles={setFiles}
        />
        <UploadCard
          label="Import CAD"
          note="STEP and STL are stored and versioned. A DXF profile can be imported as geometry."
          mode="cad"
          active={uploadMode}
          setActive={setUploadMode}
          setFiles={setFiles}
        />
        <a href="/reverse-engineer" className={actionCardClass}>
          <span className="text-[13px] text-platinum group-hover:text-white">Reverse engineer</span>
          <span className="mt-1.5 block text-[11.5px] leading-relaxed text-muted">
            You have the part and no drawing. Measure it into a model, one instrument at a time.
          </span>
        </a>
      </div>

      {files.length > 0 && (
        <UploadPanel files={files} mode={uploadMode} onClear={() => setFiles([])} />
      )}

      {error && <p className="text-[12px] text-risk">{error}</p>}
    </div>
  );
}

/* One card, four times. Square edges and a hairline separator, not a raised
   tile — this is an instrument panel, not a marketing page. */
const actionCardClass =
  "group block bg-surface px-4 py-3.5 text-left transition-colors hover:bg-raised focus-visible:outline focus-visible:outline-1 focus-visible:outline-precision";

function UploadCard({
  label,
  note,
  mode,
  setActive,
  setFiles,
}: {
  label: string;
  note: string;
  mode: string;
  active: string | null;
  setActive: (m: string | null) => void;
  setFiles: (f: File[]) => void;
}) {
  return (
    <label className={`${actionCardClass} cursor-pointer`}>
      <span className="text-[13px] text-platinum group-hover:text-white">{label}</span>
      <span className="mt-1.5 block text-[11.5px] leading-relaxed text-muted">{note}</span>
      <input
        type="file"
        multiple
        accept={ACCEPTS[mode]}
        className="hidden"
        onChange={(e) => {
          setActive(mode);
          setFiles([...(e.target.files ?? [])]);
        }}
      />
    </label>
  );
}

/**
 * Files are staged, not silently interpreted. CANVAS says plainly what it can
 * and cannot do with each type rather than showing a spinner and inventing
 * geometry.
 */
function UploadPanel({ files, mode, onClear }: { files: File[]; mode: string | null; onClear: () => void }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [done, setDone] = useState<string | null>(null);

  const upload = () => {
    start(async () => {
      const body = new FormData();
      files.forEach((f) => body.append("files", f));
      body.append("kind", mode === "cad" ? "CAD" : mode === "drawing" ? "DRAWING" : "PHOTO");
      const res = await fetch("/api/assets", { method: "POST", body });
      if (res.ok) {
        const { count } = await res.json();
        setDone(`${count} file${count === 1 ? "" : "s"} stored.`);
        router.refresh();
      }
    });
  };

  return (
    <div className="border border-line bg-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="tech-label">Staged files</span>
        <button onClick={onClear} className="tech-label hover:text-platinum">
          Clear
        </button>
      </div>
      <ul className="mb-3 space-y-1 font-mono text-[11px] text-platinum-dim">
        {files.map((f) => (
          <li key={f.name} className="flex justify-between gap-4">
            <span className="truncate">{f.name}</span>
            <span className="text-muted">{(f.size / 1024).toFixed(0)} KB</span>
          </li>
        ))}
      </ul>

      <p className="mb-3 text-[11.5px] leading-relaxed text-muted">
        {mode === "cad"
          ? "CAD files are stored and versioned. Phase 1 has no geometry kernel, so CANVAS will not claim to have read the model — build the part parametrically or reverse engineer it from measurements."
          : mode === "drawing"
            ? "Drawings are stored against the revision. Automatic dimension and GD&T extraction is not implemented, so nothing is read off the sheet until you enter it."
            : "Photographs are stored and available for guided measurement. CANVAS will not claim dimensional reconstruction from an uncalibrated photograph."}
      </p>

      {done ? (
        <p className="text-[12px] text-pass">{done}</p>
      ) : (
        <button onClick={upload} disabled={pending} className={buttonClass("primary", "sm")}>
          {pending ? "Storing…" : "Store files"}
        </button>
      )}
    </div>
  );
}
