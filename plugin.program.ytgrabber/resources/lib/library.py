# -*- coding: utf-8 -*-
"""Read movies / TV shows from the Kodi library and work out target folders."""
import json
import posixpath
import re

import xbmc


def _rpc(method, params):
    req = {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}
    resp = json.loads(xbmc.executeJSONRPC(json.dumps(req)))
    return resp.get('result', {})


def _art(d):
    art = d.get('art') or {}
    return {k: v for k, v in art.items() if k in ('poster', 'fanart', 'thumb', 'banner', 'clearlogo')}


def _movie(m):
    return {'type': 'movie', 'id': m.get('movieid'), 'title': m.get('title', ''),
            'year': m.get('year') or 0, 'file': m.get('file', ''),
            'plot': m.get('plot', ''), 'art': _art(m)}


def _show(s):
    return {'type': 'tvshow', 'id': s.get('tvshowid'), 'title': s.get('title', ''),
            'year': s.get('year') or 0, 'file': s.get('file', ''),
            'plot': s.get('plot', ''), 'art': _art(s)}


_MP = ['title', 'year', 'file', 'art', 'plot']


def get_movies():
    res = _rpc('VideoLibrary.GetMovies', {
        'properties': _MP, 'sort': {'method': 'sorttitle', 'ignorearticle': True}})
    return [_movie(m) for m in res.get('movies', [])]


def get_tvshows():
    res = _rpc('VideoLibrary.GetTVShows', {
        'properties': _MP, 'sort': {'method': 'sorttitle', 'ignorearticle': True}})
    return [_show(s) for s in res.get('tvshows', [])]


def get_item(kind, item_id):
    item_id = int(item_id)
    if kind == 'movie':
        res = _rpc('VideoLibrary.GetMovieDetails', {'movieid': item_id, 'properties': _MP})
        return _movie(res['moviedetails']) if 'moviedetails' in res else None
    res = _rpc('VideoLibrary.GetTVShowDetails', {'tvshowid': item_id, 'properties': _MP})
    return _show(res['tvshowdetails']) if 'tvshowdetails' in res else None


def _split(path):
    """Split a Kodi path (any scheme, / or \\ separators) into (dir, name)."""
    path = path.rstrip('/\\')
    idx = max(path.rfind('/'), path.rfind('\\'))
    if idx < 0:
        return '', path
    return path[:idx + 1], path[idx + 1:]


def _first_stack_part(path):
    if path.startswith('stack://'):
        return path[len('stack://'):].split(' , ')[0]
    return path


def _strip_ext(name):
    return name.rsplit('.', 1)[0] if '.' in name else name


_STACK_RE = re.compile(r'[ ._\-]*(cd|dvd|part|pt|disc|disk)[ ._\-]*\d+$', re.I)


def movie_target(item):
    """Return (folder, base_name) for a movie.

    folder always ends with a separator. base_name is the video file name
    without extension (or the disc folder name for BDMV / VIDEO_TS rips).
    """
    path = _first_stack_part(item['file'])
    # Disc images played through bluray:// or similar wrappers
    folder, name = _split(path)
    low = path.lower().replace('\\', '/')
    if '/bdmv/' in low or '/video_ts/' in low:
        idx = low.rfind('/bdmv/')
        if idx < 0:
            idx = low.rfind('/video_ts/')
        root = path[:idx + 1]
        parent, disc_name = _split(root)
        return root, disc_name
    base = _STACK_RE.sub('', _strip_ext(name))
    return folder, base


def tvshow_target(item):
    path = item['file']
    sep = '\\' if ('\\' in path and '/' not in path) else '/'
    if not path.endswith(('/', '\\')):
        path += sep
    parent, name = _split(path)
    return path, name


def target_for(item):
    return movie_target(item) if item['type'] == 'movie' else tvshow_target(item)


def display_name(item):
    if item.get('year'):
        return '%s (%s)' % (item['title'], item['year'])
    return item['title']
