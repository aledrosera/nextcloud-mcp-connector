#!/usr/bin/env bash
# scripts/olivia-check-rename.sh – fail if a structural reference to the old app id is left.
set -euo pipefail
cd "$(dirname "$0")/.."
pattern='<id>mcp_connector</id>|exapps/mcp_connector([^_a-z]|$)|nc_app_mcp_connector([^_]|$)|nc_app_mcp_connector_data|(^|[^_a-z])mcp_connector:[a-z]|"mcp_connector_(admin|settings)"|street1983nk/mcp_connector|APP_ID=mcp_connector([^_a-zA-Z0-9]|$)|APP_ID = "mcp_connector"|<name>MCP Connector</name>|proxy/mcp_connector([^_a-z]|$)|findtext\("id"\) != "mcp_connector"|frozen mcp_connector([^_]|$)'
if git grep -nE "$pattern" -- appinfo src tests scripts Dockerfile deploy docs ':!scripts/olivia-*.sh'; then
  echo "old app id still present" >&2
  exit 1
fi
echo "rename check passed"
