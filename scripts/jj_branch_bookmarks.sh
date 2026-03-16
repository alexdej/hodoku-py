#!/usr/bin/env bash
# Usage: jj_branch_bookmarks.sh <tip-bookmark> [trunk-bookmark]
#
# Outputs all bookmark names on the path from <tip-bookmark> back to the
# common ancestor with <trunk-bookmark> (default: main), in tip-to-root order.
# Safe to pipe to: xargs -I{} jj abandon {}
#
# Example:
#   bash scripts/jj_branch_bookmarks.sh feature/generator | xargs -I{} jj abandon {}

set -euo pipefail

TIP="${1:?Usage: jj_branch_bookmarks.sh <tip-bookmark> [trunk-bookmark]}"
TRUNK="${2:-main}"

jj log \
    -r "ancestors(${TIP}) ~ ancestors(${TRUNK}) | ${TIP}" \
    --no-graph \
    -T 'local_bookmarks.map(|b| b.name() ++ "\n").join("")' \
| grep .
