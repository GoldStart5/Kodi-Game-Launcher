# -*- coding: utf-8 -*-
"""Logging and settings."""
import xbmc
import xbmcaddon

ADDON_ID = 'service.cinemathemes'

SELECT_RANDOM = 0
SELECT_ORDER = 1

_debug = False


def set_debug(enabled):
    global _debug
    _debug = bool(enabled)


def log(msg, level=None):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), xbmc.LOGINFO if level is None else level)


def debug(msg):
    if _debug:
        log(msg)


class Config(object):
    """Snapshot of the add-on settings."""

    def __init__(self):
        addon = xbmcaddon.Addon()
        gs, gi, gb = addon.getSettingString, addon.getSettingInt, addon.getSettingBool

        self.mpv_path = gs('mpv_path').strip()
        self.extra_args = gs('mpv_extra_args').strip()
        self.keyword = gs('theme_keyword').strip() or 'theme'

        self.volume = max(0, min(100, gi('volume')))
        self.fade_in_ms = max(0, gi('fade_in_ms'))
        self.fade_out_ms = max(0, gi('fade_out_ms'))

        self.selection_mode = gi('selection_mode')
        self.loop = gb('loop_theme')
        self.random_start = gb('random_start')

        self.pause_on_focus_loss = gb('pause_on_focus_loss')
        self.fade_on_playback = gb('fade_on_playback')
        self.fade_outside_library = gb('fade_outside_library')
        self.switch_delay = max(0, gi('switch_delay_ms')) / 1000.0

        self.root_movies = gs('root_movies').strip()
        self.root_tvshows = gs('root_tvshows').strip()

        self.debug = gb('debug_logging')
