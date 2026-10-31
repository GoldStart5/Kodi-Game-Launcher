# -*- coding: utf-8 -*-
"""Kodi video library lookups: which folder holds an item and which source it belongs to."""
import json
import time
from collections import namedtuple

import xbmc

from . import paths
from .common import debug

ItemInfo = namedtuple('ItemInfo', 'media folder source show_id')

_IGNORED_SCHEMES = ('plugin://', 'addons://', 'upnp://', 'videodb://', 'library://', 'sources://')
_SOURCES_TTL = 60.0
_ITEM_TTL = 600.0


class Library(object):
    def __init__(self):
        self._sources = None
        self._sources_ts = 0.0
        self._items = {}

    def clear(self):
        self._sources = None
        self._items.clear()

    @staticmethod
    def _rpc(method, params):
        request = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})
        try:
            response = json.loads(xbmc.executeJSONRPC(request))
        except Exception as exc:
            debug('JSON-RPC %s failed: %s' % (method, exc))
            return None
        return response.get('result')

    def sources(self):
        now = time.monotonic()
        if self._sources is None or now - self._sources_ts > _SOURCES_TTL:
            result = self._rpc('Files.GetSources', {'media': 'video'}) or {}
            found = []
            for src in result.get('sources', []):
                for path in paths.expand_source(src.get('file', '')):
                    if path and not path.lower().startswith(_IGNORED_SCHEMES):
                        found.append(path)
            self._sources = found
            self._sources_ts = now
            debug('Video sources: %s' % found)
        return self._sources

    def source_for(self, path):
        """Longest source path that contains ``path``."""
        best = None
        for src in self.sources():
            if paths.is_under(path, src) and (best is None or len(paths.norm(src)) > len(paths.norm(best))):
                best = src
        return paths.strip_sep(best) if best else None

    def item_info(self, dbtype, dbid):
        key = (dbtype, dbid)
        now = time.monotonic()
        hit = self._items.get(key)
        if hit and now - hit[0] < _ITEM_TTL:
            return hit[1]
        info = self._lookup(dbtype, dbid)
        self._items[key] = (now, info)
        return info

    def _lookup(self, dbtype, dbid):
        media = None
        folder = None
        show_id = 0
        if dbtype == 'movie':
            res = self._rpc('VideoLibrary.GetMovieDetails', {'movieid': dbid, 'properties': ['file']})
            details = (res or {}).get('moviedetails') or {}
            if details.get('file'):
                media, folder = 'movies', paths.movie_folder(details['file'])
        else:
            if dbtype == 'tvshow':
                show_id = dbid
            elif dbtype == 'season':
                res = self._rpc('VideoLibrary.GetSeasonDetails', {'seasonid': dbid, 'properties': ['tvshowid']})
                show_id = ((res or {}).get('seasondetails') or {}).get('tvshowid')
            elif dbtype == 'episode':
                res = self._rpc('VideoLibrary.GetEpisodeDetails', {'episodeid': dbid, 'properties': ['tvshowid']})
                show_id = ((res or {}).get('episodedetails') or {}).get('tvshowid')
            if show_id and show_id > 0:
                res = self._rpc('VideoLibrary.GetTVShowDetails', {'tvshowid': show_id, 'properties': ['file']})
                details = (res or {}).get('tvshowdetails') or {}
                if details.get('file'):
                    media, folder = 'tvshows', paths.show_folder(details['file'])
        if not folder:
            return None
        source = self.source_for(folder)
        debug('%s %s -> folder=%s source=%s' % (dbtype, dbid, folder, source))
        return ItemInfo(media, folder, source, show_id if media == 'tvshows' else 0)
