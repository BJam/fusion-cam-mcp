"""Hatch build hook: bundle the Fusion bridge add-in into wheels only (not editable installs)."""

from __future__ import annotations

import os
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        # TOML `force-include` for the bridge breaks PEP 660 editable installs (empty `.pth`, broken
        # imports). Release wheels still need the add-in under `fusion_cam/bridge_addon`.
        if version != "standard":
            return
        bridge = os.path.join(self.root, "fusion-bridge")
        if not os.path.isdir(bridge):
            return
        build_data.setdefault("force_include", {})
        build_data["force_include"]["fusion-bridge"] = "fusion_cam/bridge_addon"
