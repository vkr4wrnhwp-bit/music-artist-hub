import Link from "next/link";
import { notFound } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { TopBar } from "@/components/nav";
import { Button, Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";
import { deviceSections } from "../../device-fields";
import { updateDevice, deleteDevice } from "../../actions";

export default async function EditDevicePage(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ problem?: string }>;
}) {
  const { id } = await props.params;
  const { problem } = await props.searchParams;
  const user = await requireUser();

  const device = await db.workholdingDevice.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!device) notFound();

  const [setups, jaws] = await Promise.all([
    db.setup.count({ where: { workholdingId: id } }),
    db.jaw.count({ where: { deviceId: id } }),
  ]);
  const held = setups > 0 || jaws > 0;

  return (
    <>
      <TopBar>
        <Link href="/workholding" className="tech-label hover:text-platinum">
          Workholding
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Edit device</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub={device.description}>Edit workholding device</SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          {setups > 0 && (
            <Notice tone="review" title={`Used by ${setups} setup${setups === 1 ? "" : "s"}`}>
              Jaw geometry and clamp force feed the holding margin on every one of them. Changing a figure here changes
              those verdicts — including turning an INDETERMINATE into a number, which is the point, but re-read the
              affected setups before the next run rather than assuming the margin improved.
            </Notice>
          )}

          <ShopForm
            action={updateDevice}
            sections={deviceSections(device)}
            submitLabel="Save changes"
            cancelHref="/workholding"
          >
            <input type="hidden" name="id" value={device.id} />
          </ShopForm>

          <form action={deleteDevice} className="border border-line border-l-2 border-l-risk bg-raised px-4 py-3">
            <input type="hidden" name="id" value={device.id} />
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-platinum">Remove device</p>
            <p className="mt-1.5 text-[12px] leading-relaxed text-muted">
              {held
                ? `${[
                    setups > 0 ? `${setups} setup${setups === 1 ? "" : "s"}` : null,
                    jaws > 0 ? `${jaws} generated soft jaw${jaws === 1 ? "" : "s"}` : null,
                  ]
                    .filter(Boolean)
                    .join(" and ")} reference this device. Removing it would leave them planned against nothing, so it cannot be removed.`
                : "Nothing references this device. The record is deleted and the removal is logged."}
            </p>
            <div className="mt-2.5">
              <Button type="submit" variant="danger" size="sm" disabled={held}>
                Remove device
              </Button>
            </div>
          </form>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";
