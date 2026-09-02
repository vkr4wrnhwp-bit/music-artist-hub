"use client";

import { useRef, useState, useTransition } from "react";
import { buttonClass } from "@/components/ui";
import { useInteraction, type Context } from "@/components/workspace/interaction";
import type { SceneAction } from "@/lib/engines/copilot-actions";

/**
 * CANVAS Copilot.
 *
 * The copilot answers from structured project data. When it does not have
 * what it needs, it says so and names the gap rather than producing a fluent
 * guess — the "needs" list below is a first-class part of the response, not an
 * error state.
 */

interface Message {
  role: "user" | "assistant";
  content: string;
  needs?: string[];
  references?: { kind: string; id: string; label: string }[];
  /**
   * Things to look at. These change what is on screen and nothing else, which
   * is why they are pressable — a wrong one wastes a click.
   */
  sceneActions?: SceneAction[];
  /**
   * Changes the copilot put forward. These have NOT been applied: they are in
   * the proposals queue waiting for a person. The panel links there rather
   * than offering an accept, because accepting an AI suggestion is a decision
   * with its own page and its own record.
   */
  proposals?: { kind: string; summary: string }[];
}

const SUGGESTED = [
  "Can I machine this?",
  "How should I hold this?",
  "Why two setups?",
  "What dimensions am I missing?",
  "Could this be cast instead?",
  "Can this be cheaper?",
];

export function Copilot({
  partId,
  partName,
  context,
}: {
  partId: string;
  partName: string;
  context: Record<string, unknown>;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pending, start] = useTransition();
  const scrollRef = useRef<HTMLDivElement>(null);
  const interaction = useInteraction();

  /*
   * A scene action changes what is on screen and nothing else. The target was
   * checked against this part server-side before it reached here, so this only
   * has to dispatch it — and the switch is exhaustive so a new action kind
   * cannot fall through into doing nothing silently.
   */
  const runSceneAction = (a: SceneAction) => {
    switch (a.kind) {
      case "SELECT_FEATURE":
        interaction.select(a.targetId);
        return;
      case "SET_CONTEXT":
        interaction.setContext(a.targetId as Context);
        return;
      case "FOCUS_OPERATION":
        interaction.setOperation(a.targetId);
        return;
    }
  };

  const send = (text: string) => {
    const question = text.trim();
    if (!question) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: question }]);

    start(async () => {
      const res = await fetch("/api/copilot", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ partId, question, context }),
      });
      if (!res.ok) {
        setMessages((m) => [
          ...m,
          { role: "assistant", content: "The copilot request failed. No answer was produced." },
        ]);
        return;
      }
      const data = await res.json();
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: data.reply,
          needs: data.needs,
          references: data.references,
          sceneActions: data.sceneActions,
          proposals: data.proposals,
        },
      ]);
      requestAnimationFrame(() => scrollRef.current?.scrollTo({ top: 1e6, behavior: "smooth" }));
    });
  };

  return (
    <>
      <header className="flex items-center justify-between border-b border-line px-3 py-2.5">
        <span className="instrument-label text-platinum-dim">CANVAS Copilot</span>
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
          <line x1="0" y1="6" x2="12" y2="6" stroke="var(--c-blue)" strokeWidth="1" />
          <line x1="6" y1="0" x2="6" y2="12" stroke="var(--c-blue)" strokeWidth="1" />
        </svg>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto p-3">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-[12px] leading-relaxed text-muted">
              Ask about {partName}. Answers come from this part&apos;s geometry, machine, tooling, workholding and cost
              assumptions — not from general knowledge about machining.
            </p>
            <div className="space-y-1">
              {SUGGESTED.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="block w-full border border-line px-2.5 py-1.5 text-left text-[11.5px] text-platinum-dim transition-colors hover:border-line-strong hover:text-white"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="space-y-3">
          {messages.map((m, i) => (
            <div key={i}>
              {m.role === "user" ? (
                <p className="border-l-2 border-l-line-strong pl-2.5 text-[12px] text-platinum-dim">{m.content}</p>
              ) : (
                <div className="border-l-2 border-l-precision/60 pl-2.5">
                  <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-platinum">{m.content}</p>
                  {m.needs && m.needs.length > 0 && (
                    <div className="mt-2 border border-review/30 px-2 py-1.5">
                      <p className="instrument-label text-review">Required before this can be answered</p>
                      <ul className="mt-1 space-y-0.5">
                        {m.needs.map((n) => (
                          <li key={n} className="text-[11.5px] text-muted">
                            — {n}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {m.sceneActions && m.sceneActions.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {m.sceneActions.map((a) => (
                        <button
                          key={`${a.kind}-${a.targetId}`}
                          type="button"
                          onClick={() => runSceneAction(a)}
                          className="border border-precision/50 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.1em] text-precision-dim hover:bg-raised"
                        >
                          {a.label}
                        </button>
                      ))}
                    </div>
                  )}
                  {m.proposals && m.proposals.length > 0 && (
                    <div className="mt-2 border border-review/30 px-2 py-1.5">
                      <p className="instrument-label text-review">
                        {m.proposals.length} change{m.proposals.length === 1 ? "" : "s"} put forward — not applied
                      </p>
                      <ul className="mt-1 space-y-0.5">
                        {m.proposals.map((p) => (
                          <li key={p.summary} className="text-[11.5px] leading-relaxed text-muted">
                            — {p.summary}
                          </li>
                        ))}
                      </ul>
                      <a href={`/parts/${partId}/proposals`} className="tech-label mt-1 inline-block text-precision-dim underline decoration-dotted">
                        Review them on the proposals page
                      </a>
                    </div>
                  )}
                  {m.references && m.references.length > 0 && (
                    <p className="tech-label mt-1.5">
                      Referenced: {m.references.map((r) => r.label).join(", ")}
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}
          {pending && <p className="tech-label">Thinking…</p>}
        </div>
      </div>

      <div className="border-t border-line p-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
          rows={2}
          placeholder="Ask about this part…"
          className="w-full resize-none border border-line-strong bg-void px-2.5 py-1.5 text-[12px] text-platinum placeholder:text-muted/60"
        />
        <div className="mt-1.5 flex justify-end">
          <button onClick={() => send(input)} disabled={pending || !input.trim()} className={buttonClass("primary", "sm")}>
            Ask
          </button>
        </div>
      </div>
    </>
  );
}
