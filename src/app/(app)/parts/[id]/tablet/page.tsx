import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { buildPackage } from "@/lib/package";
import { TopBar } from "@/components/nav";
import { DevLabel, StatusChip } from "@/components/ui";
import { SetupPhotoUpload } from "@/components/tablet/setup-photos";
import { storageIsEphemeral } from "@/lib/storage";

/**
 * MACHINIST TABLET VIEW
 *
 * A projection of the same manufacturing package the engineering screens
 * render — it hides depth, it does not hold different truth. Five sections in
 * the order a setup actually happens: SETUP, TOOLS, PROBE, RUN, SIGN-OFF.
 *
 * The checklist is testimony, stored as HUMAN-typed audit entries. Checking a
 * section records who and when; it clears no readiness gate that requires
 * evidence. And the sign-off control only exists while every blocking gate
 * passes — when gates are failing the signature line is replaced by the
 * failing-gate list. The tablet never offers a signature over a red gate.
 *
 * Touch targets are 48px minimum; data is mono with units, per the micro-copy
 * standard. No percentages anywhere: the header state is the worst gate.
 */

const SECTIONS = ["SETUP", "TOOLS", "PROBE", "RUN"] as const;
type Section = (typeof SECTIONS)[number];

const SECTION_TITLE: Record<Section, string> = {
  SETUP: "Setup",
  TOOLS: "Tools",
  PROBE: "Probe",
  RUN: "Run",
};

export default async function TabletPage(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ setup?: string }>;
}) {
  const { id } = await props.params;
  const { setup: setupParam } = await props.searchParams;
  const user = await requireUser();

  const pkg = await buildPackage(user.organizationId, id);
  if (!pkg) notFound();

  const setups = pkg.setups;
  const setupIndex = Math.min(Math.max(0, Number(setupParam ?? "1") - 1), Math.max(0, setups.length - 1));
  const setup = setups[setupIndex] ?? null;

  const failingGates = pkg.readiness.gates.filter(
    (g) => g.blocking && g.status !== "PASS" && g.status !== "REVIEW",
  );

  /* ---------------- Checklist state from the audit trail ---------------- */
  // Append-only: the latest entry per section wins. There is no checklist
  // table because the record of who checked what, when, IS the state.
  const checklistEntries = setup
    ? await db.auditLog.findMany({
        where: { organizationId: user.organizationId, entityType: "SetupChecklist", entityId: setup.id },
        orderBy: { createdAt: "asc" },
        include: { user: true },
      })
    : [];
  /* ---------------- How this setup was actually built ---------------- */
  const setupPhotos = setup
    ? await db.uploadedAsset.findMany({
        where: { organizationId: user.organizationId, setupId: setup.id },
        orderBy: { createdAt: "desc" },
        take: 12,
      })
    : [];
  // `uploadedBy` is a bare column with no relation, so the names are looked up
  // separately rather than joined.
  const photoUploaders = new Map(
    (
      await db.user.findMany({
        where: { organizationId: user.organizationId, id: { in: [...new Set(setupPhotos.map((ph) => ph.uploadedBy))] } },
        select: { id: true, name: true },
      })
    ).map((u) => [u.id, u.name]),
  );

  const sectionState = new Map<string, { done: boolean; by: string; atIso: string }>();
  for (const e of checklistEntries) {
    if (!e.field) continue;
    sectionState.set(e.field, {
      done: e.newValue === "DONE",
      by: e.user?.name ?? "Operator",
      atIso: e.createdAt.toISOString(),
    });
  }
  const signoffEntry = setup
    ? await db.auditLog.findFirst({
        where: { organizationId: user.organizationId, entityType: "Setup", entityId: setup.id, action: "APPROVE" },
        orderBy: { createdAt: "desc" },
        include: { user: true },
      })
    : null;

  /* ---------------- Actions ---------------- */

  async function toggleSection(formData: FormData) {
    "use server";
    const currentUser = await requireWrite();
    const setupId = String(formData.get("setupId"));
    const section = String(formData.get("section"));
    const done = String(formData.get("done")) === "1";
    if (!SECTIONS.includes(section as Section)) return;

    // The setup must belong to a revision in this organisation — reached
    // through the part, never trusted from the form alone.
    const row = await db.setup.findFirst({
      where: { id: setupId, partRevision: { part: { organizationId: currentUser.organizationId } } },
    });
    if (!row) return;

    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "SetupChecklist",
      entityId: row.id,
      action: "UPDATE",
      actorType: "HUMAN",
      field: section,
      newValue: done ? "DONE" : "PENDING",
      reason: done ? "Checked off on the shop-floor tablet" : "Unchecked on the shop-floor tablet",
    });
    redirect(`/parts/${id}/tablet?setup=${String(formData.get("setupSeq"))}`);
  }

  async function signOff(formData: FormData) {
    "use server";
    const currentUser = await requireWrite();
    const setupId = String(formData.get("setupId"));

    const fresh = await buildPackage(currentUser.organizationId, id);
    if (!fresh) notFound();
    const row = fresh.setups.find((s) => s.id === setupId);
    if (!row) return;

    // Re-checked at write time: the rendered button is not the gate.
    const failing = fresh.readiness.gates.filter(
      (g) => g.blocking && g.status !== "PASS" && g.status !== "REVIEW",
    );
    if (failing.length > 0) redirect(`/parts/${id}/tablet?setup=${String(formData.get("setupSeq"))}`);

    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "Setup",
      entityId: row.id,
      action: "APPROVE",
      actorType: "HUMAN",
      reason: "Setup complete as documented — signed off at the machine.",
    });
    redirect(`/parts/${id}/tablet?setup=${String(formData.get("setupSeq"))}`);
  }

  /* ---------------- Derived section data ---------------- */

  const setupTools = setup
    ? [...new Map(setup.operations.filter((o) => o.tool).map((o) => [o.tool!.id, o.tool!])).values()]
    : [];
  const opCards = setup
    ? setup.operations.map((o) => {
        const tp = pkg.toolpaths.find((t) => t.operationId === o.id);
        return {
          id: o.id,
          sequence: o.sequence,
          label: o.label,
          toolNumber: o.tool?.toolNumber ?? null,
          cycleMinutes: tp?.cycleTimeMinutes ?? null,
          // The one warning that matters: the first one the engine emitted.
          warning: tp?.warnings[0] ?? null,
        };
      })
    : [];
  const stock = pkg.revision.stock;

  const stateChip = (s: Section) => {
    const st = sectionState.get(s);
    return st?.done ? (
      <span className="font-mono text-[12px] uppercase tracking-[0.1em] text-pass">
        Done · {st.by} · {st.atIso.slice(11, 16)}Z
      </span>
    ) : (
      <span className="font-mono text-[12px] uppercase tracking-[0.1em] text-muted">Pending</span>
    );
  };

  const checkButton = (s: Section) => {
    const done = sectionState.get(s)?.done ?? false;
    return (
      <form action={toggleSection}>
        <input type="hidden" name="setupId" value={setup!.id} />
        <input type="hidden" name="setupSeq" value={setup!.sequence} />
        <input type="hidden" name="section" value={s} />
        <input type="hidden" name="done" value={done ? "0" : "1"} />
        <button
          type="submit"
          className={`min-h-12 border px-6 font-mono text-[13px] uppercase tracking-[0.12em] ${
            done
              ? "border-line-strong text-muted hover:text-platinum"
              : "border-precision/60 text-precision hover:bg-precision/10"
          }`}
        >
          {done ? "Uncheck" : `Mark ${SECTION_TITLE[s]} done`}
        </button>
      </form>
    );
  };

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {pkg.revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Tablet</span>
        <DevLabel>Machinist projection — same package, less depth</DevLabel>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-5">
          {/* ---------------- Header strip ---------------- */}
          <div className="flex flex-wrap items-center justify-between gap-3 border border-line-strong bg-surface px-4 py-3">
            <span className="font-mono text-[16px] tracking-tight text-platinum">
              {pkg.revision.partName} · REV {pkg.revision.revision}
            </span>
            <span className="flex items-center gap-3">
              {setups.length > 1 && (
                <span className="flex gap-1">
                  {setups.map((s, i) => (
                    <Link
                      key={s.id}
                      href={`/parts/${id}/tablet?setup=${s.sequence}`}
                      className={`flex min-h-12 min-w-12 items-center justify-center border font-mono text-[14px] ${
                        i === setupIndex ? "border-precision/60 text-precision" : "border-line text-muted hover:text-platinum"
                      }`}
                    >
                      {s.sequence}
                    </Link>
                  ))}
                </span>
              )}
              <span className="font-mono text-[13px] uppercase tracking-[0.12em] text-muted">
                Setup {setup ? `${setup.sequence} of ${setups.length}` : "— none defined"}
              </span>
              {failingGates.length > 0 ? (
                <StatusChip tone="risk">Not ready — {failingGates.length} blocking</StatusChip>
              ) : (
                <StatusChip tone="pass">{pkg.readiness.overall === "READY_TO_RUN" ? "Ready" : "Review required"}</StatusChip>
              )}
            </span>
          </div>

          {!setup ? (
            <p className="border border-line px-4 py-6 text-[14px] text-muted">
              This part has no setups yet. Setups are created when a machinist approach is approved.
            </p>
          ) : (
            <>
              {/* ---------------- 1. SETUP ---------------- */}
              <section className="border border-line bg-surface">
                <div className="flex items-center justify-between border-b border-line px-4 py-3">
                  <h2 className="font-mono text-[14px] uppercase tracking-[0.14em] text-platinum">1 · Setup</h2>
                  {stateChip("SETUP")}
                </div>
                <div className="grid gap-x-8 gap-y-2 px-4 py-4 sm:grid-cols-2">
                  {[
                    ["Machine", setup.machine ? `${setup.machine.manufacturer} ${setup.machine.model}` : "Not assigned"],
                    ["Workholding", setup.workholding?.description ?? "Not assigned"],
                    [
                      "Jaws",
                      setup.jaws.length > 0
                        ? setup.jaws
                            .map((j) => `${j.side.toLowerCase()} jaw, ${j.stepDepth.toFixed(3)} in step`)
                            .join(" · ")
                        : setup.jawSurface
                          ? setup.jawSurface.replace(/_/g, " ").toLowerCase()
                          : "Not recorded",
                    ],
                    ["Orientation", `${setup.orientation} face up`],
                    ["Work offset", setup.workOffset],
                    ["Grip depth", setup.gripDepth != null ? `${setup.gripDepth.toFixed(3)} in` : "Not recorded"],
                    ["Projection", setup.stockProjection != null ? `${setup.stockProjection.toFixed(3)} in` : "Not recorded"],
                    ["Parallels", setup.parallelHeight != null ? `${setup.parallelHeight.toFixed(3)} in` : "None"],
                    [
                      "Clamp force",
                      setup.clampForce != null
                        ? `${setup.clampForce.toFixed(0)} lbf`
                        : setup.workholding?.clampForce != null
                          ? `Device rating ${setup.workholding.clampForce.toFixed(0)} lbf — applied force not recorded`
                          : "Not recorded",
                    ],
                    ["Positive stop", setup.hasPositiveStop ? "Yes" : "No"],
                  ].map(([k, v]) => (
                    <div key={k} className="flex items-baseline justify-between gap-4 border-b border-line/50 py-1.5">
                      <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">{k}</span>
                      <span className="text-right font-mono text-[14px] text-platinum tabular-nums">{v}</span>
                    </div>
                  ))}
                </div>
                {setup.datumNote && (
                  <p className="border-t border-line px-4 py-3 text-[13px] leading-relaxed text-platinum-dim">{setup.datumNote}</p>
                )}
                {/* A photograph of how this setup was built. Which parallels,
                    which stop, which way the stock faced — that knowledge
                    leaves with the person who ran it. */}
                <div className="border-t border-line px-4 py-3">
                  <p className="instrument-label mb-2">How this setup was built</p>
                  {setupPhotos.length > 0 && (
                    <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
                      {setupPhotos.map((ph) => (
                        <figure key={ph.id} className="m-0 border border-line-strong">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={"/api/assets/" + encodeURIComponent(ph.storageKey)}
                            alt={"Setup photograph " + ph.filename}
                            className="block aspect-square w-full object-cover"
                          />
                          <figcaption className="border-t border-line px-1.5 py-1 font-mono text-[9.5px] text-muted tabular-nums">
                            {photoUploaders.get(ph.uploadedBy) ?? "unknown"} ·{" "}
                            {ph.createdAt.toISOString().slice(0, 16).replace("T", " ")}
                          </figcaption>
                        </figure>
                      ))}
                    </div>
                  )}
                  <SetupPhotoUpload setupId={setup.id} />
                  <p className="mt-2 text-[11.5px] leading-relaxed text-muted">
                    A photograph is a record of how this setup was built. It is not verification that it is correct,
                    and it clears no gate.
                  </p>
                  {storageIsEphemeral && (
                    <p className="mt-1.5 text-[11.5px] leading-relaxed text-review">
                      Storage on this deployment is ephemeral — photographs are lost on the next redeploy. Keep
                      anything you need to reproduce a setup somewhere else as well.
                    </p>
                  )}
                </div>
                <div className="border-t border-line px-4 py-3">{checkButton("SETUP")}</div>
              </section>

              {/* ---------------- 2. TOOLS ---------------- */}
              <section className="border border-line bg-surface">
                <div className="flex items-center justify-between border-b border-line px-4 py-3">
                  <h2 className="font-mono text-[14px] uppercase tracking-[0.14em] text-platinum">2 · Tools</h2>
                  {stateChip("TOOLS")}
                </div>
                <ul>
                  {setupTools.map((t) => (
                    <li key={t.id} className="flex flex-wrap items-baseline gap-x-6 gap-y-1 border-b border-line/50 px-4 py-3 last:border-0">
                      <span className="font-mono text-[16px] text-precision">T{t.toolNumber}</span>
                      <span className="min-w-0 flex-1 text-[14px] text-platinum">{t.description}</span>
                      <span className="font-mono text-[13px] text-platinum-dim tabular-nums">⌀{t.diameter.toFixed(4)} in</span>
                      <span className="font-mono text-[13px] text-platinum-dim tabular-nums">stickout {t.stickout.toFixed(3)} in</span>
                    </li>
                  ))}
                  {setupTools.length === 0 && (
                    <li className="px-4 py-3 text-[13px] text-muted">No tools assigned to this setup.</li>
                  )}
                </ul>
                <p className="border-t border-line px-4 py-2.5 text-[12.5px] leading-relaxed text-muted">
                  Check each stickout against the loaded tool before marking this done — the holding and clearance
                  numbers upstream were computed from these values, not from what is actually in the spindle.
                </p>
                <div className="border-t border-line px-4 py-3">{checkButton("TOOLS")}</div>
              </section>

              {/* ---------------- 3. PROBE ---------------- */}
              <section className="border border-line bg-surface">
                <div className="flex items-center justify-between border-b border-line px-4 py-3">
                  <h2 className="font-mono text-[14px] uppercase tracking-[0.14em] text-platinum">3 · Probe</h2>
                  {stateChip("PROBE")}
                </div>
                <div className="space-y-2 px-4 py-4">
                  <p className="text-[13px] leading-relaxed text-platinum-dim">
                    Set {setup.workOffset} from the stock in the vise. Expected stock, from the part record:
                  </p>
                  {stock ? (
                    <p className="font-mono text-[15px] text-platinum tabular-nums">
                      {stock.x.toFixed(3)} × {stock.y.toFixed(3)} × {stock.z.toFixed(3)} in · {stock.material}
                    </p>
                  ) : (
                    <p className="text-[13px] text-review">No stock recorded — the probe expectations cannot be stated.</p>
                  )}
                  <p className="text-[13px] leading-relaxed text-platinum-dim">
                    Z0 is the top of stock. With {setup.stockProjection != null ? `${setup.stockProjection.toFixed(3)} in projection` : "the recorded projection"}{" "}
                    above the jaws, verify the probed top against the parallels before trusting a single depth in the
                    program.
                  </p>
                  <p className="text-[12.5px] leading-relaxed text-muted">
                    A stored probing routine with per-feature expected values does not exist for this setup — these
                    expectations are derived from the stock record and setup geometry, and say so.
                  </p>
                </div>
                <div className="border-t border-line px-4 py-3">{checkButton("PROBE")}</div>
              </section>

              {/* ---------------- 4. RUN ---------------- */}
              <section className="border border-line bg-surface">
                <div className="flex items-center justify-between border-b border-line px-4 py-3">
                  <h2 className="font-mono text-[14px] uppercase tracking-[0.14em] text-platinum">4 · Run</h2>
                  {stateChip("RUN")}
                </div>
                <ul>
                  {opCards.map((o) => (
                    <li key={o.id} className="border-b border-line/50 px-4 py-3 last:border-0">
                      <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1">
                        <span className="font-mono text-[13px] text-muted">{String(o.sequence).padStart(2, "0")}</span>
                        <span className="min-w-0 flex-1 text-[14px] text-platinum">{o.label}</span>
                        {o.toolNumber != null && <span className="font-mono text-[14px] text-precision">T{o.toolNumber}</span>}
                        <span className="font-mono text-[13px] text-platinum-dim tabular-nums">
                          {o.cycleMinutes != null ? `${o.cycleMinutes.toFixed(1)} min` : "no toolpath"}
                        </span>
                      </div>
                      {o.warning && <p className="mt-1 text-[12.5px] leading-relaxed text-review">{o.warning}</p>}
                    </li>
                  ))}
                  {opCards.length === 0 && <li className="px-4 py-3 text-[13px] text-muted">No operations in this setup.</li>}
                </ul>
                <div className="border-t border-line px-4 py-3">{checkButton("RUN")}</div>
              </section>

              {/* ---------------- 5. SIGN-OFF ---------------- */}
              <section className="border border-line-strong bg-surface">
                <div className="border-b border-line px-4 py-3">
                  <h2 className="font-mono text-[14px] uppercase tracking-[0.14em] text-platinum">5 · Sign-off</h2>
                </div>
                {failingGates.length > 0 ? (
                  <div className="px-4 py-4">
                    <p className="mb-2 text-[13.5px] leading-relaxed text-platinum-dim">
                      There is no signature line while gates are failing. These block it:
                    </p>
                    <ul className="space-y-1.5">
                      {failingGates.map((g) => (
                        <li key={g.id} className="flex items-baseline gap-3">
                          <span className="font-mono text-[12px] uppercase tracking-[0.1em] text-risk">{g.status}</span>
                          <span className="text-[13.5px] text-platinum">{g.label}</span>
                          <span className="min-w-0 flex-1 truncate text-[12.5px] text-muted">{g.detail}</span>
                        </li>
                      ))}
                    </ul>
                    <p className="mt-3 text-[12.5px] leading-relaxed text-muted">
                      Signing here is testimony, not evidence — it cannot clear these. The gates move when the
                      underlying facts move.
                    </p>
                  </div>
                ) : signoffEntry ? (
                  <div className="px-4 py-4">
                    <p className="font-mono text-[14px] text-pass">
                      Signed off — {signoffEntry.user?.name ?? "Operator"} ·{" "}
                      {signoffEntry.createdAt.toISOString().slice(0, 16).replace("T", " ")}Z
                    </p>
                    <p className="mt-1 text-[12.5px] text-muted">
                      Recorded as a HUMAN audit entry against this setup: setup complete as documented.
                    </p>
                  </div>
                ) : (
                  <form action={signOff} className="px-4 py-4">
                    <input type="hidden" name="setupId" value={setup.id} />
                    <input type="hidden" name="setupSeq" value={setup.sequence} />
                    <p className="mb-3 text-[13.5px] leading-relaxed text-platinum-dim">
                      Every blocking gate currently passes. Signing records your name and the time against this setup:
                      &ldquo;Setup complete as documented.&rdquo;
                    </p>
                    <button
                      type="submit"
                      className="min-h-14 w-full border border-pass/60 px-6 font-mono text-[15px] uppercase tracking-[0.14em] text-pass hover:bg-pass/10 sm:w-auto"
                    >
                      Sign off setup {setup.sequence}
                    </button>
                  </form>
                )}
              </section>
            </>
          )}
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";
