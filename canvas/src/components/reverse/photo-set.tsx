"use client";

import { useState, useTransition } from "react";
import { buttonClass } from "@/components/ui";

/**
 * The recommended photo set. Views are labelled at upload time so the guided
 * measurement step can show the operator the right image when it asks for a
 * dimension, rather than making them hunt through a folder.
 */

const VIEWS = [
  { id: "TOP", label: "Top", required: true },
  { id: "BOTTOM", label: "Bottom", required: true },
  { id: "FRONT", label: "Front", required: true },
  { id: "BACK", label: "Back", required: true },
  { id: "LEFT", label: "Left", required: true },
  { id: "RIGHT", label: "Right", required: true },
  { id: "ISO", label: "Isometric", required: false },
  { id: "DETAIL", label: "Detail", required: false },
];

const SCALE_REFERENCES = [
  "None",
  "Steel rule in frame",
  "1-2-3 block",
  "Gauge block",
  "Known bearing OD",
  "Known fastener",
  "Manually entered dimension",
];

export function PhotoSetUploader({ partId }: { partId?: string }) {
  const [uploaded, setUploaded] = useState<Record<string, string>>({});
  const [scaleRef, setScaleRef] = useState(SCALE_REFERENCES[0]);
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const upload = (view: string, file: File) => {
    setError(null);
    start(async () => {
      const body = new FormData();
      body.append("files", file);
      body.append("kind", "PHOTO");
      body.append("viewLabel", view);
      body.append("scaleReference", scaleRef);
      if (partId) body.append("partId", partId);

      const res = await fetch("/api/assets", { method: "POST", body });
      if (!res.ok) {
        setError("Upload failed.");
        return;
      }
      setUploaded((u) => ({ ...u, [view]: file.name }));
    });
  };

  const done = VIEWS.filter((v) => v.required && uploaded[v.id]).length;
  const requiredCount = VIEWS.filter((v) => v.required).length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-4">
        <label className="block">
          <span className="tech-label">Scale reference</span>
          <select
            value={scaleRef}
            onChange={(e) => setScaleRef(e.target.value)}
            className="mt-1.5 border border-line-strong bg-void px-2.5 py-1.5 font-mono text-[12px] text-platinum"
          >
            {SCALE_REFERENCES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <p className="max-w-md text-[11.5px] leading-relaxed text-muted">
          A scale reference bounds the error in a photograph. It does not make the photograph a measurement instrument
          — CANVAS still asks you to measure every dimension that matters.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-px bg-line sm:grid-cols-4">
        {VIEWS.map((v) => {
          const has = Boolean(uploaded[v.id]);
          return (
            <label
              key={v.id}
              className={`flex cursor-pointer flex-col items-center justify-center gap-1.5 bg-surface px-3 py-6 transition-colors hover:bg-raised ${
                has ? "border-l-2 border-l-precision" : ""
              }`}
            >
              <span className={`font-mono text-[11px] uppercase tracking-[0.14em] ${has ? "text-precision" : "text-platinum-dim"}`}>
                {v.label}
              </span>
              <span className="tech-label truncate text-center">
                {has ? uploaded[v.id] : v.required ? "Required" : "Optional"}
              </span>
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) upload(v.id, f);
                }}
              />
            </label>
          );
        })}
      </div>

      <div className="flex items-center gap-3">
        <span className="tech-label">
          {done} / {requiredCount} required views
        </span>
        {pending && <span className="tech-label text-precision">Storing…</span>}
        {error && <span className="text-[12px] text-risk">{error}</span>}
      </div>
    </div>
  );
}
