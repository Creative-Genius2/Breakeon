"""
dsv_convert.py - Strip DeSmuME's footer from .dsv save files

DeSmuME appends a small footer to its save files:
- The last 122 bytes contain metadata (save type, size info, etc.)
- Everything before that is the raw save data that any emulator can read

So we literally just chop off the tail. That's it. That's the whole "conversion."

Some .dsv files have a footer marker we can detect:
The string "|<--Snip" appears at the start of the footer.
If we find it, we cut there. If not, we just trim 122 bytes as a safe default.
"""

import os
import shutil


# DeSmuME's footer marker - this string appears right where the junk starts
DSV_FOOTER_MARKER = b"|<--Snip"
DSV_FOOTER_SIZE = 122


def convert_dsv_to_sav(dsv_path: str, sav_path: str) -> bool:
    """
    Takes a DeSmuME .dsv file, strips the footer, writes a clean .sav

    Think of it like this:
    Your .dsv file = [actual save data][DeSmuME's sticky note about the file]
    We're just peeling off the sticky note.

    Returns True if conversion worked, False if something went wrong.
    """
    if not os.path.exists(dsv_path):
        print(f"Save file not found: {dsv_path}")
        return False

    with open(dsv_path, "rb") as f:
        data = f.read()

    # Look for DeSmuME's marker in the last ~200 bytes
    # (We search a bit extra in case the footer is slightly different)
    search_region = data[-200:]
    marker_pos = search_region.find(DSV_FOOTER_MARKER)

    if marker_pos != -1:
        # Found the marker! Cut everything from there onward
        cut_point = len(data) - 200 + marker_pos
        clean_data = data[:cut_point]
        print(f"Found DeSmuME footer marker at byte {cut_point}, stripping it")
    else:
        # No marker found — just trim the standard 122 bytes
        # This is safe because the footer is always at the end
        clean_data = data[:-DSV_FOOTER_SIZE]
        print(f"No footer marker found, trimming last {DSV_FOOTER_SIZE} bytes")

    with open(sav_path, "wb") as f:
        f.write(clean_data)

    print(f"Converted: {dsv_path} -> {sav_path}")
    print(f"  Original size: {len(data)} bytes")
    print(f"  Clean size:    {len(clean_data)} bytes")
    return True


def is_dsv_file(path: str) -> bool:
    """Check if a file is a DeSmuME save (vs already a raw .sav)"""
    return path.lower().endswith(".dsv")


def ensure_sav(save_path: str, output_dir: str) -> str:
    """
    Given any save file path, make sure we have a .sav version.
    - If it's already .sav, just copy it
    - If it's .dsv, convert it
    Returns the path to the .sav file in output_dir
    """
    filename = os.path.basename(save_path)
    name_no_ext = os.path.splitext(filename)[0]
    sav_dest = os.path.join(output_dir, f"{name_no_ext}.sav")

    if is_dsv_file(save_path):
        convert_dsv_to_sav(save_path, sav_dest)
    else:
        shutil.copy2(save_path, sav_dest)
        print(f"Copied save file: {save_path} -> {sav_dest}")

    return sav_dest


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python dsv_convert.py <path_to.dsv> [output.sav]")
        sys.exit(1)

    dsv = sys.argv[1]
    sav = sys.argv[2] if len(sys.argv) > 2 else dsv.replace(".dsv", ".sav")
    convert_dsv_to_sav(dsv, sav)
