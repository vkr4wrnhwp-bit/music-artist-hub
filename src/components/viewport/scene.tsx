"use client";

import { Canvas, useThree } from "@react-three/fiber";
import { ContactShadows, Edges, Environment, GizmoHelper, GizmoViewcube, Grid, Lightformer, OrbitControls, Line } from "@react-three/drei";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { Feature, Stock } from "@/lib/domain/features";
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
  fixture?: { jawWidth: number; jawHeight: number; gripDepth: number | null } | null;
}

/* Light workspace palette. Precision blue is deeper than the dark-theme blue
   so it holds contrast against a white ground without reading as a
   highlighter. */
const BLUE = "#0a5fd0";
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
         longer lens from further back, and so is this. */
      camera={{ position: [span * 1.35, span * 1.15, span * 1.75], fov: 28, near: 0.01, far: 1000 }}
      onPointerMissed={() => props.onSelectFeature?.(null)}
    >
      {/* A soft studio rather than a void. Product photography wants a bright
          environment with a clear key, a fill that keeps the shadow side
          readable, and a rim that separates the part from the ground. */}
      <color attach="background" args={["#f6f6f4"]} />
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
        cellColor="#eaebe9"
        sectionSize={span}
        sectionColor="#dcdedb"
        fadeDistance={span * 7}
        fadeStrength={2.2}
        position={[0, stock ? -stock.z / 2 - 0.001 : 0, 0]}
        infiniteGrid
      />

      <OrbitControls makeDefault enableDamping dampingFactor={0.12} />
      <GizmoHelper alignment="bottom-right" margin={[64, 64]}>
        <GizmoViewcube
          color="#ffffff"
          strokeColor="#c6cac7"
          textColor="#414851"
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
}: ViewportProps) {
  if (!stock) return null;

  // Part origin sits at the top face centre, matching the setup datum.
  const zOffset = -stock.z / 2;

  return (
    <group position={[0, 0, zOffset]}>
      {showStock && <StockBox stock={stock} mode={mode} />}

      {features.map((f) => (
        <FeatureMesh
          key={f.id}
          feature={f}
          stock={stock}
          selected={selectedFeatureId === f.id}
          // Everything unrelated to what the cursor is on steps back, rather
          // than the thing under the cursor shouting. The part stays legible.
          receded={Boolean((selectedFeatureId ?? hoveredFeatureId) && (selectedFeatureId ?? hoveredFeatureId) !== f.id)}
          onSelect={() => onSelectFeature?.(f.id)}
          onHover={onHoverFeature}
        />
      ))}

      <DatumIndicator size={Math.max(stock.x, stock.y) * 0.35} z={stock.z / 2} />

      {showFixture && fixture && <Fixture stock={stock} fixture={fixture} />}
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

function StockBox({ stock, mode }: { stock: Stock; mode: ViewMode }) {
  const args: [number, number, number] = [stock.x, stock.y, stock.z];
  const look = appearanceFor(stock.material);
  return (
    <mesh position={[0, 0, stock.z / 2]}>
      <boxGeometry args={args} />
      {mode === "WIREFRAME" ? (
        <meshBasicMaterial wireframe color="#9aa0a8" />
      ) : (
        <meshStandardMaterial
          color={look.color}
          metalness={look.metalness}
          roughness={look.roughness}
          transparent={mode === "TRANSPARENT"}
          opacity={mode === "TRANSPARENT" ? 0.2 : 1}
        />
      )}
      {/* Edge breaks. A machined part has crisp arrises, and drawing them is
          what separates a milled block from a rendered cube. */}
      <Edges threshold={20} color={mode === "WIREFRAME" ? "#9aa0a8" : "#6f757d"} />
    </mesh>
  );
}

/* ------------------------------------------------------------------ */
/* Features — drawn as removed volume                                  */
/* ------------------------------------------------------------------ */

function FeatureMesh({
  feature: f,
  stock,
  selected,
  receded,
  onSelect,
  onHover,
}: {
  feature: Feature;
  stock: Stock;
  selected: boolean;
  receded: boolean;
  onSelect: () => void;
  onHover?: (id: string | null, pointer: { x: number; y: number } | null) => void;
}) {
  const color = selected ? BLUE : f.critical ? "#8f6212" : "#5d6675";
  const opacity = selected ? 0.5 : receded ? 0.12 : 0.3;

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
          <Edges threshold={20} color={selected ? BLUE : receded ? "#c6cac7" : "#7d8593"} />
        </mesh>
      );
    }
    case "CIRC_POCKET":
    case "BORE": {
      const depth = f.through ? stock.z : f.depth;
      const top = stock.z + (f.top ?? 0);
      return (
        <mesh position={[f.centerX, f.centerY, top - depth / 2]} rotation={[Math.PI / 2, 0, 0]} {...common}>
          <cylinderGeometry args={[f.diameter / 2, f.diameter / 2, depth, 48]} />
          {material}
          <Edges threshold={20} color={selected ? BLUE : receded ? "#c6cac7" : "#7d8593"} />
        </mesh>
      );
    }
    case "DRILLED_HOLE":
    case "TAPPED_HOLE":
    case "COUNTERBORE":
    case "COUNTERSINK": {
      const depth = f.through ? stock.z : f.depth;
      const top = stock.z + (f.top ?? 0);
      return (
        <mesh position={[f.centerX, f.centerY, top - depth / 2]} rotation={[Math.PI / 2, 0, 0]} {...common}>
          <cylinderGeometry args={[f.diameter / 2, f.diameter / 2, depth, 24]} />
          {material}
        </mesh>
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
      // The finished profile, drawn as an outline on the top face.
      const pts: [number, number, number][] = [
        [-f.width / 2, -f.length / 2, stock.z + 0.002],
        [f.width / 2, -f.length / 2, stock.z + 0.002],
        [f.width / 2, f.length / 2, stock.z + 0.002],
        [-f.width / 2, f.length / 2, stock.z + 0.002],
        [-f.width / 2, -f.length / 2, stock.z + 0.002],
      ];
      return <Line points={pts} color={selected ? BLUE : "#6d7684"} lineWidth={selected ? 2 : 1} dashed dashSize={0.06} gapSize={0.04} />;
    }
    default:
      return null;
  }
}

/* ------------------------------------------------------------------ */
/* Datum indicator                                                     */
/* ------------------------------------------------------------------ */

function DatumIndicator({ size, z }: { size: number; z: number }) {
  const zz = z + 0.004;
  return (
    <group>
      <Line points={[[-size, 0, zz], [size, 0, zz]]} color={BLUE} lineWidth={1} />
      <Line points={[[0, -size, zz], [0, size, zz]]} color={BLUE} lineWidth={1} />
      <Line points={[[0, 0, zz], [0, 0, zz + size * 0.5]]} color={BLUE} lineWidth={1} />
      <mesh position={[0, 0, zz]}>
        <ringGeometry args={[size * 0.06, size * 0.08, 32]} />
        <meshBasicMaterial color={BLUE} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

/* ------------------------------------------------------------------ */
/* Fixture                                                             */
/* ------------------------------------------------------------------ */

function Fixture({ stock, fixture }: { stock: Stock; fixture: NonNullable<ViewportProps["fixture"]> }) {
  const grip = fixture.gripDepth ?? Math.min(0.25, stock.z * 0.3);
  const jawThickness = 1;
  const jawTopZ = grip;

  const jaw = (side: 1 | -1) => (
    <mesh position={[side * (stock.x / 2 + jawThickness / 2), 0, jawTopZ - fixture.jawHeight / 2]}>
      <boxGeometry args={[jawThickness, Math.min(fixture.jawWidth, stock.y * 1.4), fixture.jawHeight]} />
      <meshStandardMaterial color="#6e7480" metalness={0.55} roughness={0.55} />
      <Edges threshold={20} color="#4a505b" />
    </mesh>
  );

  return (
    <group>
      {jaw(1)}
      {jaw(-1)}
      {/* Parallels the part sits on. */}
      <mesh position={[0, 0, jawTopZ - fixture.jawHeight - 0.25]}>
        <boxGeometry args={[stock.x * 0.9, 0.5, 0.5]} />
        <meshStandardMaterial color="#5c626d" metalness={0.6} roughness={0.45} />
      </mesh>
    </group>
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
