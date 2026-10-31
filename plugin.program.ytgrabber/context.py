# -*- coding: utf-8 -*-
"""Library context-menu entry: pick Theme or Trailer, then open the results."""
import urllib.parse

import xbmc
import xbmcgui

ADDON_ID = 'plugin.program.ytgrabber'


def main():
    dbtype = xbmc.getInfoLabel('ListItem.DBType')
    dbid = xbmc.getInfoLabel('ListItem.DBID')
    if dbtype not in ('movie', 'tvshow') or not dbid or dbid == '-1':
        return
    title = xbmc.getInfoLabel('ListItem.Title') or 'Download'
    choice = xbmcgui.Dialog().select(title, ['Theme (soundtrack)', 'Trailer'])
    if choice < 0:
        return
    query = urllib.parse.urlencode({'action': 'results', 'kind': 'theme' if choice == 0 else 'trailer',
                                    'type': dbtype, 'id': dbid})
    xbmc.executebuiltin('ActivateWindow(Videos,"plugin://%s/?%s",return)' % (ADDON_ID, query))


if __name__ == '__main__':
    main()
