# -*- coding: utf-8 -*-
import sys

from resources.lib import tools, util


def _settings_action(name):
    if name == 'install_ytdlp':
        tools.install_ytdlp(force=False)
    elif name == 'force_ytdlp':
        tools.install_ytdlp(force=True)
    elif name == 'install_ffmpeg':
        tools.install_ffmpeg()
    elif name == 'install_js':
        tools.install_js_runtime()
    elif name == 'diagnostics':
        tools.diagnostics()
    elif name == 'refresh':
        tools.set_version_labels()


if __name__ == '__main__':
    if sys.argv and sys.argv[0].startswith('plugin://'):
        from resources.lib import main
        main.route()
    elif len(sys.argv) > 1 and sys.argv[1]:
        try:
            _settings_action(sys.argv[1])
        except Exception as e:  # never crash silently from the settings page
            import xbmcgui
            util.log('settings action failed: %s' % e)
            xbmcgui.Dialog().ok(util.ADDON_NAME, str(e))
    else:
        # launched without parameters: open the add-on's browsing page
        import xbmc
        xbmc.executebuiltin('ActivateWindow(Videos,plugin://%s/,return)' % util.ADDON_ID)
