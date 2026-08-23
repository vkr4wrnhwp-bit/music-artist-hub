"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Field, Notice, StatusChip, inputClass } from "@/components/ui";

/**
 * SCAN IMPORT.
 *
 * Two fields that are not conveniences. An STL carries no units and no
 * accuracy, so both are declared here or the import is refused: the units
 * because the same file is a 1" part or a 25.4" part, and the scanner
 * because the uncertainty on every dimension that comes out is the
 * instrument's, and there is nowhere else to get it from.
 */

export interface ScannerOption {
  id: string;
  description: string;
  uncertainty: number;
  calibrated: boolean;
}

interface Report {
  triangles: number;
  watertight: boolean;
  openEdges: number;
  planarFaces: number;
  envelope: { x: number; y: number; z: number };
  notAttempted: string[];
  partId: string;
}

export function ScanImport({ scanners }: { scanners: ScannerOption[] }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ reason: string; recommendations: string[] } | null>(null);
  const [report, setReport] = useState<Report | null>(null);

  if (scanners.length === 0) {
    return (
      <Notice tone="unknown" title="No scanning instrument on file">
        A scan is a measurement, and its uncertainty is the scanner&apos;s. Record the scanner in your metrology
        library — with the uncertainty it actually achieves in your shop, not the brochure figure — and the import
        becomes available. CANVAS will not attach an assumed accuracy to a dimension.
      </Notice>
    );
  }

  async function submit(formData: FormData) {
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      const res = await fetch("/api/parts/scan", { method: "POST", body: formData });
      const body = await res.json();
      if (!res.ok) {
        setError({ reason: body.error ?? "The import failed.", recommendations: body.recommendations ?? [] });
        return;
      }
      setReport({
        triangles: body.inspection.triangles,
        watertight: body.inspection.integrity.watertight,
        openEdges: body.inspection.integrity.openEdges,
        planarFaces: body.inspection.planarFaces.length,
        envelope: body.inspection.envelope,
        notAttempted: body.inspection.notAttempted,
        partId: body.partId,
      });
      router.refresh();
    } catch {
      setError({ reason: "The upload did not reach the server.", recommendations: ["Check the connection and retry"] });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <form action={submit} className="grid gap-3 sm:grid-cols-2">
        <Field label="Scan file" hint="Binary or ASCII STL.">
          <input type="file" name="file" accept=".stl" required className={inputClass} />
        </Field>
        <Field label="Scanner" hint="The uncertainty on every dimension below comes from this record.">
          <select name="deviceId" required defaultValue="" className={inputClass}>
            <option value="" disabled>
              Select the instrument
            </option>
            {scanners.map((s) => (
              <option key={s.id} value={s.id}>
                {s.description} — ±{s.uncertainty.toFixed(4)}&quot;{s.calibrated ? "" : " (calibration not recorded)"}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Units the scan was exported in" hint="An STL file records none. Getting this wrong is a factor of 25.4.">
          <select name="units" required defaultValue="" className={inputClass}>
            <option value="" disabled>
              Declare the units
            </option>
            <option value="IN">Inches</option>
            <option value="MM">Millimetres</option>
          </select>
        </Field>
        <div className="flex items-end">
          <Button type="submit" variant="primary" disabled={busy}>
            {busy ? "Reading the mesh…" : "Import scan"}
          </Button>
        </div>
      </form>

      {error && (
        <Notice tone="risk" title="Scan not imported">
          {error.reason}
          {error.recommendations.length > 0 && (
            <ul className="mt-1.5 space-y-1">
              {error.recommendations.map((r) => (
                <li key={r}>— {r}</li>
              ))}
            </ul>
          )}
        </Notice>
      )}

      {report && (
        <div className="space-y-3 border border-line bg-void p-3">
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <span className="tech-label">Scanned envelope</span>
            <span className="font-mono text-[15px] text-platinum tabular-nums">
              {report.envelope.x.toFixed(3)} × {report.envelope.y.toFixed(3)} × {report.envelope.z.toFixed(3)}&quot;
            </span>
            <StatusChip tone={report.watertight ? "pass" : "review"}>
              {report.watertight ? "CLOSED MESH" : `${report.openEdges.toLocaleString()} OPEN EDGES`}
            </StatusChip>
            <span className="font-mono text-[11px] text-muted">
              {report.triangles.toLocaleString()} triangles · {report.planarFaces} planar regions
            </span>
          </div>

          {!report.watertight && (
            <Notice tone="review" title="The envelope bounds what the scanner saw">
              The mesh is not closed, so the part is at least this size and may be larger. Re-scan the missing faces
              before treating the envelope as the part.
            </Notice>
          )}

          <div>
            <p className="tech-label mb-1.5 text-review">Not established by this scan</p>
            <ul className="space-y-1">
              {report.notAttempted.map((n) => (
                <li key={n} className="text-[11.5px] leading-relaxed text-muted">
                  — {n}
                </li>
              ))}
            </ul>
          </div>

          <p className="border-t border-line/60 pt-2 text-[11.5px] text-muted">
            The readings are recorded against the scanner and are PENDING — nothing has been accepted into the model.{" "}
            <a href={`/parts/${report.partId}`} className="font-mono text-precision-dim hover:text-precision">
              Open the part →
            </a>
          </p>
        </div>
      )}
    </div>
  );
}
