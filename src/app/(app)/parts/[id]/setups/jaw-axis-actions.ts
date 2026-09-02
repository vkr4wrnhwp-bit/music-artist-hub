"use server";

import { revalidatePath } from "next/cache";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";

/**
 * RECORDING WHICH AXIS THE JAWS CLOSE ON
 *
 * This is the datum that decides where the fixture is. Without it the
 * simulator models no vise at all and says so; with it the cutter is checked
 * against two jaw boxes.
 *
 * It is a measured fact about the setup, not a preference, so:
 *
 *   - There is no default. A setup with no axis recorded stays null, and the
 *     checks that need it report that they did not run. Defaulting to X would
 *     put the modelled vise on the wrong two faces half the time, and a
 *     fixture in the wrong place clears exactly the setup that would crash.
 *   - Only X and Y are accepted. An unrecognised value is refused rather than
 *     stored, because a stored value is one a collision check will trust.
 *   - The setup is re-resolved from the session's organisation through its
 *     revision's part. Setup carries no organizationId of its own, and a
 *     setup id posted in a form is one another shop could name.
 */

export async function recordJawAxis(partId: string, formData: FormData) {
  const user = await requireWrite();

  const setupId = String(formData.get("setupId") ?? "");
  const axis = String(formData.get("jawAxis") ?? "");
  if (axis !== "X" && axis !== "Y" && axis !== "") return;

  const owned = await db.setup.findFirst({
    where: { id: setupId, partRevision: { part: { id: partId, organizationId: user.organizationId } } },
    select: { id: true },
  });
  if (!owned) return;

  await db.setup.update({ where: { id: owned.id }, data: { jawAxis: axis === "" ? null : axis } });
  revalidatePath(`/parts/${partId}/setups`);
  revalidatePath(`/parts/${partId}`);
}
