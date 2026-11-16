# -*- coding: utf-8 -*-
"""Removes the PS2 Overlays patch from the skin and switches the addon back to
drawing on top of the skin. Run from the addon settings."""
import xbmc
import xbmcaddon
import xbmcgui

import skinpatch

changed = False
try:
    changed = skinpatch.remove_everywhere()
except Exception as e:
    xbmc.log('[script.service.ps2overlays] unpatch failed: %r' % e, xbmc.LOGINFO)
try:
    xbmcaddon.Addon().setSettingBool('skin_patch', False)
except Exception:
    pass
xbmcgui.Dialog().notification(
    'PS2 Overlays', 'Skin patch removed' if changed else 'The skin was not patched',
    xbmcgui.NOTIFICATION_INFO, 4000)
if changed:
    xbmc.executebuiltin('ReloadSkin()')
