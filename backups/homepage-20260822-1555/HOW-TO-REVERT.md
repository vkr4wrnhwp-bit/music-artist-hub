# Homepage backup — before the Recut rebuild

Taken before rebuilding the landing page from the Street Banker Recut
artifact. Two sections were kept unchanged by instruction and are NOT
part of the rebuild: `partials/artist_eq.html` and
`partials/departments.html` (the six-panel grid).

## Revert everything, fastest

    git checkout homepage-before-recut -- templates/landing.html templates/partials/

That restores every template in this folder to exactly this state. The
git tag `homepage-before-recut` points at the commit this was taken from.

## Revert one section

    cp backups/<this-folder>/partials/sweep.html templates/partials/sweep.html

## See what changed

    git diff homepage-before-recut -- templates/landing.html templates/partials/

## What is in here

Every file under `templates/partials/` plus `templates/landing.html`, as
they rendered on the live site at the moment of the backup.
