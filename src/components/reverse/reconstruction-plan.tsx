import {
  DATUM_SYSTEMS,
  DATUM_SYSTEM_LABEL,
  DATUM_SYSTEM_QUESTION,
  nextTask,
  type DatumSystem,
  type ReconstructionPlan,
} from "@/lib/engines/reconstruction";
import { Button, DataRow, Notice, Panel, StatusChip } from "@/components/ui";

/**
 * THE RECONSTRUCTION PLAN
 *
 * The honest output of photographing a part is not geometry. It is a list of
 * things somebody has to go and measure, in an order that does not waste their
 * afternoon — and saying so plainly is more useful than any amount of implied
 * reconstruction.
 */
export function ReconstructionPlanPanel({
  plan,
  establishDatum,
  establishedKeys,
}: {
  plan: ReconstructionPlan;
  establishDatum: (formData: FormData) => void | Promise<void>;
  /** `${system}:${letter}` for datums already accepted. */
  establishedKeys: Set<string>;
}) {
  const next = nextTask(plan);

  return (
    <div className="space-y-6">
      <Panel title="Reconstruction plan">
        <p className="max-w-2xl text-[13.5px] leading-relaxed text-platinum">{plan.headline}</p>

        <div className="mt-4 grid gap-x-8 sm:grid-cols-2">
          <DataRow label="Photographs on file" value={`${plan.photosOnFile}`} />
          <DataRow
            label="Required views outstanding"
            value={plan.missingViews.length === 0 ? "none" : plan.missingViews.map((v) => v.toLowerCase()).join(", ")}
            tone={plan.missingViews.length > 0 ? "review" : "pass"}
          />
          <DataRow label="Datums established" value={`${plan.datumsEstablished} of ${plan.datumsRequired}`} />
          <DataRow
            label="Measurements recorded"
            value={`${plan.measurementsComplete} of ${plan.measurementsRequired}`}
          />
        </div>

        <Notice tone="review" title="Photographs are not geometry">
          CANVAS does not derive dimensions from the images. No vision model is wired up, and inferring a wall
          thickness from a photograph and presenting it as a dimension would be the most dangerous thing this
          application could do. The photographs are evidence for the person reading this plan; the plan says what has
          to be measured.
        </Notice>

        {plan.blockedBy.length > 0 && (
          <div className="mt-4">
            <p className="tech-label mb-1.5">Blocking progress</p>
            <ul className="space-y-1">
              {plan.blockedBy.map((b) => (
                <li key={b} className="flex gap-2 text-[12.5px] leading-relaxed text-review">
                  <span>—</span>
                  <span>{b}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Panel>

      {/* ---------------- Datums ---------------- */}
      <Panel title="Establish the reference frame">
        <p className="max-w-2xl text-[13px] leading-relaxed text-muted">
          A bore is 2.000 <em>from something</em>. Until that something is named the number is not reproducible — the
          next person measures from a different edge and gets an answer that is equally defensible and different. This
          is why datums come first rather than merely early: dimensions taken before the frame is settled may have to
          be taken again.
        </p>

        {DATUM_SYSTEMS.map((system) => {
          const proposals = plan.datumProposals.filter((d) => d.system === system);
          if (proposals.length === 0) return null;
          return (
            <div key={system} className="mt-5 border-t border-line pt-4 first:border-0 first:pt-0">
              <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-mono text-[12px] uppercase tracking-[0.14em] text-platinum">
                  {DATUM_SYSTEM_LABEL[system as DatumSystem]}
                </span>
                <span className="tech-label">{DATUM_SYSTEM_QUESTION[system as DatumSystem]}</span>
              </div>

              <div className="space-y-3">
                {proposals.map((d) => {
                  const done = establishedKeys.has(`${d.system}:${d.letter}`);
                  return (
                    <div key={`${d.system}-${d.letter}`} className="border border-line px-3 py-2.5">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <span className="flex items-baseline gap-2.5">
                          <span className="border border-precision px-1.5 py-[1px] font-mono text-[11px] text-precision">
                            {d.letter}
                          </span>
                          <span className="font-mono text-[12.5px] text-platinum">{d.description}</span>
                          <span className="tech-label">{d.geometryType.toLowerCase()}</span>
                        </span>
                        <StatusChip tone={done ? "pass" : "unknown"}>{done ? "Established" : "Proposed"}</StatusChip>
                      </div>

                      <p className="mt-2 max-w-2xl text-[12px] leading-relaxed text-muted">{d.reason}</p>

                      {!done && (
                        <form action={establishDatum} className="mt-2.5 flex flex-wrap items-center gap-2">
                          <input type="hidden" name="letter" value={d.letter} />
                          <input type="hidden" name="system" value={d.system} />
                          <input type="hidden" name="description" value={d.description} />
                          <input type="hidden" name="geometryType" value={d.geometryType} />
                          <input type="hidden" name="featureId" value={d.featureId ?? ""} />
                          <input type="hidden" name="reason" value={d.reason} />
                          <Button type="submit" size="sm" variant="primary">
                            Accept
                          </Button>
                          <span className="text-[11.5px] text-muted">
                            Or pick a different face on the part and record that instead — this is a proposal, and the
                            person holding the component knows things the feature list does not.
                          </span>
                        </form>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </Panel>

      {/* ---------------- The work list ---------------- */}
      <Panel
        title="Measurement mission"
        meta={
          <span className="tech-label">
            {plan.measurementsComplete} / {plan.measurementsRequired}
          </span>
        }
      >
        {next && (
          <div className="mb-4 border border-line border-l-2 border-l-precision bg-raised px-4 py-3">
            <p className="tech-label">
              Measurement {String(next.order).padStart(2, "0")} / {plan.measurementsRequired}
            </p>
            <p className="mt-1 text-[16px] font-light leading-snug text-white">{next.label}</p>
            <p className="mt-1.5 max-w-2xl text-[12.5px] leading-relaxed text-platinum-dim">{next.instruction}</p>
            <p className="mt-2 max-w-2xl text-[12px] leading-relaxed text-muted">
              <span className="tech-label">Unlocks</span> {next.unlocks}
            </p>
            {next.datumLetter && (
              <p className="tech-label mt-1.5 text-precision">Reference to datum {next.datumLetter}</p>
            )}
          </div>
        )}

        <ol className="space-y-px">
          {plan.tasks.map((t) => (
            <li
              key={t.id}
              className={`flex items-start gap-3 border-l-2 px-3 py-2 ${
                t.complete
                  ? "border-l-pass bg-raised/40"
                  : t.id === next?.id
                    ? "border-l-precision bg-raised"
                    : "border-l-transparent"
              }`}
            >
              <span className="font-mono text-[11px] text-muted tabular-nums">
                {String(t.order).padStart(2, "0")}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-baseline gap-2">
                  <span className={`text-[12.5px] ${t.complete ? "text-muted line-through" : "text-platinum"}`}>
                    {t.label}
                  </span>
                  {t.datumLetter && <span className="tech-label text-precision">from {t.datumLetter}</span>}
                  {t.blocking && !t.complete && <span className="tech-label text-review">blocking</span>}
                </span>
                <span className="tech-label block">{t.context.toLowerCase()}</span>
              </span>
            </li>
          ))}
        </ol>
      </Panel>
    </div>
  );
}
