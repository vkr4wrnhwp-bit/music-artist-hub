import { Button } from "@/components/ui";

/**
 * The one setup datum the fixture model cannot do without.
 *
 * Deliberately not a preference control with a sensible default: it is a fact
 * about how the part is held, and the honest state before somebody records it
 * is "not recorded", with the consequence spelled out rather than a vise
 * quietly modelled on the wrong two faces.
 */
export function JawAxisField({
  setupId,
  value,
  action,
}: {
  setupId: string;
  value: string | null;
  action: (formData: FormData) => void;
}) {
  return (
    <form action={action} className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
      <input type="hidden" name="setupId" value={setupId} />
      <span className="tech-label">Jaws close on</span>
      <select
        name="jawAxis"
        defaultValue={value ?? ""}
        aria-label="Axis the jaws close on"
        className="border border-line-strong bg-surface px-1.5 py-1.5 text-[11px] text-platinum-dim"
      >
        <option value="">Not recorded</option>
        <option value="X">X — jaws grip the two faces across X</option>
        <option value="Y">Y — jaws grip the two faces across Y</option>
      </select>
      <Button type="submit" size="sm">
        Record
      </Button>
      {!value && (
        <span className="text-[11px] leading-snug text-review">
          Until this is recorded the simulator models no vise, and the cutter is not checked against the jaws.
        </span>
      )}
    </form>
  );
}
