#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
C="${CONCURRENCY:-6}"
render () {
  echo "=== $1 -> $2 ==="
  npx remotion render src/index.ts "$1" "renders/$2" --concurrency="$C" 2>&1 | tail -2
}
render SalesLandscape  sales-landscape.mp4
render SocialVertical  social-vertical.mp4
render HeroLandscape   hero-landscape.mp4
render CleanScreenOnly clean-screen-only.mp4
echo "=== all renders done ==="
node scripts/finish.mjs
