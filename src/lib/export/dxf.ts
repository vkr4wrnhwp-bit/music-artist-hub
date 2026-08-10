/**
 * MINIMAL DXF WRITER — deterministic, dependency-free
 *
 * Emits R12-style ASCII DXF: LINE, ARC, CIRCLE and TEXT entities on named
 * layers, with 999 comment records up front. R12 is the dialect every CAM
 * package and every free viewer still reads, which is the entire point of a
 * jaw drawing — it goes wherever the shop's programming seat is.
 *
 * Nothing here approximates: an arc is written as an arc, not as chords.
 */

export interface DxfBuilder {
  comment(text: string): void;
  line(layer: string, x1: number, y1: number, x2: number, y2: number): void;
  /** Angles in degrees, counter-clockwise from +X, per DXF convention. */
  arc(layer: string, cx: number, cy: number, r: number, startDeg: number, endDeg: number): void;
  circle(layer: string, cx: number, cy: number, r: number): void;
  text(layer: string, x: number, y: number, height: number, value: string): void;
  build(): string;
}

export function createDxf(): DxfBuilder {
  const comments: string[] = [];
  const entities: string[] = [];
  const n = (v: number) => Number(v.toFixed(6)).toString();

  return {
    comment(text) {
      comments.push(`999\n${text}`);
    },
    line(layer, x1, y1, x2, y2) {
      entities.push(`0\nLINE\n8\n${layer}\n10\n${n(x1)}\n20\n${n(y1)}\n11\n${n(x2)}\n21\n${n(y2)}`);
    },
    arc(layer, cx, cy, r, startDeg, endDeg) {
      entities.push(`0\nARC\n8\n${layer}\n10\n${n(cx)}\n20\n${n(cy)}\n40\n${n(r)}\n50\n${n(startDeg)}\n51\n${n(endDeg)}`);
    },
    circle(layer, cx, cy, r) {
      entities.push(`0\nCIRCLE\n8\n${layer}\n10\n${n(cx)}\n20\n${n(cy)}\n40\n${n(r)}`);
    },
    text(layer, x, y, height, value) {
      entities.push(`0\nTEXT\n8\n${layer}\n10\n${n(x)}\n20\n${n(y)}\n40\n${n(height)}\n1\n${value}`);
    },
    build() {
      return [
        ...comments,
        "0\nSECTION\n2\nENTITIES",
        ...entities,
        "0\nENDSEC",
        "0\nEOF",
      ].join("\n");
    },
  };
}
