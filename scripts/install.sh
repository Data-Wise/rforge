#!/bin/bash
# Install the rforge plugin to Claude Code.
# As of v1.2.0 the plugin installs to ~/.claude/plugins/rforge.
# Earlier versions used PLUGIN_NAME="rforge-orchestrator" — if you
# previously installed that, the path differs and you may want to
# remove the old directory (`rm -rf ~/.claude/plugins/rforge-orchestrator`)
# after the new install completes.

set -euo pipefail

PLUGIN_NAME="rforge"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="$HOME/.claude/plugins/$PLUGIN_NAME"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
DEV_MODE=false
if [[ "${1:-}" == "--dev" ]]; then
    DEV_MODE=true
fi

echo -e "${BLUE}=== RForge Plugin Installer ===${NC}"
echo -e "${BLUE}Plugin: ${YELLOW}$PLUGIN_NAME${NC}"
echo -e "${BLUE}Source: ${YELLOW}$SOURCE_DIR${NC}"
echo -e "${BLUE}Target: ${YELLOW}$TARGET_DIR${NC}"
echo ""

# Create plugins directory if needed
if [[ ! -d "$HOME/.claude/plugins" ]]; then
    echo -e "${YELLOW}Creating plugins directory...${NC}"
    mkdir -p "$HOME/.claude/plugins"
fi

# Remove existing installation
if [[ -e "$TARGET_DIR" ]]; then
    echo -e "${YELLOW}Removing existing installation...${NC}"
    if [[ -L "$TARGET_DIR" ]]; then
        rm "$TARGET_DIR"
    elif [[ -d "$TARGET_DIR" ]]; then
        rm -rf "$TARGET_DIR"
    fi
fi

# Install plugin
if [[ "$DEV_MODE" == true ]]; then
    echo -e "${GREEN}Installing in DEVELOPMENT mode (symlink)...${NC}"
    ln -s "$SOURCE_DIR" "$TARGET_DIR"
    echo -e "${GREEN}✓ Symlinked: $TARGET_DIR → $SOURCE_DIR${NC}"
else
    echo -e "${GREEN}Installing in PRODUCTION mode (copy)...${NC}"
    cp -r "$SOURCE_DIR" "$TARGET_DIR"
    echo -e "${GREEN}✓ Installed to: $TARGET_DIR${NC}"
fi

echo ""
echo -e "${GREEN}✓ $PLUGIN_NAME plugin installed successfully!${NC}"
echo ""

# Show available commands
echo -e "${BLUE}=== Available Commands ===${NC}"
echo ""
echo -e "  ${YELLOW}/rforge:analyze${NC} <description>   - Balanced analysis (< 30s)"
echo -e "  ${YELLOW}/rforge:quick${NC}                 - Ultra-fast check (< 10s)"
echo -e "  ${YELLOW}/rforge:thorough${NC} <description> - Comprehensive (2-5m)"
echo ""

# Show requirements
echo -e "${BLUE}=== Requirements ===${NC}"
echo -e "  ${GREEN}✓${NC} Python 3.10+ on PATH"
echo -e "  ${GREEN}✓${NC} R 4.0+ (for r:* commands)"
echo ""

if [[ "$DEV_MODE" == true ]]; then
    echo -e "${YELLOW}Development Mode:${NC} Source changes immediately reflected"
else
    echo -e "${YELLOW}Production Mode:${NC} Reinstall to get source updates"
fi

echo ""
echo -e "${GREEN}Ready to use! Try: /rforge:quick${NC}"
