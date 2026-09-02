"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { buildPackage } from "@/lib/package";
import { canSend, canTransitionQuote } from "@/lib/engines/quoting";
import { audit } from "@/lib/audit";

/**
 * THE QUOTING WRITE PATH
 *
 * Nothing in the application wrote a Quote or a CostEstimate. The Cost panel
 * computed a live figure and discarded it on navigation, while the Quoting
 * page told the user to "open a part's Cost panel to produce one, then attach
 * it to a quote" — two controls that did not exist.
 *
 * The rule that shapes all of it: an estimate is stored as a SNAPSHOT. The
 * assumption set, the line breakdown and the warnings are frozen with the
 * price, because a quote that cannot be defended in a customer meeting is
 * worthless, and defending it means showing the inputs as they were — not
 * recomputing them today and presenting the new answer as the old promise.
 */

/* ---------------- Freeze what the cost engine just computed ---------------- */

export async function storeEstimate(partId: string, formData: FormData) {
  const user = await requireWrite();

  /*
   * Recomputed here from the package rather than posted. A price that arrives
   * in a form is a price the caller chose, and this one is going to be sent to
   * a customer.
   */
  const pkg = await buildPackage(user.organizationId, partId);
  if (!pkg) return;

  const quantityRaw = String(formData.get("quantity") ?? "").trim();
  const quantity = quantityRaw === "" ? pkg.cost.quantity : Number(quantityRaw);
  if (!Number.isInteger(quantity) || quantity < 1) return;

  const { computeCost } = await import("@/lib/engines/cost");
  const assumptions = { ...pkg.costAssumptions };
  const cost = computeCost(quantity, assumptions);

  const estimate = await db.costEstimate.create({
    data: {
      partRevisionId: pkg.revision.revisionId,
      quantity,
      // The whole assumption set and every line, so the quote can be defended
      // and so drift against today's rates can be shown rather than guessed.
      assumptionsJson: JSON.stringify(assumptions),
      linesJson: JSON.stringify({ lines: cost.lines, warnings: cost.warnings }),
      unitCost: cost.unitCost,
      unitPrice: cost.unitPrice,
      lotPrice: cost.lotPrice,
      createdBy: user.name ?? user.email,
    },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    actorType: "HUMAN",
    entityType: "CostEstimate",
    entityId: estimate.id,
    action: "CREATE",
    reason: `Stored an estimate at quantity ${quantity}${cost.warnings.length > 0 ? ` with ${cost.warnings.length} assumption warning(s)` : ""}.`,
  });

  revalidatePath(`/parts/${partId}/cost`);
  revalidatePath("/quoting");
}

/* ---------------- Raise a quote ---------------- */

export async function createQuote(formData: FormData) {
  const user = await requireWrite();
  const partId = String(formData.get("partId") ?? "");
  const quoteNumber = String(formData.get("quoteNumber") ?? "").trim().slice(0, 60);
  const customer = String(formData.get("customer") ?? "").trim().slice(0, 200);
  const validRaw = String(formData.get("validUntil") ?? "").trim();
  if (quoteNumber === "") return;

  const part = await db.part.findFirst({ where: { id: partId, organizationId: user.organizationId }, select: { id: true } });
  if (!part) return;

  const validUntil = validRaw === "" ? null : new Date(validRaw);
  const quote = await db.quote.create({
    data: {
      organizationId: user.organizationId,
      partId: part.id,
      quoteNumber,
      customer: customer || null,
      status: "DRAFT",
      validUntil: validUntil && !Number.isNaN(validUntil.getTime()) ? validUntil : null,
    },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    actorType: "HUMAN",
    entityType: "Quote",
    entityId: quote.id,
    action: "CREATE",
    reason: `Quote ${quoteNumber} raised.`,
  });

  revalidatePath("/quoting");
  redirect(`/quoting/${quote.id}`);
}

/* ---------------- Attach a stored estimate to it ---------------- */

export async function attachEstimate(quoteId: string, formData: FormData) {
  const user = await requireWrite();
  const estimateId = String(formData.get("estimateId") ?? "");

  const quote = await db.quote.findFirst({ where: { id: quoteId, organizationId: user.organizationId } });
  if (!quote) return;
  // A sent quote is a promise already made. Adding a price to it afterwards
  // would change what the customer is holding.
  if (quote.status !== "DRAFT") return;

  // The estimate must be this organisation's AND this quote's part: attaching
  // another part's price to a quote is how a wrong number reaches a customer.
  const estimate = await db.costEstimate.findFirst({
    where: {
      id: estimateId,
      partRevision: { partId: quote.partId, part: { organizationId: user.organizationId } },
    },
    select: { id: true },
  });
  if (!estimate) return;

  await db.costEstimate.update({ where: { id: estimate.id }, data: { quoteId: quote.id } });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    actorType: "HUMAN",
    entityType: "Quote",
    entityId: quote.id,
    action: "UPDATE",
    field: "estimates",
    newValue: estimate.id,
  });

  revalidatePath(`/quoting/${quoteId}`);
  revalidatePath("/quoting");
}

/* ---------------- Move it along ---------------- */

export async function advanceQuote(quoteId: string, formData: FormData) {
  const user = await requireWrite();
  const to = String(formData.get("to") ?? "");

  const quote = await db.quote.findFirst({
    where: { id: quoteId, organizationId: user.organizationId },
    include: { estimates: { select: { id: true } } },
  });
  if (!quote) return;
  if (!canTransitionQuote(quote.status, to)) return;
  // A quote with no estimate on it prices nothing.
  if (to === "SENT" && !canSend(quote.estimates.length)) return;

  await db.quote.update({ where: { id: quote.id }, data: { status: to } });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    actorType: "HUMAN",
    entityType: "Quote",
    entityId: quote.id,
    action: "UPDATE",
    field: "status",
    oldValue: quote.status,
    newValue: to,
  });

  revalidatePath(`/quoting/${quoteId}`);
  revalidatePath("/quoting");
}
