"use client";

import { useState, useTransition } from "react";
import { Button, Notice, StatusChip } from "@/components/ui";
import type { StampCandidate } from "@/lib/engines/bearing-stamp";

/**
 * READING A BEARING NUMBER OFF A PHOTOGRAPH
 *
 * The panel offered a free-text field and UNKNOWN. A machinist holding a worn
 * bearing whose stamp is easier to photograph than to read had no path in.
 *
 * What this is careful about: a designation is dimensions. 6203 is a 17 mm
 * bore and 6208 is a 40 mm one, and the mating analysis reasons about the fit
 * from that — so a misread stamp does not produce a wrong caption, it produces
 * the wrong bore.
 *
 * So a reading is a CANDIDATE. It fills the designation field for the
 * machinist to check against the bearing in their hand and save deliberately;
 * it never saves itself, and the dimensions shown beside each candidate come
 * from CANVAS's catalogue rather than from the model.
 */
export function BearingStamp({ featureId, onPick }: { featureId: string; onPick: (designation: string, photoId: string) => void }) {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ photoUrl: string; photoId: string; connected: boolean; note: string; candidates: StampCandidate[] } | null>(null);

  const upload = (file: File) => {
    setError(null);
    start(async () => {
      const body = new FormData();
      body.append("photo", file);
      const res = await fetch(`/api/features/${featureId}/bearing-stamp`, { method: "POST", body });
      const json = await res.json().catch(() => null);
      if (!res.ok || !json) {
        setError(json?.error ?? "The photograph could not be read.");
        return;
      }
      setResult(json);
    });
  };

  return (
    <div className="mt-3 border-t border-line pt-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="tech-label">Or photograph the stamp</span>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          disabled={pending}
          aria-label="Photograph of the bearing stamp"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload(f);
          }}
          className="text-[12px] text-muted file:mr-3 file:border file:border-line-strong file:bg-surface file:px-3 file:py-1.5 file:text-[11px] file:font-semibold file:uppercase file:tracking-[0.12em] file:text-platinum-dim hover:file:bg-raised"
        />
        {pending && <span className="text-[11.5px] text-muted">Reading…</span>}
      </div>

      {error && <p className="mt-2 text-[12px] text-risk">{error}</p>}

      {result && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap items-start gap-4">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={result.photoUrl} alt="The bearing stamp as photographed" className="max-h-40 border border-line" />
            <div className="min-w-0 flex-1">
              {!result.connected ? (
                <Notice tone="review" title="No vision model is connected">
                  The photograph is stored against this feature so you can read the stamp yourself. Nothing has been
                  read from it, and nothing has been filled in.
                </Notice>
              ) : result.candidates.length === 0 ? (
                <Notice tone="review" title="Nothing legible on the stamp">
                  {result.note} Type the designation if you can read it — a guess from an unreadable photograph would
                  decide a bore diameter.
                </Notice>
              ) : (
                <>
                  <p className="text-[12px] leading-relaxed text-muted">
                    Read from the photograph. None of these is recorded until you pick one and save — the dimensions
                    beside each come from CANVAS&rsquo;s bearing catalogue, not from the reading, so check them against
                    the bearing in your hand.
                  </p>
                  <ul className="mt-2 space-y-2">
                    {result.candidates.map((c) => (
                      <li key={c.readAs} className="border border-line-strong bg-raised px-3 py-2">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="flex items-center gap-2">
                            <span className="font-mono text-[13px] text-platinum">{c.readAs}</span>
                            <StatusChip tone={c.bearing ? "precision" : "unknown"}>
                              {c.bearing ? "in the catalogue" : "not in the catalogue"}
                            </StatusChip>
                          </span>
                          <span className="flex items-center gap-2">
                            <span className="tech-label">read at {(c.confidence * 100).toFixed(0)}%</span>
                            <Button
                              type="button"
                              size="sm"
                              onClick={() => onPick(c.readAs, result.photoId)}
                            >
                              Use this
                            </Button>
                          </span>
                        </div>
                        <p className="mt-1 text-[11.5px] leading-relaxed text-muted">{c.note}</p>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
