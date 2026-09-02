import { NextResponse } from "next/server";
import {requireSessionApi } from "@/lib/auth";
import { db } from "@/lib/db";
import { GUIDE_MODES, type GuideMode, type GuideSession } from "@/lib/guide/engine";

/**
 * CANVAS GUIDE state — mode, experience profile, flow sessions (with the
 * visited-step history BACK ONE STEP walks). User and organisation come
 * from the session, never the request. This route can touch nothing but
 * GuideState: guide progress and manufacturing state are separate tables,
 * and this is the only one it can write.
 */

export async function GET() {
  const gate = await requireSessionApi();
  if ("denied" in gate) return gate.denied;
  const user = gate.user;
  const row = await db.guideState.findUnique({ where: { userId: user.id } });
  if (!row) return NextResponse.json({ mode: null, profile: null, sessions: {} });
  let sessions: Record<string, GuideSession> = {};
  try {
    sessions = JSON.parse(row.sessionsJson);
  } catch {
    sessions = {};
  }
  return NextResponse.json({ mode: row.mode, profile: row.profile, sessions });
}

export async function PUT(req: Request) {
  const gate = await requireSessionApi();
  if ("denied" in gate) return gate.denied;
  const user = gate.user;
  const body = (await req.json().catch(() => null)) as {
    mode?: GuideMode;
    profile?: string | null;
    sessions?: Record<string, GuideSession>;
    resetProgress?: boolean;
  } | null;
  if (!body) return NextResponse.json({ error: "Nothing to save" }, { status: 400 });
  if (body.mode !== undefined && !GUIDE_MODES.includes(body.mode)) {
    return NextResponse.json({ error: "Unknown guide mode" }, { status: 400 });
  }

  const existing = await db.guideState.findUnique({ where: { userId: user.id } });
  const mode = body.mode ?? existing?.mode ?? "ASSIST";
  const profile = body.profile !== undefined ? body.profile : existing?.profile ?? null;
  const sessionsJson = body.resetProgress
    ? "{}"
    : body.sessions !== undefined
      ? JSON.stringify(body.sessions)
      : existing?.sessionsJson ?? "{}";

  await db.guideState.upsert({
    where: { userId: user.id },
    create: { userId: user.id, organizationId: user.organizationId, mode, profile, sessionsJson },
    update: { mode, profile, sessionsJson },
  });
  return NextResponse.json({ ok: true });
}
