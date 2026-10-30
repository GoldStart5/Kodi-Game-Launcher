"""Artwork selection: every picture comes from SteamGridDB.

IGDB supplies metadata. Its images are used for:
  * poster / landscape, only when SteamGridDB has none (optional setting);
  * fanart, (a) always when no SteamGridDB hero matches the chosen size, and
    (b) optionally mixed into the list alongside the heroes, in reserved slots.

SteamGridDB -> Kodi art types
    grids, portrait          -> poster   (style "no_logo" also -> keyart)
    grids, wide (Steam-like) -> landscape
    grids, squarish          -> thumb
    heroes                   -> fanart and banner, limited to the chosen size(s); used exactly as served
    logos                    -> clearlogo
    icons                    -> icon
"""
import threading
from concurrent.futures import ThreadPoolExecutor

from .igdb import image_url
from .sgdb import SGDBError, is_image

ART_TYPES = ('poster', 'keyart', 'landscape', 'thumb', 'banner', 'clearlogo', 'icon')

# SteamGridDB hero sizes the user can choose between (setting "hero_size")
HERO_SIZES = {
    '3840x1240': {(3840, 1240)},
    '1920x620': {(1920, 620)},
    'both': {(3840, 1240), (1920, 620)},
}
DEFAULT_HERO_SIZE = '3840x1240'

# IGDB images mixed into the fanart list alongside the heroes (setting "fanart_igdb")
IGDB_NONE, IGDB_ARTWORKS, IGDB_BOTH = 'none', 'artworks', 'both'
DEFAULT_IGDB_SLOTS = 25


def classify_grid(width, height):
    """Which Kodi art type a grid belongs to, judged by its shape."""
    if not width or not height:
        return 'poster'
    if height / width >= 1.2:
        return 'poster'
    if width / height >= 1.6:
        return 'landscape'
    return 'thumb'


def hero_matches(hero, sizes):
    """True if the hero has one of the wanted sizes.

    A hero SteamGridDB reports without a size cannot be judged, so it is kept.
    """
    width, height = hero.get('width'), hero.get('height')
    if not width or not height:
        return True
    return (width, height) in sizes


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
    max_fanart = settings.get_int('max_fanart', 50) or 50
    sizes = HERO_SIZES.get(settings.get_str('hero_size', DEFAULT_HERO_SIZE), HERO_SIZES[DEFAULT_HERO_SIZE])

    art = {kind: [] for kind in ART_TYPES}
    heroes = []       # SteamGridDB fanart candidates, best first
    warnings = []

    if sgdb:
        found = _fetch_sgdb(name, steam, sgdb_game_id, sgdb, log, warnings)

        for grid in found['grids']:
            kind = classify_grid(grid.get('width'), grid.get('height'))
            art[kind].append(_entry(grid))
            if kind == 'poster' and (grid.get('style') or '') == 'no_logo':
                art['keyart'].append(_entry(grid))
        for hero in found['heroes']:
            if not hero_matches(hero, sizes):
                continue
            heroes.append(_entry(hero))
            art['banner'].append(_entry(hero))
        art['clearlogo'] = [_entry(logo) for logo in found['logos']]
        art['icon'] = [e for e in map(_icon_entry, found['icons']) if e]

    if game and settings.get_bool('igdb_art_fallback'):
        _igdb_fallback(game, art)

    fanart = _fanart_list(heroes, game, settings, max_fanart)
    return {'art': {kind: entries[:max_art] for kind, entries in art.items() if entries},
            'fanart': fanart, 'warnings': warnings}


def _igdb_images(game, include_screenshots, include_artworks=True):
    """IGDB artworks then screenshots as fanart entries (1080p, as served)."""
    if not game:
        return []
    sources = []
    if include_artworks:
        sources += game.get('artworks') or []
    if include_screenshots:
        sources += game.get('screenshots') or []
    return [{'url': image_url(s['image_id'], '1080p'),
             'preview': image_url(s['image_id'], 'screenshot_med')}
            for s in sources if s.get('image_id')]


def _fanart_list(heroes, game, settings, max_fanart):
    """SteamGridDB heroes, plus IGDB images in reserved slots when that is switched on.

    * No hero of the chosen size: IGDB artworks and screenshots are used instead
      (always, whatever else is set).
    * IGDB mixing on: heroes first, then IGDB artworks, then screenshots. IGDB gets at
      least ``igdb_fanart_slots`` places (so a long list of heroes cannot push every IGDB
      image off the end) and also any places the heroes leave unused; at least one
      place always stays with the heroes.
    """
    if not heroes:
        return _igdb_images(game, include_screenshots=True)[:max_fanart]

    mode = settings.get_str('fanart_igdb', IGDB_BOTH)
    if mode not in (IGDB_ARTWORKS, IGDB_BOTH):
        return heroes[:max_fanart]
    extra = _igdb_images(game, include_screenshots=(mode == IGDB_BOTH))
    if not extra:
        return heroes[:max_fanart]

    slots = settings.get_int('igdb_fanart_slots', DEFAULT_IGDB_SLOTS) or DEFAULT_IGDB_SLOTS
    igdb_count = min(len(extra), max(slots, max_fanart - len(heroes)), max(max_fanart - 1, 0))
    hero_count = min(len(heroes), max_fanart - igdb_count)
    return heroes[:hero_count] + extra[:igdb_count]


def _igdb_fallback(game, art):
    """Fill poster / landscape that SteamGridDB left empty with IGDB's own images."""
    cover = (game.get('cover') or {}).get('image_id')
    if cover and not art['poster']:
        art['poster'].append({'url': image_url(cover, '720p'),
                              'preview': image_url(cover, 'cover_big')})
    shots = [s for s in (game.get('artworks') or []) + (game.get('screenshots') or []) if s.get('image_id')]
    if shots and not art['landscape']:
        art['landscape'] = [{'url': image_url(s['image_id'], 'screenshot_huge'),
                             'preview': image_url(s['image_id'], 'screenshot_med')} for s in shots]
