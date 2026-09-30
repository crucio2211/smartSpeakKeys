# Smart Speak Keys Filter for NVDA

NVDA add-on that gives fine-grained control over which keys NVDA announces when
*Speak Command Keys* is turned on. Mimics JAWS behavior by suppressing NVDA
command keys and customizable keys from being spoken.

- Add-on name: `smartSpeakKeys`
- Author: Rosendo Barde Hubilla Junior
- Current version: 3.0.0
- Minimum NVDA: 2019.3.0, Last tested: 2026.1.0

## Features

- Silences distracting keys (navigation keys, common editing shortcuts) while
  *Speak Command Keys* (`NVDA+4`) is enabled
- Hardcoded silent keys: Ctrl+A/C/V/X/Z, Ctrl+Tab / Ctrl+Shift+Tab,
  Ctrl+Home and other navigation combinations
- User-configurable suppressed keys and modifiers via settings dialog
- Everything else is announced normally

## Install

1. Download the latest `smartSpeakKeys_vX.X.X.nvda-addon` from Releases.
2. Press Enter on it, or NVDA Menu → Tools → Manage Add-ons → Install.
3. Restart NVDA when asked.
4. Make sure *Speak Command Keys* is enabled (`NVDA+4`).

## Repo layout

- `manifest.ini` — add-on metadata
- `buildVars.py` — build variables
- `globalPlugins/smartSpeakKeys/` — main code
- `doc/en/readme.html` — user guide

## License

GPL v2 or later (same as NVDA).
