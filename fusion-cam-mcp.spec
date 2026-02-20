# PyInstaller spec for the Fusion 360 CAM MCP server.
#
# Bundles the MCP server, query scripts, and Fusion add-in into a single
# standalone binary. Build with:
#   pyinstaller fusion-cam-mcp.spec
#
# The resulting binary supports:
#   ./fusion-cam-mcp               # Run MCP server (stdio mode)
#   ./fusion-cam-mcp --install     # Self-install: extract add-in + write MCP config

import os

ROOT = os.path.abspath(".")
SERVER_DIR = os.path.join(ROOT, "fusion-cam-mcp-server")
QUERIES_DIR = os.path.join(SERVER_DIR, "queries")
ADDIN_DIR = os.path.join(ROOT, "fusion-mcp-bridge")

# Collect all query .py files (read as data at runtime, not imported)
query_files = [
    (os.path.join(QUERIES_DIR, f), "queries")
    for f in os.listdir(QUERIES_DIR)
    if f.endswith(".py")
]

# Collect the Fusion add-in files (extracted on --install)
addin_files = [
    (os.path.join(ADDIN_DIR, "fusion-mcp-bridge.py"), "fusion-mcp-bridge"),
    (os.path.join(ADDIN_DIR, "fusion-mcp-bridge.manifest"), "fusion-mcp-bridge"),
    (os.path.join(ADDIN_DIR, "tcp_server.py"), "fusion-mcp-bridge"),
    (os.path.join(ADDIN_DIR, "executor.py"), "fusion-mcp-bridge"),
]

a = Analysis(
    [os.path.join(SERVER_DIR, "server.py")],
    pathex=[SERVER_DIR],
    datas=query_files + addin_files,
    hiddenimports=[
        "fusion_client",
        "queries",
        "installer",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="fusion-cam-mcp",
    debug=False,
    strip=False,
    upx=True,
    console=True,
    target_arch=None,
)
