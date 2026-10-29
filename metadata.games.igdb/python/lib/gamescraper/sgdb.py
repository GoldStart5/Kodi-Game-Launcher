"""SteamGridDB API v2 client."""
import re

BASE_URL = 'https://www.steamgriddb.com/api/v2'


PAGE_SIZE = 50          # SteamGridDB returns up to 50 items per page
MAX_PAGES = 4           # 200 images per type is plenty; keeps scrapes quick
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')

# Filters, widest first. By default the API hides art flagged as humor or
# epilepsy-risk, so ask for "any"; if the API rejects a value, retry looser.
PARAM_TIERS = (
    {'nsfw': 'false', 'humor': 'any', 'epilepsy': 'any'},
    {'nsfw': 'false'},
    {},
)


class SGDBError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def is_image(url):
    """Kodi can show still images; SteamGridDB also hosts animated .webm/.mp4 art."""
    return (url or '').lower().split('?')[0].endswith(IMAGE_EXTENSIONS)


def normalize(text):
    return re.sub(r'[^a-z0-9]+', '', (text or '').lower())


class SGDBClient:
    def __init__(self, api_key, cache, session, log=None):
        self.api_key = api_key
        self.cache = cache
        self.session = session
        self.log = log or (lambda msg: None)

    def _get(self, path, params=None):
        cache_key = 'sgdb:%s:%s' % (path, sorted((params or {}).items()))
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            resp = self.session.get(
                BASE_URL + path, params=params or {},
                headers={'Authorization': 'Bearer ' + self.api_key}, timeout=15)
        except Exception as exc:  # noqa: BLE001
            raise SGDBError('Cannot reach SteamGridDB: %s' % exc)
        if resp.status_code == 404:
            self.cache.set(cache_key, [])
            return []
        if resp.status_code in (401, 403):
            raise SGDBError('SteamGridDB rejected the API key')
        if resp.status_code != 200:
            raise SGDBError('SteamGridDB error HTTP %s' % resp.status_code, resp.status_code)
        payload = resp.json()
        if not payload.get('success', False):
            return []
        data = payload.get('data') or []
        self.cache.set(cache_key, data)
        return data

    def search(self, term):
        """Return [{'id', 'name', 'release_date', ...}] best match first."""
        term = (term or '').strip().replace('/', ' ')
        if not term:
            return []
        results = self._get('/search/autocomplete/' + term)
        wanted = normalize(term)
        return [r for _, r in sorted(
            enumerate(results),
            key=lambda pair: (normalize(pair[1].get('name')) != wanted, pair[0]))]

    def _paged(self, path, params):
        items, seen = [], set()
        for page in range(MAX_PAGES):
            query = dict(params)
            if page:
                query['page'] = page
            chunk = self._get(path, query)
            fresh = [i for i in chunk if i.get('id') not in seen]
            if not fresh:  # past the end (or an API that ignores `page`)
                break
            items += fresh
            seen.update(i.get('id') for i in fresh)
            if len(chunk) < PAGE_SIZE:
                break
        return items

    def assets(self, kind, steam_appid=None, game_id=None):
        """kind: grids | heroes | logos | icons. Steam id first, then SGDB game id.

        Returns every usable still image (all pages), best-scored first.
        """
        items = []
        for params in PARAM_TIERS:
            try:
                if steam_appid:
                    items = self._paged('/%s/steam/%s' % (kind, steam_appid), params)
                if not items and game_id:
                    # game_id may be a callable so the search only happens when needed
                    resolved = game_id() if callable(game_id) else game_id
                    if resolved:
                        items = self._paged('/%s/game/%s' % (kind, resolved), params)
                break
            except SGDBError as exc:
                if exc.status != 400:
                    raise
                self.log('SteamGridDB rejected filters %s, retrying with fewer' % params)
        # keep stills; an .ico icon is kept too when it has a PNG thumbnail Kodi can show
        items = [i for i in items if i.get('url') and not i.get('nsfw')
                 and (is_image(i['url']) or (i['url'].lower().endswith('.ico') and is_image(i.get('thumb'))))]
        return sorted(items, key=lambda i: i.get('score') or 0, reverse=True)
