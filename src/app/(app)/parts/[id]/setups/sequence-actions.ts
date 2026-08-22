"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { proposeSequence, type SequencedOperation } from "@/lib/engines/sequencing";

/**
 * Applying a sequence proposal.
 *
 * The proposal is recomputed here from the database rather than trusted from
 * the form. A posted order is a list of ids a browser sent; re-deriving it
 * server-side means the order that gets written is the one the engine
 * actually stands behind, and a stale page cannot reorder a plan that has
 * changed underneath it.
 *
 * Nothing about the cutting changes. Toolpaths are per operation and are not
 * regenerated — only `Operation.sequence` moves — but the posted program's
 * order does change, so the audit entry says so and the UI says so.
 */
export async function applySequenceProposal(formData: FormData): Promise<void> {
  const user = await requireWrite();
  const setupId = String(formData.get("setupId") ?? "");
  const partId = String(formData.get("partId") ?? "");
  const back = `/parts/${partId}/setups`;

  const setup = await db.setup.findFirst({
    where: { id: setupId, partRevision: { part: { organizationId: user.organizationId } } },
    include: { operations: { include: { tool: true, feature: true }, orderBy: { sequence: "asc" } } },
  });
  if (!setup) redirect("/parts");

  const ops: SequencedOperation[] = setup.operations.map((o) => ({
    id: o.id,
    sequence: o.sequence,
    type: o.type,
    label: o.label,
    featureId: o.featureId,
    featureLabel: o.feature?.label ?? null,
    toolNumber: o.tool?.toolNumber ?? null,
  }));

  const proposal = proposeSequence(ops);

  // Nothing to do is not an error, but it must not be written either — an
  // audit entry for a change that did not happen is noise in the record.
  if (proposal.saved === 0 && proposal.violations.length === 0) {
    redirect(`${back}?problem=${encodeURIComponent("Nothing to apply — the sequence is already the best this engine can find.")}`);
  }

  const before = ops.map((o) => `T${o.toolNumber ?? "-"} ${o.type}`).join(" → ");
  await db.$transaction(
    proposal.proposedOrder.map((id, i) =>
      db.operation.update({ where: { id }, data: { sequence: i + 1 } }),
    ),
  );
  const byId = new Map(ops.map((o) => [o.id, o]));
  const after = proposal.proposedOrder.map((id) => {
    const o = byId.get(id);
    return `T${o?.toolNumber ?? "-"} ${o?.type}`;
  }).join(" → ");

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Setup",
    entityId: setupId,
    action: "UPDATE",
    actorType: "HUMAN",
    field: "operation sequence",
    oldValue: before,
    newValue: after,
    reason:
      proposal.violations.length > 0
        ? `Operation order corrected: ${proposal.violations.length} precedence rule${proposal.violations.length === 1 ? "" : "s"} the plan was breaking. Toolpaths unchanged; the posted program order changes and must be re-verified.`
        : `Operation order regrouped to save ${proposal.saved} tool change${proposal.saved === 1 ? "" : "s"}. Toolpaths unchanged; the posted program order changes and must be re-verified.`,
  });

  revalidatePath(back);
  redirect(back);
}
