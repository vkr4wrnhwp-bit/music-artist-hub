import { Button, Notice, Panel, StatusChip } from "@/components/ui";
import type { ReleaseVerdict } from "@/lib/engines/jobs";

/**
 * RELEASE TO THE FLOOR
 *
 * Readiness and release are different questions, and conflating them made this
 * unreachable: the simulation gate has no PASS branch at all — a geometric
 * visualisation is not verified stock removal — so requiring every blocking
 * gate to PASS meant no part could ever be released, and no job could ever be
 * raised against one.
 *
 * Readiness still answers "is this verified ready to run", and still says no.
 * This answers "did a named human take responsibility for running it anyway":
 *
 * - A blocking gate with no evidence behind it — missing, not attempted,
 *   failed — refuses the release. There is nothing to exercise judgement over,
 *   and no override exists, because a click cannot substitute for evidence
 *   that does not exist.
 * - A blocking gate under review is where the evidence exists and a
 *   machinist's judgement is the missing input. Each one is acknowledged
 *   individually and by name. Never a single "I accept the above": one click
 *   standing for several separate engineering judgements is the failure this
 *   whole split exists to avoid.
 *
 * Acknowledging clears nothing. The gate is still under review afterwards and
 * readiness still reports the part as not ready to run.
 */
export function ReleasePanel({
  verdict,
  revisionId,
  revision,
  released,
  action,
}: {
  verdict: ReleaseVerdict;
  revisionId: string;
  revision: string;
  released: { at: Date; by: string | null } | null;
  action: (formData: FormData) => void;
}) {
  if (released) {
    return (
      <Panel title="Released to the floor" meta={<StatusChip tone="pass">Revision {revision}</StatusChip>}>
        <p className="text-[12.5px] leading-relaxed text-platinum-dim">
          Released {new Date(released.at).toISOString().slice(0, 10)}
          {released.by ? ` by ${released.by}` : ""}. The readiness picture at that moment is stored with the revision,
          because what a job outcome has to answer afterwards is what was known when the shop said run it — and
          readiness moves as tools, instruments and machines change.
        </p>
        <p className="tech-label mt-2">Jobs can be raised against this revision.</p>
      </Panel>
    );
  }

  if (!verdict.ok) {
    return (
      <Panel title="Release to the floor" meta={<StatusChip tone="risk">Held</StatusChip>}>
        <Notice
          tone="risk"
          title={`${verdict.blockers.length} blocking gate${verdict.blockers.length === 1 ? "" : "s"} with nothing behind ${verdict.blockers.length === 1 ? "it" : "them"}`}
        >
          <ul className="mt-1 space-y-1">
            {verdict.blockers.map((b) => (
              <li key={b.id} className="text-[12px] leading-relaxed">
                <span className="text-platinum">{b.label}</span>
                <span className="tech-label ml-2">{b.status.replace(/_/g, " ").toLowerCase()}</span>
                <span className="block text-muted">{b.detail}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[12px] leading-relaxed">
            These cannot be acknowledged. There is no evidence to exercise judgement over, and a click does not
            substitute for evidence that does not exist — the way to a release is through the gate.
          </p>
        </Notice>
      </Panel>
    );
  }

  const needsAck = verdict.acknowledgeable.length > 0;

  return (
    <Panel
      title="Release to the floor"
      meta={<StatusChip tone="review">{needsAck ? `${verdict.acknowledgeable.length} to acknowledge` : "Can be released"}</StatusChip>}
    >
      <p className="max-w-2xl text-[12.5px] leading-relaxed text-platinum-dim">
        Nothing is missing. Releasing lets a job be raised against this revision. It does not clear a gate and does not
        certify the part — readiness will still report what it reports.
      </p>

      <form action={action} className="mt-4">
        <input type="hidden" name="revisionId" value={revisionId} />

        {needsAck && (
          <fieldset className="border border-line-strong p-3">
            <legend className="tech-label px-1">Take responsibility for each of these</legend>
            <p className="mb-3 max-w-2xl text-[12px] leading-relaxed text-muted">
              The evidence exists and the judgement is yours. Each is acknowledged on its own and recorded against your
              name with the release. Acknowledging does not change the gate.
            </p>
            <ul className="space-y-2.5">
              {verdict.acknowledgeable.map((a) => (
                <li key={a.id}>
                  <label className="flex items-start gap-2.5 text-[12.5px] leading-relaxed text-platinum">
                    <input
                      type="checkbox"
                      name="acknowledge"
                      value={a.id}
                      required
                      className="mt-1 accent-[color:var(--c-blue)]"
                    />
                    <span>
                      {a.label}
                      <span className="block text-[12px] text-muted">{a.detail}</span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>
        )}

        {verdict.reservations.length > 0 && (
          <div className="mt-4">
            <p className="tech-label">Released with these still open</p>
            <ul className="mt-1 space-y-0.5">
              {verdict.reservations.map((r) => (
                <li key={r.id} className="text-[12px] text-review">
                  — {r.label}: {r.status.replace(/_/g, " ").toLowerCase()}
                </li>
              ))}
            </ul>
            <p className="mt-1 text-[11.5px] text-muted">
              Not blocking, so no acknowledgement is asked for. They are stored with the release.
            </p>
          </div>
        )}

        <Button type="submit" variant="primary" className="mt-4">
          Release revision {revision}
        </Button>
      </form>
    </Panel>
  );
}
