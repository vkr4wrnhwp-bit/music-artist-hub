/**
 * Whether a workspace panel is docked away, as stored per browser.
 *
 * Three panels answer this question — the context drawer, the feature panel
 * and the operation runway — each with its own key, its own encoding and its
 * own default. What they must not have is their own idea of what FOCUS means.
 *
 * Focus Workspace is an overlay on the stored preference, not a replacement
 * for it. Entering focus collapses everything; leaving focus puts back what
 * the machinist had, which is not the same as opening everything. A panel
 * they shut an hour ago has no business reappearing because they glanced at
 * the part full-screen.
 *
 * Nothing here is engineering-grade. It is layout, and it is allowed to be
 * forgotten if storage is unavailable — hence the fallback rather than a
 * refusal.
 */

/** Pure resolution: an explicit stored choice always beats the default. */
export function resolveCollapsed(stored: string | null, collapsedValue: string, fallback: boolean): boolean {
  return stored === null ? fallback : stored === collapsedValue;
}

/** The same rule, against this browser's storage. */
export function readCollapsed(key: string, collapsedValue: string, fallback: boolean): boolean {
  try {
    return resolveCollapsed(window.localStorage.getItem(key), collapsedValue, fallback);
  } catch {
    return fallback;
  }
}
