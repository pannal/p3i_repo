#!/usr/bin/env bash
# Pack skin.p3i.estuary into the p3i_repo packed variant (3 XBT bundles + CE
# overlay), mirroring projects/Amlogic-ce/packages/mediacenter/skin.p3i.estuary/
# package.mk. Assembles into omega/skin.p3i.estuary/ at version <source>.<PACK_REV>.
set -euo pipefail

SKIN_SRC="${SKIN_SRC:-/home/panni/skin.p3i.estuary}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${OUT:-${REPO_ROOT}/omega/skin.p3i.estuary}"
OVERLAY="${OVERLAY:-/home/panni/CoreELEC/projects/Amlogic-ce/packages/mediacenter/skin.p3i.estuary/overlay}"
PACK_REV="${PACK_REV:-1}"

# Resolve TexturePacker — require exactly one (arch-specific build dir).
shopt -s nullglob
TP=( /home/panni/CoreELEC-build/build.CoreELEC-*/toolchain/bin/TexturePacker )
shopt -u nullglob
if [ "${#TP[@]}" -ne 1 ]; then
  echo "ERROR: expected exactly one TexturePacker, found ${#TP[@]}: ${TP[*]:-none}" >&2
  exit 1
fi
TEXTUREPACKER="${TP[0]}"
[ -d "$OVERLAY" ] || { echo "ERROR: overlay dir missing: $OVERLAY" >&2; exit 1; }

# Clean export of the skin's HEAD (no untracked/stray files).
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git -C "$SKIN_SRC" archive HEAD | tar -x -C "$TMP"

# Bake the CoreELEC branding overlay into media/ BEFORE packing (XBT shadows loose).
cp -PR "$OVERLAY"/. "$TMP/media/"

# Repo-variant version = source version + .PACK_REV.
SRC_VER="$(grep -m1 'id="skin.p3i.estuary"' "$TMP/addon.xml" | sed -E 's/.*\bversion="([^"]+)".*/\1/')"
NEW_VER="${SRC_VER}.${PACK_REV}"

# Assemble the published addon dir (cleared first). Everything EXCEPT raw media/
# and themes/ sources; those become XBT bundles below.
rm -rf "$OUT"
mkdir -p "$OUT/media"
for item in addon.xml LICENSE.txt changelog.txt colors extras fonts language playlists resources xml; do
  if [ -e "$TMP/$item" ]; then cp -PR "$TMP/$item" "$OUT/"; else echo "NOTE: skipping missing '$item'" >&2; fi
done

# Pack the default theme + each theme, exactly like kodi's pack_xbt.
"$TEXTUREPACKER" -input "$TMP/media" -output "$OUT/media/Textures.xbt" -dupecheck
for theme in "$TMP"/themes/*/; do
  t="$(basename "$theme")"
  "$TEXTUREPACKER" -input "$TMP/themes/$t" -output "$OUT/media/$t.xbt" -dupecheck
done

# Bump version in the assembled addon.xml ONLY (never the GitHub source).
sed -i -E "s|(id=\"skin.p3i.estuary\" version=\")[^\"]+(\")|\1${NEW_VER}\2|" "$OUT/addon.xml"

# Never ship Windows alternate-data-stream junk.
find "$OUT" -name '*:Zone.Identifier' -delete

echo "Packed skin.p3i.estuary ${SRC_VER} -> ${NEW_VER} (XBT) into ${OUT}"
ls -la "$OUT/media/"
