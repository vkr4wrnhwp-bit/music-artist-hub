import type { Stock } from "@/lib/domain/features";
import type { FixtureInfo } from "./scene";

/**
 * HOLD MEASUREMENTS — one list, two renderings.
 *
 * The refactor moved HOLD's floating value cards to a docked measurement
 * strip with numbered balloons at the anchors (the ballooned-drawing
 * convention AS9102 inspectors already read). The balloon numbers and the
 * strip rows must never disagree, so both render from this one ordered
 * list — the scene takes the anchors, the strip takes the values.
 *
 * Every value is something the holding model actually computed. Where it
 * has no value the row says so — "not recorded" is information, and a row
 * that vanishes when its value is missing hides exactly the gap an
 * operator should see. The one exception to a value: grip depth used to
 * display its drawing fallback as though it were a recorded number; now
 * the geometry may use the fallback but the ROW says not recorded.
 */

export interface HoldMeasurement {
  /** 1-based balloon number, stable with the row order. */
  n: number;
  label: string;
  /** Display value, already formatted. */
  value: string;
  tone: "neutral" | "pass" | "review" | "risk";
  /** Anchor in part coordinates (same frame the fixture draws in). */
  anchor: [number, number, number];
  /** Development-analysis classification, rendered on the row. */
  dev?: boolean;
}

export function holdMeasurements(fixture: FixtureInfo, stock: Stock): HoldMeasurement[] {
  const grip = fixture.gripDepth ?? Math.min(0.25, stock.z * 0.3);
  const jawTopZ = grip;
  const proud = fixture.stockProjection;

  const rows: Omit<HoldMeasurement, "n">[] = [
    {
      label: "Grip depth",
      value: fixture.gripDepth != null ? `${fixture.gripDepth.toFixed(3)}″` : "not recorded",
      tone: "neutral",
      anchor: [stock.x / 2 + 0.1, -stock.y / 2 - 0.15, grip / 2],
    },
    {
      label: "Jaw contact",
      value: fixture.contactArea != null ? `${fixture.contactArea.toFixed(3)} in² both faces` : "not calculable",
      tone: "neutral",
      anchor: [stock.x / 2 + 0.05, stock.y / 2 - 0.2, grip * 0.5],
    },
    {
      label: "Seating surface",
      value: "Parallels",
      tone: "neutral",
      anchor: [0, -stock.y / 2 - 0.3, jawTopZ - fixture.jawHeight - 0.25],
    },
    {
      label: "Proud of jaws",
      value: proud != null ? `${proud.toFixed(3)}″` : "not recorded",
      tone: "neutral",
      anchor: [-stock.x / 2 - 0.1, -stock.y / 2 - 0.15, grip + (proud ?? stock.z * 0.5) / 2],
    },
    {
      label: "Clamping pressure",
      value:
        fixture.contactPressure != null
          ? `${fixture.contactPressure.toLocaleString()} psi`
          : "not calculable — clamp force not recorded",
      tone: "neutral",
      anchor: [-stock.x / 2 - 0.05, stock.y / 2 - 0.2, grip * 0.5],
    },
  ];

  if (fixture.margin != null) {
    rows.push({
      label: `Holding margin — ${(fixture.verdict ?? "").toLowerCase()}`,
      value: `${fixture.margin.toFixed(2)}× · ${fixture.governingMode === "TIPPING" ? "rolling out" : "sliding"}`,
      tone: fixture.verdict === "ADEQUATE" ? "pass" : fixture.verdict === "MARGINAL" ? "review" : "risk",
      anchor: [0, 0, grip + (proud ?? stock.z) + 0.4],
      // holding-margin.ts carries a non-optional developmentAnalysis flag;
      // the classification renders on the row, not only in a tooltip.
      dev: true,
    });
  }

  return rows.map((r, i) => ({ ...r, n: i + 1 }));
}
