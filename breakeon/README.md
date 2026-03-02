# Breakeon

Play games while Claude Code thinks. Auto-pauses when Claude finishes. Auto-resumes when you send the next prompt.

Built because waiting for an AI to think is a weird kind of anxiety — you can't start anything real because it might finish in 10 seconds, but it might also take 2 minutes. So you just... sit there. Refreshing. Watching a cursor blink. Breakeon gives that dead time a purpose. You play. It handles the rest.

Uses [EmulatorJS](https://emulatorjs.org/) in your browser. Supports DS, GBA, Game Boy Color, Game Boy, NES, Famicom Disk System, SNES, and N64. Your ROMs never leave your machine.

> **v0.5.0-alpha** — Auto-naming, compact mode, multi-platform. Not yet battle-tested with live Claude Code hooks. Save backups are automatic so your progress is safe regardless.

## Install

### 1. Unzip

Put the `breakeon/` folder anywhere. Only needs Python 3.9+.

### 2. Add your ROMs to config.json

```json
{
    "games": [
        {
            "rom_path": "C:/Users/YOU/roms/Pokemon Platinum Version (USA).nds",
            "save_path": "C:/Users/YOU/roms/Pokemon Platinum.dsv"
        },
        {
            "rom_path": "C:/Users/YOU/roms/Legend of Zelda, The - The Minish Cap (USA).gba"
        },
        {
            "rom_path": "C:/Users/YOU/roms/Castlevania - Dawn of Sorrow (USA).nds"
        }
    ],
    "active_game": 0,
    "port": 3000
}
```

No `name` field needed. Breakeon reads the ROM header or cleans up the filename automatically:

| Your filename | Breakeon shows |
|---|---|
| `Pokemon Platinum Version (USA).nds` | **Pokémon Platinum** |
| `Pokemon White Version 2 (USA).nds` | **Pokémon White 2** |
| `Legend of Zelda, The - The Minish Cap (USA).gba` | **Minish Cap** |
| `Castlevania - Dawn of Sorrow (USA).nds` | **Dawn of Sorrow** |
| `Phoenix Wright - Ace Attorney - Justice for All (USA).nds` | **Justice for All** |
| `Fire Emblem - The Sacred Stones (USA).gba` | **Sacred Stones** |
| `Professor Layton and the Curious Village (USA).nds` | **Curious Village** |
| `Super Mario Advance 4 - Super Mario Bros. 3 (USA).gba` | **Super Mario Bros. 3** |
| `Final Fantasy IV (USA).gba` | **Final Fantasy IV** |

Don't like what it picks? Override per-game:

```json
{
    "name": "My Platinum Nuzlocke",
    "rom_path": "C:/Users/YOU/roms/Pokemon Platinum Version (USA).nds"
}
```

### Config reference

**Per-game fields:**
- **rom_path** (required) — full path to ROM
- **save_path** (optional) — full path to save file, omit to start fresh
- **name** (optional) — override the auto-generated display name

**Global settings:**
- **active_game** — which game loads first (0 = first in list)
- **port** — server port (default 3000)
- **compact_names** — abbreviate known series: `"compact_names": true` turns Dragon Quest IV into DQ4, Final Fantasy VI into FF6

**Supported formats:** `.nds` `.gba` `.gbc` `.gb` `.nes` `.nez` `.fds` `.sfc` `.smc` `.n64` `.z64` `.v64`

DeSmuME `.dsv` saves are auto-converted. Originals always backed up first.

### 3. Start the server

**Windows:** Double-click `start.bat`

**Mac/Linux:**
```
chmod +x start.sh
./start.sh
```

Or: `python server.py` / `python3 server.py`

Browser opens to `localhost:3000`.

### 4. Connect Claude Code hooks

Add to `~/.claude/settings.json` (global) or `.claude/settings.json` (per-project):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"/path/to/breakeon/hooks/on_thinking.py\"",
            "timeout": 5
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"/path/to/breakeon/hooks/on_thinking.py\"",
            "timeout": 5
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"/path/to/breakeon/hooks/on_idle.py\"",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

Replace `/path/to/breakeon/` with your actual path. Use `python3` on Mac/Linux.

- **UserPromptSubmit** — you hit enter → game resumes
- **PostToolUse** — Claude uses a tool → status bar updates
- **Stop** — Claude finishes → game saves and pauses

### 5. Play

Send Claude a prompt. Game unpauses. Claude finishes. Game saves and pauses. Click the game title to switch games mid-session.

## How it works

```
You type a prompt
        │
        ▼
UserPromptSubmit fires ──→ POST localhost:3000/api/thinking
        │                                │
        │                                ▼
        │                   Server state → "thinking"
        │                                │
        │                                ▼
        │                   Browser polls → game RESUMES 🎮
        │
        ▼
Claude works (edits, runs, reads...)
        │
        ├──→ PostToolUse fires ──→ Status bar updates
        │    (each tool call)      "Editing · src/app.py"
        │
        ▼
Claude finishes
        │
        ▼
Stop fires ──→ POST localhost:3000/api/idle
                               │
                               ▼
                  Save state + flush in-game save
                               │
                               ▼
                  Game PAUSED 💾
```

## Auto-naming

Three adjustments strip noise (region tags, "Version"/"Edition", unicode fixes). Eight patterns handle the rest:

1. **Separator split** — `Series: Subtitle` or `Series - Subtitle` → take right side
2. **Article drop** — leading "The", "A", "An" removed
3. **Genericness check** — if result is too vague ("Rush", "Battle"), keep series name
4. **Compact abbreviation** — when enabled, DQ4/FF6 style (config: `compact_names`)
5. **Chain unwrap** — three-deep titles keep the most distinctive part
6. **Connector split** — "and the" / "& the" treated as separators
7. **Remake detection** — port labels stripped, original title kept
8. **Platform suffix** — kept when it disambiguates (Mario Kart DS)

For NDS ROMs, reads the banner title (full Unicode). For GBA/GB, reads the header and fixes ALL-CAPS. Falls back to filename cleanup.

## Features

- **Auto-naming** — just add ROM paths
- **Compact mode** — DQ4, FF6 style abbreviations (opt-in)
- **Game library** — multiple games, switch from top bar
- **Auto-detect platform** — .nds → DS, .gba → GBA, etc.
- **Auto-save on pause** — save states + in-game saves
- **Status bar** — Claude's current tool, thinking time, tool count
- **DeSmuME support** — .dsv → .sav auto-conversion
- **Save backups** — timestamped, keeps last 20
- **Cross-platform** — Windows, Mac, Linux

## File structure

```
breakeon/
├── config.json            ← Your game library
├── start.bat              ← Double-click to start (Windows)
├── start.sh               ← Run to start (Mac/Linux)
├── server.py              ← Local server + hook handler
├── static/
│   └── index.html         ← Emulator page
├── hooks/
│   ├── on_thinking.py     ← Hook: resume + update status
│   └── on_idle.py         ← Hook: pause + save
├── utils/
│   ├── auto_name.py       ← ROM → display name pipeline
│   └── dsv_convert.py     ← .dsv → .sav converter
├── docs/
│   └── name-patterns.md   ← Naming research (15 franchises)
├── data/                  ← [auto] Working ROM/save copies
└── backups/               ← [auto] Save backups
```

## Known issues (v0.5.0-alpha)

- **Not tested with live Claude Code hooks.** Format matches docs but edge cases likely.
- **EmulatorJS API not battle-tested.** Save/load/pause may vary across versions.
- **DS emulation is heavy in-browser.** GBA and GB run smoother.
- **Game switching reloads the page.** In-game saves persist, save states don't.
- **No .sav → .dsv reverse conversion.** One-way for now.

## Error messages

- **"ROM not found"** — check file path in config.json
- **"ROM seems too small"** — possibly corrupted
- **"Port already in use"** — change `port` in config.json
- **"config.json has invalid JSON"** — missing or trailing comma

## Notes

- ROMs served on `127.0.0.1` only. Nothing hits the internet except EmulatorJS CDN.
- Server ignores hook calls if browser isn't open.
- Manual SAVE/PAUSE buttons work without hooks.
- Hooks find config.json relative to their own location.

## Why "Breakeon"

It's the break you take between prompts. It's an Eeveelution that doesn't exist. It's what happens when you tell an AI "I get anxious when you think" and the AI says "what if I babysat a game for you." The name was the human's idea. The auto-naming system was a joint research project that got out of hand in the best way.
