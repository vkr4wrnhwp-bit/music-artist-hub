"use client";

import { Canvas, useThree } from "@react-three/fiber";
import { Edges, GizmoHelper, GizmoViewcube, Grid, OrbitControls, Line } from "@react-three/drei";
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
  onSelectFeature?: (id: string | null) => void;
  fixture?: { jawWidth: number; jawHeight: number; gripDepth: number | null } | null;
}

const BLUE = "#2078ff";
const PLATINUM = "#b8bdc5";
const RAPID = "#4a5361";

export function Viewport(props: ViewportProps) {
  const { stock } = props;
  const span = stock ? Math.max(stock.x, stock.y, stock.z) : 6;

  return (
    <Canvas
      dpr={[1, 2]}
      gl={{ antialias: true }}
      camera={{ position: [span * 1.3, -span * 1.6, span * 1.2], fov: 35, near: 0.01, far: 1000 }}
      onPointerMissed={() => props.onSelectFeature?.(null)}
    >
      <color attach="background" args={["#0d1014"]} />
      <ambientLight intensity={0.85} />
      <directionalLight position={[8, -10, 14]} intensity={1.5} />
      <directionalLight position={[-10, 6, 4]} intensity={0.5} />

      {/* Machine coordinate convention: rotate once, author everything Z-up. */}
      <group rotation={[-Math.PI / 2, 0, 0]}>
        <SceneContent {...props} />
      </group>

      <Grid
        args={[span * 6, span * 6]}
        cellSize={0.5}
        cellColor="#1e242b"
        sectionSize={span}
        sectionColor="#2b333c"
        fadeDistance={span * 9}
        fadeStrength={1.5}
        position={[0, stock ? -stock.z / 2 - 0.001 : 0, 0]}
        infiniteGrid
      />

      <OrbitControls makeDefault enableDamping dampingFactor={0.12} />
      <GizmoHelper alignment="bottom-right" margin={[64, 64]}>
        <GizmoViewcube
          color="#13171c"
          strokeColor="#2b333c"
          textColor="#b8bdc5"
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
  onSelectFeature,
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
          onSelect={() => onSelectFeature?.(f.id)}
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

function StockBox({ stock, mode }: { stock: Stock; mode: ViewMode }) {
  const args: [number, number, number] = [stock.x, stock.y, stock.z];
  return (
    <mesh position={[0, 0, stock.z / 2]}>
      <boxGeometry args={args} />
      {mode === "WIREFRAME" ? (
        <meshBasicMaterial wireframe color="#3b444f" />
      ) : (
        <meshStandardMaterial
          color="#8e959f"
          metalness={0.72}
          roughness={0.35}
          transparent={mode === "TRANSPARENT"}
          opacity={mode === "TRANSPARENT" ? 0.16 : 1}
        />
      )}
      <Edges threshold={20} color={mode === "WIREFRAME" ? "#4a5361" : "#c9ced6"} />
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
  onSelect,
}: {
  feature: Feature;
  stock: Stock;
  selected: boolean;
  onSelect: () => void;
}) {
  const color = selected ? BLUE : f.critical ? "#c39034" : "#3d4652";
  const opacity = selected ? 0.55 : 0.34;

  const common = {
    onClick: (e: { stopPropagation: () => void }) => {
      e.stopPropagation();
      onSelect();
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
          <Edges threshold={20} color={selected ? BLUE : "#5a6474"} />
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
          <Edges threshold={20} color={selected ? BLUE : "#5a6474"} />
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
      <meshStandardMaterial color="#454d59" metalness={0.5} roughness={0.6} />
      <Edges threshold={20} color="#5a6474" />
    </mesh>
  );

  return (
    <group>
      {jaw(1)}
      {jaw(-1)}
      {/* Parallels the part sits on. */}
      <mesh position={[0, 0, jawTopZ - fixture.jawHeight - 0.25]}>
        <boxGeometry args={[stock.x * 0.9, 0.5, 0.5]} />
        <meshStandardMaterial color="#39414c" metalness={0.5} roughness={0.7} />
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
