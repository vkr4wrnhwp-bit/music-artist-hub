# The Room by Street Banker: the seam with this app

Distilled from the owner's two handoff documents (2026-09-14 UX rebuild
handoff, 2026-09-15 high-level handoff). Those documents govern The Room
itself; this page only records what binds **this** repository to it, so a
change on either side does not quietly break the other.

The Room lives in `teamsummitarts-sys/v2-street-banker` under
`song_builder/`, on the Render service `street-banker-v2-workflows`
(`srv-dad6q3gae00c7393s02g`, auto-deploy OFF, so a push needs a manual
deploy). Live test project:
`https://street-banker-v2-workflows.onrender.com/song-builder/?project=24965410-24d2-44c8-8cec-41cd0b2e45bc`

## What The Room owns

Song creation, start to finish: record, upload or create; arrange song
parts and tracks; takes and comping; per-instrument sound shaping;
analysis and improvement (Sound DNA, Keep/Avoid, timestamped notes,
Tempo and Key Lab); clip protection; A/B; collaboration; WAV export.

Its governing rule is **instrument, not AI demo**: generation is one
instrument inside the workflow, never a prompt box that hands back a
finished song. Its architecture is SONG / SOUND / IMPROVE / EXPORT, with
Share in the header.

## What this app keeps

- **Identity and entitlement.** One Street Banker account; The Room asks
  what the account holds. The Room never takes a card.
- **The master of record.** The finished WAV belongs in the vault, with
  the release path, the passport and the credits beside it.
- **Rights and consent state.** Who owns what, and what a voice was
  cleared for.
- **Spend.** Anything a run costs at a vendor is counted here, because
  the owner's ceiling has to hold across every suite.

## Open seams, to be settled before either side builds across them

1. **Two things are called a rack.** This app's **The Rack** (`/rack`) is
   mix and master: EQ, tube, compressor, LUFS against platform targets,
   WAV export. The Room's **Sound Rack** is per-instrument shaping
   (Texture, Motion, Space, Mix, Level). Same word, different jobs. One
   of them needs another name.
2. **Where mastering happens.** The Room's verified export is WAV and its
   handoff says not to claim mastering. So either The Room gains a finish
   stage or its export hands back to this app's Rack. The second keeps
   The Room from stacking and is the recommendation.
3. **Which audio work is song creation and which is campaign audio.** The
   owner's ruling is that all audio generation leaves this app. Splitting
   it by job rather than by vendor: stems and voice isolation are
   creation and belong with The Room; dubbing, campaign voiceover and
   sound effects are for video and ads and belong with Motion. Nothing in
   Audio Studio should stay here once both are ready.
4. **Monospace.** This app allows none anywhere in the interface
   (2026-09-13). The Room's brand guide allows it for technical readouts.
   One of the two rules has to give.
5. **The gold.** The Room's brass is `#D6AB62`; this app's gold token is
   `#D4A93C`. Close enough to look like a mistake rather than a choice.

## What must not happen

No claim that The Room's newer SONG / SOUND / IMPROVE / EXPORT
architecture is live until it is verified on the deployed service. No
external audio service without an approved model for permissions, cost,
rights, data handling and privacy. No collateral edits to V1, Noise Lab,
REACH or Royalty Sweep from Room work.
