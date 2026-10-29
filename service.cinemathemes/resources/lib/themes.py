# -*- coding: utf-8 -*-
"""Find theme files in a folder (TvTunes style: any audio file whose name contains the keyword)."""
import hashlib
import os
import re
import time

from . import paths
from .common import debug, log

_CACHE_TTL = 60.0


def natural_key(text):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', text.lower())]


class ThemeFinder(object):
    def __init__(self):
        self._cache = {}

    def clear(self):
        self._cache.clear()

    def find(self, folder, keyword):
        """Return a sorted list of theme files in ``folder`` (not recursive)."""
        if not folder:
            return []
        kw = (keyword or 'theme').strip().lower()
        ck = (paths.norm(folder), kw)
        now = time.monotonic()
        hit = self._cache.get(ck)
        if hit and now - hit[0] < _CACHE_TTL:
            return list(hit[1])
        files = self._scan(folder, kw)
        self._cache[ck] = (now, files)
        return list(files)

    @staticmethod
    def _scan(folder, kw):
        real = paths.translate(folder)
        try:
            if '://' in real:
                import xbmcvfs
                _dirs, names = xbmcvfs.listdir(real)
            else:
                names = [n for n in os.listdir(real) if os.path.isfile(os.path.join(real, n))]
        except Exception as exc:
            debug('Cannot list %s: %s' % (real, exc))
            return []
        hits = [n for n in names if kw in n.lower() and n.lower().endswith(paths.AUDIO_EXTENSIONS)]
        hits.sort(key=natural_key)
        found = [paths.join(real, n) for n in hits]
        debug('Theme scan %s -> %d file(s)' % (real, len(found)))
        return found


def make_playable(path):
    """mpv cannot read smb:// etc., so copy network files to the temp folder first."""
    if '://' not in path:
        return path
    try:
        import xbmcvfs
        tmp = xbmcvfs.translatePath('special://temp/service.cinemathemes/')
        os.makedirs(tmp, exist_ok=True)
        ext = os.path.splitext(path)[1]
        dst = os.path.join(tmp, hashlib.md5(path.encode('utf-8')).hexdigest() + ext)
        if not os.path.exists(dst) and not xbmcvfs.copy(path, dst):
            log('Could not copy %s for playback' % path)
            return None
        return dst
    except Exception as exc:
        log('Could not prepare %s for playback: %s' % (path, exc))
        return None
