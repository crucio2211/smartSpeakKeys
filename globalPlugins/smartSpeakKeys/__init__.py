# -*- coding: UTF-8 -*-
"""
Smart Speak Keys Filter
Works when Speak Command Keys is ON in NVDA settings.
Filters which keys are announced, fixes "plus" in key names.
Compatible with NVDA 2019.3+ (Python 2/3), 2021.1+ (Python 3, 32-bit), and 2026.1+ (Python 3.13, 64-bit).
"""

import globalPluginHandler
import keyboardHandler
import addonHandler
import gui
import wx
import os
import json
import re

addonHandler.initTranslation()

_originalShouldReportAsCommand = None
_originalDisplayName = None
_pluginInstance = None

# Settings saved in NVDA user config folder — persists across addon updates
try:
    import globalVars
    SETTINGS_FILE = os.path.join(globalVars.appArgs.configPath, "smartSpeakKeys_settings.json")
except Exception:
    SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "user_settings.json")

# Default settings
# Suppressed: arrow keys, tab, delete, backspace
# NOT suppressed: page up/down, home, end, escape, f1-f12
DEFAULT_SUPPRESSED_KEYS = [
    "upArrow", "downArrow", "leftArrow", "rightArrow",
    "tab", "delete", "backspace",
]

DEFAULT_SUPPRESSED_MODIFIERS = ["NVDA"]

COMMON_KEYS = [
    ("upArrow",   "Up Arrow"),
    ("downArrow",  "Down Arrow"),
    ("leftArrow",  "Left Arrow"),
    ("rightArrow", "Right Arrow"),
    ("pageUp",    "Page Up"),
    ("pageDown",  "Page Down"),
    ("home",      "Home"),
    ("end",       "End"),
    ("tab",       "Tab"),
    ("enter",     "Enter"),
    ("escape",    "Escape"),
    ("delete",    "Delete"),
    ("backspace", "Backspace"),
    ("f1",  "F1"),  ("f2",  "F2"),  ("f3",  "F3"),  ("f4",  "F4"),
    ("f5",  "F5"),  ("f6",  "F6"),  ("f7",  "F7"),  ("f8",  "F8"),
    ("f9",  "F9"),  ("f10", "F10"), ("f11", "F11"), ("f12", "F12"),
]

# All numpad keys grouped under one checkbox (numpadEnter excluded — always says "enter")
NUMPAD_KEYS = [
    "numpad0", "numpad1", "numpad2", "numpad3", "numpad4",
    "numpad5", "numpad6", "numpad7", "numpad8", "numpad9",
    "numpadDecimal",
    "numpadPlus", "numpadMinus", "numpadMultiply", "numpadDivide",
]

COMMON_MODIFIERS = [
    ("nvda",  "NVDA (all NVDA+key combos)"),
    ("ctrl",  "Ctrl (ALL Ctrl+key combos)"),
    ("alt",   "Alt (ALL Alt+key combos)"),
    ("shift", "Shift (ALL Shift+key combos)"),
    ("win",   "Win (ALL Win+key combos)"),
]


def load_settings():
    defaults = {
        "enabled": True,
        "suppressed_keys": list(DEFAULT_SUPPRESSED_KEYS),
        "suppressed_modifiers": list(DEFAULT_SUPPRESSED_MODIFIERS),
    }
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                defaults.update(saved)
    except Exception as e:
        try:
            import logHandler
            logHandler.log.warning("smartSpeakKeys: failed to load settings: %s" % e)
        except Exception:
            pass
    return defaults


def save_settings(d):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
    except Exception as e:
        try:
            import logHandler
            logHandler.log.warning("smartSpeakKeys: failed to save settings to %s: %s" % (SETTINGS_FILE, e))
        except Exception:
            pass


def only_shift_numpad_delete(gesture):
    """Check if gesture is Shift+Numpad Decimal (reports as delete but isExtended=False)."""
    try:
        # isExtended=False means the key came from numpad, not the main keyboard
        return not gesture.isExtended
    except Exception:
        return False


def _should_suppress(gesture, settings):
    if not hasattr(gesture, "mainKeyName"):
        return False

    modSet = set(m.lower() for m in gesture.modifierNames)
    mainKey = gesture.mainKeyName
    mainKeyLower = mainKey.lower()
    suppressed_keys = set(settings.get("suppressed_keys", []))
    suppressed_mods = set(m.lower() for m in settings.get("suppressed_modifiers", []))

    # If ANY modifier in the gesture is suppressed, suppress the whole combo
    for mod in modSet:
        if mod in suppressed_mods:
            return True

    # If the main key itself is in the suppressed list, suppress it
    if mainKey in suppressed_keys:
        return True

    # Shift+Numpad Decimal reports as "delete" but isExtended=False (means it's from numpad)
    # Suppress it if numpad keys are suppressed (i.e. any numpad key is in suppressed_keys)

    # Helper functions — handle both "ctrl" and "control" (NVDA uses "control" internally)
    def only_ctrl():
        return modSet in ({"ctrl"}, {"control"})

    def only_shift():
        return modSet == {"shift"}

    def only_ctrl_shift():
        return modSet in ({"ctrl", "shift"}, {"control", "shift"})

    # Hardcoded silent combos — always suppressed regardless of settings
    HARDCODED_CTRL_KEYS = {"a", "c", "v", "x", "z", "tab"}
    HARDCODED_NAV_KEYS = {"home", "end", "pageup", "pagedown"}

    if only_ctrl() and mainKeyLower in HARDCODED_CTRL_KEYS:
        return True
    if only_ctrl_shift() and mainKeyLower == "tab":
        return True
    if only_ctrl() and mainKeyLower in HARDCODED_NAV_KEYS:
        return True
    if only_ctrl_shift() and mainKeyLower in HARDCODED_NAV_KEYS:
        return True
    if only_shift() and mainKeyLower in HARDCODED_NAV_KEYS:
        return True

    return False


def _patched_shouldReportAsCommand(self):
    orig = _originalShouldReportAsCommand.fget(self)
    if not orig:
        return False
    if _pluginInstance:
        if not _pluginInstance._settings.get("enabled", True):
            return orig
        if _should_suppress(self, _pluginInstance._settings):
            return False
    return orig


def _patched_displayName(self):
    name = _originalDisplayName.fget(self)
    if not isinstance(name, str):
        return name
    if not (_pluginInstance and _pluginInstance._settings.get("enabled", True)):
        return name
    name=name.replace("+"," ")
    name=re.sub(r'(?i)ctrl','control',name)
    reps={
      'numpad enter':'enter','numpadenter':'enter',
      'numpad delete':'delete','numpaddelete':'delete',
      'numpad insert':'insert','numpadinsert':'insert',
      'numpad home':'home','numpadhome':'home',
      'numpad end':'end','numpadend':'end',
      'numpad page up':'page up','numpadpageup':'page up',
      'numpad page down':'page down','numpadpagedown':'page down',
      'numpad up':'up','numpadup':'up',
      'numpad down':'down','numpaddown':'down',
      'numpad left':'left','numpadleft':'left',
      'numpad right':'right','numpadright':'right',
    }
    lower=name.lower()
    for k,v in reps.items():
        lower=lower.replace(k,v)
    return " ".join(w.capitalize() if w!='NVDA' else w for w in lower.split())



class GlobalPlugin(globalPluginHandler.GlobalPlugin):

    scriptCategory = "Smart Speak Keys Filter"

    def __init__(self):
        super(GlobalPlugin, self).__init__()
        global _pluginInstance, _originalShouldReportAsCommand, _originalDisplayName
        _pluginInstance = self
        self._settings = load_settings()
        self._menuItem = None
        wx.CallAfter(lambda: self.reloadSettings(load_settings()))

        # Patch shouldReportAsCommand
        for cls in keyboardHandler.KeyboardInputGesture.__mro__:
            if 'shouldReportAsCommand' in cls.__dict__:
                _originalShouldReportAsCommand = cls.__dict__['shouldReportAsCommand']
                break
        if _originalShouldReportAsCommand is not None:
            keyboardHandler.KeyboardInputGesture.shouldReportAsCommand = property(
                _patched_shouldReportAsCommand
            )

        # Patch displayName to fix "plus" in key names
        for cls in keyboardHandler.KeyboardInputGesture.__mro__:
            if 'displayName' in cls.__dict__:
                _originalDisplayName = cls.__dict__['displayName']
                break
        if _originalDisplayName is not None:
            keyboardHandler.KeyboardInputGesture.displayName = property(
                _patched_displayName
            )

        wx.CallAfter(self._addMenuItem)

    def _addMenuItem(self):
        try:
            toolsMenu = gui.mainFrame.sysTrayIcon.toolsMenu
            self._menuItem = toolsMenu.Append(
                wx.ID_ANY,
                "Smart Speak Keys Settings...",
                "Configure Smart Speak Keys Filter"
            )
            gui.mainFrame.sysTrayIcon.Bind(
                wx.EVT_MENU,
                self._onOpenSettings,
                self._menuItem
            )
        except Exception as e:
            try:
                import logHandler
                logHandler.log.warning("smartSpeakKeys: menu error: %s" % e)
            except Exception:
                pass

    def _onOpenSettings(self, event):
        wx.CallAfter(self._showSettingsDialog)

    def _showSettingsDialog(self):
        dlg = SmartSpeakKeysDialog(gui.mainFrame, self._settings, self)
        dlg.ShowModal()
        dlg.Destroy()

    def reloadSettings(self, new_settings=None):
        self._settings = load_settings() if new_settings is None else new_settings

    def terminate(self):
        global _pluginInstance, _originalShouldReportAsCommand, _originalDisplayName
        if _originalShouldReportAsCommand is not None:
            keyboardHandler.KeyboardInputGesture.shouldReportAsCommand = _originalShouldReportAsCommand
            _originalShouldReportAsCommand = None
        if _originalDisplayName is not None:
            keyboardHandler.KeyboardInputGesture.displayName = _originalDisplayName
            _originalDisplayName = None
        _pluginInstance = None
        try:
            if self._menuItem:
                gui.mainFrame.sysTrayIcon.toolsMenu.Remove(self._menuItem)
        except Exception:
            pass


class SmartSpeakKeysDialog(wx.Dialog):

    def __init__(self, parent, current_settings, plugin):
        super(SmartSpeakKeysDialog, self).__init__(
            parent,
            title="Smart Speak Keys Filter Settings",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self._plugin = plugin
        self._settings = dict(current_settings)
        self._build()

    def _build(self):
        pane = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Enable/disable toggle — at the very top
        self.enabledCheckbox = wx.CheckBox(pane, label="Enable Smart Speak Keys Filter")
        self.enabledCheckbox.SetValue(self._settings.get("enabled", True))
        sizer.Add(self.enabledCheckbox, 0, wx.ALL, 8)

        # Modifier section
        mod_box = wx.StaticBox(pane, label="Suppress ALL combos using these modifier keys:")
        mod_sizer = wx.StaticBoxSizer(mod_box, wx.VERTICAL)
        self.modChecks = {}
        suppressed_mods = set(m.lower() for m in self._settings.get("suppressed_modifiers", []))
        for mod_id, mod_label in COMMON_MODIFIERS:
            cb = wx.CheckBox(pane, label=mod_label)
            cb.SetValue(mod_id in suppressed_mods)
            self.modChecks[mod_id] = cb
            mod_sizer.Add(cb, 0, wx.ALL, 3)
        sizer.Add(mod_sizer, 0, wx.ALL | wx.EXPAND, 8)

        # Individual keys section
        key_box = wx.StaticBox(pane, label="Suppress individual keys (no modifier):")
        key_sizer = wx.StaticBoxSizer(key_box, wx.VERTICAL)
        self.keyChecks = {}
        current_suppressed = set(self._settings.get("suppressed_keys", []))
        grid = wx.FlexGridSizer(cols=4, hgap=10, vgap=4)
        for key_id, key_label in COMMON_KEYS:
            cb = wx.CheckBox(pane, label=key_label)
            cb.SetValue(key_id in current_suppressed)
            self.keyChecks[key_id] = cb
            grid.Add(cb, 0, wx.EXPAND)
        key_sizer.Add(grid, 0, wx.ALL, 6)

        # Single numpad group checkbox
        numpad_suppressed = any(k in current_suppressed for k in NUMPAD_KEYS)
        self.numpadCheckbox = wx.CheckBox(pane, label="Numpad Keys")
        self.numpadCheckbox.SetValue(numpad_suppressed)
        key_sizer.Add(self.numpadCheckbox, 0, wx.LEFT | wx.BOTTOM, 6)

        sizer.Add(key_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

        # Buttons
        btnRow = wx.BoxSizer(wx.HORIZONTAL)
        resetBtn = wx.Button(pane, label="&Reset to Defaults")
        resetBtn.Bind(wx.EVT_BUTTON, self._onReset)
        btnRow.Add(resetBtn, 0, wx.RIGHT, 8)
        btnRow.AddStretchSpacer()
        okBtn = wx.Button(pane, wx.ID_OK)
        okBtn.Bind(wx.EVT_BUTTON, self._onOK)
        okBtn.SetDefault()
        btnRow.Add(okBtn, 0, wx.RIGHT, 4)
        btnRow.Add(wx.Button(pane, wx.ID_CANCEL))
        sizer.Add(btnRow, 0, wx.ALL | wx.EXPAND, 8)

        pane.SetSizerAndFit(sizer)
        self.Fit()
        self.CenterOnParent()

    def _onReset(self, event):
        self.enabledCheckbox.SetValue(True)
        for k, _ in COMMON_KEYS:
            self.keyChecks[k].SetValue(k in DEFAULT_SUPPRESSED_KEYS)
        for m, _ in COMMON_MODIFIERS:
            self.modChecks[m].SetValue(m == "nvda")
        self.numpadCheckbox.SetValue(False)

    def _onOK(self, event):
        keys = [k for k, _ in COMMON_KEYS if self.keyChecks[k].GetValue()]
        if self.numpadCheckbox.GetValue():
            keys.extend(NUMPAD_KEYS)
        mod_map = {
            "nvda": "NVDA", "ctrl": "ctrl",
            "alt": "alt", "shift": "shift", "win": "win"
        }
        mods = [mod_map[m] for m, _ in COMMON_MODIFIERS if self.modChecks[m].GetValue()]
        new_settings = {
            "enabled": self.enabledCheckbox.GetValue(),
            "suppressed_modifiers": mods,
            "suppressed_keys": keys,
        }
        save_settings(new_settings)
        self._plugin.reloadSettings(new_settings)
        self.EndModal(wx.ID_OK)
