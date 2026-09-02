"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  GUIDE_MODES,
  PROFILE_DEFAULT_MODE,
  PROFILE_LABEL,
  advance,
  back,
  canGoBack,
  currentStep,
  flowProgress,
  skip,
  startSession,
  type ExperienceProfile,
  type GuideContext,
  type GuideMode,
  type GuideSession,
} from "@/lib/guide/engine";
import { GUIDE_FLOWS } from "@/lib/guide/flows";
import { DatumMark } from "@/components/brand";

/**
 * CANVAS GUIDE — the card.
 *
 * A floating instrument, not a sidebar and not a mascot: the datum mark,
 * precision blue, plain machinist language. One card, collapsible to a tab,
 * never permanently shrinking the viewport.
 *
 * Everything it can DO is navigation and display: highlight the real
 * control (coach mark on a data-guide-target), route to the page the work
 * happens on, and read progress out of real project state. Its buttons
 * write GuideState and nothing else — completing, skipping or backing
 * through steps cannot touch a gate, a value or an audit row.
 *
 * BACK ONE STEP pops the session's actual visited history (Alt+←). It is
 * not undo: an applied manufacturing change stays applied and the card for
 * the earlier step shows the current, real value.
 */

const MODE_HELP: Record<GuideMode, string> = {
  OFF: "No tutoring. Warnings, gates and the next required action stay active.",
  ASSIST: "Recommendations and WHY on demand. No step-by-step interruption.",
  TEACH: "One guided decision at a time, with the real control highlighted.",
};

export function GuideCard({ ctx, flowId = "MAKE_A_PART" }: { ctx: GuideContext; flowId?: keyof typeof GUIDE_FLOWS }) {
  const [mode, setMode] = useState<GuideMode | null>(null); // null = not loaded
  const [profile, setProfile] = useState<string | null>(null);
  const [firstRun, setFirstRun] = useState(false);
  // Whether the card is up is a layout preference and belongs to the
  // machinist, not to the component's mount. Closing it once used to last
  // until the next render; it now lasts until they open it again.
  const [open, setOpen] = useState(true);
  const [showWhy, setShowWhy] = useState(false);
  const [camHints, setCamHints] = useState(false);
  const [session, setSession] = useState<GuideSession | null>(null);
  // All flows' sessions as loaded — persisted whole so saving one flow's
  // progress never clobbers another's.
  const allSessions = useRef<Record<string, GuideSession>>({});
  const flow = GUIDE_FLOWS[flowId] ?? GUIDE_FLOWS.MAKE_A_PART;
  const persistTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const completeEmitted = useRef(false);

  /* ---- load ---- */
  useEffect(() => {
    let cancelled = false;
    void fetch("/api/guide")
      .then((r) => r.json())
      .then((s: { mode: GuideMode | null; profile: string | null; sessions: Record<string, GuideSession> }) => {
        if (cancelled) return;
        if (s.mode === null) {
          setFirstRun(true);
          setMode("ASSIST");
        } else {
          setMode(s.mode);
          setProfile(s.profile);
          allSessions.current = s.sessions ?? {};
          if (s.sessions[flow.id]) setSession(s.sessions[flow.id]);
        }
        try {
          setCamHints(window.localStorage.getItem("canvas.camHints") === "1");
        } catch {
          /* fine */
        }
      })
      .catch(() => setMode("ASSIST"));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ---- the card's own visibility ---- */
  const OPEN_KEY = "canvas.guideCard";
  useEffect(() => {
    try {
      // Absent means never closed: the card introduces itself once. After
      // that the stored answer wins, including across parts and reloads.
      setOpen(window.localStorage.getItem(OPEN_KEY) !== "closed");
    } catch {
      /* fine */
    }
  }, []);

  const showCard = useCallback((next: boolean) => {
    setOpen(next);
    try {
      window.localStorage.setItem(OPEN_KEY, next ? "open" : "closed");
    } catch {
      /* fine */
    }
  }, []);

  // Turning tutoring OFF is itself an instruction to stop taking up the
  // screen. The card steps back to its tab; G still brings it out.
  useEffect(() => {
    if (mode === "OFF") setOpen(false);
  }, [mode]);

  // FOCUS hands the screen to the part. This card is the largest thing
  // standing on it, so it goes with the rest — without overwriting the
  // stored preference, which focus is not an answer to.
  useEffect(() => {
    const onFocusMode = (e: Event) => {
      if ((e as CustomEvent).detail) setOpen(false);
    };
    window.addEventListener("canvas:focus", onFocusMode);
    return () => window.removeEventListener("canvas:focus", onFocusMode);
  }, []);

  // Fire-and-forget telemetry: friction data for the shop, never a gate.
  const emitEvent = useCallback(
    (action: string, stepId?: string | null, detail?: string | null) => {
      void fetch("/api/guide/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ flowId: flow.id, action, stepId: stepId ?? null, detail: detail ?? null }),
      }).catch(() => {});
    },
    [flow.id],
  );

  const persist = useCallback(
    (update: { mode?: GuideMode; profile?: string | null; sessions?: Record<string, GuideSession> }) => {
      if (persistTimer.current) clearTimeout(persistTimer.current);
      persistTimer.current = setTimeout(() => {
        void fetch("/api/guide", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(update),
        }).catch(() => {});
      }, 400);
    },
    [],
  );

  const setSessionAndPersist = useCallback(
    (s: GuideSession | null) => {
      setSession(s);
      if (s) allSessions.current = { ...allSessions.current, [flow.id]: s };
      else delete allSessions.current[flow.id];
      persist({ sessions: { ...allSessions.current } });
    },
    [persist, flow.id],
  );

  const changeMode = useCallback(
    (m: GuideMode) => {
      setMode(m);
      persist({ mode: m });
      emitEvent("MODE_CHANGE", null, m);
    },
    [persist, emitEvent],
  );

  /* ---- shortcuts: G toggle, Shift+G cycle mode, Alt+← back, Esc close ---- */
  useEffect(() => {
    const typing = (t: EventTarget | null) => {
      const el = t as HTMLElement | null;
      return Boolean(el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable));
    };
    const onKey = (e: KeyboardEvent) => {
      if (typing(e.target)) return;
      if (e.key === "G" && e.shiftKey) {
        setMode((m) => {
          const next = GUIDE_MODES[(GUIDE_MODES.indexOf(m ?? "ASSIST") + 1) % GUIDE_MODES.length];
          persist({ mode: next });
          return next;
        });
      } else if ((e.key === "g" || e.key === "G") && !e.metaKey && !e.ctrlKey && !e.altKey) {
        showCard(!open);
      } else if (e.key === "ArrowLeft" && e.altKey) {
        setSession((s) => {
          if (!s || !canGoBack(s)) return s;
          const n = back(s);
          persist({ sessions: { MAKE_A_PART: n } });
          return n;
        });
      } else if (e.key === "Escape") {
        showCard(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [persist, showCard, open]);

  if (mode === null) return null;

  /* ---- collapsed tab ---- */
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => showCard(true)}
        aria-label="Open CANVAS Guide (G)"
        className="fixed bottom-24 right-3 z-40 flex items-center gap-1.5 border border-line-strong bg-surface/95 px-2.5 py-1.5 text-[9.5px] font-semibold uppercase tracking-[0.14em] text-precision-dim backdrop-blur-sm hover:text-precision"
      >
        <DatumMark size={12} />
        Guide
      </button>
    );
  }

  /* ---- first-run profile ---- */
  if (firstRun) {
    return (
      <Card onCollapse={() => showCard(false)}>
        <Header title="How familiar are you with CNC and CAM?" />
        <p className="px-3 pt-2 text-[11.5px] leading-relaxed text-muted">
          This sets how much CANVAS explains — it never restricts what you can do, and you can change it any time.
        </p>
        <div className="flex flex-col gap-1 p-3">
          {(Object.keys(PROFILE_LABEL) as ExperienceProfile[]).map((p) => (
            <button
              key={p}
              onClick={() => {
                const m = PROFILE_DEFAULT_MODE[p];
                setProfile(p);
                setMode(m);
                setFirstRun(false);
                persist({ mode: m, profile: p });
              }}
              className="min-h-10 border border-line px-3 py-2 text-left text-[12.5px] text-platinum-dim transition-colors hover:border-precision/50 hover:text-platinum"
            >
              {PROFILE_LABEL[p]}
              <span className="ml-2 text-[9.5px] font-semibold uppercase tracking-[0.1em] text-muted">
                → {PROFILE_DEFAULT_MODE[p]}
              </span>
            </button>
          ))}
        </div>
      </Card>
    );
  }

  /* ---- OFF: nothing unsolicited; the tab stays reachable ---- */
  if (mode === "OFF") {
    return (
      <Card onCollapse={() => showCard(false)}>
        <Header title="CANVAS Guide" right={<ModeSwitch mode={mode} onChange={changeMode} />} />
        <p className="px-3 py-3 text-[11.5px] leading-relaxed text-muted">
          Guide is off. Readiness gates and the next required action stay active — OFF disables tutoring, not
          manufacturing safety. Press G to close this card.
        </p>
      </Card>
    );
  }

  const view = session ? currentStep(flow, session, ctx) : null;
  const progress = session ? flowProgress(flow, session, ctx) : null;

  /* ---- ASSIST: compact — dominant blocker or next action, never the
          whole page again ---- */
  if (mode === "ASSIST") {
    const blocker = ctx.blockingGates[0] ?? null;
    return (
      <Card onCollapse={() => showCard(false)}>
        <Header title="CANVAS Guide" right={<ModeSwitch mode={mode} onChange={changeMode} />} />
        {blocker ? (
          <div className="px-3 py-2.5">
            <p className="text-[9.5px] font-semibold uppercase tracking-[0.12em] text-risk">
              Readiness blocked{ctx.blockingGates.length > 1 ? ` — ${ctx.blockingGates.length} gates` : ""}
            </p>
            <p className="mt-1 text-[12.5px] font-medium leading-snug text-platinum">
              {blocker.label}
              {ctx.blockingGates.length === 1 ? " is the only failing gate." : " is the first failing gate."}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {blocker.showMeHref && (
                <a href={blocker.showMeHref} className="border border-precision/50 px-2.5 py-1 text-[9.5px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:bg-precision/10">
                  Show me
                </a>
              )}
              <a
                href={ctx.readinessHref ?? `/parts/${ctx.partId}/readiness`}
                className="border border-line-strong px-2.5 py-1 text-[9.5px] font-semibold uppercase tracking-[0.12em] text-platinum-dim hover:text-platinum"
              >
                Resolve
              </a>
              <details className="inline-block">
                <summary className="cursor-pointer list-none border border-line-strong px-2.5 py-1 text-[9.5px] font-semibold uppercase tracking-[0.12em] text-muted hover:text-platinum">
                  Why?
                </summary>
                <p className="mt-1.5 max-w-[280px] text-[11px] leading-relaxed text-muted">{blocker.detail}</p>
              </details>
            </div>
          </div>
        ) : ctx.nextAction ? (
          <div className="px-3 py-2.5">
            <p className="text-[9.5px] font-semibold uppercase tracking-[0.12em] text-muted">Next required action</p>
            <p className="mt-1 text-[12.5px] font-medium leading-snug text-platinum">{ctx.nextAction.action}</p>
            <div className="mt-2 flex gap-2">
              {ctx.nextAction.href && (
                <a href={ctx.nextAction.href} className="border border-precision/50 px-2.5 py-1 text-[9.5px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:bg-precision/10">
                  Show me
                </a>
              )}
              <button
                onClick={() => changeMode("TEACH")}
                className="border border-line-strong px-2.5 py-1 text-[9.5px] font-semibold uppercase tracking-[0.12em] text-muted hover:text-platinum"
              >
                Teach me step by step
              </button>
            </div>
          </div>
        ) : (
          <p className="px-3 py-2.5 text-[11.5px] text-muted">No outstanding required action from the gates.</p>
        )}
      </Card>
    );
  }

  /* ---- TEACH ---- */
  if (!session) {
    return (
      <Card onCollapse={() => showCard(false)}>
        <Header title="CANVAS Guide" right={<ModeSwitch mode={mode} onChange={changeMode} />} />
        <div className="px-3 py-2.5">
          <p className="text-[12.5px] leading-snug text-platinum">{flow.title}</p>
          <p className="mt-1 text-[11.5px] leading-relaxed text-muted">
            The familiar CAM sequence — part, stock, setup, operations, simulate, verify, deliver — one guided
            decision at a time. Steps you have already done count as done.
          </p>
          <button
            onClick={() => {
              emitEvent("START");
              setSessionAndPersist(startSession(flow, ctx, new Date().toISOString()));
            }}
            className="mt-2 border border-precision/50 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:bg-precision/10"
          >
            Start
          </button>
        </div>
      </Card>
    );
  }

  if (!view || progress?.finished) {
    if (progress?.finished && session && !completeEmitted.current) {
      completeEmitted.current = true;
      emitEvent("FLOW_COMPLETE");
    }
    return (
      <Card onCollapse={() => showCard(false)}>
        <Header title="CANVAS Guide" right={<ModeSwitch mode={mode} onChange={changeMode} />} />
        <div className="px-3 py-2.5">
          <p className="text-[12.5px] text-platinum">
            {progress?.finished ? "Flow complete." : "Nothing left to guide in this flow."}
          </p>
          <p className="mt-1 text-[11px] leading-relaxed text-muted">
            Guide progress is not readiness — the gates on the readiness page are the answer to &ldquo;can I cut this
            yet&rdquo;, and they read evidence, not lessons.
          </p>
          <button
            onClick={() => { emitEvent("RESET"); setSessionAndPersist(null); }}
            className="mt-2 border border-line-strong px-2.5 py-1 text-[9.5px] font-semibold uppercase tracking-[0.12em] text-muted hover:text-platinum"
          >
            Reset guide progress
          </button>
        </div>
      </Card>
    );
  }

  const { step, index, ofTotal, status, blocked } = view;

  return (
    <Card onCollapse={() => showCard(false)}>
      <Header
        title="CANVAS Guide"
        right={
          <span className="flex items-center gap-2">
            <span className="font-mono text-[9.5px] text-muted tabular-nums">
              Step {index} of {ofTotal}
            </span>
            <ModeSwitch mode={mode} onChange={changeMode} />
          </span>
        }
      />

      <div className="px-3 py-2.5">
        {blocked ? (
          <>
            <p className="text-[9.5px] font-semibold uppercase tracking-[0.12em] text-risk">Before we continue</p>
            <p className="mt-1 text-[13px] font-medium leading-snug text-platinum">{blocked.label}</p>
            <p className="mt-1 text-[11.5px] leading-relaxed text-muted">{blocked.detail}</p>
            <p className="mt-1.5 text-[10.5px] leading-relaxed text-muted">
              This is a real gate, not a lesson. It clears when the evidence changes — the Guide can take you there,
              nothing more.
            </p>
          </>
        ) : (
          <>
            <p className="text-[13px] font-medium leading-snug text-platinum">{step.title}</p>
            <p className="mt-1 text-[11.5px] leading-relaxed text-platinum-dim">{step.body}</p>
            {camHints && step.camHint && (
              <p className="mt-1 border-l-2 border-line-strong pl-2 text-[10.5px] leading-relaxed text-muted">
                {step.camHint}
              </p>
            )}
            {step.recommended && (
              <p className="mt-1.5 text-[11px]">
                <span className="font-semibold uppercase tracking-[0.1em] text-muted text-[9px]">Recommended </span>
                <span className="text-platinum">{step.recommended}</span>
              </p>
            )}
            {status === "COMPLETED" && (
              <p className="mt-1.5 text-[10.5px] font-semibold uppercase tracking-[0.1em] text-pass">
                Already done — the project state says so
              </p>
            )}
          </>
        )}

        {showWhy && <p className="mt-2 border-t border-line pt-2 text-[11px] leading-relaxed text-muted">{step.why}</p>}

        {/* Actions, in the mandated order. */}
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          <GBtn
            disabled={!canGoBack(session)}
            onClick={() => { emitEvent("BACK", view.step.id); setSessionAndPersist(back(session)); }}
            title="Back one step (Alt+←) — follows your actual path; never undoes a change"
          >
            ← Back
          </GBtn>
          {step.href && (
            <a
              href={withGuideTarget(step.href(ctx), step.uiTarget)}
              className="border border-precision/50 px-2.5 py-1 text-[9.5px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:bg-precision/10"
            >
              {blocked ? "Take me there" : "Do it with me"}
            </a>
          )}
          <GBtn onClick={() => setShowWhy((w) => !w)}>{showWhy ? "Hide why" : "Explain why"}</GBtn>
          {!blocked && status === "COMPLETED" && (
            <GBtn onClick={() => { emitEvent("ADVANCE", view.step.id); setSessionAndPersist(advance(flow, session, ctx)); }}>Next step</GBtn>
          )}
          {!blocked && status !== "COMPLETED" && (
            <GBtn onClick={() => { emitEvent("SKIP", view.step.id); setSessionAndPersist(skip(flow, session, ctx)); }} title="Defers the lesson. Satisfies nothing.">
              Skip for now
            </GBtn>
          )}
          {blocked && blocked.href && (
            <GBtn onClick={() => { emitEvent("SKIP", view.step.id, "blocked"); setSessionAndPersist(skip(flow, session, ctx)); }} title="The gate stays unresolved.">
              Leave unresolved
            </GBtn>
          )}
        </div>

        <div className="mt-2 flex items-center justify-between border-t border-line pt-1.5">
          <label className="flex items-center gap-1.5 text-[9.5px] uppercase tracking-[0.1em] text-muted">
            <input
              type="checkbox"
              checked={camHints}
              onChange={(e) => {
                setCamHints(e.target.checked);
                try {
                  window.localStorage.setItem("canvas.camHints", e.target.checked ? "1" : "0");
                } catch {
                  /* fine */
                }
              }}
            />
            CAM terminology hints
          </label>
          <span className="font-mono text-[9.5px] text-muted tabular-nums">
            {progress!.completed}/{progress!.total} done{progress!.skipped > 0 ? ` · ${progress!.skipped} deferred` : ""}
          </span>
        </div>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */

function withGuideTarget(href: string, target?: string): string {
  if (!target) return href;
  return `${href}${href.includes("?") ? "&" : "?"}guide=${encodeURIComponent(target)}`;
}

function Card({ children, onCollapse }: { children: React.ReactNode; onCollapse?: () => void }) {
  return (
    <aside
      aria-label="CANVAS Guide"
      className="fixed z-40 border-line-strong bg-surface/97 shadow-[0_10px_36px_rgba(0,0,0,0.45)] backdrop-blur-sm max-lg:inset-x-0 max-lg:bottom-0 max-lg:max-h-[70dvh] max-lg:overflow-y-auto max-lg:border-t lg:bottom-24 lg:right-3 lg:w-[344px] lg:max-w-[calc(100vw-24px)] lg:border"
    >
      {/* Bottom-sheet grab bar — phones and small tablets only. Tapping it
          collapses the sheet back to the Guide tab; the card floats at lg+. */}
      <button
        type="button"
        onClick={onCollapse}
        aria-label="Collapse the guide sheet"
        className="flex w-full items-center justify-center py-1.5 lg:hidden"
      >
        <span aria-hidden className="h-1 w-10 rounded-full bg-line-strong" />
      </button>
      {children}
    </aside>
  );
}

function Header({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
      <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-precision-dim">
        <DatumMark size={12} />
        {title}
      </span>
      {right}
    </div>
  );
}

function ModeSwitch({ mode, onChange }: { mode: GuideMode; onChange: (m: GuideMode) => void }) {
  return (
    <span className="flex border border-line" role="radiogroup" aria-label="Guide mode">
      {GUIDE_MODES.map((m) => (
        <button
          key={m}
          role="radio"
          aria-checked={mode === m}
          title={MODE_HELP[m]}
          onClick={() => onChange(m)}
          className={`px-1.5 py-[3px] text-[8.5px] font-semibold uppercase tracking-[0.1em] transition-colors ${
            mode === m ? "bg-precision/15 text-precision-dim" : "text-muted hover:text-platinum"
          }`}
        >
          {m}
        </button>
      ))}
    </span>
  );
}

function GBtn({
  children,
  onClick,
  disabled,
  title,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  title?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className="border border-line-strong px-2.5 py-1 text-[9.5px] font-semibold uppercase tracking-[0.12em] text-muted transition-colors hover:text-platinum disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </button>
  );
}
