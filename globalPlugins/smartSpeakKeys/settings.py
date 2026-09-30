# -*- coding: UTF-8 -*-
"""
Settings manager for Smart Speak Keys Filter addon.
Handles saving and loading of suppressed keys configuration.
"""

import json
import os

# Default keys to suppress (arrow keys + common navigation)
# These are the mainKeyName values from NVDA's keyboard handler
DEFAULT_SUPPRESSED_KEYS = [
    "upArrow",
    "downArrow",
    "leftArrow",
    "rightArrow",
    "pageUp",
    "pageDown",
    "home",
    "end",
    "tab",
    "escape",
    "f1", "f2", "f3", "f4", "f5", "f6",
    "f7", "f8", "f9", "f10", "f11", "f12",
]

# Path to save user settings (inside addon folder)
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "user_settings.json")


def load_settings():
    """
    Load settings from file.
    Returns a dict with:
      - suppressed_keys: list of mainKeyName strings to suppress
      - suppress_nvda_commands: bool, whether to suppress NVDA+key combos
      - filter_enabled: bool, master on/off for the filter
    """
    defaults = {
        "suppressed_keys": DEFAULT_SUPPRESSED_KEYS,
        "suppress_nvda_commands": True,
        "filter_enabled": True,
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                # Merge with defaults in case new keys were added
                defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_settings(settings_dict):
    """Save settings dict to file."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings_dict, f, indent=2)
        return True
    except Exception as e:
        return False


def get_default_keys():
    """Return the default suppressed keys list."""
    return list(DEFAULT_SUPPRESSED_KEYS)
