# Homepage image replacement map

Every homepage image, classified. Written during the implementation pass;
the replacement work itself is **blocked** — see the bottom of this file.

## Classification

| # | Section | Asset | Verdict | Why |
| --- | --- | --- | --- | --- |
| 2 | Hero | `hero-band-wide` / `hero-band-tall` | **REPLACE** | Generated. Reads as stock. The most valuable frame on the site and the least credible. |
| 3 | Artist EQ | `eq-room` | KEEP | Used as a frame with its centre painted out; the console sits in a real hole. Carries no claim. |
| 4 | Six Departments | `departments` | RETOUCH | Repaired once (fabricated wall text removed). Composition is strong; the generated look remains. |
| 5 | AI Artist Twin | `artist-twin` | **REPLACE** | Generated, and repaired for invented track lists. A real artist at work is the whole point of this section. |
| 6 | Three Lanes | `lanes-unit` | KEEP | Object-led. Hardware, no people, no claim. Now carries live overlay controls. |
| 7 | Creative Studio | `creative-wide` / `creative-close` | **REPLACE** | Generated merch table, repaired for fake branding. A real campaign series would prove the section's claim. |
| 8 | Rollout Engine | `rollout-wide` / `rollout-close` | **REPLACE** | Generated, repaired for nonsensical tour routes. |
| 9 | Royalty Sweep | `sweep-wide` / `sweep-close` | KEEP | Object-led archival frame. Repaired and holding. |
| 10 | Global Distribution | `distro-wide` / `distro-close` | KEEP | Object-led. Repaired for invented registration numbers. |
| 11 | Metadata Passport | `passport-wide` / `passport-close` | KEEP | Blueprint. Used unaltered, no repair needed. |
| 12 | Closing | `closing-wide` / `closing-close` | KEEP | Used unaltered, cropped only. The strongest frame on the page. |

Six KEEP, one RETOUCH, four REPLACE, zero REMOVE.

## Where real photography is worth most

Ranked. Hero first because it is seen by everyone and currently reads as
stock; Creative Studio second because a real campaign series is
*evidence* for that section's central claim rather than decoration.

1. Hero
2. Creative Studio
3. AI Artist Twin
4. Rollout Engine
5. Fan Intelligence (no homepage section yet)

Object-led visuals stay for Royalty Sweep, Distribution, Metadata
Passport, Three Lanes and the closing frame — those sections are about
paperwork and hardware, and a face would be decoration.

## Rules applied

- No copy over faces, instruments, merchandise, artwork, calendars,
  records, tapes, road cases or any object the frame is about.
- No fake dashboards composited into photography.
- No heavy recolouring of real photography.
- No implication that any artist shown is represented by Street Banker.
- **No repetition of the same artist across sections.** This is why the
  artist portrait series was ruled out for a three-section swap: the same
  recognisable face in the hero, Creative Studio and Rollout turns a page
  selling infrastructure for any artist into one artist's press kit.
- Dedicated mobile crops, never a centre-crop of the desktop frame.
- Usage rights tracked per asset before publication.

## Per-slot specification for replacement

| Slot | Aspect | Master | Focal point | Copy position | Natural negative space |
| --- | --- | --- | --- | --- | --- |
| `hero-wide` | 1342 × 775 | 1342 | performer, left third | copy left | blown-out sky, right |
| `hero-tall` | 900 × 1200 | 900 | performer | copy above image | upper frame |
| `creative-wide` | 830 × 980 | 830 | subject centre | copy left of image | — |
| `creative-close` | 600 × 520 | 600 | subject | copy above | — |
| `rollout-wide` | 940 × 710 | 940 | figure walking, centre | copy right, over bleed | dark corridor walls |
| `rollout-close` | 600 × 630 | 600 | figure | copy above | — |

`tools/build_photo.py` generates every derivative from one original:

```bash
python tools/build_photo.py incoming/artist-photos/crowd.jpg hero-wide --focus 0.3,0.4
```

`--focus` names the point that must survive the crop. Centre-cropping
decides that for itself and usually decides wrong.

## Status: BLOCKED

Blocked on the stop condition the brief names — **a real artist image
lacking confirmed usage permission** — plus a delivery problem.

1. Two documentary photographs (a crowd frame from the stage, a backstage
   corridor) were selected for the hero and Rollout Engine. They were
   posted into the chat, which renders an image without creating a file,
   so they never reached disk. Downloads, Desktop, OneDrive, Pictures,
   Dropbox and the repository were all searched; the machine has one
   drive and one user profile and the files are not on it.
2. A third candidate — a live shot under red stage light — carries a
   visible photographer's watermark in the top-right corner. That
   contradicts the stated ownership. It was not used, and the watermark
   was not removed: stripping an author's mark to use their work is a
   different act from removing fabricated text off a generated image, and
   it is not one to perform.

No AI images were generated during this pass. Nothing was retouched
beyond what was already repaired in earlier section work.

## Rights tracking

| Asset | Photographer | Permission | Credit required | Expires |
| --- | --- | --- | --- | --- |
| All current homepage images | generated | n/a | no | n/a |
| `crowd` (pending) | owner-stated | stated owned, unverified in writing | no (owner's own) | n/a |
| `corridor` (pending) | owner-stated | stated owned, unverified in writing | no (owner's own) | n/a |
| red-light live shot | watermark "K.J.M…" | **not established** | yes, if licensed | unknown |
