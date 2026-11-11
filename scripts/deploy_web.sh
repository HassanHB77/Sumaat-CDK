#!/usr/bin/env bash
# Build the React app (web/) and deploy it with the SumaatWeb stack.
#
# Usage (from the project folder):
#   ./scripts/deploy_web.sh
#
# - If web/package.json exists: npm ci + npm run build -> web/dist, then the stack uploads web/dist.
# - If not (before Step 7's app exists): the stack uploads the placeholder page.
# - Writes outputs.json (same as the other deploys). Docker is NOT needed for this stack.
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
JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 uv run cdk deploy SumaatWeb --exclusively --outputs-file outputs.json

echo "== Done: $(jq -r '.SumaatWeb.SiteUrl' outputs.json)"
