import { NextResponse } from "next/server";
import { getSessionUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { DEFAULT_ENVIRONMENT, type SavedPreset, type ViewEnvironment } from "@/lib/view-environment";

/**
 * Per-user viewport preferences. Display settings only — nothing readable or
 * writable here touches a gate, a measurement or provenance, which is why
 * this route can be this simple. User and organisation come from the
 * session, never from the request.
 *
 * Answers with a status, never a redirect. `requireUser()` sends a route
 * handler's caller to /sign-in as a 307, which a fetch() follows and then
 * parses a page of HTML as JSON — the write is lost and the client is told
 * nothing. It is also deliberately NOT behind the write-role check: which
 * colour a viewer looks at the model in is theirs, not manufacturing data.
 */

function notSignedIn(): Response {
  return NextResponse.json({ error: "Not signed in." }, { status: 401 });
}

export async function GET() {
  const user = await getSessionUser();
  if (!user) return notSignedIn();
  const row = await db.viewPreference.findUnique({ where: { userId: user.id } });
  if (!row) return NextResponse.json({ env: null, saved: [], updatedAtIso: null });

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
  // The stamp is what lets the client keep a colour it picked in the last
  // second over a server row written an hour ago.
  return NextResponse.json({ env, saved, updatedAtIso: row.updatedAt.toISOString() });
}

export async function PUT(req: Request) {
  const user = await getSessionUser();
  if (!user) return notSignedIn();
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
