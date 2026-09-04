/**
 * SHOW ME routing — gate → the physical scene behind it.
 *
 * One map, shared by the readiness page and the Guide card, so the two
 * never disagree about where a blocker lives. Coach-mark targets
 * (?guide=…) highlight the exact element on arrival. Gates whose blocker
 * has no physical scene return null — no link is better than a vague one.
 */
export function showMeHrefFor(partId: string, gateId: string, gateLabel: string): string | null {
  const map: Record<string, string> = {
    geometry: `/parts/${partId}?guide=context-part`,
    stock: `/parts/${partId}?guide=define-stock`,
    machine: `/parts/${partId}?guide=define-stock`,
    material: `/parts/${partId}?guide=context-part`,
    workholding: `/parts/${partId}/setups?guide=hold-scene`,
    tools: `/parts/${partId}/tooling?guide=tool-assignment`,
    // The changer mapping lives on the machines page — the tool-loading
    // gate's evidence is pockets, not assignments. This was returning null
    // on a BLOCKING gate: no link on the one gate whose fix lives furthest
    // from the part.
    "tool-loading": `/machines`,
    reach: `/parts/${partId}/tooling?guide=tool-assignment`,
    corners: `/parts/${partId}/tooling?guide=tool-assignment`,
    tolerance: `/parts/${partId}/inspection?guide=inspection-plan`,
    /*
     * Capability and plan are different gates with different evidence, and
     * they were pointed at the same page.
     *
     * The inspection PLAN gate is about sessions and readings, which live on
     * the part. The CAPABILITY gate is a property of the instruments the shop
     * owns — it moves when a more capable instrument is recorded, and nothing
     * on the part's inspection page can move it. Sending a machinist there
     * with a failing capability gate hands him the one screen that cannot
     * help; the metrology library is where the answer is.
     */
    "inspection-capability": `/metrology`,
    inspection: `/parts/${partId}/inspection?guide=inspection-plan`,
    /*
     * The coverage gate's scene is the operation plan — the list where you can
     * see, per setup, which features are cut and which are not. The machinist
     * page is where an approach that creates operations is chosen, and that is
     * where next-action.ts sends the operator to FIX it; SHOW ME is the other
     * half of that pair and lands on the evidence rather than on the remedy.
     */
    coverage: `/parts/${partId}/setups`,
    responsibility: `/parts/${partId}/responsibility`,
  };
  const g = gateId.toLowerCase();
  const l = gateLabel.toLowerCase();
  const key = Object.keys(map).find((k) => g.includes(k) || l.includes(k));
  return key ? map[key] : null;
}

/* ------------------------------------------------------------------ */
/* Review findings                                                     */
/* ------------------------------------------------------------------ */

/** The contexts a deep link may put the workspace into. */
export const FOCUS_CONTEXTS = ["PART", "HOLD", "CUT", "VERIFY"] as const;
export type FocusContext = (typeof FOCUS_CONTEXTS)[number];

/**
 * Where SHOW ME on a review finding should land.
 *
 * A finding already carries the operation, the feature, the point and the
 * context it is best understood in. The link tested `setupId` FIRST, and four
 * of the six finding kinds carry both a setupId and CUT context — including
 * the lateral rapid below the jaw line, the one the engine's own tests call
 * the case this check exists for. All of them landed on a list of setup
 * cards, which cannot show a move. The coordinate triple was printed beside
 * the button instead, which is a machinist reading numbers where they could
 * be looking at the thing.
 *
 * Context decides, not setupId.
 *
 * HOLD is conditional and the condition is load-bearing: the workspace builds
 * its HOLD scene from the FIRST setup alone, so deep-linking a second setup's
 * grip finding would draw the wrong vise while claiming to show the problem.
 * That case keeps today's behaviour and goes to the setup list.
 */
export function findingShowMeHref(
  partId: string,
  location: {
    setupId: string | null;
    operationId: string | null;
    featureId: string | null;
    context: FocusContext;
  },
  primarySetupId: string | null,
): string {
  switch (location.context) {
    case "VERIFY":
      return location.featureId
        ? `/parts/${partId}?context=VERIFY&feature=${location.featureId}`
        : `/parts/${partId}?context=VERIFY`;
    case "CUT":
      return location.operationId
        ? `/parts/${partId}?context=CUT&op=${location.operationId}`
        : `/parts/${partId}?context=CUT`;
    case "HOLD":
      return location.setupId !== null && location.setupId === primarySetupId
        ? `/parts/${partId}?context=HOLD`
        : `/parts/${partId}/setups`;
    case "PART":
    default:
      return location.featureId
        ? `/parts/${partId}?context=PART&feature=${location.featureId}`
        : `/parts/${partId}`;
  }
}

/**
 * What a deep link is asking the workspace to focus on, after checking that it
 * exists on THIS part.
 *
 * The ids arrive in a URL. They are matched against ids that came out of an
 * organisation-scoped package, so an id belonging to another shop's part
 * simply does not match and is dropped — a request parameter can select among
 * what the session already loaded, never introduce anything.
 */
export function pickFocus(
  sp: { context?: string; feature?: string; op?: string },
  featureIds: string[],
  operationIds: string[],
): { context: FocusContext | null; featureId: string | null; operationId: string | null } {
  const context = FOCUS_CONTEXTS.find((c) => c === sp.context) ?? null;
  return {
    context,
    featureId: sp.feature && featureIds.includes(sp.feature) ? sp.feature : null,
    operationId: sp.op && operationIds.includes(sp.op) ? sp.op : null,
  };
}
