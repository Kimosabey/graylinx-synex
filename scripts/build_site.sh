#!/usr/bin/env bash
# Build the published site: exactly one page, and nothing else.
#
# mvp/MVP.html is self-contained — no external CSS, JS, fonts or images — so
# publishing is a copy. That is deliberate: it means the page a reviewer opens is
# byte-identical to the one in the repository, and there is no build step that
# could make the two disagree.
#
# Everything else in this repository stays unpublished. docs/00-source/ in
# particular holds the 78-page reference document and the FDD specification.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/site"

rm -rf "$OUT"
mkdir -p "$OUT"
cp "$ROOT/mvp/MVP.html" "$OUT/index.html"

# Belt and braces alongside netlify.toml: a crawler that ignores headers still
# reads robots.txt, and a stray direct hit still gets the meta tag in the page.
cat > "$OUT/robots.txt" <<'ROBOTS'
User-agent: *
Disallow: /
ROBOTS

cat > "$OUT/_headers" <<'HEADERS'
/*
  X-Robots-Tag: noindex, nofollow, noarchive
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer
HEADERS

echo "built site/ — $(wc -c < "$OUT/index.html") bytes, 1 page"
ls -la "$OUT"
