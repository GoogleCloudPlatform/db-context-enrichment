#!/bin/bash
set -e

# This script builds the standalone executable for Linux, replicating release.yml logic.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.."

# 1. Install uv (if not present)
if ! command -v uv &> /dev/null; then
    echo "uv not found, installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# 2. Install dependencies
uv sync --frozen

# 3. Get versions from pyproject.toml
TOOLBOX_VERSION=$(grep -o '^toolbox_version = "[^"]*"' pyproject.toml | cut -d '"' -f 2)
EVALBENCH_VERSION=$(grep -o '^evalbench_version = "[^"]*"' pyproject.toml | cut -d '"' -f 2)

echo "Found toolbox version: ${TOOLBOX_VERSION}"
echo "Found evalbench version: ${EVALBENCH_VERSION}"

# 4. Download genai-toolbox binary (Linux amd64)
DOWNLOAD_URL="https://storage.googleapis.com/genai-toolbox/v${TOOLBOX_VERSION}/linux/amd64/toolbox"
echo "Downloading toolbox from: ${DOWNLOAD_URL}"
curl -L --fail -o "toolbox" "${DOWNLOAD_URL}"
chmod +x "toolbox"

# 5. Download evalbench binary (Linux x64)
ARCHIVE="linux.x64.evalbench.tar.gz"
DOWNLOAD_URL="https://github.com/GoogleCloudPlatform/evalbench/releases/download/v${EVALBENCH_VERSION}/${ARCHIVE}"
echo "Downloading evalbench from: ${DOWNLOAD_URL}"
curl -L --fail -o "${ARCHIVE}" "${DOWNLOAD_URL}"
tar -xzf "${ARCHIVE}"
chmod +x "evalbench"
rm "${ARCHIVE}"

# 6. Build binary with PyInstaller
uv run pyinstaller pyinstaller.spec

# 7. Validate binary
./dist/db-context-enrichment --help

# 8. Prepare distribution (Staging)
mkdir -p staging
cp -r skills/ staging/skills/
cp -r commands/ staging/commands/
mkdir -p staging/skills/autoctx-init/scripts/
mkdir -p staging/skills/autoctx-evaluate/scripts/

mv dist/db-context-enrichment staging/
mv toolbox staging/skills/autoctx-init/scripts/
mv evalbench staging/skills/autoctx-evaluate/scripts/

# Update gemini-extension.json
BINARY_NAME="\${extensionPath}/db-context-enrichment"
TOOLBOX_NAME="\${extensionPath}/skills/autoctx-init/scripts/toolbox"

jq ".contextFileName = \"GEMINI.md\" | .mcpServers.mcp_db_context_enrichment.command = \"$BINARY_NAME\" | .mcpServers.mcp_db_context_enrichment.args = [] | .mcpServers.mcp_toolbox = {\"command\": \"$TOOLBOX_NAME\", \"args\": [\"--stdio\", \"--config\", \"autoctx/tools.yaml\"]}" gemini-extension.json > staging/gemini-extension.json

cp GEMINI.md staging/
cp LICENSE staging/

# Create tarball
cd staging
tar -czf ../linux.x64.db-context-enrichment.tar.gz *
cd ..

echo "Build completed successfully! Artifact at linux.x64.db-context-enrichment.tar.gz"
