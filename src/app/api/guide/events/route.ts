import { NextResponse } from "next/server";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";

/**
 * GUIDE EVENTS — product telemetry for the shop, nothing more.
 *
 * One append-only row per interaction: where flows start, where people
 * go back, what gets skipped, where flows complete. The knowledge page
 * reads these to show FRICTION (steps people back out of or skip), so
 * the shop can see where its people struggle — the events never feed a
 * gate, never touch manufacturing state, and carry no engineering data.
 * User and organisation come from the session, never the payload.
 */

const ACTIONS = new Set(["START", "ADVANCE", "BACK", "SKIP", "RESET", "MODE_CHANGE", "FLOW_COMPLETE"]);

export async function POST(req: Request) {
  const user = await requireUser();
  const body = (await req.json().catch(() => null)) as {
    flowId?: string;
    stepId?: string | null;
    action?: string;
    detail?: string | null;
  } | null;
  if (!body?.flowId || !body.action || !ACTIONS.has(body.action)) {
    return NextResponse.json({ error: "Unknown guide event" }, { status: 400 });
  }
  await db.guideEvent.create({
    data: {
      organizationId: user.organizationId,
      userId: user.id,
      flowId: String(body.flowId).slice(0, 64),
      stepId: body.stepId ? String(body.stepId).slice(0, 64) : null,
      action: body.action,
      detail: body.detail ? String(body.detail).slice(0, 200) : null,
    },
  });
  return NextResponse.json({ ok: true });
}
