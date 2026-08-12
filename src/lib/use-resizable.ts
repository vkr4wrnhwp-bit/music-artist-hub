"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Resizable panel width: drag the handle, width persists per user in
 * localStorage, double-click snaps back to the default. Clamped so a
 * panel can neither vanish nor eat the canvas — the work window stays
 * the hero of the layout no matter what gets dragged.
 *
 * `edge` is which edge of the panel the handle sits on: a "start" handle
 * (left edge of a right-docked panel) grows the panel as the pointer
 * moves left; an "end" handle (right edge of a left-docked drawer) grows
 * it as the pointer moves right.
 */
export function useResizableWidth(opts: {
  storageKey: string;
  defaultWidth: number;
  min: number;
  max: number;
  edge: "start" | "end";
}) {
  const { storageKey, defaultWidth, min, max, edge } = opts;
  const [width, setWidth] = useState(defaultWidth);
  const [dragging, setDragging] = useState(false);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(storageKey);
      if (stored !== null) {
        const v = Number(stored);
        if (Number.isFinite(v)) setWidth(Math.min(max, Math.max(min, v)));
      }
    } catch {
      /* private mode — session-only widths are fine */
    }
  }, [storageKey, min, max]);

  const persist = useCallback(
    (v: number) => {
      try {
        window.localStorage.setItem(storageKey, String(v));
      } catch {
        /* fine */
      }
    },
    [storageKey],
  );

  const onPointerDown = useCallback(
    (down: React.PointerEvent) => {
      down.preventDefault();
      const startX = down.clientX;
      const startW = width;
      setDragging(true);
      const move = (e: PointerEvent) => {
        if (frame.current !== null) return;
        frame.current = requestAnimationFrame(() => {
          frame.current = null;
          const delta = edge === "start" ? startX - e.clientX : e.clientX - startX;
          setWidth(Math.min(max, Math.max(min, startW + delta)));
        });
      };
      const up = (e: PointerEvent) => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
        setDragging(false);
        const delta = edge === "start" ? startX - e.clientX : e.clientX - startX;
        persist(Math.min(max, Math.max(min, startW + delta)));
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    },
    [width, min, max, edge, persist],
  );

  const reset = useCallback(() => {
    setWidth(defaultWidth);
    persist(defaultWidth);
  }, [defaultWidth, persist]);

  return { width, dragging, onPointerDown, reset };
}

/** The handle element's shared look: a 5px hit strip that lights precision blue while dragged. */
export const RESIZE_HANDLE_CLASS =
  "absolute inset-y-0 z-30 hidden w-[5px] cursor-col-resize lg:block " +
  "hover:bg-precision/40 active:bg-precision/60 transition-colors";
