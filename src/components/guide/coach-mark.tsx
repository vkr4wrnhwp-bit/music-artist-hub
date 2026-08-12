"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

/**
 * COACH MARK — highlights the real control the Guide sent the user to.
 *
 * Arrival with `?guide=<target>` finds the element carrying
 * `data-guide-target="<target>"` (a stable, deliberate id — never a CSS
 * selector guess), scrolls it into view and draws a precision-blue outline
 * around it. The element itself stays fully interactive: the mark is a
 * pointer-events-none overlay, not a modal, and Esc or any click dismisses
 * it. It never dims warnings and never traps focus.
 */
export function CoachMark() {
  const params = useSearchParams();
  const target = params.get("guide");
  const [rect, setRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  useEffect(() => {
    if (!target) {
      setRect(null);
      return;
    }
    let raf = 0;
    let dismissed = false;
    const find = () => {
      const el = document.querySelector<HTMLElement>(`[data-guide-target="${CSS.escape(target)}"]`);
      if (!el || dismissed) {
        setRect(null);
        return;
      }
      const r = el.getBoundingClientRect();
      setRect({ x: r.left - 6, y: r.top - 6, w: r.width + 12, h: r.height + 12 });
    };
    // The page may still be laying out (or the target may be inside a
    // collapsed section) — retry briefly, then track scroll/resize.
    const start = Date.now();
    const tick = () => {
      find();
      if (Date.now() - start < 4000) raf = requestAnimationFrame(tick);
    };
    tick();
    const el = document.querySelector<HTMLElement>(`[data-guide-target="${CSS.escape(target)}"]`);
    el?.scrollIntoView({ block: "center", behavior: "smooth" });

    const dismiss = () => {
      dismissed = true;
      setRect(null);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") dismiss();
    };
    window.addEventListener("pointerdown", dismiss, { once: true });
    window.addEventListener("keydown", onKey);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointerdown", dismiss);
      window.removeEventListener("keydown", onKey);
    };
  }, [target]);

  if (!rect) return null;
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed z-50 border-2 border-precision shadow-[0_0_0_4px_color-mix(in_srgb,var(--c-blue)_25%,transparent)] transition-all duration-150"
      style={{ left: rect.x, top: rect.y, width: rect.w, height: rect.h }}
    />
  );
}
