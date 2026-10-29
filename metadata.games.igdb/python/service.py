"""Background service: keeps advancedsettings.xml in step with the add-on's toggle.

Kodi's settings page cannot run code when a switch is flipped, so this tiny
service listens for settings changes. It does nothing else and uses no CPU
while idle.
"""
import os

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from lib.gamescraper import advanced

ADDON_ID = 'metadata.games.igdb'
TOGGLE = 'advancedsettings_toggle'
XML_PATH = 'special://profile/advancedsettings.xml'


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


def _paths():
    addon = xbmcaddon.Addon()  # fresh every time: a stored Addon() would not see new values
    profile = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    return addon, xbmcvfs.translatePath(XML_PATH), os.path.join(profile, 'advancedsettings_state.json')


def _notify(message, icon=xbmcgui.NOTIFICATION_INFO):
    xbmcgui.Dialog().notification('IGDB + SteamGridDB scraper', message, icon, 8000)


def on_start():
    """If advancedsettings.xml already has our entries, show the toggle as ON."""
    addon, xml_path, state_path = _paths()
    state = advanced.adopt(xml_path, state_path)
    if addon.getSettingBool(TOGGLE) != state:
        addon.setSettingBool(TOGGLE, state)
        log('Toggle set to %s to match advancedsettings.xml' % state)


def on_settings_changed():
    addon, xml_path, state_path = _paths()
    want = addon.getSettingBool(TOGGLE)
    try:
        result = advanced.sync(want, xml_path, state_path)
    except advanced.AdvancedSettingsError as exc:
        log('Not changed: %s' % exc, xbmc.LOGWARNING)
        _notify('%s. The file was left as it was.' % exc, xbmcgui.NOTIFICATION_WARNING)
        # put the switch back so it shows the real situation
        addon.setSettingBool(TOGGLE, bool(advanced.load_state(state_path)))
        return
    if result:
        log('advancedsettings.xml entries %s' % result)
        _notify('advancedsettings.xml %s. Restart Kodi to apply.' % result)


class Monitor(xbmc.Monitor):
    def onSettingsChanged(self):
        on_settings_changed()


def main():
    monitor = Monitor()
    try:
        on_start()
    except Exception as exc:  # noqa: BLE001 - never let the service die at start-up
        log('Start-up check failed: %s' % exc, xbmc.LOGWARNING)
    monitor.waitForAbort()


if __name__ == '__main__':
    main()
