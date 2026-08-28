# Hero storyboard — 96 s, 1920×1080, 30 fps

The authoritative timing lives in `src/script.ts`; this document is the reason
behind each choice. Frame numbers are at 30 fps for the hero cut.

| # | Scene | In | Sec | Shot | Camera | Copy sits |
|---|---|---|---|---|---|---|
| 1 | `open` | 0:00 | 4.5 | — | mark draws, wordmark rises | centred |
| 2 | `problem` | 0:04.5 | 4.5 | — | still | left |
| 3 | `today` | 0:09 | 7.0 | `today` | slow 1.06× breath | right |
| 4 | `marker` | 0:16 | 8.0 | `markers` | push to marker card | right |
| 5 | `telemetry` | 0:24 | 10.0 | `telemetry` | push to trace window | bottom |
| 6 | `engineer` | 0:34 | 11.0 | `engineer` | push to evidence chain | bottom |
| 7 | `authority` | 0:45 | 5.0 | — | still | left |
| 8 | `envelope` | 0:50 | 8.0 | `map` | push to changed region | right |
| 9 | `boundary` | 0:58 | 8.0 | `transfer` | push to write-disabled banner | right |
| 10 | `compare` | 1:06 | 11.0 | `compare` | push to the metric grid | bottom |
| 11 | `baseline` | 1:17 | 7.0 | `library` | push to revision lineage | right |
| 12 | `verdict` | 1:24 | 5.5 | — | still | left |
| 13 | `end` | 1:29.5 | 6.5 | — | lockup + disclosure | centred |

## Why this order

The film is one argument, not a feature tour:

1. **A problem you recognise** (1–2). A rider's sentence, and the silence after it.
2. **The system answers it** (3–6). Objective → marker → measured trace →
   ranked causes. Each scene is the consequence of the one before.
3. **The system's limits** (7–9). It recommends, it stays inside an envelope,
   and it never touches the ECU. Constraint scenes sit in the middle where they
   read as engineering rather than as a disclaimer at the end.
4. **The payoff** (10–12). The A/B disagrees with the rider, and TRACE reports
   it anyway. This is the argument the whole film exists to make.
5. **The signature** (13).

## Camera language

One move only: a slow push toward a named region of the frame, easing
`cubic-bezier(0.22, 0.61, 0.36, 1)` and settling at 72 % of the scene so every
result is **held**, never still moving when the viewer reads it. No tilt, no
parallax, no floating panels. The interface is photographed, not animated.

The push starts at 88 % of its target scale, so the largest move in the film is
about 14 % — enough to feel intentional, small enough never to look like a
zoom effect. `Screen.tsx` clamps the pan so the capture always covers the
frame.

## Type and scrim

Two levels of text on screen at once, never three: a mono eyebrow naming what
the system is doing, then a display headline, then one line of why it matters.
The copy sits on a band that reaches the ground colour outright — a
semi-transparent scrim lets interface text show through the headline, which
reads as a rendering fault rather than a layer.

## The cutdowns

Both are recompositions, not crops.

- **SalesLandscape (~30 s)** — `open, problem, engineer, compare, verdict, end`
  at 0.62× pace. Keeps the problem, the one differentiating capability, and the
  honest outcome.
- **SocialVertical (~15 s, 1080×1920)** — `problem, compare, verdict, end` at
  0.5× pace. Every shot is re-framed for the taller aspect
  (`tightenForVertical`) and all copy moves to the lower third, so the vertical
  cut is composed for its own frame rather than cropped out of the wide one.
- **CleanScreenOnly** — the same 96 s with the entire explanation layer off,
  for a presenter who wants to narrate live or for localisation.
