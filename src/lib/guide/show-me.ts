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
    reach: `/parts/${partId}/tooling?guide=tool-assignment`,
    corners: `/parts/${partId}/tooling?guide=tool-assignment`,
    tolerance: `/parts/${partId}/inspection?guide=inspection-plan`,
    "inspection-capability": `/parts/${partId}/inspection?guide=inspection-plan`,
    inspection: `/parts/${partId}/inspection?guide=inspection-plan`,
    responsibility: `/parts/${partId}/responsibility`,
  };
  const g = gateId.toLowerCase();
  const l = gateLabel.toLowerCase();
  const key = Object.keys(map).find((k) => g.includes(k) || l.includes(k));
  return key ? map[key] : null;
}
