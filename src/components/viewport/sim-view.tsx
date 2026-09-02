"use client";

import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import type { StockRemovalSimulator } from "@/lib/sim/stock-removal";
import { STOCK_BOTTOM_Z, sceneZ, stockTopZ } from "./part-frame";

/**
 * CUT — the stock being machined, in the viewport.
 *
 * The mutable playback state lives in a shared handle rather than React
 * state, because the mesh rewrites 30k vertex heights per frame and the HUD
 * only needs to hear about it at reading speed. useFrame advances the
 * simulator clock; the DOM transport mutates the same handle.
 *
 * Rendering rules with intent behind them:
 * - Raw stock and machined surface are different colours because the
 *   difference is the entire point of watching: what has been touched.
 * - The tool turns red only on a REAL recorded collision window from the
 *   deterministic pass — never as decoration.
 * - The holder is translucent because it is context, not subject.
 */

export interface SimHandle {
  sim: StockRemovalSimulator;
  time: number;
  playing: boolean;
  speed: number;
  followTool: boolean;
  /** Bumped by the transport when it scrubs, so the rig reseeks immediately. */
  scrubbed: number;
}

const RAW = new THREE.Color("#a9a59d");      // mill-scale skin
const MACHINED = new THREE.Color("#cfd4d8"); // fresh aluminum
const COLLISION_WINDOW = 0.02; // minutes either side of a recorded event

export function SimRig({ handle, stock }: { handle: SimHandle; stock: { x: number; y: number; z: number } }) {
  const { sim } = handle;
  const field = sim.field;
  // Part Z zero is the top face of the stock. The enclosing group already
  // centres the part on the origin; this rig used to centre it a second time,
  // which put the simulated block, its cutter and its base plate half a stock
  // height below the solid, the features and the datum indicator.
  const topZ = stockTopZ(stock.z);

  const meshRef = useRef<THREE.Mesh>(null);
  const skirtRef = useRef<THREE.Mesh>(null);
  const toolRef = useRef<THREE.Group>(null);
  const toolMatRef = useRef<THREE.MeshStandardMaterial>(null);
  const worldPos = useMemo(() => new THREE.Vector3(), []);
  const controls = useThree((s) => s.controls) as { target: THREE.Vector3; update: () => void } | null;
  const lastSeek = useRef(-1);
  const lastScrub = useRef(0);

  /* ---- geometry allocated once, heights rewritten in place ---- */

  const gridGeom = useMemo(() => {
    const { nx, ny, cell } = field;
    const grid = new THREE.BufferGeometry();
    const pos = new Float32Array(nx * ny * 3);
    const col = new Float32Array(nx * ny * 3);
    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const k = (j * nx + i) * 3;
        pos[k] = (i + 0.5) * cell - stock.x / 2;
        pos[k + 1] = (j + 0.5) * cell - stock.y / 2;
        pos[k + 2] = topZ;
      }
    }
    const idx: number[] = [];
    for (let j = 0; j < ny - 1; j++) {
      for (let i = 0; i < nx - 1; i++) {
        const a = j * nx + i;
        idx.push(a, a + 1, a + nx, a + 1, a + nx + 1, a + nx);
      }
    }
    grid.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    grid.setAttribute("color", new THREE.BufferAttribute(col, 3));
    grid.setIndex(idx);
    return grid;
  }, [field, stock.x, stock.y, stock.z]);

  function rewriteHeights() {
    const { nx, ny } = field;
    const pos = gridGeom.getAttribute("position") as THREE.BufferAttribute;
    const col = gridGeom.getAttribute("color") as THREE.BufferAttribute;
    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const v = j * nx + i;
        const h = field.data[v];
        pos.setZ(v, h);
        const machined = h < stock.z - 1e-6;
        const c = machined ? MACHINED : RAW;
        col.setXYZ(v, c.r, c.g, c.b);
      }
    }
    pos.needsUpdate = true;
    col.needsUpdate = true;
    gridGeom.computeVertexNormals();
  }

  useFrame((_, delta) => {
    if (handle.playing) {
      handle.time = Math.min(sim.totalTime, handle.time + (delta / 60) * handle.speed);
      if (handle.time >= sim.totalTime) handle.playing = false;
    }
    const needSeek = handle.time !== lastSeek.current || handle.scrubbed !== lastScrub.current;
    if (needSeek) {
      sim.seek(handle.time);
      rewriteHeights();
      lastSeek.current = handle.time;
      lastScrub.current = handle.scrubbed;
    }

    const m = sim.metricsAt(handle.time);
    if (toolRef.current) {
      toolRef.current.position.set(m.position.x, m.position.y, sceneZ(stock.z, m.position.z));
      toolRef.current.visible = true;
    }
    if (toolMatRef.current) {
      const inCollision = sim.collisions.some((c) => Math.abs(c.time - handle.time) < COLLISION_WINDOW);
      toolMatRef.current.color.set(inCollision ? "#d43226" : m.rapid ? "#9aa0a8" : "#5f8fce");
      toolMatRef.current.emissive.set(inCollision ? "#7a150e" : "#000000");
    }
    if (handle.followTool && controls && toolRef.current) {
      toolRef.current.getWorldPosition(worldPos);
      controls.target.lerp(worldPos, 0.2);
      controls.update();
    }
  });

  const op = sim.ops[sim.metricsAt(handle.time).opIndex];
  const toolR = (op?.toolDiameter ?? 0.25) / 2;
  const flute = Math.max(0.2, op?.fluteLength ?? 0.75);

  return (
    <group>
      <mesh ref={meshRef} geometry={gridGeom}>
        <meshStandardMaterial vertexColors metalness={0.55} roughness={0.38} side={THREE.DoubleSide} />
      </mesh>
      {/* Thin base plate at the very bottom — visual seating only, kept well
          below anything a toolpath can reach so it can never mask a cut. */}
      <mesh ref={skirtRef} position={[0, 0, STOCK_BOTTOM_Z + 0.015]}>
        <boxGeometry args={[stock.x, stock.y, 0.03]} />
        <meshStandardMaterial color="#a9a59d" metalness={0.5} roughness={0.45} />
      </mesh>

      <group ref={toolRef} visible={false}>
        {/* Cutter: flute length at nominal diameter. */}
        <mesh position={[0, 0, flute / 2]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[toolR, toolR, flute, 24]} />
          <meshStandardMaterial ref={toolMatRef} color="#5f8fce" metalness={0.7} roughness={0.3} />
        </mesh>
        {/* Holder: context, not subject. */}
        <mesh position={[0, 0, flute + 0.45]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[Math.max(toolR * 1.6, 0.35), Math.max(toolR * 1.9, 0.45), 0.9, 24]} />
          <meshStandardMaterial color="#6e7480" metalness={0.6} roughness={0.4} transparent opacity={0.35} />
        </mesh>
      </group>
    </group>
  );
}
