"use client";

import { useRef, useState, useTransition } from "react";
import { buttonClass } from "@/components/ui";

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
        { role: "assistant", content: data.reply, needs: data.needs, references: data.references },
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
