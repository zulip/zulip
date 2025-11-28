#!/usr/bin/env python3
"""
Generate emoji_codes.json without requiring npm packages.

This script creates a minimal emoji_codes.json file that contains:
- name_to_codepoint: mapping of emoji names to Unicode codepoints
- codepoint_to_name: mapping of Unicode codepoints to emoji names
- emoticon_conversions: mapping of text emoticons to emoji names
- names: list of all emoji names (for picker)
- emoji_catalog: categorized emoji (simplified)

Usage:
    python scripts/generate_emoji_codes.py
"""
import os
import sys

# Set up path to import from Zulip modules
ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ZULIP_PATH)

import orjson

from tools.setup.emoji.emoji_names import EMOJI_NAME_MAPS
from tools.setup.emoji.emoji_setup_utils import (
    EMOTICON_CONVERSIONS,
    emoji_names_for_picker,
    generate_codepoint_to_name_map,
    generate_name_to_codepoint_map,
)


def generate_minimal_emoji_catalog(emoji_name_maps: dict) -> dict:
    """
    Generate a minimal emoji catalog without requiring npm emoji-datasource.

    This groups all emoji under generic categories based on common patterns.
    It's sufficient for the backend to start; the frontend may not use this
    for the emoji picker.
    """
    # Default category mapping based on common emoji codepoint ranges
    emoji_catalog = {
        "Smileys & Emotion": [],
        "People & Body": [],
        "Animals & Nature": [],
        "Food & Drink": [],
        "Travel & Places": [],
        "Activities": [],
        "Objects": [],
        "Symbols": [],
        "Flags": [],
    }

    for code in emoji_name_maps.keys():
        # Simple heuristic: put all in one category for minimal implementation
        # This is sufficient for backend startup
        emoji_catalog["Smileys & Emotion"].append(code)

    return emoji_catalog


def main() -> None:
    print("Generating emoji_codes.json...")

    # Generate the required mappings using existing Zulip functions
    names = emoji_names_for_picker(EMOJI_NAME_MAPS)
    codepoint_to_name = generate_codepoint_to_name_map(EMOJI_NAME_MAPS)
    name_to_codepoint = generate_name_to_codepoint_map(EMOJI_NAME_MAPS)
    emoji_catalog = generate_minimal_emoji_catalog(EMOJI_NAME_MAPS)

    # Create output directory
    output_dir = os.path.join(ZULIP_PATH, "static", "generated", "emoji")
    os.makedirs(output_dir, exist_ok=True)

    # Write emoji_codes.json
    output_path = os.path.join(output_dir, "emoji_codes.json")
    emoji_data = {
        "names": names,
        "name_to_codepoint": name_to_codepoint,
        "codepoint_to_name": codepoint_to_name,
        "emoji_catalog": emoji_catalog,
        "emoticon_conversions": EMOTICON_CONVERSIONS,
    }

    with open(output_path, "wb") as f:
        f.write(orjson.dumps(emoji_data))

    file_size = os.path.getsize(output_path)
    print(f"Generated {output_path}")
    print(f"File size: {file_size:,} bytes")
    print(f"Emoji names: {len(names)}")
    print(f"Name to codepoint mappings: {len(name_to_codepoint)}")
    print(f"Codepoint to name mappings: {len(codepoint_to_name)}")


if __name__ == "__main__":
    main()
