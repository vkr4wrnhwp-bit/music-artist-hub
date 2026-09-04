import Link from "next/link";
import { notFound } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { buildPackage } from "@/lib/package";
import { buildSetupSheet, type SheetField } from "@/lib/setup-sheet";

/**
 * THE SETUP SHEET, ON PAPER.
 *
 * Deliberately not built out of the app's Panel/Table components. Those are
 * designed for a dark instrument screen; this is designed for a sheet of white
 * paper on a machine that is running, read by somebody in gloves under shop
 * lighting. Black on white, large type, heavy rules, and a print stylesheet
 * that drops the navigation and the link back.
 *
 * Everything on it comes from `buildSetupSheet`. This file decides where things
 * sit and nothing about what is true.
 */

const Missing = ({ children = "not recorded" }: { children?: string }) => (
  <span className="text-[0.92em] uppercase tracking-[0.08em] text-neutral-500">{children}</span>
);

function Fields({ rows }: { rows: SheetField[] }) {
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1.5">
      {rows.map((r) => (
        <div key={r.label} className="contents">
          <dt className="text-[11px] uppercase tracking-[0.1em] text-neutral-600">{r.label}</dt>
          <dd className="font-mono text-[13px] tabular-nums text-black">{r.value ?? <Missing />}</dd>
        </div>
      ))}
    </dl>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="break-inside-avoid border-t-2 border-black pt-2">
      <h2 className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-black">{title}</h2>
      {children}
    </section>
  );
}

export default async function SetupSheetPage({
  params,
}: {
  params: Promise<{ id: string; sid: string }>;
}) {
  const { id, sid } = await params;
  const user = await requireUser();
  const pkg = await buildPackage(user.organizationId, id);
  if (!pkg) notFound();

  const sheet = buildSetupSheet(pkg, sid);
  if (!sheet) notFound();

  const th = "border-b border-black px-2 py-1 text-left text-[10px] font-bold uppercase tracking-[0.1em]";
  const td = "border-b border-neutral-300 px-2 py-1.5 align-top";

  return (
    <div className="min-h-screen bg-white text-black">
      {/* Screen-only: back to the app. Never printed. */}
      <div className="print:hidden border-b border-neutral-300 bg-neutral-100 px-6 py-2 text-[12px]">
        <Link href={`/parts/${id}/setups`} className="text-neutral-700 underline">
          ← Setups
        </Link>
        <span className="ml-4 text-neutral-500">Print this. It is meant to go to the machine with the program.</span>
      </div>

      <main className="mx-auto max-w-[8.5in] space-y-5 p-8 print:p-0">
        {/* ---------------- Masthead ---------------- */}
        <header className="border-b-4 border-black pb-3">
          <div className="flex items-start justify-between gap-6">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-neutral-600">Setup sheet</div>
              <h1 className="mt-1 text-[26px] font-bold leading-none tracking-tight">{sheet.part.name}</h1>
              <div className="mt-1.5 font-mono text-[12px] text-neutral-700">
                {sheet.part.number ? `${sheet.part.number} · ` : ""}Rev {sheet.part.revision}
                {sheet.part.material ? ` · ${sheet.part.material}` : ""}
                {sheet.part.condition ? ` ${sheet.part.condition}` : ""}
              </div>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-neutral-600">
                Setup {sheet.setup.sequence}
              </div>
              <div className="text-[17px] font-bold leading-tight">{sheet.setup.name}</div>
              <div className="font-mono text-[12px] text-neutral-700">
                {sheet.setup.machine ?? "no machine assigned"} · {sheet.setup.workOffset}
              </div>
            </div>
          </div>
        </header>

        {/* ---------------- Program zero. The first thing anyone needs. ---------------- */}
        <section className="break-inside-avoid border-2 border-black p-3">
          <div className="text-[10px] font-bold uppercase tracking-[0.16em]">Program zero</div>
          <div className="mt-1.5 grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1 font-mono text-[14px]">
            <span className="text-[11px] uppercase tracking-[0.1em] text-neutral-600">X0 Y0</span>
            <span className="font-bold">{sheet.origin.xy}</span>
            <span className="text-[11px] uppercase tracking-[0.1em] text-neutral-600">Z0</span>
            <span className="font-bold">{sheet.origin.z}</span>
            <span className="text-[11px] uppercase tracking-[0.1em] text-neutral-600">Part up</span>
            <span className="font-bold">{sheet.setup.orientation}</span>
          </div>
          {sheet.origin.datumNote && (
            <p className="mt-2 border-t border-neutral-300 pt-2 text-[12px] leading-snug">{sheet.origin.datumNote}</p>
          )}
        </section>

        <div className="grid grid-cols-2 gap-5">
          <Section title="Stock">
            <Fields rows={sheet.stock} />
          </Section>

          <Section title="Workholding">
            <Fields rows={sheet.workholding} />
            <p className="mt-2 text-[11px] leading-snug text-neutral-700">
              {sheet.holding ? (
                <>
                  Holding assessed <span className="font-bold">{sheet.holding.level.replace(/_/g, " ")}</span>
                  {sheet.holding.margin ? ` at ${sheet.holding.margin} margin` : ""}
                  {sheet.geometrySource
                    ? `, from ${sheet.geometrySource === "MEASURED" ? "measured" : "planned"} geometry.`
                    : "."}
                </>
              ) : (
                "Holding has not been assessed for this setup."
              )}
            </p>
          </Section>
        </div>

        {/* ---------------- Tools ---------------- */}
        <Section title={`Tools — ${sheet.tools.length}`}>
          {sheet.tools.length === 0 ? (
            <p className="text-[12px]">No tool is assigned to any operation in this setup.</p>
          ) : (
            <table className="w-full font-mono text-[12px] tabular-nums">
              <thead>
                <tr>
                  <th className={th}>T</th>
                  <th className={th}>Description</th>
                  <th className={th}>⌀</th>
                  <th className={th}>Stickout</th>
                  <th className={th}>Holder</th>
                  <th className={th}>Pocket</th>
                  <th className={th}>H / D</th>
                </tr>
              </thead>
              <tbody>
                {sheet.tools.map((t) => (
                  <tr key={t.toolNumber}>
                    <td className={`${td} font-bold`}>T{t.toolNumber}</td>
                    <td className={`${td} font-sans`}>{t.description}</td>
                    <td className={td}>{t.diameter.toFixed(4)}</td>
                    <td className={td}>{t.stickout.toFixed(3)}</td>
                    <td className={`${td} font-sans text-[11px]`}>{t.holder}</td>
                    <td className={td}>{t.pocket ?? <Missing>load it</Missing>}</td>
                    <td className={td}>{t.lengthOffset}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>

        {/* ---------------- Operations ---------------- */}
        <Section title={`Order of operations — ${sheet.operations.length}`}>
          <table className="w-full font-mono text-[12px] tabular-nums">
            <thead>
              <tr>
                <th className={th}>#</th>
                <th className={th}>Operation</th>
                <th className={th}>Pass</th>
                <th className={th}>T</th>
                <th className={th}>Z from</th>
                <th className={th}>Z to</th>
                <th className={th}>RPM</th>
                <th className={th}>Feed</th>
                <th className={th}>Min</th>
              </tr>
            </thead>
            <tbody>
              {sheet.operations.map((o) => (
                <tr key={o.sequence} className={o.noMotion ? "bg-neutral-100" : undefined}>
                  <td className={td}>{o.sequence}</td>
                  <td className={`${td} font-sans`}>
                    {o.label}
                    {o.noMotion && (
                      <span className="ml-2 border border-black px-1 text-[9px] font-bold uppercase tracking-[0.1em]">
                        not cut
                      </span>
                    )}
                    {o.featureLabel && <div className="text-[10px] text-neutral-600">{o.featureLabel}</div>}
                  </td>
                  <td className={td}>
                    {o.pass === "FINISH" ? (
                      <span className="border border-black px-1 text-[9px] font-bold uppercase tracking-[0.1em]">finish</span>
                    ) : (
                      <span className="text-[10px] uppercase tracking-[0.08em] text-neutral-600">rough</span>
                    )}
                  </td>
                  <td className={td}>{o.toolNumber != null ? `T${o.toolNumber}` : <Missing>none</Missing>}</td>
                  <td className={td}>{o.topZ.toFixed(3)}</td>
                  <td className={td}>{o.finalZ.toFixed(3)}</td>
                  <td className={td}>{o.rpm ?? <Missing>—</Missing>}</td>
                  <td className={td}>{o.feed ?? <Missing>—</Missing>}</td>
                  <td className={td}>{o.cycleMinutes != null ? o.cycleMinutes.toFixed(1) : <Missing>—</Missing>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[12px] font-bold">
            {sheet.cycleMinutes != null
              ? `Cycle time for this setup: ${sheet.cycleMinutes.toFixed(1)} min, cutting only. Tool changes, setup and inspection are not in this figure.`
              : "Cycle time cannot be totalled — at least one operation produced no toolpath."}
          </p>
        </Section>

        {/* ---------------- What has to be checked ---------------- */}
        {sheet.characteristics.length > 0 && (
          <Section title={`Check these — ${sheet.characteristics.length}`}>
            <table className="w-full text-[12px]">
              <thead>
                <tr>
                  <th className={th}>Feature</th>
                  <th className={th}>Nominal</th>
                  <th className={th}>Tolerance</th>
                  <th className={th}>How</th>
                </tr>
              </thead>
              <tbody>
                {sheet.characteristics.map((c) => (
                  <tr key={c.label}>
                    <td className={td}>{c.label}</td>
                    <td className={`${td} font-mono tabular-nums`}>{c.nominal ?? <Missing>see drawing</Missing>}</td>
                    <td className={`${td} font-mono tabular-nums`}>{c.tolerance ?? <Missing>general</Missing>}</td>
                    <td className={td}>{c.method ?? <Missing>no method assigned</Missing>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>
        )}

        {/* ---------------- Not made by this program ---------------- */}
        {sheet.notMadeHere.length > 0 && (
          <Section title="Not made by this program">
            <ul className="space-y-1.5 text-[12px]">
              {sheet.notMadeHere.map((n) => (
                <li key={n.label}>
                  <span className="font-bold">{n.label}</span> — {n.reason}
                  {n.by && <span className="text-neutral-600"> ({n.by})</span>}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {/* ---------------- What this sheet cannot tell you ---------------- */}
        {sheet.unknowns.length > 0 && (
          <section className="break-inside-avoid border-2 border-black p-3">
            <div className="text-[10px] font-bold uppercase tracking-[0.16em]">
              Resolve at the machine — {sheet.unknowns.length}
            </div>
            <ul className="mt-2 space-y-1.5 text-[12px] leading-snug">
              {sheet.unknowns.map((u) => (
                <li key={u} className="flex gap-2">
                  <span aria-hidden="true" className="font-bold">
                    □
                  </span>
                  <span>{u}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* ---------------- Gate state. Printed so a sheet is never clearance. ---------------- */}
        <section className="break-inside-avoid border-t-2 border-black pt-2">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[11px] font-bold uppercase tracking-[0.16em]">Readiness at the time of printing</h2>
            <span className="border border-black px-2 py-0.5 text-[11px] font-bold uppercase tracking-[0.1em]">
              {sheet.gateState.overall.replace(/_/g, " ")}
            </span>
          </div>
          {sheet.gateState.blocking.length > 0 ? (
            <ul className="mt-2 space-y-1 text-[12px] leading-snug">
              {sheet.gateState.blocking.map((g) => (
                <li key={g.label}>
                  <span className="font-bold">{g.label}</span> — {g.detail}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-[12px]">No blocking gate is open on this package.</p>
          )}
          <p className="mt-3 border-t border-neutral-300 pt-2 text-[12px] font-bold leading-snug">
            {sheet.developmentNotice}
          </p>
          <p className="mt-1 text-[11px] leading-snug text-neutral-700">
            This sheet is a description of the plan, not an approval to run it. It carries the readiness state above
            because a sheet in somebody&rsquo;s hand is not clearance to cut.
          </p>
        </section>
      </main>
    </div>
  );
}

export const dynamic = "force-dynamic";
