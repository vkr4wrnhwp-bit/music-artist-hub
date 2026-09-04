import { Button, Field, StatusChip, inputClass } from "@/components/ui";
import { JAW_SURFACES, JAW_SURFACE_LABEL } from "@/lib/engines/holding-margin";

/**
 * THE SETUP, AS ACTUALLY BUILT
 *
 * These numbers could only be written by the approach generator. A machinist
 * who planned 0.250" of grip and set 0.400" had no way to say so, while the
 * holding margin, the jaw-clearance check, the fixture model in the simulator
 * and the release snapshot were all computed from the number they could not
 * correct.
 *
 * The form states which it is looking at. The arithmetic downstream is the
 * same either way; what it is entitled to claim is not — a margin computed
 * from a planned grip describes a setup nobody has built yet.
 *
 * A blank field is left blank. It does not fall back to the planned value and
 * does not become zero: the workholding engine already names an input it does
 * not have, and a zero would be a measurement nobody took.
 */
export function SetupGeometryForm({
  setup,
  machines,
  devices,
  action,
}: {
  setup: {
    id: string;
    machineId: string | null;
    workholdingId: string | null;
    gripDepth: number | null;
    gripLength: number | null;
    stockProjection: number | null;
    parallelHeight: number | null;
    jawAxis: string | null;
    jawSurface: string | null;
    orientation: string;
    flipAxis: string | null;
    quarterTurns: number | null;
    originX: number | null;
    originY: number | null;
    workOffset: string;
    datumNote: string | null;
    geometrySource: string | null;
    geometryRecordedBy: string | null;
    geometryRecordedAt: Date | null;
  };
  machines: { id: string; label: string }[];
  devices: { id: string; label: string }[];
  action: (formData: FormData) => void;
}) {
  const measured = setup.geometrySource === "MEASURED";
  const planned = setup.geometrySource === "PLANNED";

  return (
    <details className="mt-3 border-t border-line pt-3">
      <summary className="flex cursor-pointer flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-platinum-dim">
        Setup as built
        <StatusChip tone={measured ? "pass" : planned ? "review" : "unknown"}>
          {measured ? "Measured" : planned ? "Planned, not measured" : "Not recorded"}
        </StatusChip>
      </summary>

      <p className="mt-2 max-w-2xl text-[12px] leading-relaxed text-muted">
        {measured ? (
          <>
            Recorded by {setup.geometryRecordedBy ?? "somebody"} on{" "}
            {setup.geometryRecordedAt ? new Date(setup.geometryRecordedAt).toISOString().slice(0, 10) : "an unknown date"}.
            The holding margin below is computed from the setup as it was actually built.
          </>
        ) : planned ? (
          <>
            These are the approach generator&rsquo;s intent, not a measurement. The holding margin below describes a
            setup nobody has built yet — record what you actually set and it describes the real one.
          </>
        ) : (
          <>
            Nothing on file says where these numbers came from. Record what you actually set at the machine.
          </>
        )}
      </p>

      <form action={action} className="mt-3 space-y-3">
        <input type="hidden" name="setupId" value={setup.id} />

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Machine">
            <select name="machineId" defaultValue={setup.machineId ?? ""} className={inputClass}>
              <option value="">Not assigned</option>
              {machines.map((m) => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
          </Field>
          <Field label="Workholding">
            <select name="workholdingId" defaultValue={setup.workholdingId ?? ""} className={inputClass}>
              <option value="">Not assigned</option>
              {devices.map((d) => (
                <option key={d.id} value={d.id}>{d.label}</option>
              ))}
            </select>
          </Field>
        </div>

        <div className="grid gap-3 sm:grid-cols-4">
          <Field label="Grip depth, in" hint="How deep the jaws hold the stock.">
            <input name="gripDepth" type="number" step="0.001" min={0} defaultValue={setup.gripDepth ?? ""} placeholder="not recorded" className={inputClass} />
          </Field>
          <Field label="Grip length, in" hint="How much jaw width the part actually sits across.">
            <input name="gripLength" type="number" step="0.001" min={0} defaultValue={setup.gripLength ?? ""} placeholder="not recorded" className={inputClass} />
          </Field>
          <Field label="Stock proud, in" hint="What stands above the top of the jaws.">
            <input name="stockProjection" type="number" step="0.001" min={0} defaultValue={setup.stockProjection ?? ""} placeholder="not recorded" className={inputClass} />
          </Field>
          <Field label="Parallel height, in">
            <input name="parallelHeight" type="number" step="0.001" min={0} defaultValue={setup.parallelHeight ?? ""} placeholder="not recorded" className={inputClass} />
          </Field>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Jaws close on" hint="Decides where the fixture is in the simulator. Not guessed.">
            <select name="jawAxis" defaultValue={setup.jawAxis ?? ""} className={inputClass}>
              <option value="">Not recorded</option>
              <option value="X">X — across the faces perpendicular to X</option>
              <option value="Y">Y — across the faces perpendicular to Y</option>
            </select>
          </Field>
          <Field label="Jaw surface" hint="Sets the friction coefficient the holding margin uses.">
            <select name="jawSurface" defaultValue={setup.jawSurface ?? "UNKNOWN"} className={inputClass}>
              {JAW_SURFACES.map((j) => (
                <option key={j} value={j}>{JAW_SURFACE_LABEL[j]}</option>
              ))}
            </select>
          </Field>
          <Field label="Work offset">
            <input name="workOffset" defaultValue={setup.workOffset} maxLength={10} className={inputClass} />
          </Field>
        </div>

        <Field label="Datum note" hint="What the work offset is measured from. A reading with no reference is not reproducible.">
          <input name="datumNote" defaultValue={setup.datumNote ?? ""} maxLength={500} className={inputClass} />
        </Field>

        {/*
          HOW THE PART SITS.

          "BOTTOM" cannot say which way it was turned to get there. Rolled
          about X mirrors every Y, pitched about Y mirrors every X, and both
          put the same face up — two different parts, and a program written
          under the wrong reading is dimensionally perfect and mirrored.
        */}
        <div className="grid gap-3 sm:grid-cols-4">
          <Field
            label="Turned over about"
            hint={
              setup.orientation === "BOTTOM"
                ? "Required. X if you rolled it front to back, Y if you turned it left to right."
                : "Only for a setup with the part bottom up."
            }
          >
            <select name="flipAxis" defaultValue={setup.flipAxis ?? ""} className={inputClass}>
              <option value="">Not turned over</option>
              <option value="X">X — rolled front to back, every Y mirrors</option>
              <option value="Y">Y — turned left to right, every X mirrors</option>
            </select>
          </Field>
          <Field label="Index, quarter turns" hint="Counter-clockwise about Z. 0 to 3.">
            <input name="quarterTurns" type="number" step="1" min={0} max={3} defaultValue={setup.quarterTurns ?? 0} className={inputClass} />
          </Field>
          <Field label="Zero X from stock centre, in" hint="0 puts X0 at the centre. Negative is toward −X.">
            <input name="originX" type="number" step="0.0001" defaultValue={setup.originX ?? 0} className={inputClass} />
          </Field>
          <Field label="Zero Y from stock centre, in">
            <input name="originY" type="number" step="0.0001" defaultValue={setup.originY ?? 0} className={inputClass} />
          </Field>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" variant="primary" size="sm">Record as measured</Button>
          <span className="text-[11px] text-muted">
            A blank field stays blank. It is not filled in from the plan, and it does not become zero.
          </span>
        </div>
      </form>
    </details>
  );
}
