"""Map an IGDB game record to the fields Kodi's video info tag understands."""
import re
import time

STEAM_URL = re.compile(r'store\.steampowered\.com/app/(\d+)')


def steam_appid(game):
    for site in game.get('websites') or []:
        match = STEAM_URL.search(site.get('url') or '')
        if match:
            return match.group(1)
    return None


def _names(items):
    return [i['name'] for i in (items or []) if i.get('name')]


def _companies(game, role):
    return [c['company']['name'] for c in (game.get('involved_companies') or [])
            if c.get(role) and (c.get('company') or {}).get('name')]


def _dedupe(values):
    seen, out = set(), []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def igdb_to_details(game, settings):
    """Return {'info', 'uniqueids', 'ratings', 'default_rating'}."""
    plot = game.get('summary') or ''
    storyline = game.get('storyline') or ''
    if storyline and settings.get_bool('append_storyline'):
        plot = (plot + '\n\n' + storyline).strip()

    info = {
        'title': game.get('name') or '',
        'originaltitle': game.get('name') or '',
        'plot': plot,
        'plotoutline': (game.get('summary') or '').split('\n')[0][:300],
        'genre': _names(game.get('genres')),
    }

    studios = _companies(game, 'developer')
    if settings.get_bool('include_publisher'):
        studios += _companies(game, 'publisher')
    info['studio'] = _dedupe(studios)

    stamp = game.get('first_release_date')
    if stamp:
        moment = time.gmtime(stamp)
        info['year'] = moment.tm_year
        info['premiered'] = time.strftime('%Y-%m-%d', moment)

    if settings.get_bool('game_tags'):
        info['tag'] = _dedupe(_names(game.get('themes')) + _names(game.get('game_modes'))
                              + _names(game.get('player_perspectives')))

    if settings.get_bool('trailer'):
        for video in game.get('videos') or []:
            if video.get('video_id'):
                info['trailer'] = 'plugin://plugin.video.youtube/play/?video_id=%s' % video['video_id']
                break

    ratings = {}
    score = game.get('total_rating') or game.get('rating')
    if score:
        votes = game.get('total_rating_count') or 0
        ratings['igdb'] = {'rating': round(score / 10.0, 1), 'votes': votes}

    uniqueids = {'igdb': str(game['id'])} if 'id' in game else {}
    steam = steam_appid(game)
    if steam:
        uniqueids['steam'] = steam

    return {
        'info': info,
        'uniqueids': uniqueids,
        'ratings': ratings,
        'default_rating': 'igdb' if ratings else None,
    }
