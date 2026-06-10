#!/usr/bin/env python3
"""
Setup script: Adds Comfy Pilot MCP server to Claude Desktop config.
Run this once, then restart Claude Desktop.
"""

import json
import os
import sys
import shutil
from pathlib import Path

# Paths
MCP_SERVER = r"C:\Users\Chris\Documents\ComfyUI\custom_nodes\comfy-pilot\mcp_server.py"
CLAUDE_CONFIG = Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"

# Find best Python executable (prefer the one running this script)
python_exe = sys.executable

def main():
    print(f"Python:      {python_exe}")
    print(f"MCP server:  {MCP_SERVER}")
    print(f"Claude config: {CLAUDE_CONFIG}")
    print()

    # Check MCP server exists
    if not os.path.isfile(MCP_SERVER):
        print(f"ERROR: MCP server not found at {MCP_SERVER}")
        print("Make sure Comfy Pilot is installed in ComfyUI.")
        sys.exit(1)

    # Read existing config (or start fresh)
    config = {}
    if CLAUDE_CONFIG.exists():
        with open(CLAUDE_CONFIG, "r", encoding="utf-8") as f:
            try:
                config = json.load(f)
                print("Loaded existing Claude Desktop config.")
            except json.JSONDecodeError:
                print("WARNING: Could not parse existing config, starting fresh.")
    else:
        print("No existing config found, creating new one.")

    # Back up existing config
    if CLAUDE_CONFIG.exists():
        backup = CLAUDE_CONFIG.with_suffix(".json.bak")
        shutil.copy2(CLAUDE_CONFIG, backup)
        print(f"Backed up existing config to: {backup}")

    # Add/update mcpServers entry
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["comfyui"] = {
        "command": python_exe,
        "args": [MCP_SERVER]
    }

    # Write updated config
    CLAUDE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with open(CLAUDE_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print()
    print("SUCCESS! Added comfyui MCP server to Claude Desktop config.")
    print()
    print("Current mcpServers:")
    for name, cfg in config.get("mcpServers", {}).items():
        print(f"  {name}: {cfg.get('command')} {' '.join(cfg.get('args', []))}")
    print()
    print(">>> RESTART Claude Desktop for changes to take effect. <<<")

if __name__ == "__main__":
    main()
