import { Button, Notice, Panel, StatusChip } from "@/components/ui";
import type { ReleaseVerdict } from "@/lib/engines/jobs";

/**
 * RELEASE TO THE FLOOR
 *
 * The Jobs section said jobs are created from a released part revision and
 * nothing could release one. This is that control, and it is deliberately not
 * a confirm button that overrides the gates:
 *
 * - A blocking gate that is not PASS refuses the release, and the refusal
 *   names each gate. There is no override, because principle 2 says a click
 *   does not satisfy an engineering condition — the evidence has to change.
 * - Gates that are short but not blocking do not refuse it. They are shown as
 *   reservations, and they are stored with the release, so the job carries
 *   what was known when somebody said run it.
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

  return (
    <Panel
      title="Release to the floor"
      meta={<StatusChip tone={verdict.ok ? "review" : "risk"}>{verdict.ok ? "Can be released" : "Held"}</StatusChip>}
    >
      {verdict.ok ? (
        <>
          <p className="max-w-2xl text-[12.5px] leading-relaxed text-platinum-dim">
            No blocking gate is unresolved. Releasing lets a job be raised against this revision. It does not clear a
            gate and does not certify the part — it records that the shop decided to run it, against the gates as they
            stand now.
          </p>
          {verdict.reservations.length > 0 && (
            <div className="mt-3">
              <p className="tech-label">Released with these still open</p>
              <ul className="mt-1 space-y-0.5">
                {verdict.reservations.map((r) => (
                  <li key={r.id} className="text-[12px] text-review">
                    — {r.label}: {r.status.replace(/_/g, " ").toLowerCase()}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <form action={action} className="mt-4">
            <input type="hidden" name="revisionId" value={revisionId} />
            <Button type="submit" variant="primary">
              Release revision {revision}
            </Button>
          </form>
        </>
      ) : (
        <Notice tone="risk" title={`${verdict.blockers.length} blocking gate${verdict.blockers.length === 1 ? "" : "s"} unresolved`}>
          <ul className="mt-1 space-y-1">
            {verdict.blockers.map((b) => (
              <li key={b.id} className="text-[12px] leading-relaxed">
                <span className="text-platinum">{b.label}</span> — {b.detail}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[12px] leading-relaxed">
            There is no override here. A blocking gate is satisfied by evidence, not by acknowledging it, so the way
            to a release is through the gate.
          </p>
        </Notice>
      )}
    </Panel>
  );
}
