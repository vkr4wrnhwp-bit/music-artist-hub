"use client";

import { CONTEXTS, useInteraction, type Context } from "./interaction";

/**
 * CONTEXT RAIL
 *
 * PART · HOLD · CUT · VERIFY · $
 *
 * These are not five modules. They are five ways of looking at one physical
 * object, and the object does not change when you switch between them — only
 * what is drawn around it does.
 *
 * That distinction is the point. The old workspace had setups, workholding,
 * tools, operations, inspection and cost as six equal-weight panels, which
 * quietly taught the operator that they were six separate things to be filled
 * in. They are not. They are questions about one part sitting in one vise.
 */

const CONTEXT_QUESTION: Record<Context, string> = {
  PART: "What is it?",
  HOLD: "How is it held?",
  CUT: "How is it cut?",
  VERIFY: "How do we know?",
  COST: "What does it cost?",
};

const CONTEXT_SYMBOL: Record<Context, string> = {
  PART: "Part",
  HOLD: "Hold",
  CUT: "Cut",
  VERIFY: "Verify",
  COST: "$",
};

export function ContextRail({ className = "", compact = false }: { className?: string; compact?: boolean }) {
  const { state, setContext } = useInteraction();

  return (
    <div className={`flex items-stretch gap-px bg-line ${className}`} role="tablist" aria-label="Manufacturing context">
      {CONTEXTS.map((c) => {
        const active = state.activeContext === c;
        return (
          <button
            key={c}
            role="tab"
            aria-selected={active}
            data-guide-target={`context-${c.toLowerCase()}`}
            title={CONTEXT_QUESTION[c]}
            onClick={() => setContext(c)}
            className={`group relative flex-1 bg-surface text-left transition-colors ${
              compact ? "px-1.5 py-1.5 text-center" : "px-3 py-2.5"
            } ${active ? "text-precision" : "text-muted hover:text-platinum"}`}
          >
            <span
              aria-hidden
              className={`absolute inset-x-0 top-0 h-[2px] transition-colors ${
                active ? "bg-precision" : "bg-transparent"
              }`}
            />
            <span className="block text-[10.5px] font-semibold uppercase tracking-[0.14em]">{CONTEXT_SYMBOL[c]}</span>
            {/* In a 356px column the question line wraps to three lines and
                stops being a question. It stays as the button's title there. */}
            {!compact && (
              <span
                className={`mt-0.5 hidden text-[11px] leading-tight sm:block ${
                  active ? "text-platinum-dim" : "text-muted/70"
                }`}
              >
                {CONTEXT_QUESTION[c]}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/**
 * What each context actually turns on in the scene.
 *
 * Kept next to the rail rather than inside the viewport so that adding a
 * context is one edit, and so that it is obvious at a glance that every
 * context maps onto real geometry the app already computes — none of these
 * switches reveal something that is not there.
 */
export function sceneFlagsFor(context: Context) {
  switch (context) {
    case "PART":
      return { showStock: true, showFixture: false, showToolpath: false, showTool: false };
    case "HOLD":
      return { showStock: true, showFixture: true, showToolpath: false, showTool: false };
    case "CUT":
      return { showStock: true, showFixture: false, showToolpath: true, showTool: true };
    case "VERIFY":
      return { showStock: true, showFixture: false, showToolpath: false, showTool: false };
    case "COST":
      return { showStock: true, showFixture: false, showToolpath: false, showTool: false };
  }
}
