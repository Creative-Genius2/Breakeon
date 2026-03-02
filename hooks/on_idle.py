"""
on_idle.py - Claude Code hook: fires on Stop event

Stop event fires when Claude finishes its response.
stdin JSON has: session_id, transcript_path, permission_mode,
                hook_event_name ("Stop"), stop_hook_active

We tell the server Claude is done, which triggers:
1. Emulator saves state
2. Emulator flushes in-game save
3. Game pauses
"""

import urllib.request
import json
import os
import sys


def notify_server(port=3000):
    """Tell the Breakeon server that Claude is idle"""

    # Read stdin but we don't need much from the Stop event
    try:
        sys.stdin.read()
    except Exception:
        pass

    url = f"http://127.0.0.1:{port}/api/idle"
    try:
        req = urllib.request.Request(url, method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=2) as resp:
            pass
    except Exception:
        # Server might not be running
        pass


if __name__ == "__main__":
    port = 3000
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "..", "config.json")
        with open(config_path) as f:
            port = json.load(f).get("port", 3000)
    except Exception:
        pass
    notify_server(port)
