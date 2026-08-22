import { techniqueFor, UNIVERSAL_CAUTIONS } from "@/lib/metrology/technique";
import type { MeasurementGeometry } from "@/lib/engines/inspection-capability";

/**
 * How to take the reading, shown where the instrument is named.
 *
 * Collapsed by default. A machinist who knows how to rock a bore gauge does
 * not need to be told again on every feature, and a panel that shouts
 * technique at an experienced operator is the fastest way to get the whole
 * screen ignored. It is there when it is wanted.
 *
 * Renders nothing at all when there is no technique on file for the
 * instrument — the same refusal the drawings make.
 */
export function MeasurementTechnique({
  deviceType,
  geometry,
  instrumentLabel,
}: {
  deviceType: string;
  geometry: MeasurementGeometry | null;
  instrumentLabel?: string;
}) {
  const t = techniqueFor(deviceType, geometry);
  if (!t) return null;

  return (
    <details className="group mt-2 border-t border-line pt-2">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[9.5px] font-semibold uppercase tracking-[0.12em] text-muted hover:text-platinum">
        How to take this reading
        <span className="text-muted group-open:hidden">▸</span>
        <span className="hidden text-muted group-open:inline">▾</span>
      </summary>

      <div className="mt-2 space-y-2.5">
        {instrumentLabel && (
          <p className="text-[11px] leading-relaxed text-muted">
            Standard technique for {instrumentLabel.toLowerCase()}. General practice, not advice about this part — and
            following it makes a reading trustworthy, not an instrument capable of a tolerance it cannot resolve.
          </p>
        )}

        {(
          [
            ["Set up", t.setup],
            ["Take the reading", t.taking],
            ["What goes wrong", t.pitfalls],
          ] as const
        ).map(([heading, lines]) => (
          <div key={heading}>
            <p className="tech-label mb-1">{heading}</p>
            <ul className="space-y-1">
              {lines.map((l) => (
                <li key={l} className="flex gap-2 text-[11.5px] leading-relaxed text-muted">
                  <span className={heading === "What goes wrong" ? "text-review" : "text-precision"}>—</span>
                  <span>{l}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}

        <div>
          <p className="tech-label mb-1">True of every reading</p>
          <ul className="space-y-1">
            {UNIVERSAL_CAUTIONS.map((c) => (
              <li key={c} className="flex gap-2 text-[11.5px] leading-relaxed text-muted">
                <span className="text-precision">—</span>
                <span>{c}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </details>
  );
}
