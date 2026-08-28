# Product brief — MASTERCLIP OS

Written after running the application and inspecting every major screen at
3200×2060. Nothing here is inferred from documentation alone.

## One-sentence promise

**MASTERCLIP OS turns a written shot into finished, quality-checked cinematic
footage across every AI video provider — and tells you exactly what each
approved second cost.**

## Primary target user

The producer or technical director of a small studio running AI video
generation at volume — someone who has to answer "which model, how many takes,
what did it cost, and is it good enough to ship?" every day, across several
providers with incompatible APIs and pricing.

## The problem

Generating AI video at volume degenerates into a mess of browser tabs, one per
provider. Costs are unpredictable and only visible after the fact. Every take
has to be eyeballed by a human, including the broken ones. Nothing records why
a shot was approved, what produced it, or what the good take actually cost.

## Three strongest benefits

1. **One shot spec, priced across every provider before you spend.** The
   canonical shot is written once; the matrix prices every model/seed
   combination up front.
2. **Broken takes never reach a human.** Technical QC decodes and measures every
   output — black frames, freezes, wrong duration, truncation, low bitrate — and
   auto-rejects failures.
3. **Cost per *approved* second.** Not cost per render. The only number that
   reflects what usable footage actually costs.

## Three most visually demonstrable features

1. The **candidate matrix**, priced before submission.
2. The **review grid** — real playable takes side by side with QC verdicts.
3. The **cost lab** — spend resolved into cost per approved second.

## The hero workflow

Shot spec → priced matrix → batch submit → queue → automatic QC rejects a
defect → human review and approve → promote to master → provenance package.

This is chosen because it is the only journey that contains a genuine
before-and-after: a written intention at one end, finished graded footage and a
defensible cost figure at the other. It is also entirely real — it runs end to
end in the sandbox with no credentials and no spend.

## What must NOT be shown

- Audio Intelligence, Live Lab and Song Lab surfaces. They are real code but the
  audit of 2026-08-28 found them mock-backed on this deployment and Song Lab
  entirely unaudited. Showing them would imply a maturity that has not been
  demonstrated.
- Any provider API key, session cookie, or the seeded account's email address.
- The `masters` delivery path string, which exposes a container-local directory.

## Claims that can be substantiated

- Real MP4s are produced, decoded, measured and packaged. (Verified: the
  pipeline test runs ffmpeg and ffprobe end to end.)
- QC genuinely rejects defective renders without human involvement. (Verified.)
- The ledger records estimate and charge separately, and cost per approved
  second is computed from approved outputs only. (Verified.)
- Sandbox mode costs nothing and refuses billable providers. (Verified on
  2026-08-28, after the fix in PR #61 — before that it did not.)

## Claims that CANNOT be substantiated

- Any statement about the visual quality of paid provider output. No live
  provider generation has ever been run from this build.
- Any specific saving versus a named competitor.
- Throughput or latency figures at production scale.

The film therefore sells the *system*, never the generated pixels.

## Documented assumptions

1. **Sandbox footage is art-directed.** The mock provider's default output is
   diagnostic colour bars. A `cinematic` pattern was added to the sandbox
   generator so takes read as night-exterior footage matching the seeded
   creative brief. It is selected explicitly, changes no default, and the
   application's own on-screen SANDBOX banner remains visible throughout the
   film. The film never claims the footage came from a paid model.
2. **No voiceover.** No licensed TTS is available in this environment, so the
   film is built to be fully comprehensible muted, which is the stronger
   requirement anyway.
3. **Typography.** The application uses system font stacks, so there is no brand
   font to honour. Archivo (display) and IBM Plex Mono (data) were selected as
   premium substitutes and bundled locally.
