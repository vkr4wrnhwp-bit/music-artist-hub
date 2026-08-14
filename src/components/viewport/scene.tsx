"use client";

import { Canvas, useThree } from "@react-three/fiber";
import { createContext, useContext } from "react";
import {
  DEFAULT_ENVIRONMENT,
  LINE_MODE_OPACITY,
  LINE_WEIGHT_PX,
  ANNOTATION_SCALE,
  type ViewEnvironment,
} from "@/lib/view-environment";
import { ContactShadows, Edges, Environment, GizmoHelper, GizmoViewcube, Grid, Html, Lightformer, OrbitControls, Line } from "@react-three/drei";
import { holdMeasurements } from "./hold-measurements";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { Feature, Stock } from "@/lib/domain/features";
import { buildPartSolid } from "./part-solid";
import { SimRig } from "./sim-view";
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
  /**
   * Live stock-removal simulation (CUT). When present, the machined stock
   * replaces the finished part — the whole point is that the part does not
   * exist yet.
   */
  simHandle?: import("./sim-view").SimHandle | null;
  /**
   * View environment — how the scene is drawn, never what it shows. Absent
   * means the Studio White defaults.
   */
  env?: import("@/lib/view-environment").ViewEnvironment;
  /** AUTO defers to the device; PERFORMANCE trades shadows, reflections and
      pixel ratio for frame rate. Never removes geometry or warnings. */
  quality?: "AUTO" | "HIGH" | "PERFORMANCE";
  /**
   * Datum reference frame, anchored to the features that establish it. A
   * proposed datum renders visibly different from an accepted one — the
   * viewport never draws an inference the way it draws a decision.
   */
  datums?: SceneDatum[];
  /**
   * Per-feature verification state for the INSPECTION view mode, computed
   * server-side by the same conformance rule the FAIR generator uses. Colour
   * only — the state itself lives in the measurement records.
   */
  verify?: Record<string, VerifyState>;
}

export interface SceneDatum {
  letter: string;
  geometryType: string;
  accepted: boolean;
  featureId: string | null;
}

export type VerifyState = "CONFORMS" | "NONCONFORMS" | "NOT_MEASURED" | "CANNOT_DETERMINE";

/** Locked semantic colours for verification state. Green/red/grey, no others. */
const VERIFY_COLOR: Record<VerifyState, string> = {
  CONFORMS: "#17754e",
  NONCONFORMS: "#c22a1e",
  NOT_MEASURED: "#7d838b",
  CANNOT_DETERMINE: "#7d838b",
};

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

/* View environment: provided inside the Canvas so every scene component can
   read how it should be drawn without eight layers of prop threading. */
const EnvCtx = createContext<ViewEnvironment>(DEFAULT_ENVIRONMENT);
const useEnv = () => useContext(EnvCtx);


/** Applies the environment background to the live scene whenever it changes. */
function SceneBackground({ color }: { color: string }) {
  const scene = useThree((s) => s.scene);
  useEffect(() => {
    scene.background = new THREE.Color(color);
  }, [scene, color]);
  return null;
}

/** Mix a line colour toward the background so "intensity" reads as strength. */
function withOpacityToward(color: string, background: string, strength: number): string {
  const c = new THREE.Color(background).lerp(new THREE.Color(color), Math.min(1, Math.max(0, strength)));
  return `#${c.getHexString()}`;
}
const PLATINUM = "#414851";
const RAPID = "#a8aeb6";

export function Viewport(props: ViewportProps) {
  const { stock } = props;
  const span = stock ? Math.max(stock.x, stock.y, stock.z) : 6;

  return (
    <Canvas
      dpr={props.quality === "PERFORMANCE" ? [1, 1.25] : [1, 2]}
      gl={{ antialias: true }}
      shadows={props.quality !== "PERFORMANCE"}
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
      {/* Imperative, not <color attach> — attach runs at construction, so a
          changed background hex from the View environment drawer was never
          re-applied to the live scene. This follows the prop every render. */}
      <SceneBackground color={props.env?.background ?? WORK_WINDOW} />
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
      <Environment resolution={props.quality === "PERFORMANCE" ? 64 : 256} environmentIntensity={props.quality === "PERFORMANCE" ? 0.15 : 0.2 + (props.env?.reflectionStrength ?? 0.5) * 0.6}>
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
      <EnvCtx.Provider value={props.env ?? DEFAULT_ENVIRONMENT}>
        <group rotation={[-Math.PI / 2, 0, 0]}>
          <SceneContent {...props} />
        </group>
      </EnvCtx.Provider>

      {/* A soft contact shadow grounds the part. Without it the component
          floats, and a floating object reads as a CAD viewport rather than as
          a physical thing sitting on a surface. */}
      {props.quality !== "PERFORMANCE" && (props.env?.shadowStrength ?? 0.42) > 0.01 && (
        <ContactShadows
          position={[0, stock ? -stock.z / 2 - 0.002 : 0, 0]}
          scale={span * 3.2}
          opacity={props.env?.shadowStrength ?? 0.42}
          blur={2.4}
          far={span * 1.4}
          resolution={1024}
          color="#3a3f45"
        />
      )}

      {/* Floor plane — grounds the part. Tinted and toggled by the view
          environment; a machinist inspecting a shiny wall can turn it off. */}
      {(props.env?.floorVisible ?? true) && props.env && props.env.preset !== "STUDIO_WHITE" && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, stock ? -stock.z / 2 - 0.004 : -0.004, 0]}>
          <planeGeometry args={[span * 8, span * 8]} />
          <meshStandardMaterial
            color={props.env.floorColor}
            metalness={props.env.floorReflectivity}
            roughness={1 - props.env.floorReflectivity * 0.6}
          />
        </mesh>
      )}

      {/* The datum grid stays, but quietly, and only far enough out to give
          scale without competing with the component for attention. */}
      {(props.env?.gridVisible ?? true) && (
        <Grid
          args={[span * 6, span * 6]}
          cellSize={0.5}
          cellColor={props.env ? withOpacityToward(props.env.gridColor, props.env.background, 0.12 + props.env.gridIntensity * 0.2) : "#ebedec"}
          sectionSize={span}
          sectionColor={props.env ? withOpacityToward(props.env.gridColor, props.env.background, 0.25 + props.env.gridIntensity * 0.45) : "#d6dade"}
          fadeDistance={span * 7}
          fadeStrength={2.2}
          position={[0, stock ? -stock.z / 2 - 0.001 : 0, 0]}
          infiniteGrid
        />
      )}

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
    // RESET VIEW — default camera and orbit target. Scene data untouched.
    const reset = () => {
      (controls as { reset?: () => void } | null)?.reset?.();
    };
    window.addEventListener("canvas:reset-view", reset);
    return () => {
      window.removeEventListener("canvas:setview", handler);
      window.removeEventListener("canvas:reset-view", reset);
    };
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
  simHandle,
  datums,
  verify,
}: ViewportProps) {
  if (!stock) return null;

  // Part origin sits at the top face centre, matching the setup datum.
  const zOffset = -stock.z / 2;

  return (
    <group position={[0, 0, zOffset]}>
      {/* During simulation the machined stock IS the model — the finished
          part, its features and the static path give way to it. */}
      {simHandle && <SimRig handle={simHandle} stock={stock} />}

      {!simHandle && showStock && <PartBody stock={stock} features={features} mode={mode} />}

      {!simHandle && features.map((f) => (
        <FeatureMesh
          key={f.id}
          feature={f}
          stock={stock}
          selected={selectedFeatureId === f.id}
          hovered={hoveredFeatureId === f.id}
          onSelect={() => onSelectFeature?.(f.id)}
          onHover={onHoverFeature}
          verifyState={verify?.[f.id]}
        />
      ))}

      {!simHandle && datums && datums.length > 0 && <DatumFlags datums={datums} features={features} stock={stock} />}

      <DatumIndicator stock={stock} />

      {showFixture && fixture && <Fixture stock={stock} fixture={fixture} callouts={Boolean(showHoldCallouts)} />}
      {!simHandle && showToolpath && moves && moves.length > 1 && <Toolpath moves={moves} playhead={playhead} zTop={stock.z / 2} />}
      {!simHandle && showTool && moves && moves.length > 1 && <ToolMarker moves={moves} playhead={playhead} zTop={stock.z / 2} />}
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
          what separates a milled component from a rendered blob. Strength and
          visibility follow the view environment. */}
      <PartEdges mode={mode} />
    </mesh>
  );
}

function PartEdges({ mode }: { mode: ViewMode }) {
  const env = useEnv();
  const strength = LINE_MODE_OPACITY[env.edgeMode];
  if (mode !== "WIREFRAME" && strength === 0) return null;
  return (
    <Edges
      threshold={28}
      color={mode === "WIREFRAME" ? "#9aa0a8" : withOpacityToward("#31363d", env.background, 0.35 + strength * 0.65)}
    />
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
  verifyState,
}: {
  feature: Feature;
  stock: Stock;
  selected: boolean;
  hovered: boolean;
  onSelect: () => void;
  onHover?: (id: string | null, pointer: { x: number; y: number } | null) => void;
  verifyState?: VerifyState;
}) {
  // Now that the part is a real solid with the material genuinely removed,
  // these volumes are no longer how a feature is drawn — they are the pick
  // target and the highlight. Invisible at rest, so the part reads as a part;
  // they light up under the cursor, which is what makes hover feel physical.
  const active = selected || hovered;
  // The selection accent follows the view environment; it defaults to the
  // semantic precision blue and a custom choice is contrast-checked upstream.
  const sel = useEnv().selectedFeatureColor;
  const ringHigh = useEnv().featureRingHighContrast;
  const color = selected ? sel : f.critical ? "#8f6212" : sel;
  // Restrained. The selected volume reads as tinted glass over machined metal,
  // not as a highlighter — the edge line is what identifies it, the fill only
  // has to say "this one". These are deliberately low because the volumes are
  // DoubleSide with depthWrite off, so front and back faces both contribute
  // and the value on screen is roughly double what is written here. At 0.24 a
  // selected bore read as a saturated translucent puck standing proud of the
  // pocket floor; the blue Edges line was already doing the identification.
  const opacity = selected ? 0.14 : hovered ? 0.09 : 0;

  // INSPECTION view mode: every toleranced feature wears its verification
  // state as a persistent ring/edge in the locked semantic colours. This is
  // the measurement record made visible — it is computed server-side by the
  // same conformance rule the FAIR generator uses, never invented here.
  const inspecting = useEnv().viewMode === "INSPECTION" && verifyState !== undefined;
  const verifyColor = verifyState ? VERIFY_COLOR[verifyState] : null;

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
          <Edges
            threshold={20}
            color={inspecting && !active ? verifyColor! : active ? sel : "#c6cac7"}
            visible={active || inspecting}
          />
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
          {(active || inspecting) && (
            <mesh position={[f.centerX, f.centerY, top + 0.004]}>
              <ringGeometry args={[f.diameter / 2, (f.diameter / 2) * (ringHigh ? 1.08 : 1.055), 96]} />
              <meshBasicMaterial
                color={inspecting && !active ? verifyColor! : sel}
                transparent
                opacity={ringHigh ? 1 : selected ? 0.95 : inspecting && !active ? 0.85 : 0.6}
                side={THREE.DoubleSide}
              />
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
          {(active || inspecting) && (
            <mesh position={[f.centerX, f.centerY, top + 0.004]}>
              <ringGeometry args={[f.diameter / 2, (f.diameter / 2) * 1.16, 64]} />
              <meshBasicMaterial
                color={inspecting && !active ? verifyColor! : BLUE}
                transparent
                opacity={selected ? 0.95 : inspecting && !active ? 0.85 : 0.6}
                side={THREE.DoubleSide}
              />
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
/**
 * Datum reference flags — the print's datum letters placed on the model.
 *
 * A datum linked to a feature anchors at that feature; an unlinked datum
 * (a face-of-part datum) anchors at the edge of the top face, spread by
 * letter so A/B/C never overlap. An accepted datum is drawn in the datum
 * blue; a proposed one is grey and says PROPOSED — the viewport draws an
 * inference visibly differently from a decision, always.
 *
 * Visibility follows the environment's datum line mode; OFF hides these
 * along with the origin mark.
 */
function DatumFlags({ datums, features, stock }: { datums: SceneDatum[]; features: Feature[]; stock: Stock }) {
  const env = useEnv();
  const strength = LINE_MODE_OPACITY[env.datumLineMode];
  if (strength === 0) return null;
  const scale = ANNOTATION_SCALE[env.annotationSize];

  let edgeIndex = 0;
  return (
    <group>
      {datums.map((d) => {
        const f = d.featureId ? features.find((x) => x.id === d.featureId) : undefined;
        let x: number, y: number;
        if (f && "centerX" in f && "centerY" in f) {
          x = (f as { centerX: number }).centerX;
          y = (f as { centerY: number }).centerY;
        } else {
          // Face datums walk along the front edge of the top face.
          x = -stock.x / 2 + stock.x * 0.18 * (1 + edgeIndex);
          y = -stock.y / 2;
          edgeIndex += 1;
        }
        const zz = stock.z + 0.02;
        const stem = 0.28 * scale;
        const color = d.accepted ? BLUE : "#7d838b";
        return (
          <group key={`${d.letter}-${d.featureId ?? "face"}`}>
            <Line points={[[x, y, zz], [x, y, zz + stem]]} color={color} lineWidth={1 + strength} dashed={!d.accepted} dashSize={0.03} gapSize={0.02} />
            <Html position={[x, y, zz + stem]} center zIndexRange={[20, 0]} style={{ pointerEvents: "none" }}>
              <div
                style={{ opacity: 0.35 + strength * 0.65, transform: `scale(${scale})` }}
                className={`flex items-center gap-1 border bg-white/90 px-1.5 py-0.5 font-mono ${
                  d.accepted ? "border-[#0b72ff] text-[#0b72ff]" : "border-dashed border-[#7d838b] text-[#5c626a]"
                }`}
              >
                <span className="text-[13px] font-bold leading-none">{d.letter}</span>
                {!d.accepted && <span className="text-[8px] uppercase tracking-[0.1em]">proposed</span>}
              </div>
            </Html>
          </group>
        );
      })}
    </group>
  );
}

function DatumIndicator({ stock }: { stock: Stock }) {
  const env = useEnv();
  const span = Math.max(0.12, Math.min(stock.x, stock.y) * 0.09);
  const zz = stock.z + 0.02;
  const ring = span * 0.34;
  const strength = LINE_MODE_OPACITY[env.datumLineMode];
  if (strength === 0) return null;
  const lw = 1 + strength * 1.5;

  return (
    <group>
      {/* Crosshair, broken at the centre so the ring reads as the origin. */}
      <Line points={[[-span, 0, zz], [-ring * 1.3, 0, zz]]} color={BLUE} lineWidth={lw} />
      <Line points={[[ring * 1.3, 0, zz], [span, 0, zz]]} color={BLUE} lineWidth={lw} />
      <Line points={[[0, -span, zz], [0, -ring * 1.3, zz]]} color={BLUE} lineWidth={lw} />
      <Line points={[[0, ring * 1.3, zz], [0, span, zz]]} color={BLUE} lineWidth={lw} />
      {/* Z stem — the axis the offset is set on. */}
      <Line points={[[0, 0, zz], [0, 0, zz + span * 1.1]]} color={BLUE} lineWidth={lw} />
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
/**
 * Vise jaws and parallels are hardened ground steel, and they were rendering
 * as near-black slabs.
 *
 * The cause was the metalness workflow, not the colour. A material at
 * metalness 0.55 has almost no diffuse response, so it can only show what the
 * environment reflects — and this scene's environment is four small procedural
 * lightformers at 0.5 intensity, because the drei HDR presets fetch from a CDN
 * this sandbox cannot reach. A dark base colour under those conditions has
 * nothing to reflect and goes to black.
 *
 * So: bring the base value up into the range the part materials already use,
 * drop metalness far enough that the hemisphere and key lights contribute real
 * diffuse shading, and raise envMapIntensity so the lightformers still read as
 * specular highlights on the jaw faces.
 *
 * The jaws stay a step darker and a shade cooler than any workpiece material
 * in MATERIAL_APPEARANCE — tooling should not compete with the part for
 * attention, and hardened jaw steel genuinely is duller than faced aluminium.
 * The parallels are ground finer than the jaws, so they are smoother.
 */
const JAW_STEEL = { color: "#878e98", metalness: 0.52, roughness: 0.34, envMapIntensity: 1.15 } as const;
const PARALLEL_STEEL = { color: "#98a0a9", metalness: 0.58, roughness: 0.2, envMapIntensity: 1.3 } as const;

function Fixture({
  stock,
  fixture,
  callouts,
}: {
  stock: Stock;
  fixture: NonNullable<ViewportProps["fixture"]>;
  callouts: boolean;
}) {
  const env = useEnv();
  const grip = fixture.gripDepth ?? Math.min(0.25, stock.z * 0.3);
  const jawThickness = 1;
  const jawTopZ = grip;
  const contactLength = Math.min(fixture.gripLength ?? stock.y, stock.y);
  const proud = fixture.stockProjection;

  const jaw = (side: 1 | -1) => (
    <mesh key={side} position={[side * (stock.x / 2 + jawThickness / 2), 0, jawTopZ - fixture.jawHeight / 2]}>
      <boxGeometry args={[jawThickness, Math.min(fixture.jawWidth, stock.y * 1.4), fixture.jawHeight]} />
      <meshStandardMaterial {...JAW_STEEL} />
      <Edges threshold={20} color="#5f6772" />
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
        <meshStandardMaterial {...PARALLEL_STEEL} />
        <Edges threshold={20} color="#5f6772" />
      </mesh>

      {callouts && (
        <>
          {/* Grip depth — measured on the face it applies to. */}
          <Line
            points={[[stock.x / 2 + 0.02, -stock.y / 2 - 0.15, 0], [stock.x / 2 + 0.02, -stock.y / 2 - 0.15, grip]]}
            color={BLUE}
            lineWidth={LINE_WEIGHT_PX[env.measurementLineWeight]}
          />
          {/* The values themselves live in the docked measurement strip; the
              scene carries only the numbered balloons at the anchors, the
              ballooned-drawing convention. One shared list keeps the numbers
              and the rows in lockstep — see hold-measurements.ts. */}
          {holdMeasurements(fixture, stock).map((m) => (
            <Balloon key={m.n} n={m.n} position={m.anchor} tone={m.tone} />
          ))}
        </>
      )}
    </group>
  );
}

/** A numbered balloon at a measurement anchor. The value lives in the strip. */
function Balloon({
  n,
  position,
  tone,
}: {
  n: number;
  position: [number, number, number];
  tone: "neutral" | "pass" | "review" | "risk";
}) {
  const scale = ANNOTATION_SCALE[useEnv().annotationSize];
  const ring =
    tone === "pass" ? "#17754e" : tone === "review" ? "#96570d" : tone === "risk" ? "#c22a1e" : BLUE;
  return (
    <Html position={position} center zIndexRange={[20, 0]} style={{ pointerEvents: "none" }}>
      <div
        style={{ borderColor: ring, color: ring, transform: scale !== 1 ? `scale(${scale})` : undefined }}
        className="flex h-[18px] w-[18px] items-center justify-center rounded-full border-[1.5px] bg-white/92 font-mono text-[10px] font-bold leading-none"
      >
        {n}
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

  const tw = LINE_WEIGHT_PX[useEnv().toolpathLineWeight];
  return (
    <group>
      {segments.rapid.map((pts, i) => (
        <Line key={`r${i}`} points={pts} color={RAPID} lineWidth={Math.max(1, tw * 0.5)} dashed dashSize={0.05} gapSize={0.05} />
      ))}
      {segments.cut.map((pts, i) => (
        <Line key={`c${i}`} points={pts} color={BLUE} lineWidth={tw} />
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
