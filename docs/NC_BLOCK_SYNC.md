# NC block synchronization — BUILT

The analyzer renders the immutable original (served from the stored
UPLOADED row, not the client's file) as a read-only viewer: line
numbers, monospace, 26-line-of-truth per program line.

Both directions work:
- click a backplot segment → the viewer scrolls to and highlights its
  source line;
- click a code line → the backplot frames and highlights that line's
  motion.

Backplot payload carries the source line per segment ([kind, line,
x0,y0,x1,y1]). The plot draws on the light work-window ground with
fixed inks (the drawing is lit; the instrument is dark) — a defect
from the dark-theme flip, found and fixed during verification.

## Original vs proposed

Accepting proposals opens the ORIGINAL VS PROPOSED panel: a per-change
source diff (− original line / + line with the F-word swapped),
derived client-side from the same rule the emitter enforces, with the
authoritative masked-diff check still server-side at generation. Modal
feeds (no F-word in range) are shown as will-be-unapplied rather than
faked. The backplot's PROPOSED mode highlights accepted feed regions
with the caption "geometry identical by construction (masked diff)".
