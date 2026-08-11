import { NextResponse } from "next/server";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { DEFAULT_ENVIRONMENT, type SavedPreset, type ViewEnvironment } from "@/lib/view-environment";

/**
 * Per-user viewport preferences. Display settings only — nothing readable or
 * writable here touches a gate, a measurement or provenance, which is why
 * this route can be this simple. User and organisation come from the
 * session, never from the request.
 */

export async function GET() {
  const user = await requireUser();
  const row = await db.viewPreference.findUnique({ where: { userId: user.id } });
  if (!row) return NextResponse.json({ env: null, saved: [] });

  let env: ViewEnvironment | null = null;
  let saved: SavedPreset[] = [];
  try {
    env = { ...DEFAULT_ENVIRONMENT, ...(JSON.parse(row.envJson) as Partial<ViewEnvironment>) };
  } catch {
    env = null;
  }
  try {
    saved = JSON.parse(row.savedPresetsJson) as SavedPreset[];
  } catch {
    saved = [];
  }
  return NextResponse.json({ env, saved });
}

export async function PUT(req: Request) {
  const user = await requireUser();
  const body = (await req.json().catch(() => null)) as { env?: ViewEnvironment; saved?: SavedPreset[] } | null;
  if (!body || (body.env === undefined && body.saved === undefined)) {
    return NextResponse.json({ error: "Nothing to save" }, { status: 400 });
  }

  const existing = await db.viewPreference.findUnique({ where: { userId: user.id } });
  const envJson = body.env !== undefined ? JSON.stringify(body.env) : existing?.envJson ?? JSON.stringify(DEFAULT_ENVIRONMENT);
  const savedPresetsJson = body.saved !== undefined ? JSON.stringify(body.saved) : existing?.savedPresetsJson ?? "[]";

  await db.viewPreference.upsert({
    where: { userId: user.id },
    create: { userId: user.id, organizationId: user.organizationId, envJson, savedPresetsJson },
    update: { envJson, savedPresetsJson },
  });
  return NextResponse.json({ ok: true });
}
