"""
on_thinking.py - Claude Code hook: fires on UserPromptSubmit and PostToolUse

Used for two events:

1. UserPromptSubmit — user hits enter, Claude starts working
   stdin JSON has: session_id, cwd, hook_event_name, prompt

2. PostToolUse — Claude just used a tool (Edit, Write, Bash, etc.)
   stdin JSON has: session_id, cwd, hook_event_name, tool_name,
                   tool_input (with file_path, command, etc.),
                   tool_response

Both tell the server "Claude is active" so the game stays unpaused.
PostToolUse also sends tool info so the status bar updates.
"""

import urllib.request
import json
import os
import sys


def notify_server(port=3000):
    """Tell the Breakeon server that Claude is active, with context"""

    context = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            hook_data = json.loads(raw)

            event = hook_data.get("hook_event_name", "")
            context["event"] = event
            context["session_id"] = hook_data.get("session_id", "")

            if event == "PostToolUse":
                # After a tool call — we get tool details for the status bar
                context["tool"] = hook_data.get("tool_name", "")
                tool_input = hook_data.get("tool_input", {})
                if isinstance(tool_input, dict):
                    context["file"] = (
                        tool_input.get("file_path", "")
                        or tool_input.get("path", "")
                        or tool_input.get("command", "")[:80]
                    )

            elif event == "UserPromptSubmit":
                # User just sent a prompt — Claude is about to start
                context["tool"] = ""
                context["file"] = ""

    except Exception:
        pass

    url = f"http://127.0.0.1:{port}/api/thinking"
    body = json.dumps(context).encode()
    try:
        req = urllib.request.Request(
            url, method="POST", data=body,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            pass
    except Exception:
        # Server might not be running — that's fine
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
