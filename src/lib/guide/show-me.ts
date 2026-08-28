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
    responsibility: `/parts/${partId}/responsibility`,
  };
  const g = gateId.toLowerCase();
  const l = gateLabel.toLowerCase();
  const key = Object.keys(map).find((k) => g.includes(k) || l.includes(k));
  return key ? map[key] : null;
}
