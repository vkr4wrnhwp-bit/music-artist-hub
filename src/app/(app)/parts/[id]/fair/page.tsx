import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { loadRevision } from "@/lib/data";
import { buildFair, type FairField, type FairCharacteristic } from "@/lib/engines/fair";
import { TopBar } from "@/components/nav";
import { Notice, Panel, SectionHeading, StatusChip } from "@/components/ui";
import { PrintButton } from "@/components/print-button";

/**
 * AS9102 FIRST ARTICLE INSPECTION REPORT
 *
 * Assembled by the deterministic FAIR engine from records on file. The page
 * renders what exists and names what does not — a field the shop has not
 * recorded prints as REQUIRED — NOT ON FILE, never as a plausible blank.
 * Only INSPECTION-mode measurement sessions feed Form 3; reverse-engineering
 * readings of a reference article are not first-article results.
 */

export default async function FairPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();
  const revision = await loadRevision(user.organizationId, id);
  if (!revision) notFound();

  const [drawings, measurements] = await Promise.all([
    db.drawing.findMany({ where: { partRevisionId: revision.revisionId } }),
    db.measurement.findMany({
      where: { session: { partRevisionId: revision.revisionId, mode: "INSPECTION" } },
      include: { device: true, session: true },
      orderBy: { createdAt: "desc" },
    }),
  ]);

  const fair = buildFair({
    organizationName: user.organizationName,
    partNumber: revision.partNumber,
    partName: revision.partName,
    revision: revision.revision,
    intent: revision.intent,
    features: revision.features,
    drawings: drawings.map((d) => ({ title: d.title, sheetNumber: d.sheetNumber })),
    inspectionMeasurements: measurements.map((m) => ({
      featureId: m.featureId,
      sessionMode: m.session.mode,
      value: m.resolvedValue ?? m.measuredValue,
      uncertainty: m.uncertainty,
      instrument: m.device?.description ?? null,
      measuredAt: m.createdAt.toISOString(),
      repeatCount: m.repeatCount,
    })),
    generatedAtIso: new Date().toISOString(),
    preparedBy: user.name || user.email,
  });

  const s = fair.summary;

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">First article</span>
      </TopBar>

      {/* Print isolation: only the report leaves the printer. */}
      <style>{`@media print {
        body * { visibility: hidden; }
        #fair-report, #fair-report * { visibility: visible; }
        #fair-report { position: absolute; left: 0; top: 0; width: 100%; padding: 0.5in; }
        #fair-report .no-print { display: none; }
      }`}</style>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div id="fair-report" className="mx-auto max-w-5xl space-y-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <SectionHeading sub="AS9102 Forms 1–3, assembled from records on file. Blank is not an option on this report: a requirement CANVAS holds no record for is printed as REQUIRED — NOT ON FILE.">
              First Article Inspection Report
            </SectionHeading>
            <span className="no-print">
              <PrintButton />
            </span>
          </div>

          {s.nonconforming > 0 && (
            <Notice tone="risk" title={`${s.nonconforming} nonconforming characteristic${s.nonconforming === 1 ? "" : "s"}`}>
              This FAIR documents a nonconformance. It does not disposition it.
            </Notice>
          )}
          {s.measured < s.characteristics && (
            <Notice tone="review" title={`${s.characteristics - s.measured} of ${s.characteristics} characteristics have no first-article measurement`}>
              Only INSPECTION-mode measurement sessions feed this report. Readings taken from a reference or worn
              article in reverse engineering are deliberately excluded — they are not first-article results.
            </Notice>
          )}

          {/* ---- Form 1 ---- */}
          <Panel
            title="Form 1 — Part Number Accountability"
            meta={<StatusChip tone="neutral">{fair.form1.fairNumber}</StatusChip>}
            dense
          >
            <dl className="grid grid-cols-1 gap-x-8 gap-y-1 px-4 py-3 sm:grid-cols-2">
              <Field label="Part number" f={fair.form1.partNumber} />
              <Field label="Part name" f={fair.form1.partName} />
              <Field label="Revision" f={fair.form1.revision} />
              <Field label="Drawing number" f={fair.form1.drawingNumber} />
              <Field label="Drawing revision" f={fair.form1.drawingRevision} />
              <Field label="Organization" f={fair.form1.organization} />
              <Field label="Serial / lot number" f={fair.form1.serialNumber} />
              <Field label="Purchase order" f={fair.form1.purchaseOrder} />
              <Field label="Supplier code" f={fair.form1.supplierCode} />
              <Row label="Detail / assembly" value={fair.form1.detailOrAssembly} />
              <Row label="Full / partial FAI" value={fair.form1.fullOrPartial} />
              <Field label="Prepared by" f={fair.form1.preparedBy} />
              <Row label="Generated" value={fair.generatedAtIso.replace("T", " ").slice(0, 19) + " UTC"} />
            </dl>
          </Panel>

          {/* ---- Form 2 ---- */}
          <Panel title="Form 2 — Product Accountability: Materials, Special Processes, Functional Testing" dense>
            <table className="w-full text-left text-[12px]">
              <thead>
                <tr className="border-b border-line-strong">
                  {["", "Name / description", "Specification", "Source", "Certificate / report"].map((h) => (
                    <th key={h} className="instrument-label px-4 py-2">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {fair.form2.map((r) => (
                  <tr key={r.kind} className="border-b border-line/60 align-top last:border-0">
                    <td className="instrument-label px-4 py-2.5 whitespace-nowrap">
                      {r.kind === "MATERIAL" ? "Material" : r.kind === "SPECIAL_PROCESS" ? "Special process" : "Functional test"}
                    </td>
                    <td className="px-4 py-2.5"><FieldValue f={r.name} /></td>
                    <td className="px-4 py-2.5"><FieldValue f={r.specification} /></td>
                    <td className="px-4 py-2.5"><FieldValue f={r.supplier} /></td>
                    <td className="px-4 py-2.5"><FieldValue f={r.certificateNumber} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          {/* ---- Form 3 ---- */}
          <Panel
            title="Form 3 — Characteristic Accountability"
            meta={
              <span className="flex gap-2">
                <StatusChip tone="neutral">{s.characteristics} characteristics</StatusChip>
                {s.conforming > 0 && <StatusChip tone="pass">{s.conforming} conform</StatusChip>}
                {s.nonconforming > 0 && <StatusChip tone="risk">{s.nonconforming} nonconform</StatusChip>}
                {s.undetermined > 0 && <StatusChip tone="review">{s.undetermined} undetermined</StatusChip>}
              </span>
            }
            dense
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-[12px]">
                <thead>
                  <tr className="border-b border-line-strong">
                    {["#", "Characteristic", "Requirement", "Result", "Method", "Conformance"].map((h) => (
                      <th key={h} className="instrument-label px-4 py-2">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {fair.form3.map((c) => (
                    <tr key={c.charNumber} className="border-b border-line/60 align-top last:border-0">
                      <td className="px-4 py-2.5 font-mono tabular-nums">{c.charNumber}</td>
                      <td className="px-4 py-2.5">
                        <span className="text-platinum">{c.location}</span>
                        {c.designator && (
                          <span className="mt-0.5 block text-[10px] font-semibold uppercase tracking-[0.12em] text-review">
                            Critical
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-[11.5px] text-platinum-dim tabular-nums">
                        {c.requirement}
                        <span className="block text-muted">{c.tolerance}</span>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-[11.5px] tabular-nums">
                        {c.result.state === "MEASURED" ? (
                          <>
                            <span className="text-platinum">{c.result.value.toFixed(4)}″</span>
                            <span className="block text-muted">
                              ±{c.result.uncertainty.toFixed(4)}″ · n={c.result.repeatCount} · {c.result.instrument}
                            </span>
                          </>
                        ) : (
                          <span className="font-sans text-[11px] font-semibold uppercase tracking-[0.1em] text-review">
                            Not measured
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5"><FieldValue f={c.inspectionMethod} /></td>
                      <td className="px-4 py-2.5"><Conformance c={c} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <p className="text-[11px] leading-relaxed text-muted">
            Generated by CANVAS from records on file. {s.fieldsNotOnFile} required field
            {s.fieldsNotOnFile === 1 ? " is" : "s are"} not on file and printed as such. Conformance verdicts are
            stated only where a recorded result, a stated tolerance, a single nominal and an adequate instrument
            decide them; everything else is UNDETERMINED with the reason given. This report documents — it does not
            approve, and it does not disposition nonconformances.
          </p>
        </div>
      </main>
    </>
  );
}

function Field({ label, f }: { label: string; f: FairField }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line/60 py-1.5">
      <dt className="instrument-label shrink-0">{label}</dt>
      <dd className="text-right text-[12.5px]"><FieldValue f={f} /></dd>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line/60 py-1.5">
      <dt className="instrument-label shrink-0">{label}</dt>
      <dd className="text-right font-mono text-[12px] text-platinum">{value}</dd>
    </div>
  );
}

function FieldValue({ f }: { f: FairField }) {
  if (f.state === "ON_FILE") return <span className="font-mono text-[12px] text-platinum">{f.value}</span>;
  return (
    <span className="text-[11px] leading-snug text-review">
      <span className="font-semibold uppercase tracking-[0.1em]">Required — not on file</span>
      <span className="block text-muted">{f.requirement}</span>
    </span>
  );
}

function Conformance({ c }: { c: FairCharacteristic }) {
  const v = c.conformance;
  if (v.verdict === "CONFORMS")
    return <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-pass">Conforms</span>;
  if (v.verdict === "NONCONFORMS")
    return (
      <span className="text-[11px] leading-snug">
        <span className="font-semibold uppercase tracking-[0.1em] text-risk">Nonconforms</span>
        <span className="block font-mono text-muted tabular-nums">
          {v.departure > 0 ? "+" : ""}{v.departure.toFixed(4)}″ beyond limit
        </span>
        <span className="block text-muted"><FieldValue f={v.nonconformanceDoc} /></span>
      </span>
    );
  return (
    <span className="text-[11px] leading-snug">
      <span className="font-semibold uppercase tracking-[0.1em] text-review">Undetermined</span>
      <span className="block text-muted">{v.reason}</span>
    </span>
  );
}

export const dynamic = "force-dynamic";
