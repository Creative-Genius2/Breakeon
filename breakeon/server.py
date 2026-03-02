"""
server.py - Breakeon local server

This runs on localhost (your machine only, not the internet) and does 3 jobs:

1. SERVES THE GAME PAGE
   When you open localhost:3000, it serves the index.html with the emulator.

2. SERVES YOUR ROM AND SAVE
   The emulator in the browser needs to download the ROM to play it.
   But the ROM lives somewhere random on your disk (like C:/Games/roms/).
   This server reads your config.json, finds the ROM, and serves it at /rom.
   Same for save files at /save.
   
   Your ROM never leaves your machine — it goes:
   Your disk -> this server -> your browser. All on 127.0.0.1 (localhost).

3. MANAGES HOOK STATE
   The Claude Code hooks call /api/thinking and /api/idle to tell us
   what Claude is doing. The emulator page polls /api/state to find out.
   
   Hook fires "Claude started" -> POST /api/thinking -> page polls -> resumes game
   Hook fires "Claude stopped" -> POST /api/idle -> page polls -> pauses + saves game
"""

import http.server
import json
import os
import re
import shutil
import sys
import threading
import time
from pathlib import Path

# Where this script lives — all paths relative to here
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"       # Working copies of ROM/save go here
BACKUP_DIR = BASE_DIR / "backups"  # Save backups

# Import our utilities
sys.path.insert(0, str(BASE_DIR / "utils"))
from dsv_convert import ensure_sav, is_dsv_file
from auto_name import auto_name_or_override


def load_config():
    """Load user config — their game library and settings"""
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(config):
    """Save config back (for switching active game)"""
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def get_active_game(config):
    """Get the currently selected game from the library"""
    games = config.get("games", [])
    active = config.get("active_game", 0)
    if not games:
        return {"name": "No games", "rom_path": "", "save_path": ""}
    active = max(0, min(active, len(games) - 1))
    return games[active]


def resolve_name(game, config=None):
    """Get the display name for a game entry.
    Uses the user's name if set, otherwise auto-generates from the ROM."""
    compact = (config or {}).get("compact_names", False)
    return auto_name_or_override(
        game.get("rom_path", ""),
        game.get("name", ""),
        compact=compact,
    )


# Map file extensions to EmulatorJS core names
# This is how EmulatorJS knows which emulator engine to boot
CORE_MAP = {
    ".nds": "melonds",     # DS (melonDS)
    ".gba": "mgba",        # GBA (mGBA)
    ".gbc": "gambatte",    # Game Boy Color
    ".gb":  "gambatte",    # Game Boy
    ".nes": "fceumm",      # NES
    ".nez": "fceumm",      # NES (alt)
    ".fds": "fceumm",      # Famicom Disk System
    ".snes": "snes9x",     # SNES
    ".sfc": "snes9x",      # SNES (alt)
    ".smc": "snes9x",      # SNES (alt)
    ".n64": "mupen64plus_next",  # N64
    ".z64": "mupen64plus_next",  # N64 (alt)
    ".v64": "mupen64plus_next",  # N64 (alt)
}

# Human-readable platform labels for the UI
PLATFORM_NAMES = {
    "melonds": "DS",
    "mgba": "GBA",
    "gambatte": "GB/GBC",
    "fceumm": "NES/FDS",
    "snes9x": "SNES",
    "mupen64plus_next": "N64",
}


def get_core_for_rom(rom_path):
    """Figure out which EmulatorJS core to use based on the file extension"""
    ext = os.path.splitext(rom_path)[1].lower()
    return CORE_MAP.get(ext, "melonds")  # default to DS if unknown


def setup_data_dir(config):
    """
    Copy the active game's ROM and save into our data/ folder.
    This also handles .dsv -> .sav conversion.
    """
    DATA_DIR.mkdir(exist_ok=True)
    BACKUP_DIR.mkdir(exist_ok=True)

    game = get_active_game(config)
    rom_path = game.get("rom_path", "")
    save_path = game.get("save_path", "")

    # Figure out the right file extension for the ROM copy
    rom_ext = os.path.splitext(rom_path)[1].lower() if rom_path else ".nds"
    rom_dest = DATA_DIR / f"game{rom_ext}"

    # Clean out old ROM files (in case we switched from .gba to .nds etc)
    # ONLY remove ROM files, NOT save files
    for old in DATA_DIR.glob("game.*"):
        if old.suffix.lower() in CORE_MAP:  # only delete known ROM extensions
            old.unlink()

    # Copy ROM
    if not rom_path:
        print("WARNING: No ROM path configured")
        print("  Add a game to the 'games' list in config.json")
        return

    if not os.path.exists(rom_path):
        print(f"WARNING: ROM not found at {rom_path}")
        print("  Check the rom_path in config.json — does the file exist?")
        return

    # Basic ROM validation — check it's not empty or suspiciously small
    rom_size = os.path.getsize(rom_path)
    if rom_size == 0:
        print(f"WARNING: ROM file is empty: {rom_path}")
        return
    if rom_ext == ".nds" and rom_size < 131072:  # DS ROMs are at least 128KB
        print(f"WARNING: ROM seems too small for a DS game ({rom_size} bytes): {rom_path}")
        print("  File might be corrupted or incomplete")
    if rom_ext == ".gba" and rom_size < 32768:  # GBA ROMs are at least 32KB
        print(f"WARNING: ROM seems too small for a GBA game ({rom_size} bytes): {rom_path}")

    try:
        shutil.copy2(rom_path, rom_dest)
        print(f"ROM loaded: {rom_path} ({rom_size / 1024 / 1024:.1f} MB)")
        print(f"  Core: {get_core_for_rom(rom_path)}")
    except PermissionError:
        print(f"ERROR: Permission denied reading ROM: {rom_path}")
        print("  Check file permissions or run as administrator")
        return
    except Exception as e:
        print(f"ERROR: Failed to copy ROM: {e}")
        return

    # Copy and convert save
    if save_path and os.path.exists(save_path):
        # Back up the original save first (never lose progress!)
        backup_name = f"save_backup_{int(time.time())}"
        ext = os.path.splitext(save_path)[1]
        shutil.copy2(save_path, BACKUP_DIR / f"{backup_name}{ext}")

        # Convert .dsv to .sav if needed, or just copy
        ensure_sav(save_path, str(DATA_DIR))

        # Rename to what EmulatorJS expects
        sav_files = list(DATA_DIR.glob("*.sav"))
        if sav_files:
            target = DATA_DIR / "game.sav"
            if sav_files[0] != target:
                sav_files[0].rename(target)
        print(f"Save loaded: {save_path}")
    else:
        if save_path:
            print(f"No save file found at: {save_path}")
        else:
            print(f"No save file configured (starting fresh)")


# =====================================================
# CLAUDE STATE TRACKING
#
# Tracks what Claude is doing and for how long.
# "thinking" = Claude is working, you should be playing
# "idle" = Claude is done, game pauses
#
# We also track:
#   - when Claude started thinking (for elapsed time)
#   - what tool Claude is using (Edit, Write, Bash, etc.)
#   - what file Claude is touching
#   - a running count of tool calls this session
# =====================================================

claude_state = "idle"
claude_started_at = 0        # timestamp when thinking began
claude_tool = ""             # current tool (Edit, Write, Bash, etc.)
claude_file = ""             # current file being worked on
claude_tool_count = 0        # how many tool calls this thinking session
claude_total_tools = 0       # total tool calls across all sessions
claude_total_thinking = 0.0  # total seconds spent thinking
state_lock = threading.Lock()


class BreakeonHandler(http.server.SimpleHTTPRequestHandler):
    """
    Custom HTTP handler. Routes:
    
    GET /          -> The emulator page (index.html)
    GET /rom       -> Your ROM file (binary, can be large ~128MB for DS)
    GET /save      -> Your save file (small, ~512KB typically)
    GET /api/state -> Current Claude state {"state": "thinking"|"idle"}
    POST /api/thinking -> Hook calls this when Claude starts
    POST /api/idle     -> Hook calls this when Claude finishes
    POST /api/save-notify -> Page calls this after saving (for backup)
    """

    def do_GET(self):
        global claude_state, claude_started_at, claude_tool, claude_file
        global claude_tool_count, claude_total_tools, claude_total_thinking

        if self.path == "/" or self.path == "/index.html":
            # Serve the emulator page
            self.serve_file(STATIC_DIR / "index.html", "text/html")

        elif self.path == "/rom":
            # Serve the ROM — find whatever game file is in data/
            rom_file = None
            for f in DATA_DIR.iterdir():
                if f.name.startswith("game") and f.suffix.lower() in CORE_MAP:
                    rom_file = f
                    break
            if rom_file and rom_file.exists():
                self.serve_file(rom_file, "application/octet-stream")
            else:
                self.send_error(404, "ROM not found. Check config.json games list")

        elif self.path == "/save":
            # Serve the save file
            sav_file = DATA_DIR / "game.sav"
            if sav_file.exists():
                self.serve_file(sav_file, "application/octet-stream")
            else:
                self.send_error(404, "No save file")

        elif self.path == "/api/state":
            # The emulator page polls this every 500ms
            # Returns Claude's state plus timing and activity info
            with state_lock:
                state = claude_state
                elapsed = 0
                if state == "thinking" and claude_started_at > 0:
                    elapsed = time.time() - claude_started_at
                self.send_json({
                    "state": state,
                    "elapsed": round(elapsed, 1),
                    "tool": claude_tool,
                    "file": claude_file,
                    "tool_count": claude_tool_count,
                    "total_tools": claude_total_tools,
                    "total_thinking": round(claude_total_thinking + elapsed, 1),
                    "timestamp": time.time(),
                })

        elif self.path == "/api/game-info":
            # Returns the active game and the full library
            config = load_config()
            game = get_active_game(config)
            games = config.get("games", [])
            active = config.get("active_game", 0)
            rom = game.get("rom_path", "")

            # Build a clean list for the UI
            game_list = []
            for i, g in enumerate(games):
                r = g.get("rom_path", "")
                game_list.append({
                    "index": i,
                    "name": resolve_name(g, config),
                    "core": get_core_for_rom(r),
                    "platform": PLATFORM_NAMES.get(get_core_for_rom(r), "Unknown"),
                    "has_save": bool(g.get("save_path")),
                })

            self.send_json({
                "name": resolve_name(game, config),
                "core": get_core_for_rom(rom),
                "active": active,
                "games": game_list,
            })

        else:
            # Try to serve static files (JS, CSS, etc.)
            file_path = STATIC_DIR / self.path.lstrip("/")
            if file_path.exists() and file_path.is_file():
                content_type = self.guess_type(str(file_path))
                self.serve_file(file_path, content_type)
            else:
                self.send_error(404)

    def do_POST(self):
        global claude_state, claude_started_at, claude_tool, claude_file
        global claude_tool_count, claude_total_tools, claude_total_thinking

        if self.path == "/api/thinking":
            # Claude started working — time to play!
            # Read the context the hook sent us
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len) if content_len > 0 else b""
            context = {}
            try:
                if body:
                    context = json.loads(body)
            except:
                pass

            with state_lock:
                if claude_state != "thinking":
                    claude_started_at = time.time()
                    claude_tool_count = 0
                claude_state = "thinking"
                claude_tool = context.get("tool", claude_tool) or ""
                claude_file = context.get("file", claude_file) or ""
                claude_tool_count += 1
                claude_total_tools += 1

            tool_info = f" [{context.get('tool', '')}]" if context.get('tool') else ""
            file_info = f" on {context.get('file', '')}" if context.get('file') else ""
            self.send_json({"ok": True, "state": "thinking"})
            print(f"[hook] Claude is thinking{tool_info}{file_info}")

        elif self.path == "/api/idle":
            # Claude finished — pause and save
            with state_lock:
                elapsed = 0
                tools_used = claude_tool_count
                if claude_state == "thinking" and claude_started_at > 0:
                    elapsed = time.time() - claude_started_at
                    claude_total_thinking += elapsed
                claude_state = "idle"
            self.send_json({"ok": True, "state": "idle"})
            print(f"[hook] Claude is idle — thought for {elapsed:.1f}s, {tools_used} tool calls")

        elif self.path == "/api/save-notify":
            # The browser saved — back up the save file
            self.backup_save()
            self.send_json({"ok": True})

        elif self.path.startswith("/api/switch-game"):
            # Switch to a different game from the library
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len) if content_len > 0 else b""
            try:
                req = json.loads(body) if body else {}
                game_index = int(req.get("index", 0))
            except:
                game_index = 0

            config = load_config()
            games = config.get("games", [])
            if 0 <= game_index < len(games):
                config["active_game"] = game_index
                save_config(config)
                # Re-setup data dir with new game
                setup_data_dir(config)
                game = games[game_index]
                self.send_json({
                    "ok": True,
                    "name": resolve_name(game, config),
                    "core": get_core_for_rom(game.get("rom_path", "")),
                    "message": "Reload the page to start the new game"
                })
                print(f"[server] Switched to: {resolve_name(game, config)}")
            else:
                self.send_json({"ok": False, "error": "Invalid game index"})

        else:
            self.send_error(404)

    def do_HEAD(self):
        """Handle HEAD requests (browser checks if save file exists)"""
        if self.path == "/save":
            sav_file = DATA_DIR / "game.sav"
            if sav_file.exists():
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", sav_file.stat().st_size)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
            else:
                self.send_error(404, "No save file")
        else:
            # Fall through to GET handler logic for other paths
            self.send_response(200)
            self.end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight requests from the browser"""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def serve_file(self, path, content_type):
        """Send a file back to the browser"""
        try:
            with open(path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(data))
            # Allow the page to access these files (CORS)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(500, str(e))

    def send_json(self, data):
        """Send a JSON response"""
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def backup_save(self):
        """Copy current save to backups/ with timestamp"""
        sav = DATA_DIR / "game.sav"
        if sav.exists():
            backup = BACKUP_DIR / f"game_{int(time.time())}.sav"
            shutil.copy2(sav, backup)
            # Keep only last 20 backups
            backups = sorted(BACKUP_DIR.glob("game_*.sav"))
            for old in backups[:-20]:
                old.unlink()

    def guess_type(self, path):
        """Map file extensions to content types"""
        ext = os.path.splitext(path)[1].lower()
        return {
            ".html": "text/html",
            ".js": "application/javascript",
            ".css": "text/css",
            ".json": "application/json",
            ".png": "image/png",
            ".ico": "image/x-icon",
        }.get(ext, "application/octet-stream")

    def log_message(self, format, *args):
        """Quieter logging — only show interesting stuff"""
        msg = format % args
        if "/api/state" not in msg:  # Don't spam the poll requests
            print(f"[server] {msg}")


def main():
    # Load config with helpful error messages
    try:
        config = load_config()
    except FileNotFoundError:
        print("ERROR: config.json not found!")
        print(f"  Expected at: {CONFIG_PATH}")
        print("  Create it with your game paths. See README.md for format.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: config.json has invalid JSON: {e}")
        print("  Common fixes:")
        print("    - Check for missing commas between items")
        print("    - Check for trailing commas (not allowed in JSON)")
        print("    - Make sure all strings use double quotes")
        sys.exit(1)

    # Validate config has games
    games = config.get("games", [])
    if not games:
        print("ERROR: No games in config.json!")
        print("  Add at least one game to the 'games' list. See README.md")
        sys.exit(1)

    port = config.get("port", 3000)

    print("=" * 50)
    print("  BREAKEON SERVER")
    print("=" * 50)

    game = get_active_game(config)
    print(f"\n  Active game: {resolve_name(game, config)}")
    print(f"  Library: {len(games)} game(s)")

    # Prepare ROM and save files
    setup_data_dir(config)

    print(f"\n  Starting server on http://localhost:{port}")
    print(f"  Open that URL in your browser to play!")
    print(f"  Press Ctrl+C to stop\n")

    try:
        server = http.server.HTTPServer(("127.0.0.1", port), BreakeonHandler)
    except OSError as e:
        if "Address already in use" in str(e) or "10048" in str(e):
            print(f"ERROR: Port {port} is already in use!")
            print(f"  Either close whatever is using port {port}, or")
            print(f"  change the port in config.json to something else (like 3001)")
            sys.exit(1)
        raise

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
