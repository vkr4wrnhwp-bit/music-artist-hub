import { redirect } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { loadRevision } from "@/lib/data";
import { buildFingerprint, describeFingerprintDisclosure, SHARING_DESCRIPTION, SHARING_LEVELS } from "@/lib/engines/network";
import { TopBar } from "@/components/nav";
import { Button, DevLabel, EmptyState, Notice, Panel, SectionHeading, StatusChip, Table, Td } from "@/components/ui";

/**
 * NETWORK
 *
 * Architected now, gated off by default. This page exists to make the privacy
 * model visible and auditable before any matching exists, not to advertise a
 * feature that does not ship yet.
 */

export default async function NetworkPage() {
  const user = await requireUser();

  const [org, parts] = await Promise.all([
    db.organization.findUnique({ where: { id: user.organizationId } }),
    db.part.findMany({ where: { organizationId: user.organizationId }, orderBy: { updatedAt: "desc" } }),
  ]);
  if (!org) redirect("/");

  // The example fingerprint is built from a real part so the disclosure table
  // shows exactly what would leave, not a mock-up.
  const samplePart = parts[0];
  const sample = samplePart ? await loadRevision(user.organizationId, samplePart.id) : null;
  const setupCount = sample
    ? await db.setup.count({ where: { partRevisionId: sample.revisionId } })
    : 0;

  const fingerprint = sample
    ? buildFingerprint({
        intent: sample.intent,
        stock: sample.stock,
        features: sample.features,
        setupCount,
        workholdingType: "VISE",
        machineTravelX: 30,
        operationTypes: ["FACE", "POCKET_2D", "DRILL", "CONTOUR_2D"],
      })
    : null;

  const disclosure = fingerprint ? describeFingerprintDisclosure(fingerprint) : [];

  async function setDefaultSharing(formData: FormData) {
    "use server";
    const currentUser = await requireUser();
    const level = String(formData.get("level"));
    if (!SHARING_LEVELS.includes(level as never)) redirect("/network");

    const before = await db.organization.findUnique({ where: { id: currentUser.organizationId } });
    await db.organization.update({ where: { id: currentUser.organizationId }, data: { defaultSharing: level } });

    await db.networkPermission.create({
      data: {
        organizationId: currentUser.organizationId,
        scope: "ORG",
        level,
        grantedBy: currentUser.id,
      },
    });

    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "Organization",
      entityId: currentUser.organizationId,
      action: "UPDATE",
      actorType: "HUMAN",
      field: "defaultSharing",
      oldValue: before?.defaultSharing,
      newValue: level,
      reason: "Network participation changed",
    });

    redirect("/network");
  }

  return (
    <>
      <TopBar>
        <span className="tech-label">Network</span>
        <DevLabel>Architecture only — no matching in this phase</DevLabel>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading sub="A shop's part geometry is its livelihood. The privacy model was built before the matching, not after it — so this page shows you the exact shape of what could ever leave, while the matching itself does not exist yet.">
            Manufacturing network
          </SectionHeading>

          <Notice tone="pass" title={`Current participation: ${org.defaultSharing}`}>
            {SHARING_DESCRIPTION[org.defaultSharing as keyof typeof SHARING_DESCRIPTION]}
          </Notice>

          <Panel title="Participation level">
            <form action={setDefaultSharing} className="space-y-2">
              {SHARING_LEVELS.map((level) => (
                <label
                  key={level}
                  className="flex cursor-pointer items-start gap-3 border border-line px-3.5 py-3 hover:border-line-strong"
                >
                  <input
                    type="radio"
                    name="level"
                    value={level}
                    defaultChecked={org.defaultSharing === level}
                    className="mt-1 accent-[color:var(--c-blue)]"
                  />
                  <span>
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-platinum">{level.replace(/_/g, " ")}</span>
                      {level === "PRIVATE" && <StatusChip tone="pass">Default</StatusChip>}
                    </span>
                    <span className="mt-0.5 block max-w-2xl text-[12px] leading-relaxed text-muted">
                      {SHARING_DESCRIPTION[level]}
                    </span>
                  </span>
                </label>
              ))}
              <Button type="submit" variant="primary">
                Save participation level
              </Button>
            </form>
          </Panel>

          <Panel title="What an anonymous fingerprint contains">
            {!fingerprint ? (
              <EmptyState
                title="No parts to fingerprint"
                body="Create a part and CANVAS will show you the exact anonymous record that would be produced from it."
                action={{ label: "Part library", href: "/parts" }}
              />
            ) : (
              <>
                <p className="mb-4 max-w-2xl text-[12.5px] leading-relaxed text-muted">
                  Built from <span className="text-platinum">{sample?.partName}</span>. Note what is absent: no part
                  name, no customer, no dimension, no tolerance value, no feature label, no notes, no organisation
                  identity. The record is lossy by construction — bands and families, never numbers.
                </p>
                <Table head={["Field", "Value", "Re-identification risk"]}>
                  {disclosure.map((d) => (
                    <tr key={d.field} className="hover:bg-raised">
                      <Td className="text-platinum">{d.field}</Td>
                      <Td muted>{d.value}</Td>
                      <Td>
                        <StatusChip tone={d.risk === "NONE" ? "pass" : "review"}>{d.risk}</StatusChip>
                      </Td>
                    </tr>
                  ))}
                </Table>
              </>
            )}
          </Panel>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Supplier matching" meta={<DevLabel>Not implemented</DevLabel>}>
              <EmptyState
                title="Requires network participation"
                body="When enough shops opt in, CANVAS can compare anonymous fingerprints and tell you when someone already produces a compatible component family at far higher volume than you can reach. Identity is only ever revealed if you accept an introduction."
              />
            </Panel>

            <Panel title="Revenue opportunities" meta={<DevLabel>Not implemented</DevLabel>}>
              <EmptyState
                title="Requires network participation"
                body="The same matching runs in reverse: if your shop already makes a family efficiently, CANVAS can surface demand for it elsewhere in the network."
              />
            </Panel>
          </div>

          <Panel title="Per-part sharing" dense>
            {parts.length === 0 ? (
              <p className="p-4 text-[12px] text-muted">No parts.</p>
            ) : (
              <Table head={["Part", "Sharing", "Fingerprint published"]}>
                {parts.map((p) => (
                  <tr key={p.id} className="hover:bg-raised">
                    <Td className="text-platinum">{p.name}</Td>
                    <Td>
                      <StatusChip tone={p.sharing === "PRIVATE" ? "pass" : "review"}>{p.sharing}</StatusChip>
                    </Td>
                    <Td muted>No</Td>
                  </tr>
                ))}
              </Table>
            )}
          </Panel>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";
