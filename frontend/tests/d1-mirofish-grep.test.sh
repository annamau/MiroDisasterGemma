#!/usr/bin/env bash
# D1 mirofish purge guard. Fails if any user-visible path mentions MiroFish.
set -e

# Resolve repo root so the script works from any working directory
REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

# Widened scope per v2 plan — these paths are user-visible OR critical config
PATHS=(
  frontend/src
  frontend/index.html
  frontend/package.json
  backend/pyproject.toml
  docker-compose.yml
  .env.example
)

# Allowlist:
#   - historical docs (deliberate record of the rename)
#   - the demo-readiness plan files themselves (they reference the legacy product
#     name in "what v1 got wrong" / file-list context — not user-visible)
#   - the test script name + npm script ref ("test:no-mirofish") — meta references
#     to the guard that have to mention the word
ALLOWLIST_REGEX='docs/license-decision\.md|docs/progress\.md|frontend/CHINESE_TEXT_INVENTORY\.md|ROADMAP\.md|docs/aurora-demo-readiness-plan-v[12]\.md|test:no-mirofish|d1-mirofish-grep'

# docker-compose: only fail on NEO4J_AUTH default containing mirofish; ignore service/container name lines
check_docker_compose() {
  if grep -qE 'NEO4J_AUTH=.*mirofish' docker-compose.yml; then
    echo "FAIL: docker-compose.yml NEO4J_AUTH still uses mirofish default"
    return 1
  fi
  echo "OK: docker-compose.yml NEO4J_AUTH default is clean"
}

# Match both "MiroFish" and "mirofish"
# docker-compose.yml: ignore service/container names (mirofish:, container_name: mirofish-*)
# — these are infrastructure names, not user-visible product strings.
MATCHES=$(git grep -i 'mirofish' -- "${PATHS[@]}" 2>/dev/null \
  | grep -vE "$ALLOWLIST_REGEX" \
  | grep -vE '^docker-compose\.yml:\s*(mirofish:|#|  mirofish:|    container_name: mirofish)' \
  || true)

if [ -n "$MATCHES" ]; then
  echo "FAIL: mirofish strings remain in user-visible paths:"
  echo "$MATCHES"
  exit 1
fi
echo "OK: no mirofish strings in user-visible paths"

check_docker_compose || exit 1

# Also assert no Google Fonts loads in index.html
if grep -qE 'fonts\.googleapis\.com|fonts\.gstatic\.com' frontend/index.html; then
  echo "FAIL: frontend/index.html still loads Google Fonts CDN"
  exit 1
fi
echo "OK: no Google Fonts CDN in index.html"
