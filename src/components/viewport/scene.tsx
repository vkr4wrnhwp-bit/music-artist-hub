"use client";

import { Canvas, useThree } from "@react-three/fiber";
import { ContactShadows, Edges, Environment, GizmoHelper, GizmoViewcube, Grid, Html, Lightformer, OrbitControls, Line } from "@react-three/drei";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { Feature, Stock } from "@/lib/domain/features";
import { buildPartSolid } from "./part-solid";
import type { Move } from "@/lib/engines/cam/types";

/**
 * PART VIEWPORT
 *
 * Renders the parametric feature model, the stock envelope, the workholding
 * and the toolpath in machine coordinates: X right, Y back, Z up, origin at
 * the datum. Three.js is Y-up, so the whole scene is rotated once at the root
 * rather than every geometry being authored in a different convention.
 *
 * Features are rendered as the volume they REMOVE, drawn as translucent
 * negative space, because that is what a machinist is actually reasoning
 * about. Phase 1 does not perform boolean subtraction — see
 * /docs/CAM_ENGINE.md for why that is honest rather than convenient.
 */

export type ViewMode = "SHADED" | "WIREFRAME" | "TRANSPARENT";

/**
 * What the viewport needs to draw the setup, and what the holding model
 * concluded about it. Every field is either a recorded setup value or an
 * output of `assessHoldingMargin` — nothing here is invented for the picture.
 */
export interface FixtureInfo {
  jawWidth: number;
  jawHeight: number;
  gripDepth: number | null;
  gripLength: number | null;
  stockProjection: number | null;
  /** Both jaw faces, in². */
  contactArea: number | null;
  /** lbf/in² on that area. */
  contactPressure: number | null;
  margin: number | null;
  verdict: string | null;
  governingMode: string | null;
  jawSurface: string | null;
}

export interface ViewportProps {
  stock: Stock | null;
  features: Feature[];
  moves?: Move[];
  /** 0–1 scrub position through the toolpath. */
  playhead?: number;
  showStock: boolean;
  showFixture: boolean;
  showToolpath: boolean;
  showTool: boolean;
  mode: ViewMode;
  selectedFeatureId?: string | null;
  hoveredFeatureId?: string | null;
  onSelectFeature?: (id: string | null) => void;
  /** Fires as the cursor enters and leaves feature geometry. No click needed. */
  onHoverFeature?: (id: string | null, pointer: { x: number; y: number } | null) => void;
  fixture?: FixtureInfo | null;
  /** True in HOLD, where the setup itself is the subject. */
  showHoldCallouts?: boolean;
}

/* WebGL cannot read CSS custom properties, so the work-window palette is
   mirrored here as literals. These are the only place the 3D and the page can
   disagree — if `--canvas-work-window`, `--canvas-blue` or `--canvas-text`
   move in globals.css, they have to move here in the same commit.

   WORK_WINDOW must equal `--canvas-work-window` exactly, or the canvas paints
   a slightly different white than the page around it and the seam is visible
   at the edge of the viewport.

   BLUE is `--canvas-blue`. Selection is drawn at low opacity rather than at
   full saturation — restrained precision blue, no bloom, no emissive. */
const WORK_WINDOW = "#FAFAF8";
const BLUE = "#0b72ff";
const PLATINUM = "#414851";
const RAPID = "#a8aeb6";

export function Viewport(props: ViewportProps) {
  const { stock } = props;
  const span = stock ? Math.max(stock.x, stock.y, stock.z) : 6;

  return (
    <Canvas
      dpr={[1, 2]}
      gl={{ antialias: true }}
      shadows
      /* Product-photography framing: a strong three-quarter view with enough
         focal length to avoid the wide-angle distortion that makes a machined
         part look like a game asset. A commercial product shot is taken on a
         longer lens from further back, and so is this.

         The work window is the hero of the layout, so the framing is tight.
         Measured on the seeded 6.000 x 4.000 x 0.750 plate in a 962x637 work
         window, this distance puts the part's bounding box at 85% of the
         canvas width and 71% of its height — about 60% of the canvas by
         bounding box against a 55-70% target, up from 44.7%. The previous distance left the upper-left
         third of the canvas empty, largely because the floating dimension card
         was reserving the top-right — that card has been moved to the bottom
         corner and reduced, so the framing no longer has to make room for it.

         Pulled in further than this and a 6" plate starts touching the frame
         edges under orbit; the focal length stays long enough not to bow the
         edges of a prismatic part. */
      camera={{ position: [span * 0.9, span * 0.78, span * 1.19], fov: 30, near: 0.01, far: 1000 }}
      onPointerMissed={() => props.onSelectFeature?.(null)}
    >
      {/* A soft studio rather than a void. Product photography wants a bright
          environment with a clear key, a fill that keeps the shadow side
          readable, and a rim that separates the part from the ground. */}
      <color attach="background" args={[WORK_WINDOW]} />
      <hemisphereLight args={["#ffffff", "#d2d5d1", 1.0]} />
      <ambientLight intensity={0.25} />
      {/* Key, fill, rim. Metal needs something to reflect or it reads as clay,
          so a studio environment does the work a bare light rig cannot. */}
      {/* All three in WORLD space, where up is +Y. Keyed from above and to the
          right so the top face — the one that gets machined and the one the
          operator is looking at — is the brightest surface in frame. */}
      <directionalLight position={[9, 14, 11]} intensity={1.5} />
      <directionalLight position={[-11, 5, 7]} intensity={0.55} />
      <directionalLight position={[-3, 4, -12]} intensity={0.4} />
      {/* A softbox rig built from lightformers rather than a preset HDR.
          Presets fetch an environment map from a CDN, which makes the viewport
          depend on the network to render a part — and fails closed to a lost
          WebGL context when that network is not there. This is generated in
          process, so it works on a shop floor with no internet. */}
      <Environment resolution={256} environmentIntensity={0.5}>
        <Lightformer form="rect" intensity={3} position={[0, 8, 3]} scale={[12, 7, 1]} target={[0, 0, 0]} />
        <Lightformer form="rect" intensity={1.3} position={[-7, 3, 4]} scale={[6, 7, 1]} target={[0, 0, 0]} />
        <Lightformer form="rect" intensity={1} position={[7, 2, -4]} scale={[6, 7, 1]} target={[0, 0, 0]} />
        <Lightformer form="ring" intensity={0.5} position={[0, -5, 0]} scale={9} target={[0, 0, 0]} />
      </Environment>

      {/* Machine coordinate convention: rotate once, author everything Z-up.
          This maps part (x, y, z) onto world (x, z, -y) — so the part's +Z,
          which is up at the machine, is world +Y. Camera positions elsewhere
          in this file and in the view presets are in WORLD space and have to
          respect that, or the default view ends up under the part looking at
          the face nobody machines. */}
      <group rotation={[-Math.PI / 2, 0, 0]}>
        <SceneContent {...props} />
      </group>

      {/* A soft contact shadow grounds the part. Without it the component
          floats, and a floating object reads as a CAD viewport rather than as
          a physical thing sitting on a surface. */}
      <ContactShadows
        position={[0, stock ? -stock.z / 2 - 0.002 : 0, 0]}
        scale={span * 3.2}
        opacity={0.42}
        blur={2.4}
        far={span * 1.4}
        resolution={1024}
        color="#3a3f45"
      />

      {/* The datum grid stays, but quietly, and only far enough out to give
          scale without competing with the component for attention. */}
      <Grid
        args={[span * 6, span * 6]}
        cellSize={0.5}
        cellColor="#ebedec"
        sectionSize={span}
        sectionColor="#d6dade"
        fadeDistance={span * 7}
        fadeStrength={2.2}
        position={[0, stock ? -stock.z / 2 - 0.001 : 0, 0]}
        infiniteGrid
      />

      <OrbitControls makeDefault enableDamping dampingFactor={0.12} />
      {/* Top-right. The bottom-right corner is where the dimension card now
          sits, and two overlapping objects in one corner is worse than a
          gizmo in the empty air above the part. */}
      <GizmoHelper alignment="top-right" margin={[64, 64]}>
        <GizmoViewcube
          color="#ffffff"
          strokeColor="#c8cdd3"
          textColor="#3a424c"
          hoverColor={BLUE}
          faces={["Right", "Left", "Top", "Bottom", "Front", "Back"]}
        />
      </GizmoHelper>
      <CameraSync />
    </Canvas>
  );
}

/** Exposes the camera so the orthographic view buttons can drive it. */
function CameraSync() {
  const { camera, controls } = useThree();
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ position: [number, number, number] }>).detail;
      if (!detail) return;
      camera.position.set(...detail.position);
      camera.lookAt(0, 0, 0);
      (controls as { update?: () => void } | null)?.update?.();
    };
    window.addEventListener("canvas:setview", handler);
    return () => window.removeEventListener("canvas:setview", handler);
  }, [camera, controls]);
  return null;
}

function SceneContent({
  stock,
  features,
  moves,
  playhead = 1,
  showStock,
  showFixture,
  showToolpath,
  showTool,
  mode,
  selectedFeatureId,
  hoveredFeatureId,
  onSelectFeature,
  onHoverFeature,
  fixture,
  showHoldCallouts,
}: ViewportProps) {
  if (!stock) return null;

  // Part origin sits at the top face centre, matching the setup datum.
  const zOffset = -stock.z / 2;

  return (
    <group position={[0, 0, zOffset]}>
      {showStock && <PartBody stock={stock} features={features} mode={mode} />}

      {features.map((f) => (
        <FeatureMesh
          key={f.id}
          feature={f}
          stock={stock}
          selected={selectedFeatureId === f.id}
          hovered={hoveredFeatureId === f.id}
          onSelect={() => onSelectFeature?.(f.id)}
          onHover={onHoverFeature}
        />
      ))}

      <DatumIndicator stock={stock} />

      {showFixture && fixture && <Fixture stock={stock} fixture={fixture} callouts={Boolean(showHoldCallouts)} />}
      {showToolpath && moves && moves.length > 1 && <Toolpath moves={moves} playhead={playhead} zTop={stock.z / 2} />}
      {showTool && moves && moves.length > 1 && <ToolMarker moves={moves} playhead={playhead} zTop={stock.z / 2} />}
    </group>
  );
}

/* ------------------------------------------------------------------ */
/* Stock                                                               */
/* ------------------------------------------------------------------ */

/**
 * Physically distinguishable materials.
 *
 * This is not decoration. A machinist reads a part's material off its
 * appearance before reading any label, and aluminium, steel, stainless, cast
 * iron and brass do not look alike. Getting the roughness and colour
 * approximately right communicates manufacturing state faster than text, and
 * getting it wrong — putting a chrome finish on a milled 6061 block —
 * communicates that the software does not know what it is looking at.
 *
 * Values are chosen to read as *machined*: moderate metalness with real
 * roughness, never a mirror. A freshly milled face is not a mirror.
 */
const MATERIAL_APPEARANCE: Record<string, { color: string; metalness: number; roughness: number }> = {
  ALUMINUM: { color: "#b8bcc0", metalness: 0.62, roughness: 0.42 },
  ALUMINIUM: { color: "#b8bcc0", metalness: 0.62, roughness: 0.42 },
  STEEL: { color: "#9aa0a8", metalness: 0.72, roughness: 0.36 },
  STAINLESS: { color: "#a9aeb4", metalness: 0.78, roughness: 0.28 },
  TOOL_STEEL: { color: "#8a9098", metalness: 0.75, roughness: 0.3 },
  CAST_IRON: { color: "#7c7d7a", metalness: 0.35, roughness: 0.72 },
  BRASS: { color: "#c2a668", metalness: 0.7, roughness: 0.34 },
  BRONZE: { color: "#b08d63", metalness: 0.68, roughness: 0.4 },
  COPPER: { color: "#c08466", metalness: 0.72, roughness: 0.36 },
  TITANIUM: { color: "#9d9a97", metalness: 0.6, roughness: 0.46 },
  PLASTIC: { color: "#d5d7d2", metalness: 0.05, roughness: 0.85 },
};

function appearanceFor(material: string) {
  const key = (material || "").toUpperCase().replace(/[\s-]+/g, "_");
  for (const candidate of Object.keys(MATERIAL_APPEARANCE)) {
    if (key.includes(candidate)) return MATERIAL_APPEARANCE[candidate];
  }
  // Unrecognised material reads as a neutral machined metal rather than
  // pretending to be something specific.
  return { color: "#adb1b6", metalness: 0.55, roughness: 0.5 };
}

/**
 * The part as an actual solid — stock with the features genuinely removed,
 * rather than a block with translucent volumes floating inside it.
 *
 * Memoised on the geometry inputs because rebuilding the cross-sections on
 * every render would rebuild them on every hover.
 */
function PartBody({ stock, features, mode }: { stock: Stock; features: Feature[]; mode: ViewMode }) {
  const solid = useMemo(() => buildPartSolid(stock, features), [stock, features]);
  const look = appearanceFor(stock.material);

  return (
    <mesh geometry={solid.geometry}>
      {mode === "WIREFRAME" ? (
        <meshBasicMaterial wireframe color="#9aa0a8" />
      ) : (
        <meshStandardMaterial
          color={look.color}
          metalness={look.metalness}
          roughness={look.roughness}
          transparent={mode === "TRANSPARENT"}
          opacity={mode === "TRANSPARENT" ? 0.25 : 1}
          side={THREE.DoubleSide}
        />
      )}
      {/* Edge breaks. A machined part has crisp arrises, and drawing them is
          what separates a milled component from a rendered blob. */}
      <Edges threshold={28} color={mode === "WIREFRAME" ? "#9aa0a8" : "#6f757d"} />
    </mesh>
  );
}

/* `StockBox` lived here: an uncut block drawn when the part was a box with
   translucent volumes floating inside it. `PartBody` + `buildPartSolid` made
   it dead the day the real subtracted solid landed, and it had no call sites.
   Removed rather than left as a second, wrong way to draw a part. */

/* ------------------------------------------------------------------ */
/* Features — drawn as removed volume                                  */
/* ------------------------------------------------------------------ */

function FeatureMesh({
  feature: f,
  stock,
  selected,
  hovered,
  onSelect,
  onHover,
}: {
  feature: Feature;
  stock: Stock;
  selected: boolean;
  hovered: boolean;
  onSelect: () => void;
  onHover?: (id: string | null, pointer: { x: number; y: number } | null) => void;
}) {
  // Now that the part is a real solid with the material genuinely removed,
  // these volumes are no longer how a feature is drawn — they are the pick
  // target and the highlight. Invisible at rest, so the part reads as a part;
  // they light up under the cursor, which is what makes hover feel physical.
  const active = selected || hovered;
  const color = selected ? BLUE : f.critical ? "#8f6212" : BLUE;
  // Restrained. The selected volume reads as tinted glass over machined metal,
  // not as a highlighter — the edge line is what identifies it, the fill only
  // has to say "this one". These are deliberately low because the volumes are
  // DoubleSide with depthWrite off, so front and back faces both contribute
  // and the value on screen is roughly double what is written here. At 0.24 a
  // selected bore read as a saturated translucent puck standing proud of the
  // pocket floor; the blue Edges line was already doing the identification.
  const opacity = selected ? 0.14 : hovered ? 0.09 : 0;

  const common = {
    onClick: (e: { stopPropagation: () => void }) => {
      e.stopPropagation();
      onSelect();
    },
    onPointerOver: (e: { stopPropagation: () => void; clientX: number; clientY: number }) => {
      e.stopPropagation();
      onHover?.(f.id, { x: e.clientX, y: e.clientY });
    },
    onPointerMove: (e: { stopPropagation: () => void; clientX: number; clientY: number }) => {
      e.stopPropagation();
      onHover?.(f.id, { x: e.clientX, y: e.clientY });
    },
    onPointerOut: (e: { stopPropagation: () => void }) => {
      e.stopPropagation();
      onHover?.(null, null);
    },
  };

  const material = (
    <meshStandardMaterial color={color} transparent opacity={opacity} depthWrite={false} side={THREE.DoubleSide} />
  );

  switch (f.kind) {
    case "RECT_POCKET": {
      const top = stock.z + (f.top ?? 0);
      return (
        <mesh position={[f.centerX, f.centerY, top - f.depth / 2]} {...common}>
          <boxGeometry args={[f.width, f.length, f.depth]} />
          {material}
          <Edges threshold={20} color={active ? BLUE : "#c6cac7"} visible={active} />
        </mesh>
      );
    }
    case "CIRC_POCKET":
    case "BORE": {
      const depth = f.through ? stock.z : f.depth;
      const top = stock.z + (f.top ?? 0);
      // A capped cylinder filling the bore renders as a translucent puck
      // sitting in the hole — the thing you notice is a blue disc, not the
      // feature. Open-ended and back-faced, the highlight is the bore WALL
      // lit from inside, which is what selecting a bore should look like.
      // Pulled a hair inside the true radius so it sits in the void rather
      // than fighting the machined surface for the same pixels.
      const r = (f.diameter / 2) * 0.997;
      return (
        <group>
          {/* The wall, tinted. Looking down into a through hole you see the far
              side of the tube, so anything above a light tint fills the circle
              and reads as a plug sitting in the bore rather than as the bore
              being selected. */}
          <mesh position={[f.centerX, f.centerY, top - depth / 2]} rotation={[Math.PI / 2, 0, 0]} {...common}>
            <cylinderGeometry args={[r, r, depth, 96, 1, true]} />
            <meshBasicMaterial
              color={color}
              transparent
              opacity={active ? (selected ? 0.2 : 0.12) : 0}
              depthWrite={false}
              side={THREE.BackSide}
            />
          </mesh>
          {/* The rim. This is what actually identifies the feature: a crisp
              annulus around the mouth, the way a machinist would ring a
              diameter on a print. */}
          {active && (
            <mesh position={[f.centerX, f.centerY, top + 0.004]}>
              <ringGeometry args={[f.diameter / 2, (f.diameter / 2) * 1.055, 96]} />
              <meshBasicMaterial color={BLUE} transparent opacity={selected ? 0.95 : 0.6} side={THREE.DoubleSide} />
            </mesh>
          )}
        </group>
      );
    }
    case "DRILLED_HOLE":
    case "TAPPED_HOLE":
    case "COUNTERBORE":
    case "COUNTERSINK": {
      // Same reasoning as the bore above: light the wall, do not fill the hole.
      const depth = f.through ? stock.z : f.depth;
      const top = stock.z + (f.top ?? 0);
      const hr = (f.diameter / 2) * 0.997;
      return (
        <group>
          <mesh position={[f.centerX, f.centerY, top - depth / 2]} rotation={[Math.PI / 2, 0, 0]} {...common}>
            <cylinderGeometry args={[hr, hr, depth, 48, 1, true]} />
            <meshBasicMaterial
              color={color}
              transparent
              opacity={active ? (selected ? 0.2 : 0.12) : 0}
              depthWrite={false}
              side={THREE.BackSide}
            />
          </mesh>
          {active && (
            <mesh position={[f.centerX, f.centerY, top + 0.004]}>
              <ringGeometry args={[f.diameter / 2, (f.diameter / 2) * 1.16, 64]} />
              <meshBasicMaterial color={BLUE} transparent opacity={selected ? 0.95 : 0.6} side={THREE.DoubleSide} />
            </mesh>
          )}
        </group>
      );
    }
    case "SLOT": {
      const dx = f.endX - f.startX;
      const dy = f.endY - f.startY;
      const len = Math.hypot(dx, dy) || f.width;
      const angle = Math.atan2(dy, dx);
      const top = stock.z + (f.top ?? 0);
      return (
        <mesh
          position={[(f.startX + f.endX) / 2, (f.startY + f.endY) / 2, top - f.depth / 2]}
          rotation={[0, 0, angle]}
          {...common}
        >
          <boxGeometry args={[len, f.width, f.depth]} />
          {material}
        </mesh>
      );
    }
    case "BOSS":
      return (
        <mesh position={[f.centerX, f.centerY, stock.z + f.height / 2]} rotation={[Math.PI / 2, 0, 0]} {...common}>
          <cylinderGeometry args={[f.diameter / 2, f.diameter / 2, f.height, 32]} />
          <meshStandardMaterial color={selected ? BLUE : "#8e959f"} metalness={0.7} roughness={0.35} />
        </mesh>
      );
    case "OUTSIDE_CONTOUR": {
      // The finished profile. This existed to show where the profile would be
      // cut, back when the part was drawn as an uncut block — now the solid IS
      // the finished profile, so drawing it permanently is a duplicate line
      // floating above the part. It survives only as a highlight.
      if (!active) return null;
      const pts: [number, number, number][] = [
        [-f.width / 2, -f.length / 2, stock.z + 0.004],
        [f.width / 2, -f.length / 2, stock.z + 0.004],
        [f.width / 2, f.length / 2, stock.z + 0.004],
        [-f.width / 2, f.length / 2, stock.z + 0.004],
        [-f.width / 2, -f.length / 2, stock.z + 0.004],
      ];
      return <Line points={pts} color={BLUE} lineWidth={2} dashed dashSize={0.06} gapSize={0.04} />;
    }
    default:
      return null;
  }
}

/* ------------------------------------------------------------------ */
/* Datum indicator                                                     */
/* ------------------------------------------------------------------ */

/**
 * The coordinate origin, drawn on the part's top face.
 *
 * Two things were wrong here and both were visible. The arms were sized from
 * `max(stock.x, stock.y)`, so on a 6.000 x 4.000 plate the Y arms overran the
 * 2.000 half-depth and a short blue stub hung off the front wall, attached to
 * nothing. And the crosshair was drawn at `stock.z / 2` — the middle of the
 * solid, not its top face — so it was buried in the material and survived only
 * as disconnected fragments glimpsed inside a bore.
 *
 * Now: clamped inside the stock on both axes, and lifted clear of the top
 * face, which is where a setup origin actually is.
 */
/**
 * The work offset origin, drawn as a machinist's datum mark.
 *
 * This used to span 40% of the part in X and Y, which meant two long blue
 * lines lying across the component. At a glance that reads as annotation drawn
 * *on* the part rather than as a marker sitting at a point — and on this part
 * the origin is the bore centre, so the arms ran straight through the feature
 * you were trying to look at.
 *
 * A datum mark is a symbol, not a measurement. It is now sized as a fixed
 * fraction of the smaller plan dimension, small enough to read as a target and
 * to stay clear of whatever it sits on, with a short Z stem so the axis the
 * offset is set on is unambiguous.
 */
function DatumIndicator({ stock }: { stock: Stock }) {
  const span = Math.max(0.12, Math.min(stock.x, stock.y) * 0.09);
  const zz = stock.z + 0.02;
  const ring = span * 0.34;

  return (
    <group>
      {/* Crosshair, broken at the centre so the ring reads as the origin. */}
      <Line points={[[-span, 0, zz], [-ring * 1.3, 0, zz]]} color={BLUE} lineWidth={1.5} />
      <Line points={[[ring * 1.3, 0, zz], [span, 0, zz]]} color={BLUE} lineWidth={1.5} />
      <Line points={[[0, -span, zz], [0, -ring * 1.3, zz]]} color={BLUE} lineWidth={1.5} />
      <Line points={[[0, ring * 1.3, zz], [0, span, zz]]} color={BLUE} lineWidth={1.5} />
      {/* Z stem — the axis the offset is set on. */}
      <Line points={[[0, 0, zz], [0, 0, zz + span * 1.1]]} color={BLUE} lineWidth={1.5} />
      <mesh position={[0, 0, zz]}>
        <ringGeometry args={[ring * 0.72, ring, 48]} />
        <meshBasicMaterial color={BLUE} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

/* ------------------------------------------------------------------ */
/* Fixture                                                             */
/* ------------------------------------------------------------------ */

/**
 * HOLD — the setup as a physical thing.
 *
 * Workholding is spatial. A grip depth in a table is a number an operator
 * scrolls past; the same number drawn on the face it applies to, with the
 * contact patch lit and the material standing proud of the jaws visible above
 * it, is the setup. That is the whole argument for this view.
 *
 * Every callout carries a value the holding model actually computed. Where the
 * model has no value — clamping force not recorded, so no contact pressure —
 * the callout says so rather than filling the gap.
 */
function Fixture({
  stock,
  fixture,
  callouts,
}: {
  stock: Stock;
  fixture: NonNullable<ViewportProps["fixture"]>;
  callouts: boolean;
}) {
  const grip = fixture.gripDepth ?? Math.min(0.25, stock.z * 0.3);
  const jawThickness = 1;
  const jawTopZ = grip;
  const contactLength = Math.min(fixture.gripLength ?? stock.y, stock.y);
  const proud = fixture.stockProjection;

  const jaw = (side: 1 | -1) => (
    <mesh key={side} position={[side * (stock.x / 2 + jawThickness / 2), 0, jawTopZ - fixture.jawHeight / 2]}>
      <boxGeometry args={[jawThickness, Math.min(fixture.jawWidth, stock.y * 1.4), fixture.jawHeight]} />
      <meshStandardMaterial color="#6e7480" metalness={0.55} roughness={0.55} />
      <Edges threshold={20} color="#4a505b" />
    </mesh>
  );

  // The band of the part the jaws actually hold: grip depth tall, grip length
  // long, on both clamped faces. This is the area the margin is computed over.
  const contact = (side: 1 | -1) => (
    <mesh key={`c${side}`} position={[side * (stock.x / 2 + 0.004), 0, grip / 2]}>
      <planeGeometry args={[contactLength, grip]} />
      <meshBasicMaterial
        color={BLUE}
        transparent
        opacity={0.34}
        side={THREE.DoubleSide}
        depthWrite={false}
      />
    </mesh>
  );

  return (
    <group>
      {[1, -1].map((s) => jaw(s as 1 | -1))}
      {callouts && [1, -1].map((s) => (
        <group key={`cg${s}`} rotation={[0, Math.PI / 2, 0]} position={[0, 0, 0]}>
          {/* rotated so the plane faces outward from the clamped face */}
        </group>
      ))}
      {callouts && [1, -1].map((s) => contact(s as 1 | -1))}

      {/* Parallels the part seats on — the seating surface. */}
      <mesh position={[0, 0, jawTopZ - fixture.jawHeight - 0.25]}>
        <boxGeometry args={[stock.x * 0.9, 0.5, 0.5]} />
        <meshStandardMaterial color="#5c626d" metalness={0.6} roughness={0.45} />
      </mesh>

      {callouts && (
        <>
          {/* Grip depth — measured on the face it applies to. */}
          <Line
            points={[[stock.x / 2 + 0.02, -stock.y / 2 - 0.15, 0], [stock.x / 2 + 0.02, -stock.y / 2 - 0.15, grip]]}
            color={BLUE}
            lineWidth={2}
          />
          {/* Each callout sits off a different edge so five of them can be on
              screen at once without stacking on each other. */}
          <Callout position={[stock.x / 2 + 0.45, -stock.y / 2 - 0.1, grip / 2]} label="Grip depth">
            {grip.toFixed(3)}″
          </Callout>

          <Callout position={[stock.x / 2 + 0.45, stock.y / 2 - 0.2, grip * 0.5]} label="Jaw contact">
            {fixture.contactArea != null ? `${fixture.contactArea.toFixed(3)} in² both faces` : "not calculable"}
          </Callout>

          <Callout position={[0, -stock.y / 2 - 0.55, jawTopZ - fixture.jawHeight - 0.25]} label="Seating surface">
            Parallels
          </Callout>

          {proud != null && (
            <Callout position={[-stock.x / 2 - 0.45, -stock.y / 2 - 0.1, grip + proud / 2]} label="Proud of jaws">
              {proud.toFixed(3)}″
            </Callout>
          )}

          {fixture.contactPressure != null && (
            <Callout position={[-stock.x / 2 - 0.45, stock.y / 2 - 0.2, grip * 0.5]} label="Clamping pressure">
              {fixture.contactPressure.toLocaleString()} psi
            </Callout>
          )}

          {fixture.margin != null && (
            <Callout
              position={[0, 0, grip + (proud ?? stock.z) + 0.55]}
              label={`Holding margin — ${(fixture.verdict ?? "").toLowerCase()}`}
              tone={fixture.verdict === "ADEQUATE" ? "pass" : fixture.verdict === "MARGINAL" ? "review" : "risk"}
            >
              {fixture.margin.toFixed(2)}× · {fixture.governingMode === "TIPPING" ? "rolling out" : "sliding"}
            </Callout>
          )}
        </>
      )}
    </group>
  );
}

/** A leader-less callout pinned to a point in the scene. */
function Callout({
  position,
  label,
  children,
  tone = "neutral",
}: {
  position: [number, number, number];
  label: string;
  children: React.ReactNode;
  tone?: "neutral" | "pass" | "review" | "risk";
}) {
  const border =
    tone === "pass"
      ? "border-l-pass"
      : tone === "review"
        ? "border-l-review"
        : tone === "risk"
          ? "border-l-risk"
          : "border-l-precision";
  return (
    // No distanceFactor: an annotation is not part of the scene and should not
    // grow when you zoom in. Fixed screen size keeps it readable at any camera
    // distance and stops five of them filling the viewport.
    <Html position={position} center zIndexRange={[20, 0]}>
      <div
        className={`pointer-events-none whitespace-nowrap border border-line-strong ${border} border-l-2 bg-card/95 px-1.5 py-[3px] shadow-[0_1px_6px_rgba(20,24,28,0.16)]`}
      >
        <p className="text-[7.5px] font-semibold uppercase leading-none tracking-[0.1em] text-muted">{label}</p>
        <p className="mt-[2px] font-mono text-[10px] leading-none text-platinum">{children}</p>
      </div>
    </Html>
  );
}

/* ------------------------------------------------------------------ */
/* Toolpath                                                            */
/* ------------------------------------------------------------------ */

function Toolpath({ moves, playhead, zTop }: { moves: Move[]; playhead: number; zTop: number }) {
  const segments = useMemo(() => {
    const cut: [number, number, number][][] = [];
    const rapid: [number, number, number][][] = [];
    const upTo = Math.max(1, Math.floor(moves.length * playhead));
    let currentCut: [number, number, number][] = [];
    let currentRapid: [number, number, number][] = [];

    const pt = (m: Move): [number, number, number] => [m.x, m.y, zTop + m.z];

    for (let i = 0; i < upTo; i++) {
      const m = moves[i];
      const isRapid = m.feed === null;
      if (isRapid) {
        if (currentCut.length > 1) cut.push(currentCut);
        currentCut = [];
        if (currentRapid.length === 0 && i > 0) currentRapid.push(pt(moves[i - 1]));
        currentRapid.push(pt(m));
      } else {
        if (currentRapid.length > 1) rapid.push(currentRapid);
        currentRapid = [];
        if (currentCut.length === 0 && i > 0) currentCut.push(pt(moves[i - 1]));
        currentCut.push(pt(m));
      }
    }
    if (currentCut.length > 1) cut.push(currentCut);
    if (currentRapid.length > 1) rapid.push(currentRapid);
    return { cut, rapid };
  }, [moves, playhead, zTop]);

  return (
    <group>
      {segments.rapid.map((pts, i) => (
        <Line key={`r${i}`} points={pts} color={RAPID} lineWidth={1} dashed dashSize={0.05} gapSize={0.05} />
      ))}
      {segments.cut.map((pts, i) => (
        <Line key={`c${i}`} points={pts} color={BLUE} lineWidth={1.5} />
      ))}
    </group>
  );
}

function ToolMarker({ moves, playhead, zTop }: { moves: Move[]; playhead: number; zTop: number }) {
  const ref = useRef<THREE.Group>(null);
  const idx = Math.min(moves.length - 1, Math.max(0, Math.floor(moves.length * playhead) - 1));
  const m = moves[idx];
  if (!m) return null;
  return (
    <group ref={ref} position={[m.x, m.y, zTop + m.z]}>
      {/* Cutter */}
      <mesh position={[0, 0, 0.5]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.1875, 0.1875, 1, 24]} />
        <meshStandardMaterial color={PLATINUM} metalness={0.85} roughness={0.25} />
      </mesh>
      {/* Holder */}
      <mesh position={[0, 0, 1.6]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.55, 0.35, 1.2, 24]} />
        <meshStandardMaterial color="#5c6672" metalness={0.6} roughness={0.5} />
      </mesh>
    </group>
  );
}
