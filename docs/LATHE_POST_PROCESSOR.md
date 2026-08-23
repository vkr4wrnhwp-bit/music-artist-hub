# Lathe post processor

`turn/post.ts` — generic Fanuc-style 2-axis DEVELOPMENT post: G18 G20
G40 G80 G99 preamble, T0101-style calls, G96 S + M3 or G97 S + M3,
mandatory G50 clamp when any op runs CSS (REFUSES to emit without it),
M8/M9, G32-style thread passes, M30. One canned cycle only — rigid
tapping (M29/G84, closed by G80), because a tap's reversal cannot be
expressed as feed moves and emitting them as G1 would strip the thread
on the way out. No other canned cycles, no threading
cycles, no TNR compensation — later, and listed as such. Every header:
NOT FOR PRODUCTION USE. There is no turning export path yet; the
workspace withholds even the preview while blocking gates fail.
