"use client";

import { useState } from "react";
import { Button, Field, Panel, inputClass } from "@/components/ui";
import { JOB_OUTCOMES, OUTCOME_CAUSES, OUTCOME_LABEL, type JobOutcomeCode } from "@/lib/engines/network";
import { JOB_STATUS_LABEL, type JobStatus } from "@/lib/engines/jobs";

/**
 * The three job forms.
 *
 * The one that matters is the outcome form. Its cause list is driven by the
 * chosen code and comes from the taxonomy in network.ts — a free-text cause
 * cannot be counted across jobs, and counting across jobs is the entire
 * reason to record one. The client narrows the choice; the server refuses
 * anything outside the list, because a form is not a validator.
 */

export function JobTransport({ next, action }: { next: JobStatus[]; action: (formData: FormData) => void }) {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
      <span className="tech-label">Next</span>
      {next.map((s) => (
        <form key={s} action={action}>
          <input type="hidden" name="to" value={s} />
          <Button type="submit" size="sm" variant={s === "CANCELLED" ? "default" : "primary"}>
            {JOB_STATUS_LABEL[s]}
          </Button>
        </form>
      ))}
    </div>
  );
}

export function ActualsForm({
  job,
  action,
}: {
  job: { actualCycleMinutes: number | null; actualSetupHours: number | null; scrapCount: number; notes: string | null };
  action: (formData: FormData) => void;
}) {
  return (
    <form action={action} className="mt-4 space-y-3 border-t border-line pt-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Actual cycle, minutes per part">
          <input
            name="actualCycleMinutes"
            type="number"
            step="0.1"
            min={0}
            defaultValue={job.actualCycleMinutes ?? ""}
            placeholder="not recorded"
            className={inputClass}
          />
        </Field>
        <Field label="Actual setup, hours">
          <input
            name="actualSetupHours"
            type="number"
            step="0.1"
            min={0}
            defaultValue={job.actualSetupHours ?? ""}
            placeholder="not recorded"
            className={inputClass}
          />
        </Field>
        <Field label="Scrap count">
          <input name="scrapCount" type="number" min={0} defaultValue={job.scrapCount} className={inputClass} />
        </Field>
      </div>
      <Field label="Notes">
        <input name="notes" defaultValue={job.notes ?? ""} maxLength={2000} className={inputClass} />
      </Field>
      <p className="tech-label">
        A blank field stays blank. It never falls back to the estimate — an actual seeded from the estimate makes the
        comparison agree with itself.
      </p>
      <Button type="submit" size="sm">Record actuals</Button>
    </form>
  );
}

export function OutcomeForm({
  operations,
  action,
}: {
  operations: { id: string; label: string }[];
  action: (formData: FormData) => void;
}) {
  const [code, setCode] = useState<JobOutcomeCode>("SUCCESS");
  const causes = OUTCOME_CAUSES[code];
  const isFailure = code !== "SUCCESS";

  return (
    <Panel title="Record what happened">
      <form action={action} className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Outcome">
            <select
              name="code"
              value={code}
              onChange={(e) => setCode(e.target.value as JobOutcomeCode)}
              className={inputClass}
            >
              {JOB_OUTCOMES.map((c) => (
                <option key={c} value={c}>{OUTCOME_LABEL[c]}</option>
              ))}
            </select>
          </Field>
          <Field
            label="Cause"
            hint="Chosen from the list, not typed. A cause in somebody's own words cannot be counted across jobs."
          >
            <select name="cause" className={inputClass} key={code}>
              {causes.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </Field>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Operation, if it was one">
            <select name="operationId" defaultValue="" className={inputClass}>
              <option value="">Not tied to an operation</option>
              {operations.map((o) => (
                <option key={o.id} value={o.id}>{o.label}</option>
              ))}
            </select>
          </Field>
          <Field label="Tool number">
            <input name="toolNumber" type="number" min={1} placeholder="—" className={inputClass} />
          </Field>
          <Field label="Parts affected">
            <input name="partsAffected" type="number" min={0} defaultValue={0} className={inputClass} />
          </Field>
        </div>

        {isFailure ? (
          <Field
            label="Corrective action"
            hint="What was done about it. A failure with no corrective action teaches the next person nothing, and is refused."
          >
            <input name="correctiveAction" minLength={10} maxLength={2000} className={inputClass} />
          </Field>
        ) : (
          <input type="hidden" name="correctiveAction" value="—" />
        )}

        <Field label="Notes">
          <input name="notes" maxLength={2000} className={inputClass} />
        </Field>

        <Button type="submit" variant="primary">Record outcome</Button>
      </form>
    </Panel>
  );
}
