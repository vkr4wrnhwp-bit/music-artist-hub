import Link from "next/link";
import { notFound } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { TopBar } from "@/components/nav";
import { Button, Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";
import { machineSections } from "../../machine-fields";
import { updateMachine, deleteMachine } from "../../machine-actions";

export default async function EditMachinePage(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ problem?: string }>;
}) {
  const { id } = await props.params;
  const { problem } = await props.searchParams;
  const user = await requireUser();

  const machine = await db.machine.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!machine) notFound();

  const [setups, programs, loaded] = await Promise.all([
    db.setup.count({ where: { machineId: id } }),
    db.nCProgram.count({ where: { machineId: id } }),
    db.tool.count({ where: { machineId: id, pocket: { not: null } } }),
  ]);
  const held = setups > 0 || programs > 0;

  return (
    <>
      <TopBar>
        <Link href="/machines" className="tech-label hover:text-platinum">
          Machines
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">
          {machine.manufacturer} {machine.model}
        </span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub={`${machine.manufacturer} ${machine.model}`}>Edit machine</SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          {machine.isReferenceProfile && (
            <Notice tone="review" title="This is a reference profile">
              It was seeded as example data, not verified against a machine on your floor. Editing it does not make it
              verified — check the figures against the machine's own documentation before you rely on the envelope gate.
            </Notice>
          )}

          {setups > 0 && (
            <Notice tone="review" title={`Used by ${setups} setup${setups === 1 ? "" : "s"}`}>
              Travels and spindle limits are what the machine envelope gate is checked against. Reducing one here can
              turn a passing part into a failing one, which is the gate doing its job — but re-read the affected setups
              rather than assuming nothing moved.
            </Notice>
          )}

          {loaded > 0 && (
            <Notice tone="review" title={`${loaded} tool${loaded === 1 ? "" : "s"} loaded in the changer`}>
              The changer capacity cannot be reduced below the highest occupied pocket. Unload from the{" "}
              <Link href={`/machines/${machine.id}/carousel`} className="text-precision hover:underline">
                carousel
              </Link>{" "}
              first if you need to shrink it.
            </Notice>
          )}

          <ShopForm
            action={updateMachine}
            sections={machineSections(machine)}
            submitLabel="Save changes"
            cancelHref="/machines"
          >
            <input type="hidden" name="id" value={machine.id} />
          </ShopForm>

          <form action={deleteMachine} className="border border-line border-l-2 border-l-risk bg-raised px-4 py-3">
            <input type="hidden" name="id" value={machine.id} />
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-platinum">Remove machine</p>
            <p className="mt-1.5 text-[12px] leading-relaxed text-muted">
              {held
                ? `${[
                    setups > 0 ? `${setups} setup${setups === 1 ? "" : "s"}` : null,
                    programs > 0 ? `${programs} NC program${programs === 1 ? "" : "s"}` : null,
                  ]
                    .filter(Boolean)
                    .join(" and ")} reference this machine. Removing it would leave them planned against nothing, so it cannot be removed.`
                : loaded > 0
                  ? `Nothing is planned against this machine. Removing it returns its ${loaded} loaded tool${loaded === 1 ? "" : "s"} to the crib, which is where they would physically go.`
                  : "Nothing references this machine. The record is deleted and the removal is logged."}
            </p>
            <div className="mt-2.5">
              <Button type="submit" variant="danger" size="sm" disabled={held}>
                Remove machine
              </Button>
            </div>
          </form>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";
