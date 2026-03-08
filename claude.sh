#!/bin/bash
# Drop-in replacement for `claude` — runs inside the isolated dev container.
# Usage: ./claude.sh [claude args...]
#        ./claude.sh --bash   # drop into a shell instead

TAG="693f55f2-e0e7-4624-8f8f-5f0bf01e51dd"
IMAGE="hodoku-claude:$TAG"

HODOKU_SRC="$(dirname "$(pwd)")/HoDoKu"
JJ_CONFIG="$HOME/.config/jj"
CLAUDE_CONFIG="$HOME/.claude"

if [ "$1" = "--bash" ]; then
    shift
    exec docker run -it --rm \
        -v "$(pwd)":/workspace \
        -v "$HODOKU_SRC":/HoDoKu:ro \
        -v "$JJ_CONFIG":/root/.config/jj:ro \
        -v "$CLAUDE_CONFIG":/root/.claude \
        -e ANTHROPIC_API_KEY \
        --entrypoint bash \
        "$IMAGE" "$@"
fi

exec docker run -it --rm \
    -v "$(pwd)":/workspace \
    -v "$HODOKU_SRC":/HoDoKu:ro \
    -v "$JJ_CONFIG":/root/.config/jj:ro \
    -e ANTHROPIC_API_KEY \
    "$IMAGE" \
    --dangerously-skip-permissions \
    "$@"
