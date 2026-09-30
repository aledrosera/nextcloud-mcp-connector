#!/usr/bin/env bash
# scripts/olivia-rename.sh – rename the ExApp id mcp_connector -> mcp_connector_olivia where it
# names the app. The Python package and the "mcp_connector" logger stay untouched. Idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."
NEW=mcp_connector_olivia
files=()
while IFS= read -r f; do files+=("$f"); done < <(git ls-files -- appinfo src tests scripts Dockerfile deploy docs '.github/*' 'compose*.yml' '.env*.example' \
  | grep -v -e '^scripts/olivia-rename.sh$' -e '^scripts/olivia-check-rename.sh$')
perl -pi -e "
  s{<id>mcp_connector</id>}{<id>${NEW}</id>}g;
  s{<namespace>McpConnector</namespace>}{<namespace>McpConnectorOlivia</namespace>}g;
  s{<name>MCP Connector</name>}{<name>MCP Connector (olivia)</name>}g;
  s{street1983nk/mcp_connector(?!_olivia)}{aledrosera/${NEW}}g;
  s{exapps/mcp_connector(?![_a-z])}{exapps/${NEW}}g;
  s{proxy/mcp_connector(?![_a-z])}{proxy/${NEW}}g;
  s{nc_app_mcp_connector(?![_a-z]|_data)}{nc_app_${NEW}}g;
  s{nc_app_mcp_connector_data}{nc_app_${NEW}_data}g;
  s{\bmcp_connector:(?=[a-z])}{${NEW}:}g;
  s{\"mcp_connector_(admin|settings)\"}{\"${NEW}_\$1\"}g;
  s{APP_ID=\"mcp_connector\"}{APP_ID=\"${NEW}\"}g;
  s{APP_ID=mcp_connector(?![_a-zA-Z0-9])}{APP_ID=${NEW}}g;
  s{APP_ID = \"mcp_connector\"}{APP_ID = \"${NEW}\"}g;
  s{findtext\(\"id\"\) != \"mcp_connector\"}{findtext(\"id\") != \"${NEW}\"}g;
  s{frozen mcp_connector\b(?!_)}{frozen ${NEW}}g;
" "${files[@]}"
echo "renamed ${#files[@]} files to ${NEW}"
