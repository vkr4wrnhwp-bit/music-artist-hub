# Homepage backup — 2026-07-29

Snapshot of the Street Banker homepage as it stood at commit `41f9777`,
immediately before the closing band was swapped from the arena photograph
to the archive-shelf photograph. Everything needed to bring this exact
version back is in this folder.

## What's here

| File | What it is |
|---|---|
| `COPY.md` | Every word on the page, in order, with links |
| `landing_config.py` | All homepage content and image wiring |
| `templates/landing.html` | The full page — self-contained, no macros |
| `static/img/sb-hero-photo.jpg` | Hero: performer + crowd |
| `static/img/sb-lane-01..03.jpg` | The three rack-unit lane cards |
| `static/img/sb-band-sweep.jpg` | Royalty Sweep background (backstage corridor) |
| `static/img/sb-band.jpg` | Closing band (front-of-house + arena) |
| `static/img/streetbanker-logo-dark.svg` | Header + footer logo |
| `rendered-homepage.html` | The live page's HTML as served on this date |

## Restore — either method

**Method 1 — git tag:**

```bash
git checkout homepage-sweep-photo-2026-07-29 -- landing_config.py templates/landing.html static/img/sb-hero-photo.jpg static/img/sb-lane-01.jpg static/img/sb-lane-02.jpg static/img/sb-lane-03.jpg static/img/sb-band.jpg static/img/sb-band-sweep.jpg
```

**Method 2 — copy from this folder.** From the repo root:

```bash
cp backups/homepage-2026-07-29/landing_config.py . && cp backups/homepage-2026-07-29/templates/landing.html templates/ && cp backups/homepage-2026-07-29/static/img/* static/img/
```

After either: bump `VERSION` in `static/js/sw.js` and the `?v=` numbers in
`landing_config.py`, or phones keep serving the cached previous version.

## The page

1. **Nav** — logo + tagline, four links, Login + Start Free Scan
2. **Hero** — THE ARTIST BACK OFFICE. beside the performer photograph
3. **Three Lanes** — three rack-unit cards: release, build, own
4. **Royalty Sweep** — the only dark section; the backstage-corridor
   photograph fills it, copy set over a scrim. No product screenshot, so
   no figures that could read as real earnings.
5. **Signature Tools** — five real modules, icon + name, one row
6. **Band** — full-bleed arena strip, no text, no link
7. **Final CTA** — your music is the product, your catalog is the asset
8. **Minimal footer** — four columns, socials, copyright

## Rules this version follows

- Homepage explains the promise; interior pages carry the detail
- No section makes more than one point; paragraphs are two lines max
- Every link resolves to a real route
- No invented client names, partner logos, or statistics; any figure in
  a product visual is labeled illustrative
- Gold is an accent only — labels, active states, the Sweep CTA
- One dark section; the rest stays white/ivory editorial
- Mobile: copy stacks before imagery, buttons are full-width and tappable

## Earlier versions

| Tag | Folder | What changed after it |
|---|---|---|
| `homepage-approved-2026-07-26` | `backups/homepage-2026-07-26/` | Artwork-led page, before the editorial rewrite |
| `homepage-editorial-2026-07-26` | `backups/homepage-editorial-2026-07-26/` | Editorial rewrite, before the arena band and the Sweep photograph |
| `homepage-sweep-photo-2026-07-29` | this folder | Arena band replaced by the archive-shelf photograph |

Unused artwork from the earlier versions (`sb-hero.jpg`, `sb-engines.jpg`,
`sb-distro-lanes.jpg`, `sb-ownership.jpg`, `sb-patchbay.jpg`) remains in
`static/img/`.
