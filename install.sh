#!/usr/bin/env bash
set -euo pipefail

# Downloads the latest fusion-cam-mcp binary for this platform and runs --install.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/BJam/fusion-cam-mcp/main/install.sh | bash

REPO="BJam/fusion-cam-mcp"
INSTALL_DIR="$HOME/fusion-cam-mcp"
BINARY="$INSTALL_DIR/fusion-cam-mcp"

info()  { echo "  ✓ $*"; }
err()   { echo "  ✗ $*" >&2; }

detect_asset() {
    local os arch
    os="$(uname -s)"
    arch="$(uname -m)"

    case "$os" in
        Darwin)
            case "$arch" in
                arm64)  echo "fusion-cam-mcp-darwin-arm64" ;;
                x86_64) echo "fusion-cam-mcp-darwin-x64" ;;
                *)      err "Unsupported macOS architecture: $arch"; exit 1 ;;
            esac
            ;;
        Linux)
            err "Linux binaries are not currently published."
            err "Use the developer setup instead: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
            exit 1
            ;;
        *)
            err "Unsupported OS: $os (use install.ps1 on Windows)"
            exit 1
            ;;
    esac
}

get_download_url() {
    local asset="$1"
    local url
    url="https://github.com/$REPO/releases/latest/download/$asset"
    echo "$url"
}

main() {
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║  Fusion 360 CAM MCP — Download & Install     ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""

    local asset
    asset="$(detect_asset)"
    info "Platform: $asset"

    local url
    url="$(get_download_url "$asset")"

    mkdir -p "$INSTALL_DIR"

    echo ""
    echo "── Downloading latest release ──"
    if command -v curl &>/dev/null; then
        curl -fSL --progress-bar -o "$BINARY" "$url"
    elif command -v wget &>/dev/null; then
        wget -q --show-progress -O "$BINARY" "$url"
    else
        err "Neither curl nor wget found. Install one and try again."
        exit 1
    fi
    info "Downloaded to $BINARY"

    chmod +x "$BINARY"

    # Strip macOS quarantine attribute so Gatekeeper doesn't block it
    if [[ "$(uname -s)" == "Darwin" ]]; then
        xattr -d com.apple.quarantine "$BINARY" 2>/dev/null || true
    fi

    echo ""
    echo "── Running installer ──"
    "$BINARY" --install < /dev/tty
}

main
