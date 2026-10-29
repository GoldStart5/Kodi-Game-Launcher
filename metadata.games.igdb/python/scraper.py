"""Kodi movie-scraper entry point: games from IGDB, art from IGDB + SteamGridDB."""
import json
import os
import re
import sys
import time
from urllib.parse import parse_qsl

import requests
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from lib.gamescraper import art as art_module
from lib.gamescraper import mapping
from lib.gamescraper.cache import FileCache
from lib.gamescraper.igdb import ApiError, IGDBClient, image_url, release_year
from lib.gamescraper.sgdb import SGDBClient, SGDBError
from lib.gamescraper.settings import Settings

# Kodi keeps this Python process alive between scrapes (reuselanguageinvoker), so
# anything created at import time goes stale. Never keep an xbmcaddon.Addon() here:
# it is a snapshot and would not see settings saved after the first scrape.
ADDON_ID = 'metadata.games.igdb'
SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'Kodi-%s' % ADDON_ID
CREDENTIAL_KEYS = ('igdb_client_id', 'igdb_client_secret', 'sgdb_api_key')


def log(msg, level=xbmc.LOGDEBUG):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


def warn(msg):
    log(msg, xbmc.LOGWARNING)


def notify(msg):
    warn(msg)
    xbmcgui.Dialog().notification('IGDB + SteamGridDB scraper', msg, xbmcgui.NOTIFICATION_WARNING)


class Context:
    """Clients and folders for one scraper invocation."""

    def __init__(self, settings, addon):
        self.settings = settings
        profile = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        cache = FileCache(os.path.join(profile, 'cache'))
        creds, source = _load_credentials(settings, profile)
        client_id, client_secret = creds['igdb_client_id'], creds['igdb_client_secret']
        sgdb_key = creds['sgdb_api_key']
        log('credentials found: igdb=%s sgdb=%s (%s)' % (
            bool(client_id and client_secret), bool(sgdb_key), source), xbmc.LOGINFO)
        self.igdb = (IGDBClient(client_id, client_secret, cache, SESSION, log)
                     if client_id and client_secret else None)
        self.sgdb = SGDBClient(sgdb_key, cache, SESSION, log) if sgdb_key else None


def _load_credentials(settings, profile):
    """Keys from Kodi settings (per-source, then global); fall back to credentials.json.

    Any key Kodi gives us is also written to credentials.json in the add-on's data
    folder, so scraping keeps working even if Kodi's own settings storage loses
    them. You can also create that file by hand:
    {"igdb_client_id": "...", "igdb_client_secret": "...", "sgdb_api_key": "..."}
    """
    path = os.path.join(profile, 'credentials.json')
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            stored = json.load(handle)
        if not isinstance(stored, dict):
            stored = {}
    except (OSError, ValueError):
        stored = {}

    creds, sources, dirty = {}, set(), False
    for key in CREDENTIAL_KEYS:
        value = settings.credential(key)
        if value:
            sources.add('kodi settings')
            if stored.get(key) != value:
                stored[key] = value
                dirty = True
        else:
            value = str(stored.get(key) or '').strip()
            if value:
                sources.add('credentials.json')
        creds[key] = value

    if dirty:
        try:
            os.makedirs(profile, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as handle:
                json.dump(stored, handle)
            os.chmod(path, 0o600)
        except OSError as exc:
            warn('Could not save credentials.json: %s' % exc)
    return creds, ', '.join(sorted(sources)) or 'none'


def lookup_string(ids):
    return json.dumps(ids)


def parse_lookup(text):
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except (TypeError, ValueError):
        warn("Can't parse lookup string (from another add-on?): %s" % text)
        return None


# -- find ----------------------------------------------------------------------

def _clean_title(title):
    title = title.replace('_', ' ')
    return re.sub(r'\s+', ' ', title).strip()


def _search_igdb(ctx, title, year):
    results = ctx.igdb.search(title, year)
    if not results:
        # "Game: Subtitle" / "Game - Subtitle" often matches under the short name only
        short = re.split(r'\s*(?::| - )\s*', title, maxsplit=1)[0]
        if short and short != title:
            results = ctx.igdb.search(short, year)
    return results


def find(handle, title, year, ctx):
    title = _clean_title(title)
    log("Find '%s' (%s)" % (title, year), xbmc.LOGINFO)
    found = False

    if ctx.igdb:
        try:
            for game in _search_igdb(ctx, title, year):
                label = game['name']
                game_year = release_year(game)
                if game_year:
                    label += ' (%d)' % game_year
                item = xbmcgui.ListItem(label, offscreen=True)
                tag = item.getVideoInfoTag()
                tag.setTitle(game['name'])
                if game_year:
                    tag.setYear(game_year)
                cover = (game.get('cover') or {}).get('image_id')
                if cover:
                    item.setArt({'thumb': image_url(cover, 'cover_big')})
                xbmcplugin.addDirectoryItem(handle, lookup_string({'igdb': str(game['id'])}), item, True)
                found = True
        except ApiError as exc:
            notify(str(exc))
    elif ctx.sgdb:
        notify('IGDB Client ID/Secret not found - using SteamGridDB only. See credentials.json in the add-on data folder')
    else:
        notify('IGDB Client ID/Secret not found - set them in the scraper settings or in credentials.json')

    if not found and ctx.sgdb:
        try:
            for result in ctx.sgdb.search(title)[:10]:
                ids = {'sgdb': str(result['id']), 'name': result.get('name', title)}
                label = result.get('name', title)
                stamp = result.get('release_date')
                if stamp:
                    ids['year'] = time.gmtime(stamp).tm_year
                    label += ' (%d)' % ids['year']
                item = xbmcgui.ListItem(label, offscreen=True)
                item.getVideoInfoTag().setTitle(ids['name'])
                xbmcplugin.addDirectoryItem(handle, lookup_string(ids), item, True)
        except SGDBError as exc:
            notify(str(exc))


# -- NFO -----------------------------------------------------------------------

def nfo_url(handle, nfo):
    ids = {}
    match = re.search(r'igdb\.com/games/([a-z0-9\-_]+)', nfo, re.I)
    if match:
        ids['igdb_slug'] = match.group(1)
    match = re.search(r'<uniqueid[^>]*type="igdb"[^>]*>\s*(\d+)\s*<', nfo, re.I)
    if match:
        ids['igdb'] = match.group(1)
    if ids:
        xbmcplugin.addDirectoryItem(handle, lookup_string(ids), xbmcgui.ListItem(offscreen=True), True)


# -- getdetails ----------------------------------------------------------------

def _set_art(item, collected):
    tag = item.getVideoInfoTag()
    for art_type, entries in collected['art'].items():
        for entry in entries:
            try:
                tag.addAvailableArtwork(entry['url'], art_type, preview=entry['preview'])
            except TypeError:
                tag.addAvailableArtwork(entry['url'], art_type)
    if collected['fanart']:
        # setAvailableFanart wants {'image', 'preview'}, unlike addAvailableArtwork
        item.setAvailableFanart([{'image': f['url'], 'preview': f['preview']}
                                 for f in collected['fanart']])


def get_details(handle, ids, ctx, silent=False):
    game = None
    try:
        if ctx.igdb and ids.get('igdb'):
            game = ctx.igdb.get_game(ids['igdb'])
        elif ctx.igdb and ids.get('igdb_slug'):
            game = ctx.igdb.get_game_by_slug(ids['igdb_slug'])
    except ApiError as exc:
        if not silent:
            notify(str(exc))
        return False

    if game:
        details = mapping.igdb_to_details(game, ctx.settings)
        name, steam = game.get('name', ''), mapping.steam_appid(game)
    elif ids.get('sgdb') and ctx.sgdb:
        name = ids.get('name', '')
        info = {'title': name, 'originaltitle': name}
        if ids.get('year'):
            info['year'] = int(ids['year'])
        details = {'info': info, 'uniqueids': {'sgdb': str(ids['sgdb'])},
                   'ratings': {}, 'default_rating': None}
        steam = None
    else:
        return False

    collected = art_module.collect(
        name, game, steam, ids.get('sgdb'), ctx.sgdb, ctx.settings, log)

    if collected['warnings'] and not silent:
        notify(collected['warnings'][0])

    info = details['info']
    item = xbmcgui.ListItem(info['title'], offscreen=True)
    tag = item.getVideoInfoTag()
    tag.setTitle(info['title'])
    tag.setOriginalTitle(info.get('originaltitle', info['title']))
    if info.get('plot'):
        tag.setPlot(info['plot'])
        tag.setPlotOutline(info.get('plotoutline', ''))
    if info.get('genre'):
        tag.setGenres(info['genre'])
    if info.get('studio'):
        tag.setStudios(info['studio'])
    if info.get('year'):
        tag.setYear(info['year'])
    if info.get('premiered'):
        tag.setPremiered(info['premiered'])
    if info.get('tag'):
        tag.setTags(info['tag'])
    if info.get('trailer'):
        tag.setTrailer(info['trailer'])
    if details['uniqueids']:
        default = 'igdb' if 'igdb' in details['uniqueids'] else next(iter(details['uniqueids']))
        tag.setUniqueIDs(details['uniqueids'], default)
    if details['ratings']:
        tag.setRatings({k: (v['rating'], v.get('votes', 0)) for k, v in details['ratings'].items()},
                       details['default_rating'])
    _set_art(item, collected)

    xbmcplugin.setResolvedUrl(handle, True, item)
    return True


# -- dispatch ------------------------------------------------------------------

def run():
    argv = sys.argv[1:]
    handle = int(argv[0])
    params = dict(parse_qsl(argv[1].lstrip('?'))) if len(argv) > 1 and argv[1] else {}
    enddir = True

    action = params.get('action')
    if not action:
        warn("No action in params")
    else:
        path_settings = None
        if params.get('pathSettings'):
            try:
                path_settings = json.loads(params['pathSettings'])
            except ValueError:
                warn('Bad pathSettings: %s' % params['pathSettings'])
        log('action=%s, per-source settings received: %s' % (
            action, sorted(path_settings) if isinstance(path_settings, dict) else 'none'), xbmc.LOGINFO)
        addon = xbmcaddon.Addon()  # fresh every call, see note at the top
        ctx = Context(Settings(addon, path_settings), addon)

        if action == 'find' and 'title' in params:
            find(handle, params['title'], params.get('year'), ctx)
        elif action == 'getdetails' and ('url' in params or 'uniqueIDs' in params):
            ids = parse_lookup(params.get('uniqueIDs') or params.get('url'))
            if ids:
                enddir = not get_details(handle, ids, ctx, silent='uniqueIDs' in params)
        elif action == 'NfoUrl' and 'nfo' in params:
            nfo_url(handle, params['nfo'])
        else:
            warn('Unhandled action: %s' % action)

    if enddir:
        xbmcplugin.endOfDirectory(handle)


if __name__ == '__main__':
    run()
