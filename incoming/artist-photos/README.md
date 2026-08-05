# Drop real photography here

Originals at full resolution. Do not pre-resize or pre-crop — every
derivative is generated from the original, and cropping twice costs
quality that cannot be recovered.

## Slots waiting for a photograph

| Slot | Section | Aspect | Master width |
| --- | --- | --- | --- |
| `hero-wide` | 2 Hero, desktop | 1342 x 775 | 1342 |
| `hero-tall` | 2 Hero, phone | 900 x 1200 | 900 |
| `creative-wide` | 7 Creative Studio, desktop | 830 x 980 | 830 |
| `creative-close` | 7 Creative Studio, phone | 600 x 520 | 600 |
| `rollout-wide` | 8 Rollout Engine, desktop | 940 x 710 | 940 |
| `rollout-close` | 8 Rollout Engine, phone | 600 x 630 | 600 |

The hero takes **two different photographs**, not two crops of one: a
landscape frame for desktop and a separate portrait frame for phones. A
wide crowd shot cropped to 3:4 keeps about a fifth of its width and loses
the crowd, which is the whole subject.

## Building

    python tools/build_photo.py incoming/artist-photos/<file> <slot> --focus x,y

`--focus` is the point that must survive the crop, as fractions of the
original's width and height. `0.5,0.5` is the centre and is usually
wrong: put it on the face, the hands, or whatever the frame is about.

Check the crop before writing anything:

    python tools/build_photo.py incoming/artist-photos/<file> hero-wide --focus 0.4,0.3 --dry-run

## After building

1. Update the `alt` text in the config to describe the new scene.
2. Bump the `?v=` on any changed asset and bump `VERSION` in
   `static/js/sw.js` — the service worker is cache-first on `/static`
   and will keep serving the old picture otherwise.

This folder is for source material and is not served. Nothing in it
reaches the site until it has been through `build_photo.py`.

## Credit

None. These photographs are the owner's own work, so there is no
photographer to attribute and no licence to acknowledge. The credit
partial that briefly existed for this was removed rather than left
unused.

The alt text still describes the scene, because that is an accessibility
requirement rather than a credit — and it does not name anyone in the
picture as a Street Banker artist, because a face on a marketing page is
read as an endorsement and that would be a claim about a business
relationship.
