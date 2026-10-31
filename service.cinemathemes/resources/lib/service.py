# -*- coding: utf-8 -*-
"""The Kodi side: watches what the user is looking at and tells the player what to do."""
import os
import time
import traceback
from collections import namedtuple

import xbmc
import xbmcgui

from . import paths
from .common import ADDON_ID, Config, debug, log, set_debug
from .focus import FocusWatcher
from .library import Library
from .mpv_player import MpvThemePlayer
from .themes import ThemeFinder, make_playable

TICK = 0.15

# kind: 'browse' (library list), 'info' (video info dialog) or 'other'
UI = namedtuple('UI', 'kind media content dbtype dbid')
OTHER = UI('other', '', '', '', 0)

KEEP = object()   # "do not change the theme"

# A movie whose info dialog was opened, or a show whose seasons/episodes were entered, keeps its own
# theme in the list until another item is focused. dbtype is 'movie' or 'tvshow'.
Sticky = namedtuple('Sticky', 'dbtype dbid key files')


def _to_int(text):
    try:
        return int(text)
    except (TypeError, ValueError):
        return 0


def _media_from(folder_path, content, dbtype=''):
    fp = (folder_path or '').lower()
    if fp.startswith(('videodb://movies', 'videodb://recentlyaddedmovies')):
        return 'movies'
    if fp.startswith(('videodb://tvshows', 'videodb://inprogresstvshows', 'videodb://recentlyaddedepisodes')):
        return 'tvshows'
    if content in ('movies', 'sets') or dbtype in ('movie', 'set'):
        return 'movies'
    if content in ('tvshows', 'seasons', 'episodes') or dbtype in ('tvshow', 'season', 'episode'):
        return 'tvshows'
    return ''


class _Monitor(xbmc.Monitor):
    def __init__(self, service):
        super(_Monitor, self).__init__()
        self._service = service

    def onSettingsChanged(self):
        self._service.settings_dirty = True


class ThemeService(object):
    def __init__(self):
        self.settings_dirty = False
        self.cfg = Config()
        set_debug(self.cfg.debug)
        self.monitor = _Monitor(self)
        self.focus = FocusWatcher(log)
        self.library = Library()
        self.finder = ThemeFinder()
        self.player = MpvThemePlayer(lambda: self.cfg, log, self._on_player_error)

        self._notice = None
        self._pending_sig = None
        self._pending_since = 0.0
        self._committed_sig = None
        self._committed_kind = None
        self._last_ctx_sig = None
        self._target = (None, [])
        self._last_root = {}
        self._last_browse = None   # (media, dbtype, dbid) of the last focused library item
        self._sticky = None

    # ------------------------------------------------------------------ main loop
    def run(self):
        log('Service started')
        self.player.start()
        try:
            while not self.monitor.abortRequested():
                if self.settings_dirty:
                    self._reload()
                try:
                    self._tick()
                except Exception:
                    log('Error in service loop:\n%s' % traceback.format_exc())
                self.player.watchdog()
                self._show_notice()
                if self.monitor.waitForAbort(TICK):
                    break
        finally:
            self.player.shutdown()
            log('Service stopped')

    def _reload(self):
        self.settings_dirty = False
        self.cfg = Config()
        set_debug(self.cfg.debug)
        self.finder.clear()
        self.library.clear()
        self._last_root.clear()
        self._sticky = None
        self._committed_sig = None          # force the theme to be resolved again
        log('Settings reloaded')

    def _on_player_error(self, message):
        self._notice = message

    def _show_notice(self):
        if self._notice:
            message, self._notice = self._notice, None
            xbmcgui.Dialog().notification('Cinema Themes', message, xbmcgui.NOTIFICATION_ERROR, 6000)

    # ------------------------------------------------------------------ per-tick logic
    def _tick(self):
        cfg = self.cfg
        now = time.monotonic()
        ui = self._read_ui()
        sig = ('other',) if ui.kind == 'other' else tuple(ui)

        if sig != self._pending_sig:
            self._pending_sig = sig
            self._pending_since = now

        if sig != self._committed_sig:
            returning = (self._committed_kind == 'other' and sig == self._last_ctx_sig)
            if returning or now - self._pending_since >= cfg.switch_delay:
                self._commit(sig, ui)

        focused = self.focus.has_focus() if cfg.pause_on_focus_loss else True
        playing = cfg.fade_on_playback and xbmc.getCondVisibility('Player.HasMedia')
        if ui.kind == 'other':
            context_ok = not cfg.fade_outside_library
        else:
            context_ok = self._committed_kind in ('browse', 'info')

        key, files = self._target
        self.player.set_target(key, files, bool(focused and not playing and context_ok))

    def _commit(self, sig, ui):
        self._committed_sig = sig
        self._committed_kind = ui.kind
        if ui.kind == 'other':
            return
        self._last_ctx_sig = sig
        result = self._resolve(ui)
        if result is not KEEP:
            self._target = result
            debug('Target: %s (%s)' % (result[0], ui,))

    # ------------------------------------------------------------------ reading the screen
    def _read_ui(self):
        cond = xbmc.getCondVisibility
        info_open = cond('Window.IsActive(movieinformation)')
        videos_open = cond('Window.IsActive(videos)')
        if not (info_open or videos_open):
            return OTHER

        label = xbmc.getInfoLabel
        dbtype = label('ListItem.DBType').lower()
        dbid = _to_int(label('ListItem.DBID'))
        has_item = dbtype in ('movie', 'tvshow', 'season', 'episode', 'set') and (dbid > 0 or dbtype == 'set')

        if info_open:
            if has_item:
                media = _media_from('', '', dbtype)
                self._last_browse = (media, dbtype, dbid)
                return UI('info', media, '', dbtype, dbid)
            if self._last_browse:
                media, dbtype, dbid = self._last_browse
                return UI('info', media, '', dbtype, dbid)
            return OTHER

        content = label('Container.Content').lower()
        media = _media_from(label('Container.FolderPath'), content, dbtype)
        if not media:
            return OTHER
        if has_item:
            self._last_browse = (media, dbtype, dbid)
        return UI('browse', media, content, dbtype if has_item else '', dbid if has_item else 0)

    # ------------------------------------------------------------------ choosing the theme
    def _resolve_sticky(self, ui):
        """Return the sticky theme while it still applies, otherwise forget it."""
        sticky = self._sticky
        if not sticky:
            return None
        media = 'movies' if sticky.dbtype == 'movie' else 'tvshows'
        same_item = ui.dbtype == sticky.dbtype and ui.dbid == sticky.dbid
        no_item = ui.kind == 'browse' and ui.media == media and not ui.dbtype
        if same_item or no_item:
            return (sticky.key, sticky.files)
        self._sticky = None
        return None

    def _resolve(self, ui):
        sticky = self._resolve_sticky(ui)
        if sticky:
            return sticky
        cfg = self.cfg
        in_show = ui.media == 'tvshows' and (ui.dbtype in ('season', 'episode') or ui.content in ('seasons', 'episodes'))
        item_scope = ui.kind == 'info' and ui.dbtype in ('movie', 'tvshow', 'season', 'episode') or in_show

        info = None
        if ui.dbtype in ('movie', 'tvshow', 'season', 'episode') and ui.dbid > 0:
            info = self.library.item_info(ui.dbtype, ui.dbid)
        media = info.media if info else ui.media
        if not media:
            return KEEP

        # 1. the item's own theme (info dialog, seasons, episodes)
        if item_scope and info and info.folder:
            files = self.finder.find(info.folder, cfg.keyword)
            if files:
                result = self._finish(paths.norm(info.folder), files)
                is_root_folder = bool(info.source) and paths.norm(info.folder) == paths.norm(info.source)
                if result[0] is not None and not is_root_folder:
                    if ui.kind == 'info' and ui.dbtype == 'movie':
                        self._sticky = Sticky('movie', ui.dbid, result[0], result[1])
                    elif in_show and info.show_id > 0:
                        # inside the show: remember it, so leaving to the show list keeps its theme
                        self._sticky = Sticky('tvshow', info.show_id, result[0], result[1])
                return result

        # 2. the root theme of the source folder the item lives in
        root = info.source if info else None
        if info and not root:
            root = self._guess_root(info.folder)
        if root:
            files = self.finder.find(root, cfg.keyword)
            if files:
                self._last_root[media] = (paths.norm(root), files)
                return self._finish(paths.norm(root), files)
        else:
            # no usable item under the cursor: reuse the last root we found
            last = self._last_root.get(media)
            if last:
                return self._finish(last[0], last[1])

        # 3. optional fallback from the settings
        fallback = self._fallback(media)
        if fallback:
            return self._finish(*fallback)

        # 4. no root theme at all: the focused movie or show plays its own theme
        if ui.kind == 'browse' and info and info.folder and ui.dbtype in ('movie', 'tvshow'):
            files = self.finder.find(info.folder, cfg.keyword)
            if files:
                return self._finish(paths.norm(info.folder), files)

        return (None, [])

    def _guess_root(self, folder):
        """No library source matched: use the closest parent folder that holds a theme file."""
        current = paths.parent(folder)
        for _ in range(3):
            if not current:
                break
            if self.finder.find(current, self.cfg.keyword):
                debug('Guessed root folder %s for %s' % (current, folder))
                return current
            nxt = paths.parent(current)
            if not nxt or nxt == current:
                break
            current = nxt
        return None

    def _finish(self, key, files):
        playable = [p for p in (make_playable(f) for f in files) if p]
        if not playable:
            return (None, [])
        return (key, playable)

    def _fallback(self, media):
        configured = self.cfg.root_movies if media == 'movies' else self.cfg.root_tvshows
        if not configured:
            return None
        real = paths.translate(configured)
        if real.lower().endswith(paths.AUDIO_EXTENSIONS):
            if os.path.isfile(real) or '://' in real:
                return (paths.norm(real), [real])
            return None
        files = self.finder.find(real, self.cfg.keyword)
        return (paths.norm(real), files) if files else None
