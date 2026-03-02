"""
auto_name.py — Generate friendly display names from ROM files.

Three adjustments:
  1. Strip region/dump tags: (USA), (Europe), [!], [f1], (Rev 1), etc.
  2. Strip "Version", "Edition" suffixes (preserving trailing numbers)
  3. Fix common unicode: Pokemon → Pokémon

Eight patterns (applied in order):
  1. "Series: Subtitle" → take subtitle
  2. Drop leading articles ("The ", "A ", "An ") from result
  3. If result is too short/generic, restore series name
  4. Abbreviate known series when compact_names is on (DQ9, FF4)
  5. Multi-level chains: split again, keep deepest distinctive part
  6. Strip connector phrases ("and the", "& the")
  7. Remakes: if both port name and original title present, keep original
  8. Keep platform suffixes when needed for disambiguation
"""

import struct
import re
import os

# ─── ROM HEADER READERS ─────────────────────────────────────────────

def read_nds_title(rom_path: str) -> str:
    """Read the English banner title from an NDS ROM (UTF-16, multi-line)."""
    try:
        with open(rom_path, "rb") as f:
            f.seek(0x68)
            banner_offset = struct.unpack("<I", f.read(4))[0]
            if banner_offset == 0:
                return ""
            f.seek(banner_offset + 0x340)
            raw = f.read(256)
            title = raw.decode("utf-16-le", errors="ignore").split("\x00")[0]
            return " ".join(title.splitlines()).strip()
    except (OSError, struct.error):
        return ""


def read_nds_header_name(rom_path: str) -> str:
    """Read the short 12-byte ASCII name from NDS header offset 0x000."""
    try:
        with open(rom_path, "rb") as f:
            raw = f.read(12)
            return raw.decode("ascii", errors="ignore").strip("\x00 ")
    except OSError:
        return ""


def read_nds_game_code(rom_path: str) -> str:
    """Read the 4-byte game code from NDS header offset 0x00C."""
    try:
        with open(rom_path, "rb") as f:
            f.seek(0x0C)
            return f.read(4).decode("ascii", errors="ignore").strip("\x00")
    except OSError:
        return ""


def read_gba_title(rom_path: str) -> str:
    """Read the 12-byte ASCII title from GBA header offset 0xA0."""
    try:
        with open(rom_path, "rb") as f:
            f.seek(0xA0)
            raw = f.read(12)
            return raw.decode("ascii", errors="ignore").strip("\x00 ")
    except OSError:
        return ""


def read_gba_game_code(rom_path: str) -> str:
    """Read the 4-byte game code from GBA header offset 0xAC."""
    try:
        with open(rom_path, "rb") as f:
            f.seek(0xAC)
            return f.read(4).decode("ascii", errors="ignore").strip("\x00")
    except OSError:
        return ""


def read_gb_title(rom_path: str) -> str:
    """Read the 11-16 byte ASCII title from GB/GBC header offset 0x134."""
    try:
        with open(rom_path, "rb") as f:
            f.seek(0x134)
            raw = f.read(16)
            return raw.decode("ascii", errors="ignore").strip("\x00 ")
    except OSError:
        return ""


def read_n64_title(rom_path: str) -> str:
    """Read the 20-byte ASCII title from N64 header offset 0x20."""
    try:
        with open(rom_path, "rb") as f:
            f.seek(0x20)
            raw = f.read(20)
            return raw.decode("ascii", errors="ignore").strip("\x00 ")
    except OSError:
        return ""


def read_snes_title(rom_path: str) -> str:
    """Read the 21-byte ASCII title from SNES internal header.
    Tries LoROM (0x7FC0) then HiROM (0xFFC0)."""
    try:
        with open(rom_path, "rb") as f:
            for offset in (0x7FC0, 0xFFC0):
                f.seek(offset)
                raw = f.read(21)
                text = raw.decode("ascii", errors="ignore").strip("\x00 ")
                if text and all(c.isprintable() for c in text):
                    return text
        return ""
    except OSError:
        return ""


def read_nes_title(rom_path: str) -> str:
    """NES ROMs (iNES format) have no internal title. Return empty."""
    return ""


# ─── HEADER READER DISPATCH ─────────────────────────────────────────

PLATFORM_READERS = {
    ".nds": read_nds_title,
    ".gba": read_gba_title,
    ".gb":  read_gb_title,
    ".gbc": read_gb_title,
    ".n64": read_n64_title,
    ".z64": read_n64_title,
    ".v64": read_n64_title,
    ".sfc": read_snes_title,
    ".smc": read_snes_title,
    ".nes": read_nes_title,
    ".nez": read_nes_title,
    ".fds": read_nes_title,
}


def read_rom_title(rom_path: str) -> str:
    """Read the internal title from any supported ROM."""
    ext = os.path.splitext(rom_path)[1].lower()
    reader = PLATFORM_READERS.get(ext)
    if reader:
        return reader(rom_path)
    return ""


# ─── ADJUSTMENT 1: STRIP REGION / DUMP TAGS ─────────────────────────

def strip_tags(name: str) -> str:
    """Remove (USA), (Europe), (En,Fr), [!], [f1], (Rev 1), etc."""
    name = re.sub(r"\s*\([^)]*\)", "", name)
    name = re.sub(r"\s*\[[^\]]*\]", "", name)
    return name.strip()


# ─── ADJUSTMENT 2: STRIP "VERSION" / "EDITION" ──────────────────────

def strip_version(name: str) -> str:
    """Remove 'Version' or 'Edition' but preserve trailing numbers.
    'Pokémon White Version 2' → 'Pokémon White 2'
    'Pokémon Yellow Version: Special Pikachu Edition' → 'Pokémon Yellow'
    'Pokémon Emerald Version' → 'Pokémon Emerald'
    """
    # If "Version" is followed by a colon, strip everything from Version onward
    # (the colon introduces a subtitle that is itself an edition label)
    name = re.sub(r"\s+Version\s*:.*$", "", name, flags=re.IGNORECASE)
    # Otherwise strip just the word "Version", keeping anything after it (like "2")
    name = re.sub(r"\s+Version\b", "", name, flags=re.IGNORECASE)
    # Same for Edition
    name = re.sub(r"\s+Edition\b", "", name, flags=re.IGNORECASE)
    return name.strip()


# ─── ADJUSTMENT 3: UNICODE FIXES ────────────────────────────────────

UNICODE_FIXES = {
    "Pokemon": "Pokémon",
    "POKEMON": "Pokémon",
}

def fix_unicode(name: str) -> str:
    """Fix common ASCII→Unicode issues."""
    for plain, fancy in UNICODE_FIXES.items():
        name = name.replace(plain, fancy)
    return name


# ─── PATTERN 1 + 6: SPLIT ON SEPARATOR ──────────────────────────────

def split_on_separator(name: str) -> tuple[str, str]:
    """Split 'Series: Subtitle' or 'Series - Subtitle' into (series, subtitle).
    Also handles connector phrases: 'X and the Y' → ('X', 'Y').
    Returns (series, subtitle) or (name, '') if no separator found."""
    if ": " in name:
        parts = name.split(": ", 1)
        return parts[0].strip(), parts[1].strip()
    if " - " in name:
        parts = name.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    # Pattern 6: connector phrases act as separators
    for conn in (" and the ", " & the "):
        if conn in name.lower():
            idx = name.lower().index(conn)
            return name[:idx].strip(), name[idx + len(conn):].strip()
    return name, ""


# ─── PATTERN 2: DROP LEADING ARTICLES ────────────────────────────────

def strip_leading_article(name: str) -> str:
    """Remove leading 'The ', 'A ', 'An ' from a name."""
    for article in ("The ", "A ", "An "):
        if name.startswith(article):
            return name[len(article):]
    return name


# ─── PATTERN 3: GENERICNESS CHECK ───────────────────────────────────

GENERIC_WORDS = {
    "rush", "battle", "zero", "party", "world", "quest",
    "wars", "force", "advance", "fusion", "touch", "go",
    "dash", "land", "island", "arena", "attack", "star",
    "strike", "heroes", "legends", "saga", "origins",
    "revolution", "rising", "returns", "chronicles",
}

def is_too_generic(name: str) -> bool:
    """Check if a name is too short or generic to stand alone."""
    words = name.lower().split()
    if len(words) <= 1 and words[0] in GENERIC_WORDS:
        return True
    return False


# ─── PATTERN 4: COMPACT NAME ABBREVIATIONS ──────────────────────────

COMPACT_SERIES = {
    "Final Fantasy":   "FF",
    "Dragon Quest":    "DQ",
    "Mega Man":        "MM",
}

def compact_numbered(name: str) -> str:
    """When compact_names is on, abbreviate known series with roman/arabic numbers.
    'Final Fantasy IV' → 'FF4', 'Dragon Quest IX: Subtitle' → 'DQ9'
    Only abbreviates when a number is present in the series portion.
    """
    for series, abbr in COMPACT_SERIES.items():
        if not name.startswith(series):
            continue
        remainder = name[len(series):].strip()

        # If there's a colon, check series portion for a number
        # "Dragon Quest IV: Chapters of the Chosen" → "DQ4"
        if ": " in remainder:
            before_colon = remainder.split(": ", 1)[0].strip()
            roman = roman_to_int(before_colon) if before_colon else 0
            if roman > 0:
                return f"{abbr}{roman}"
            m = re.match(r"^(\d+)$", before_colon)
            if m:
                return f"{abbr}{m.group(1)}"

        # No colon — check for number directly after series name
        roman = roman_to_int(remainder.split()[0]) if remainder else 0
        if roman > 0:
            after_numeral = remainder.split(None, 1)[1] if len(remainder.split()) > 1 else ""
            if not after_numeral:
                return f"{abbr}{roman}"
            else:
                return f"{abbr}{roman} {after_numeral}"
        m = re.match(r"^(\d+)\b(.*)$", remainder)
        if m:
            num = m.group(1)
            rest = m.group(2).strip()
            if not rest:
                return f"{abbr}{num}"
            else:
                return f"{abbr}{num} {rest}"
        # No number found — don't abbreviate (Mega Man Zero stays Mega Man Zero)
    return name


ROMAN_MAP = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
    "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12,
    "XIII": 13, "XIV": 14, "XV": 15, "XVI": 16,
}

def roman_to_int(s: str) -> int:
    return ROMAN_MAP.get(s.upper(), 0)


# ─── PATTERN 5: MULTI-LEVEL CHAINS ──────────────────────────────────

def unwrap_chains(name: str) -> str:
    """For deeply nested titles, split again and keep the deepest part."""
    series, subtitle = split_on_separator(name)
    if subtitle:
        inner_series, inner_sub = split_on_separator(subtitle)
        if inner_sub:
            if re.search(r"\b(19|20)\d{2}\b", inner_series):
                return inner_series
            return inner_sub

        if re.search(r"\b(19|20)\d{2}\b", series) and len(series) > 25:
            cleaned = re.sub(
                r"^(Yu-Gi-Oh!\s*\w*'?s?\s*|Digimon\s*\w*\s*)",
                "", series, flags=re.IGNORECASE
            ).strip()
            if cleaned and len(cleaned) > 5:
                return cleaned

        return subtitle
    return name


# ─── PATTERN 10+11: SONIC GENESIS TITLES ────────────────────────────

def handle_sonic_genesis(name: str) -> str:
    """Handle Sonic's original trilogy and lock-on combos.

    Pattern 10: "Sonic the Hedgehog [N]" → "Sonic [N]", bare → "Sonic 1"
    Pattern 11: "Sonic & Knuckles + Sonic the Hedgehog [N]" → "Sonic [N] & Knuckles"
    """
    # Pattern 11: lock-on detection — look for + separator
    if "+" in name:
        parts = [p.strip() for p in name.split("+")]
        sk_part = None
        sonic_part = None
        for p in parts:
            if re.match(r"sonic\s*&\s*knuckles", p, re.IGNORECASE):
                sk_part = p
            elif re.search(r"sonic", p, re.IGNORECASE):
                sonic_part = p
        if sk_part and sonic_part:
            # Extract number from the sonic part
            m = re.search(r"(\d+)", sonic_part)
            num = m.group(1) if m else None
            if num:
                return f"Sonic {num} & Knuckles"

    # Pattern 10: "Sonic the Hedgehog [N]" → "Sonic [N]" or "Sonic 1"
    m = re.match(r"Sonic\s+the\s+Hedgehog\s*(\d*)", name, re.IGNORECASE)
    if m:
        num = m.group(1).strip()
        return f"Sonic {num}" if num else "Sonic 1"

    return ""  # not a genesis Sonic title




REMAKE_LABELS = [
    "Super Mario Advance",
    "Classic NES Series",
    "Famicom Mini",
    "NES Classics",
]

def handle_remakes(name: str) -> str:
    """If the title contains both a port label and an original game name,
    prefer the original."""
    series, subtitle = split_on_separator(name)
    if subtitle:
        for label in REMAKE_LABELS:
            if series.startswith(label):
                return subtitle
    return name


# ─── TITLE CASE ──────────────────────────────────────────────────────

LOWERCASE_WORDS = {"of", "the", "and", "in", "at", "to", "for", "a", "an", "on"}

def smart_title_case(name: str) -> str:
    """Title-case a name, keeping small words lowercase (except first word)."""
    words = name.split()
    result = []
    for i, word in enumerate(words):
        if len(word) >= 2 and word != word.lower() and word != word.upper():
            result.append(word)
        elif word.upper() == word and len(word) <= 3:
            result.append(word)
        elif i == 0:
            result.append(word.capitalize())
        elif word.lower() in LOWERCASE_WORDS:
            result.append(word.lower())
        else:
            result.append(word.capitalize())
    return " ".join(result)


def fix_shouting(name: str) -> str:
    """Convert ALL-CAPS words to title case, preserving mixed-case and short acronyms."""
    words = name.split()
    needs_fix = False
    for w in words:
        if len(w) > 3 and w == w.upper() and w.isalpha():
            needs_fix = True
            break
    if needs_fix:
        return smart_title_case(name)
    return name


# ─── MAIN PIPELINE ──────────────────────────────────────────────────

def friendly_name(raw_title: str, compact: bool = False) -> str:
    """Apply the full pipeline: 3 adjustments + 8 patterns.
    
    Args:
        raw_title: Raw ROM title or filename
        compact: If True, abbreviate known series (DQ9, FF4, Sonic → short)
    """
    name = raw_title.strip()
    if not name:
        return ""

    # ── Adjustment 1: Strip region/dump tags
    name = strip_tags(name)

    # ── Adjustment 2: Strip "Version" / "Edition"
    name = strip_version(name)

    # ── Adjustment 3: Unicode fixes
    name = fix_unicode(name)

    # ── Pattern 10+11: Sonic Genesis titles (before anything else)
    sonic_result = handle_sonic_genesis(name)
    if sonic_result:
        return sonic_result

    # ── Pattern 7: Handle remakes first (before generic split)
    name = handle_remakes(name)

    # ── Pattern 4: Compact abbreviations (when enabled, before split)
    #    Must run on the full name so "Dragon Quest IV: Subtitle" → "DQ4"
    if compact:
        compacted = compact_numbered(name)
        if compacted != name:
            return fix_shouting(compacted.strip())

    # ── Pattern 5: Unwrap multi-level chains (does Pattern 1 recursively)
    result = unwrap_chains(name)

    # If unwrap didn't find multi-level, do a single Pattern 1 split
    if result == name:
        series, subtitle = split_on_separator(name)
        if subtitle:
            # ── Pattern 3: Check if result is too generic
            if is_too_generic(subtitle) or is_too_generic(strip_leading_article(subtitle)):
                result = name  # keep full name
            else:
                result = subtitle
        else:
            result = name  # no separator, keep as-is

    # ── Pattern 2: Strip leading article (always, regardless of path)
    result = strip_leading_article(result)

    # ── Final: Fix ALL-CAPS words from ROM headers (GBA/GB)
    result = fix_shouting(result)

    return result.strip()


# ─── PUBLIC API ──────────────────────────────────────────────────────

def auto_name(rom_path: str, compact: bool = False) -> str:
    """Generate a friendly display name from a ROM file.
    
    Priority:
      1. NDS banner title (best quality — full unicode, multi-language)
      2. ROM header short name (GBA/GB/N64/SNES — uppercase, truncated)
      3. Filename fallback (strip extension + apply pipeline)
    """
    title = read_rom_title(rom_path)
    
    if title:
        return friendly_name(title, compact=compact)

    basename = os.path.splitext(os.path.basename(rom_path))[0]
    return friendly_name(basename, compact=compact)


def auto_name_or_override(rom_path: str, user_name: str = "", compact: bool = False) -> str:
    """Return user's name if provided, otherwise auto-generate."""
    if user_name and user_name.strip():
        return user_name.strip()
    return auto_name(rom_path, compact=compact)


# ─── CLI TEST ────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        # Sonic Genesis + lock-on
        ("Sonic the Hedgehog (USA)", "Sonic 1"),
        ("Sonic the Hedgehog 2 (USA)", "Sonic 2"),
        ("Sonic the Hedgehog 3 (USA)", "Sonic 3"),
        ("Sonic & Knuckles (USA)", "Sonic & Knuckles"),
        ("Sonic & Knuckles + Sonic the Hedgehog 3 (USA)", "Sonic 3 & Knuckles"),
        ("Sonic & Knuckles + Sonic the Hedgehog 2 (USA)", "Sonic 2 & Knuckles"),

        # Pokémon — mainline keeps "Pokémon [X]"
        ("Pokemon Platinum Version (USA)", "Pokémon Platinum"),
        ("Pokemon HeartGold Version (USA)", "Pokémon HeartGold"),
        ("Pokemon Yellow Version: Special Pikachu Edition (USA)", "Pokémon Yellow"),
        ("Pokemon Mystery Dungeon: Explorers of Sky (USA)", "Explorers of Sky"),
        ("Pokemon Emerald Version (USA)", "Pokémon Emerald"),
        ("Pokemon White Version 2 (USA)", "Pokémon White 2"),
        ("Pokemon Black Version (USA)", "Pokémon Black"),

        # Zelda
        ("The Legend of Zelda: Phantom Hourglass (USA)", "Phantom Hourglass"),
        ("The Legend of Zelda: The Minish Cap (USA)", "Minish Cap"),
        ("The Legend of Zelda: Spirit Tracks (USA)", "Spirit Tracks"),
        ("The Legend of Zelda: A Link to the Past (USA)", "Link to the Past"),

        # Castlevania
        ("Castlevania: Dawn of Sorrow (USA)", "Dawn of Sorrow"),
        ("Castlevania: Portrait of Ruin (USA)", "Portrait of Ruin"),
        ("Castlevania: Aria of Sorrow (USA)", "Aria of Sorrow"),

        # Fire Emblem
        ("Fire Emblem: The Sacred Stones (USA)", "Sacred Stones"),
        ("Fire Emblem: Shadow Dragon (USA)", "Shadow Dragon"),

        # Mario & Luigi
        ("Mario & Luigi: Bowser's Inside Story (USA)", "Bowser's Inside Story"),
        ("Mario & Luigi: Superstar Saga (USA)", "Superstar Saga"),

        # Phoenix Wright — multi-level
        ("Phoenix Wright: Ace Attorney - Justice for All (USA)", "Justice for All"),
        ("Phoenix Wright: Ace Attorney - Trials and Tribulations (USA)", "Trials and Tribulations"),

        # Yu-Gi-Oh — deep chain
        ("Yu-Gi-Oh! 5D's World Championship 2009: Stardust Accelerator (USA)", "World Championship 2009"),

        # Professor Layton — connector phrase
        ("Professor Layton and the Curious Village (USA)", "Curious Village"),
        ("Professor Layton and the Unwound Future (USA)", "Unwound Future"),

        # Kingdom Hearts
        ("Kingdom Hearts: Chain of Memories (USA)", "Chain of Memories"),
        ("Kingdom Hearts 358/2 Days (USA)", "Kingdom Hearts 358/2 Days"),

        # Sonic — generic check keeps series name
        ("Sonic Rush (USA)", "Sonic Rush"),
        ("Sonic Battle (USA)", "Sonic Battle"),

        # Kirby — connector phrase
        ("Kirby & the Amazing Mirror (USA)", "Amazing Mirror"),

        # Mega Man
        ("Mega Man Battle Network 3 (USA)", "Mega Man Battle Network 3"),
        ("Mega Man Zero (USA)", "Mega Man Zero"),
        ("Mega Man ZX (USA)", "Mega Man ZX"),

        # Advance Wars
        ("Advance Wars: Dual Strike (USA)", "Dual Strike"),
        ("Advance Wars: Days of Ruin (USA)", "Days of Ruin"),

        # Metroid
        ("Metroid: Zero Mission (USA)", "Zero Mission"),

        # Remakes
        ("Super Mario Advance 4: Super Mario Bros. 3 (USA)", "Super Mario Bros. 3"),
        ("Classic NES Series: The Legend of Zelda (USA)", "Legend of Zelda"),

        # No separator — keep full name
        ("Sonic Rush Adventure (USA)", "Sonic Rush Adventure"),
        ("New Super Mario Bros. (USA)", "New Super Mario Bros."),
        ("Mario Kart DS (USA)", "Mario Kart DS"),
        ("Advance Wars (USA)", "Advance Wars"),

        # GBA/GB uppercase headers
        ("POKEMON EMER", "Pokémon Emer"),
        ("ZELDA", "Zelda"),
        ("MEGAMAN ZERO", "Megaman Zero"),

        # Dragon Quest
        ("Dragon Quest IV: Chapters of the Chosen (USA)", "Chapters of the Chosen"),

        # NDS banner
        ("Pokémon Platinum Version", "Pokémon Platinum"),
    ]

    # ── Standard mode tests
    print("AUTO-NAMER TEST RESULTS (standard)")
    print("=" * 70)
    passed = failed = 0
    for raw, expected in test_cases:
        result = friendly_name(raw)
        ok = result == expected
        passed += ok
        failed += (not ok)
        status = "✓" if ok else "✗"
        print(f"  {status} {raw[:45]:45s}")
        if not ok:
            print(f"      expected: {expected}")
            print(f"      got:      {result}")
    print("=" * 70)
    print(f"  {passed} passed, {failed} failed out of {len(test_cases)}")

    # ── Compact mode tests
    compact_cases = [
        ("Final Fantasy IV (USA)", "FF4"),
        ("Final Fantasy VI Advance (USA)", "FF6 Advance"),
        ("Dragon Quest IX: Sentinels of the Starry Skies (USA)", "DQ9"),
        ("Dragon Quest IV: Chapters of the Chosen (USA)", "DQ4"),
        ("Sonic Rush (USA)", "Sonic Rush"),
        ("Sonic Rush Adventure (USA)", "Sonic Rush Adventure"),
        ("Mega Man Zero (USA)", "Mega Man Zero"),
        ("Pokemon Platinum Version (USA)", "Pokémon Platinum"),
    ]

    print("\nCOMPACT MODE TEST RESULTS")
    print("=" * 70)
    cp = cf = 0
    for raw, expected in compact_cases:
        result = friendly_name(raw, compact=True)
        ok = result == expected
        cp += ok
        cf += (not ok)
        status = "✓" if ok else "✗"
        print(f"  {status} {raw[:45]:45s}")
        if not ok:
            print(f"      expected: {expected}")
            print(f"      got:      {result}")
    print("=" * 70)
    print(f"  {cp} passed, {cf} failed out of {len(compact_cases)}")
