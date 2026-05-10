#!/bin/bash
# Uninstall the rforge plugin from Claude Code.
# Note: as of v1.2.0 the plugin installs to ~/.claude/plugins/rforge.
# Earlier versions (v0.1.0 from the claude-plugins monorepo) installed
# to ~/.claude/plugins/rforge-orchestrator — if you have that legacy
# install, remove it manually with:
#   rm -rf ~/.claude/plugins/rforge-orchestrator

set -euo pipefail

PLUGIN_NAME="rforge"
TARGET_DIR="$HOME/.claude/plugins/$PLUGIN_NAME"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== RForge Plugin Uninstaller ===${NC}"
echo ""

# Check if plugin is installed
if [[ ! -e "$TARGET_DIR" ]]; then
    echo -e "${YELLOW}Plugin is not installed${NC}"
    echo -e "Location checked: $TARGET_DIR"
    exit 0
fi

# Determine installation type
if [[ -L "$TARGET_DIR" ]]; then
    INSTALL_TYPE="symlink (development mode)"
else
    INSTALL_TYPE="directory (production mode)"
fi

echo -e "${YELLOW}Found installation:${NC} $INSTALL_TYPE"
echo -e "${YELLOW}Location:${NC} $TARGET_DIR"
echo ""

# Confirm uninstall
read -p "$(echo -e ${YELLOW}Uninstall plugin? [y/N]:${NC} )" -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Uninstall cancelled${NC}"
    exit 0
fi

# Remove plugin
echo -e "${BLUE}Removing plugin...${NC}"

if [[ -L "$TARGET_DIR" ]]; then
    rm "$TARGET_DIR"
    echo -e "${GREEN}✓ Removed symlink${NC}"
elif [[ -d "$TARGET_DIR" ]]; then
    rm -rf "$TARGET_DIR"
    echo -e "${GREEN}✓ Removed directory${NC}"
fi

echo ""
echo -e "${GREEN}✓ Plugin uninstalled successfully${NC}"
echo ""
echo -e "${BLUE}To reinstall:${NC}"
echo -e "  brew install --HEAD data-wise/tap/rforge   # Recommended (Homebrew)"
echo -e "  # Or from a local checkout:"
echo -e "  cd ~/projects/dev-tools/rforge"
echo -e "  ./scripts/install.sh         # Production mode"
echo -e "  ./scripts/install.sh --dev   # Development mode"
