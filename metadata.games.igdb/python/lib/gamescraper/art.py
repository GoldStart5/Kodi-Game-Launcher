"""Artwork selection: every picture comes from SteamGridDB.

IGDB supplies metadata only. Its images are used purely as a fallback for an
art type when SteamGridDB has nothing at all for that type (optional setting).

SteamGridDB -> Kodi art types
    grids, portrait          -> poster   (style "no_logo" also -> keyart)
    grids, wide (Steam-like) -> landscape
    grids, squarish          -> thumb
    heroes                   -> fanart and banner (images are used exactly as SteamGridDB serves them)
    logos                    -> clearlogo
    icons                    -> icon
"""
import threading
from concurrent.futures import ThreadPoolExecutor

from .igdb import image_url
from .sgdb import SGDBError, is_image

ART_TYPES = ('poster', 'keyart', 'landscape', 'thumb', 'banner', 'clearlogo', 'icon')


def classify_grid(width, height):
    """Which Kodi art type a grid belongs to, judged by its shape."""
    if not width or not height:
        return 'poster'
    if height / width >= 1.2:
        return 'poster'
    if width / height >= 1.6:
        return 'landscape'
    return 'thumb'


def _entry(item):
    return {'url': item['url'], 'preview': item.get('thumb') or item['url']}


def _icon_entry(icon):
    url = icon['url']
    if url.lower().endswith('.ico'):
        # Kodi can't display .ico; the API's PNG thumbnail is fine
        thumb = icon.get('thumb') or ''
        if not is_image(thumb):
            return None
        url = thumb
    return {'url': url, 'preview': icon.get('thumb') or url}


def _fetch_sgdb(name, steam, sgdb_game_id, sgdb, log, warnings):
    """Fetch heroes/grids/logos/icons side by side; returns {kind: [items]}."""
    resolved = {}
    lock = threading.Lock()

    def game_id():
        if sgdb_game_id:
            return sgdb_game_id
        with lock:  # several kinds may need it at once; search only once
            if 'id' not in resolved:
                results = sgdb.search(name)
                resolved['id'] = results[0]['id'] if results else None
            return resolved['id']

    def fetch(kind):
        try:
            return kind, sgdb.assets(kind, steam, game_id)
        except SGDBError as exc:
            log('SteamGridDB %s failed: %s' % (kind, exc))
            if str(exc) not in warnings:
                warnings.append(str(exc))
            return kind, []

    with ThreadPoolExecutor(max_workers=4) as pool:
        return dict(pool.map(fetch, ('heroes', 'grids', 'logos', 'icons')))


def collect(name, game, steam, sgdb_game_id, sgdb, settings, log):
    """Return {'art': {type: [{'url','preview'}]}, 'fanart': [...], 'warnings': [...]}."""
    max_art = settings.get_int('max_art', 30) or 30
    max_fanart = settings.get_int('max_fanart', 15) or 15

    art = {kind: [] for kind in ART_TYPES}
    candidates = []   # fanart candidates, best first
    warnings = []

    if sgdb:
        found = _fetch_sgdb(name, steam, sgdb_game_id, sgdb, log, warnings)

        for grid in found['grids']:
            kind = classify_grid(grid.get('width'), grid.get('height'))
            art[kind].append(_entry(grid))
            if kind == 'poster' and (grid.get('style') or '') == 'no_logo':
                art['keyart'].append(_entry(grid))
        for hero in found['heroes']:
            candidates.append({'url': hero['url'], 'preview': hero.get('thumb') or hero['url'],
                               'w': hero.get('width'), 'h': hero.get('height')})
            art['banner'].append(_entry(hero))
        art['clearlogo'] = [_entry(logo) for logo in found['logos']]
        art['icon'] = [e for e in map(_icon_entry, found['icons']) if e]

    if game and settings.get_bool('igdb_art_fallback'):
        _igdb_fallback(game, art, candidates)

    fanart = [{'url': c['url'], 'preview': c['preview']} for c in candidates[:max_fanart]]
    return {'art': {kind: entries[:max_art] for kind, entries in art.items() if entries},
            'fanart': fanart, 'warnings': warnings}


def _igdb_fallback(game, art, candidates):
    """Fill art types SteamGridDB left empty with IGDB's own images."""
    cover = (game.get('cover') or {}).get('image_id')
    if cover and not art['poster']:
        art['poster'].append({'url': image_url(cover, '720p'),
                              'preview': image_url(cover, 'cover_big')})
    shots = [s for s in (game.get('artworks') or []) + (game.get('screenshots') or []) if s.get('image_id')]
    if shots and not candidates:
        candidates.extend({'url': image_url(s['image_id'], '1080p'),
                           'preview': image_url(s['image_id'], 'screenshot_med'),
                           'w': s.get('width'), 'h': s.get('height')} for s in shots)
    if shots and not art['landscape']:
        art['landscape'] = [{'url': image_url(s['image_id'], 'screenshot_huge'),
                             'preview': image_url(s['image_id'], 'screenshot_med')} for s in shots]
