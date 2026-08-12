"use client";

import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { RotationalProfile } from "@/lib/manufacturing/turn/geometry";
import type { TurnOpForSim, TurnSim } from "@/lib/manufacturing/turn/sim";
import { buildTurnSim, stateAt, toolAt } from "@/lib/manufacturing/turn/sim";

/**
 * 3D LATHE VIEW — DEVELOPMENT. Kinematic stock-removal playback for a
 * turned part: the axisymmetric envelope revolved live from the radius
 * field, a tool point that moves with the clock, and stock-state steps
 * at each operation boundary.
 *
 * What it is NOT — and says so on screen: not a collision checker, not a
 * gouge detector; internal operations advance the clock but do not carve
 * the OD envelope (never faked). Same light work window as the mill
 * viewport: the instrument is dark, the work is lit.
 */

const RAW = new THREE.Color("#a9a59d");
const MACHINED = new THREE.Color("#cfd4d8");
const RADIAL_SEGMENTS = 64;

interface Handle {
  time: number;
  playing: boolean;
  speed: number;
}

function LatheRig({ sim, handle, onClock }: { sim: TurnSim; handle: Handle; onClock: (t: number) => void }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const toolRef = useRef<THREE.Group>(null);
  const toolMatRef = useRef<THREE.MeshStandardMaterial>(null);
  const lastSeek = useRef(-1);
  const lastReport = useRef(0);

  // One (nz+1) × (RADIAL_SEGMENTS+1) grid: positions rewritten in place from
  // the radius field, colours flipped raw→machined where material came off.
  const geom = useMemo(() => {
    const nz = sim.nz;
    const g = new THREE.BufferGeometry();
    const rows = nz + 1;
    const cols = RADIAL_SEGMENTS + 1;
    const pos = new Float32Array(rows * cols * 3);
    const col = new Float32Array(rows * cols * 3);
    const idx: number[] = [];
    for (let j = 0; j < rows - 1; j++) {
      for (let i = 0; i < cols - 1; i++) {
        const a = j * cols + i;
        idx.push(a, a + cols, a + 1, a + 1, a + cols, a + cols + 1);
      }
    }
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.BufferAttribute(col, 3));
    g.setIndex(idx);
    return g;
  }, [sim.nz]);

  function rewrite(t: number) {
    const radii = stateAt(sim, t);
    const pos = geom.getAttribute("position") as THREE.BufferAttribute;
    const col = geom.getAttribute("color") as THREE.BufferAttribute;
    const rows = sim.nz + 1;
    const cols = RADIAL_SEGMENTS + 1;
    for (let j = 0; j < rows; j++) {
      const r = radii[Math.min(j, sim.nz - 1)];
      const machined = r < sim.stockRadius - 1e-6;
      const c = machined ? MACHINED : RAW;
      const z = j * sim.cell;
      for (let i = 0; i < cols; i++) {
        const a = (j * cols + i) * 3;
        const th = (i / RADIAL_SEGMENTS) * Math.PI * 2;
        pos.array[a] = z;
        pos.array[a + 1] = Math.cos(th) * r;
        pos.array[a + 2] = Math.sin(th) * r;
        col.array[a] = c.r;
        col.array[a + 1] = c.g;
        col.array[a + 2] = c.b;
      }
    }
    pos.needsUpdate = true;
    col.needsUpdate = true;
    geom.computeVertexNormals();
  }

  useFrame((_, delta) => {
    if (handle.playing) {
      handle.time = Math.min(sim.totalMinutes, handle.time + (delta / 60) * handle.speed);
      if (handle.time >= sim.totalMinutes) handle.playing = false;
    }
    if (handle.time !== lastSeek.current) {
      rewrite(handle.time);
      lastSeek.current = handle.time;
    }
    const tool = toolAt(sim, handle.time);
    if (tool && toolRef.current) {
      toolRef.current.position.set(tool.z, Math.abs(tool.x) / 2, 0);
      toolRef.current.visible = true;
      if (toolMatRef.current) toolMatRef.current.color.set(tool.kind === "RAPID" ? "#9aa0a8" : "#0b72ff");
    }
    // Report the clock to the HUD at reading speed, not frame rate.
    if (Math.abs(handle.time - lastReport.current) > 0.005) {
      lastReport.current = handle.time;
      onClock(handle.time);
    }
  });

  return (
    <group position={[-sim.stockLength / 2, 0, 0]}>
      <mesh ref={meshRef} geometry={geom}>
        <meshStandardMaterial vertexColors metalness={0.55} roughness={0.38} side={THREE.DoubleSide} />
      </mesh>
      {/* Chuck context at the tailstock-far end: translucent, not subject. */}
      <mesh position={[-0.45, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[sim.stockRadius * 1.6, sim.stockRadius * 1.6, 0.9, 32]} />
        <meshStandardMaterial color="#6e7480" metalness={0.6} roughness={0.4} transparent opacity={0.3} />
      </mesh>
      {/* Tool point: a small insert-ish wedge riding the programmed point. */}
      <group ref={toolRef} visible={false}>
        <mesh position={[0, 0.09, 0]}>
          <coneGeometry args={[0.05, 0.18, 4]} />
          <meshStandardMaterial ref={toolMatRef} color="#0b72ff" metalness={0.7} roughness={0.3} />
        </mesh>
      </group>
    </group>
  );
}

export function LatheSimView({ profile, ops }: { profile: RotationalProfile; ops: TurnOpForSim[] }) {
  const sim = useMemo(() => buildTurnSim(profile, ops), [profile, ops]);
  const handleRef = useRef<Handle>({ time: 0, playing: false, speed: 4 });
  const [clock, setClock] = useState(0);
  const [, force] = useState(0);
  const span = Math.max(sim.stockLength, sim.stockRadius * 2);

  const bump = () => force((v) => v + 1);

  return (
    <div className="space-y-2">
      <div className="h-[340px] w-full border border-line" style={{ background: "#fafaf8" }}>
        <Canvas dpr={[1, 2]} gl={{ antialias: true }} camera={{ position: [span * 0.55, span * 0.5, span * 0.95], fov: 30, near: 0.01, far: 1000 }}>
          <color attach="background" args={["#fafaf8"]} />
          <ambientLight intensity={0.7} />
          <directionalLight position={[4, 6, 4]} intensity={1.1} />
          <directionalLight position={[-4, 2, -3]} intensity={0.4} />
          <LatheRig sim={sim} handle={handleRef.current} onClock={setClock} />
          <OrbitControls makeDefault enableDamping dampingFactor={0.12} />
        </Canvas>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={() => {
            if (handleRef.current.time >= sim.totalMinutes) handleRef.current.time = 0;
            handleRef.current.playing = !handleRef.current.playing;
            bump();
          }}
          className="border border-precision/50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:bg-precision/10"
        >
          {handleRef.current.playing ? "Pause" : "Play"}
        </button>
        <input
          type="range"
          min={0}
          max={sim.totalMinutes}
          step={sim.totalMinutes / 500}
          value={clock}
          onChange={(e) => {
            handleRef.current.time = Number(e.target.value);
            handleRef.current.playing = false;
            setClock(handleRef.current.time);
          }}
          className="min-w-40 flex-1 accent-[#0b72ff]"
          aria-label="Simulation clock"
        />
        <span className="font-mono text-[11px] text-muted tabular-nums">
          {clock.toFixed(2)} / {sim.totalMinutes.toFixed(2)} min
        </span>
        <select
          value={handleRef.current.speed}
          onChange={(e) => {
            handleRef.current.speed = Number(e.target.value);
            bump();
          }}
          className="border border-line-strong bg-void px-1.5 py-0.5 font-mono text-[10px] text-platinum-dim"
          aria-label="Playback speed"
        >
          {[1, 4, 10, 30].map((s) => (
            <option key={s} value={s}>{s}×</option>
          ))}
        </select>
      </div>

      {/* Stock states: jump the clock to each operation boundary. */}
      <div className="flex flex-wrap gap-1.5">
        <button
          onClick={() => { handleRef.current.time = 0; handleRef.current.playing = false; setClock(0); }}
          className="border border-line-strong px-2 py-0.5 font-mono text-[10px] text-platinum-dim hover:bg-panel"
        >
          Raw stock
        </button>
        {sim.opEnds.map((o) => (
          <button
            key={o.opIndex}
            onClick={() => { handleRef.current.time = o.tEnd; handleRef.current.playing = false; setClock(o.tEnd); }}
            className={`border px-2 py-0.5 font-mono text-[10px] hover:bg-panel ${clock >= o.tEnd - 1e-6 ? "border-precision/50 text-precision-dim" : "border-line-strong text-platinum-dim"}`}
          >
            After {o.operationNumber} — {o.label.length > 22 ? `${o.label.slice(0, 22)}…` : o.label}
          </button>
        ))}
      </div>

      <ul className="space-y-0.5">
        {sim.notes.map((n, i) => (
          <li key={i} className="text-[10.5px] leading-relaxed text-muted">{n}</li>
        ))}
        <li className="text-[10.5px] leading-relaxed text-muted">
          Kinematic replay only: not a collision or gouge check, and the tool is drawn as its programmed point, not its real geometry.
        </li>
      </ul>
    </div>
  );
}
