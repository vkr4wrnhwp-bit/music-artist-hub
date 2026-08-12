# ROI / capacity — BUILT (ESTIMATED, assumptions shown)

`src/lib/nc/roi.ts` + the ROI panel on the NC analyzer. Deterministic
arithmetic over the accepted RAISE proposals only: save/part, batch
hours, annual machine hours, and a capacity value ONLY when the shop
has a configured machine rate — no rate, no dollar figure, rather than
assuming one. Every output is labelled ESTIMATED and states that
recovered hours are capacity, not revenue. Negative savings clamp to
zero.
