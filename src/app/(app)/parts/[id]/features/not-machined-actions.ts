"use server";

import { revalidatePath } from "next/cache";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";

/**
 * "THIS FEATURE IS NOT MADE BY THIS PROGRAM"
 *
 * The coverage gate asks whether every feature is cut by an operation. On a
 * real part the answer is sometimes legitimately no: a FILLET has no operation
 * type in the CAM engine at all, a chamfer is broken at the bench, a bore
 * arrives in the extrusion, a slot is a vendor operation. Without a way to say
 * so the gate could never be cleared on those parts, and a gate that cannot be
 * cleared is a gate every shop learns to route around.
 *
 * A SENTENCE, NOT A CHECKBOX
 *
 * The reason is required and stored as prose, for three reasons. A checkbox is
 * a click, and this codebase does not clear gates with clicks. The setup sheet
 * has to print what the person actually said, because "chamfer broken at the
 * bench" is an instruction to somebody. And six months later "who decided this
 * bore was not ours" has an answer, which is why the name and the timestamp
 * travel with it.
 *
 * This is not an exception to principle 2. Nothing here is an engineering
 * condition that evidence would have to settle — it is a manufacturing fact
 * only a person can know, in the same class as confirming the material. The
 * gate does not swallow it either: coverage repeats the sentence in its detail
 * rather than reporting a clean pass.
 */

export async function recordNotMachined(partId: string, formData: FormData) {
  const user = await requireWrite();
  const featureId = String(formData.get("featureId") ?? "");

  const owned = await db.feature.findFirst({
    where: { id: featureId, partRevision: { part: { id: partId, organizationId: user.organizationId } } },
  });
  if (!owned) return;

  const reason = String(formData.get("reason") ?? "").trim().slice(0, 240);

  // An empty box is the clear. Blank and whitespace both read as "nobody
  // accounted for this", which is what assessCoverage() also decides, so the
  // stored value and the gate cannot disagree about what an empty string means.
  const clearing = reason === "";

  // Nothing to record either way — clearing what was never set is not an event.
  if (clearing && !owned.notMachinedReason) return;
  if (!clearing && owned.notMachinedReason === reason) return;

  await db.feature.update({
    where: { id: owned.id },
    data: clearing
      ? { notMachinedReason: null, notMachinedBy: null, notMachinedAt: null }
      : { notMachinedReason: reason, notMachinedBy: user.name, notMachinedAt: new Date() },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Feature",
    entityId: owned.id,
    action: "UPDATE",
    actorType: "HUMAN",
    field: "notMachinedReason",
    oldValue: owned.notMachinedReason ?? "cut by this program",
    newValue: clearing ? "cut by this program" : reason,
    reason: clearing
      ? `${owned.label} goes back to being made by this program, so the coverage gate wants an operation for it again.`
      : `${owned.label} is not made by this program. Recorded so the coverage gate can pass while still naming it.`,
  });

  revalidatePath(`/parts/${partId}`, "layout");
}
