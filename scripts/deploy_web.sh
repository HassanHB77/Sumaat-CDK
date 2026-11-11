#!/usr/bin/env bash
# Build the React app (web/) and deploy it with the SumaatWeb stack.
#
# Usage (from the project folder):
#   ./scripts/deploy_web.sh
#
# - If web/package.json exists: npm ci + npm run build -> web/dist, then the stack uploads web/dist.
# - If not (before Step 7's app exists): the stack uploads the placeholder page.
# - Merges SumaatWeb's outputs into outputs.json (keeps the other stacks'). Docker is NOT needed.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f web/package.json ]; then
  echo "== Building web/ (npm ci && npm run build)"
  (cd web && npm ci && npm run build)
  [ -f web/dist/index.html ] || { echo "Build finished but web/dist/index.html is missing"; exit 1; }
else
  echo "== No web/package.json yet: deploying the placeholder page"
fi

echo "== Deploying SumaatWeb"
# Deploy into a temp file, then MERGE into outputs.json: writing outputs.json directly would replace it with
# only SumaatWeb's outputs and lose the other stacks' ids (used by get_token.py, seed.py, smoke_test.sh).
TMP_OUT="$(mktemp)"
trap 'rm -f "$TMP_OUT"' EXIT
JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 uv run cdk deploy SumaatWeb --exclusively --outputs-file "$TMP_OUT"
if [ -f outputs.json ]; then
  jq -s '.[0] * .[1]' outputs.json "$TMP_OUT" > outputs.json.new && mv outputs.json.new outputs.json
else
  cp "$TMP_OUT" outputs.json
fi

echo "== Done: $(jq -r '.SumaatWeb.SiteUrl' outputs.json)"
