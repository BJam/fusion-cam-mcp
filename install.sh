#!/bin/bash
#
# Install the Fusion 360 CAM MCP add-in by creating a symlink
# in Fusion's AddIns directory.
#
# Usage: ./install.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ADDIN_SRC="$SCRIPT_DIR/fusion-cam-mcp-addin"
ADDIN_NAME="fusion-cam-mcp-addin"

# Fusion 360 AddIns directory (macOS)
FUSION_ADDINS_MAC="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns"

# Fusion 360 AddIns directory (Windows, via WSL or Git Bash)
FUSION_ADDINS_WIN="$APPDATA/Autodesk/Autodesk Fusion 360/API/AddIns"

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    FUSION_ADDINS="$FUSION_ADDINS_MAC"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
    FUSION_ADDINS="$FUSION_ADDINS_WIN"
else
    echo "Error: Unsupported OS. Please manually symlink:"
    echo "  $ADDIN_SRC -> <Fusion 360 AddIns directory>/$ADDIN_NAME"
    exit 1
fi

# Check that the add-in source exists
if [ ! -d "$ADDIN_SRC" ]; then
    echo "Error: Add-in source not found at $ADDIN_SRC"
    exit 1
fi

# Check that Fusion's AddIns directory exists
if [ ! -d "$FUSION_ADDINS" ]; then
    echo "Error: Fusion 360 AddIns directory not found at:"
    echo "  $FUSION_ADDINS"
    echo ""
    echo "Make sure Fusion 360 has been installed and run at least once."
    exit 1
fi

TARGET="$FUSION_ADDINS/$ADDIN_NAME"

# Remove existing symlink or directory if present
if [ -L "$TARGET" ]; then
    echo "Removing existing symlink at $TARGET"
    rm "$TARGET"
elif [ -d "$TARGET" ]; then
    echo "Warning: A directory (not symlink) already exists at $TARGET"
    echo "Please remove it manually if you want to replace it."
    exit 1
fi

# Create the symlink
ln -s "$ADDIN_SRC" "$TARGET"

echo ""
echo "Successfully installed Fusion 360 CAM MCP add-in!"
echo ""
echo "  Source: $ADDIN_SRC"
echo "  Link:   $TARGET"
echo ""
echo "Next steps:"
echo "  1. Open Fusion 360"
echo "  2. Go to UTILITIES > ADD-INS (Shift+S)"
echo "  3. Find 'fusion-cam-mcp-addin' in the Add-Ins tab"
echo "  4. Click 'Run'"
echo ""
