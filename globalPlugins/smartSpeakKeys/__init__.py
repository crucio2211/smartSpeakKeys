# -*- coding: UTF-8 -*-
"""
Smart Speak Keys Filter
Works when Speak Command Keys is ON in NVDA settings.
Filters which keys are announced, fixes "plus" in key names.
Compatible with NVDA 2019.3 and later (Python 3 only).
"""

import globalPluginHandler
import keyboardHandler
import addonHandler
import gui
import wx
import os
import json
import re
from gui import guiHelper
from gui import nvdaControls
from gui.settingsDialogs import SettingsPanel

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
	("upArrow", "Up Arrow"),
	("downArrow", "Down Arrow"),
	("leftArrow", "Left Arrow"),
	("rightArrow", "Right Arrow"),
	("pageUp", "Page Up"),
	("pageDown", "Page Down"),
	("home", "Home"),
	("end", "End"),
	("tab", "Tab"),
	("enter", "Enter"),
	("escape", "Escape"),
	("delete", "Delete"),
	("backspace", "Backspace"),
	("f1", "F1"), ("f2", "F2"), ("f3", "F3"), ("f4", "F4"),
	("f5", "F5"), ("f6", "F6"), ("f7", "F7"), ("f8", "F8"),
	("f9", "F9"), ("f10", "F10"), ("f11", "F11"), ("f12", "F12"),
]

# All numpad keys grouped under one checkbox (numpadEnter excluded — always says "enter")
NUMPAD_KEYS = [
	"numpad0", "numpad1", "numpad2", "numpad3", "numpad4",
	"numpad5", "numpad6", "numpad7", "numpad8", "numpad9",
	"numpadDecimal",
	"numpadPlus", "numpadMinus", "numpadMultiply", "numpadDivide",
]

NUMPAD_KEY_LABELS = [
	"Numpad 0", "Numpad 1", "Numpad 2", "Numpad 3", "Numpad 4",
	"Numpad 5", "Numpad 6", "Numpad 7", "Numpad 8", "Numpad 9",
	"Numpad Decimal",
	"Numpad Plus", "Numpad Minus", "Numpad Multiply", "Numpad Divide",
]

COMMON_MODIFIERS = [
	("nvda", "NVDA (all NVDA+key combos)"),
	("ctrl", "Ctrl (ALL Ctrl+key combos)"),
	("alt", "Alt (ALL Alt+key combos)"),
	("shift", "Shift (ALL Shift+key combos)"),
	("win", "Win (ALL Win+key combos)"),
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
	name = name.replace("+", " ")
	name = re.sub(r'(?i)\bctrl\b', 'control', name)
	reps = {
		'numpad enter': 'enter', 'numpadenter': 'enter',
		'numpad delete': 'delete', 'numpaddelete': 'delete',
		'numpad insert': 'insert', 'numpadinsert': 'insert',
		'numpad home': 'home', 'numpadhome': 'home',
		'numpad end': 'end', 'numpadend': 'end',
		'numpad page up': 'page up', 'numpadpageup': 'page up',
		'numpad page down': 'page down', 'numpadpagedown': 'page down',
		'numpad up': 'up', 'numpadup': 'up',
		'numpad down': 'down', 'numpaddown': 'down',
		'numpad left': 'left', 'numpadleft': 'left',
		'numpad right': 'right', 'numpadright': 'right',
	}
	lower = name.lower()
	for k, v in reps.items():
		lower = lower.replace(k, v)
	return " ".join(w.capitalize() if w != 'NVDA' else w for w in lower.split())


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	scriptCategory = "Smart Speak Keys Filter"

	def __init__(self):
		super(GlobalPlugin, self).__init__()
		global _pluginInstance, _originalShouldReportAsCommand, _originalDisplayName
		_pluginInstance = self
		self._settings = load_settings()

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
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(SmartSpeakKeysSettingsPanel)

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
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(SmartSpeakKeysSettingsPanel)
		except Exception:
			pass


class SmartSpeakKeysSettingsPanel(SettingsPanel):
	# Translators: Title of the Smart Speak Keys Filter settings category.
	title = _("Smart Speak Keys Filter")

	def makeSettings(self, settingsSizer):
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		settings = load_settings()
		# Enable/disable toggle — at the very top
		self.enabledCheckbox = sHelper.addItem(
			wx.CheckBox(self, label=_("Enable Smart Speak Keys Filter"))
		)
		self.enabledCheckbox.SetValue(settings.get("enabled", True))
		# Modifier keys — accessible checkable list, like NVDA's own
		# keyboard settings "NVDA modifier keys" list.
		self.modIds = [modId for modId, _modLabel in COMMON_MODIFIERS]
		self.modList = sHelper.addLabeledControl(
			_("Suppress ALL combos using these modifier keys:"),
			nvdaControls.CustomCheckListBox,
			choices=[modLabel for _modId, modLabel in COMMON_MODIFIERS],
		)
		suppressedMods = set(m.lower() for m in settings.get("suppressed_modifiers", []))
		self.modList.CheckedItems = [
			n for n, modId in enumerate(self.modIds) if modId in suppressedMods
		]
		self.modList.Select(0)
		# Individual keys (including numpad keys listed individually) —
		# accessible checkable list instead of grouped checkboxes.
		self.keyIds = [keyId for keyId, _keyLabel in COMMON_KEYS] + list(NUMPAD_KEYS)
		keyLabels = [keyLabel for _keyId, keyLabel in COMMON_KEYS] + NUMPAD_KEY_LABELS
		self.keyList = sHelper.addLabeledControl(
			_("Suppress individual keys (no modifier):"),
			nvdaControls.CustomCheckListBox,
			choices=keyLabels,
		)
		suppressedKeys = set(settings.get("suppressed_keys", []))
		self.keyList.CheckedItems = [
			n for n, keyId in enumerate(self.keyIds) if keyId in suppressedKeys
		]
		self.keyList.Select(0)
		# Reset button
		self.resetButton = sHelper.addItem(wx.Button(self, label=_("&Reset to Defaults")))
		self.resetButton.Bind(wx.EVT_BUTTON, self.onReset)

	def onReset(self, event):
		self.enabledCheckbox.SetValue(True)
		self.modList.CheckedItems = [
			n for n, modId in enumerate(self.modIds) if modId == "nvda"
		]
		self.keyList.CheckedItems = [
			n for n, keyId in enumerate(self.keyIds) if keyId in DEFAULT_SUPPRESSED_KEYS
		]
		self.modList.Select(0)
		self.keyList.Select(0)

	def onSave(self):
		modMap = {
			"nvda": "NVDA", "ctrl": "ctrl",
			"alt": "alt", "shift": "shift", "win": "win",
		}
		mods = [modMap[self.modIds[n]] for n in self.modList.CheckedItems]
		keys = [self.keyIds[n] for n in self.keyList.CheckedItems]
		newSettings = {
			"enabled": self.enabledCheckbox.GetValue(),
			"suppressed_modifiers": mods,
			"suppressed_keys": keys,
		}
		save_settings(newSettings)
		if _pluginInstance is not None:
			_pluginInstance.reloadSettings(newSettings)
