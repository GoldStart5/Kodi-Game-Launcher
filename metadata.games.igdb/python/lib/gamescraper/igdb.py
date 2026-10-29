"""IGDB v4 client (Twitch OAuth client-credentials + Apicalypse queries)."""
import difflib
import re
import time

TOKEN_URL = 'https://id.twitch.tv/oauth2/token'
API_URL = 'https://api.igdb.com/v4/'
IMAGE_URL = 'https://images.igdb.com/igdb/image/upload/t_{size}/{image_id}.jpg'

# IGDB allows 4 requests/second per Client-ID; stay just under it.
MIN_INTERVAL = 0.27
TOKEN_SAFETY_MARGIN = 3600  # refresh one hour before expiry

# Every field here is long-standing in the v4 API. Anything that has been
# renamed over time (category/game_type, age ratings, external games) is left
# out on purpose: one unknown field makes IGDB reject the *whole* query.
FULL_FIELDS = (
    'name,slug,summary,storyline,first_release_date,rating,total_rating,'
    'total_rating_count,'
    'genres.name,themes.name,game_modes.name,player_perspectives.name,'
    'involved_companies.developer,involved_companies.publisher,'
    'involved_companies.company.name,'
    'cover.image_id,cover.width,cover.height,'
    'artworks.image_id,artworks.width,artworks.height,'
    'screenshots.image_id,screenshots.width,screenshots.height,'
    'videos.video_id,websites.url'
)
MINIMAL_FIELDS = 'name,slug,summary,first_release_date,total_rating,cover.image_id'
SEARCH_FIELDS = 'name,slug,first_release_date,cover.image_id'


# IGDB game types that are real, standalone games (not DLC, skins, bundles, mods...):
# 0 main game, 4 standalone expansion, 8 remake, 9 remaster, 10 expanded game, 11 port
REAL_GAME_TYPES = (0, 4, 8, 9, 10, 11)


class ApiError(Exception):
    """Raised for failures the user should hear about (bad keys, no network...)."""


def image_url(image_id, size):
    return IMAGE_URL.format(size=size, image_id=image_id)


def normalize(text):
    return re.sub(r'[^a-z0-9]+', '', (text or '').lower())


def _quote(text):
    return text.replace('\\', ' ').replace('"', ' ').strip()


def rank_results(results, title, year=None):
    """Order candidates: exact name, then closest name, matching year as tie-break."""
    wanted = normalize(title)
    wanted_year = int(year) if year else None

    def key(pair):
        index, game = pair
        name = normalize(game.get('name'))
        return (name != wanted,
                -difflib.SequenceMatcher(None, wanted, name).ratio(),
                wanted_year is not None and release_year(game) != wanted_year,
                index)

    return [game for _, game in sorted(enumerate(results), key=key)]


def release_year(game):
    stamp = game.get('first_release_date')
    if not stamp:
        return None
    return time.gmtime(stamp).tm_year


class IGDBClient:
    def __init__(self, client_id, client_secret, cache, session, log=None,
                 sleep=time.sleep, clock=time.time):
        self.client_id = client_id
        self.client_secret = client_secret
        self.cache = cache
        self.session = session
        self.log = log or (lambda msg: None)
        self._sleep = sleep
        self._clock = clock
        self._last_call = 0.0
        self._token = None

    # -- auth ------------------------------------------------------------
    def _load_token(self):
        stored = self.cache.get('igdb_token:' + self.client_id, ttl=10 * 365 * 86400)
        if stored and stored.get('expires_at', 0) - TOKEN_SAFETY_MARGIN > self._clock():
            return stored['access_token']
        return None

    def _fetch_token(self):
        try:
            resp = self.session.post(TOKEN_URL, params={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'client_credentials',
            }, timeout=15)
        except Exception as exc:  # noqa: BLE001 - network errors vary
            raise ApiError('Cannot reach Twitch to authenticate IGDB: %s' % exc)
        if resp.status_code in (400, 401, 403):
            raise ApiError('Twitch rejected the IGDB Client ID / Secret')
        if resp.status_code != 200:
            raise ApiError('Twitch auth failed (HTTP %s)' % resp.status_code)
        data = resp.json()
        token = data['access_token']
        self.cache.set('igdb_token:' + self.client_id, {
            'access_token': token,
            'expires_at': self._clock() + int(data.get('expires_in', 0)),
        })
        return token

    def _get_token(self, force=False):
        if not force:
            if self._token:
                return self._token
            self._token = self._load_token()
            if self._token:
                return self._token
        self._token = self._fetch_token()
        return self._token

    # -- transport -------------------------------------------------------
    def _throttle(self):
        wait = MIN_INTERVAL - (self._clock() - self._last_call)
        if wait > 0:
            self._sleep(wait)
        self._last_call = self._clock()

    def query(self, endpoint, body):
        cache_key = 'igdb:%s:%s' % (endpoint, body)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        refreshed = False
        for attempt in range(4):
            token = self._get_token()
            self._throttle()
            try:
                resp = self.session.post(
                    API_URL + endpoint, data=body.encode('utf-8'),
                    headers={'Client-ID': self.client_id,
                             'Authorization': 'Bearer ' + token,
                             'Accept': 'application/json'},
                    timeout=15)
            except Exception as exc:  # noqa: BLE001
                raise ApiError('Cannot reach IGDB: %s' % exc)
            if resp.status_code == 200:
                data = resp.json()
                self.cache.set(cache_key, data)
                return data
            if resp.status_code == 401 and not refreshed:
                refreshed = True
                self._get_token(force=True)
                continue
            if resp.status_code == 429:
                self._sleep(1.0 + attempt)
                continue
            raise ApiError('IGDB error HTTP %s: %s' % (resp.status_code, resp.text[:200]))
        raise ApiError('IGDB is rate limiting requests, try again later')

    def _query_with_fallback(self, endpoint, bodies):
        """Try each body in turn; only HTTP 400 (bad query) moves to the next."""
        last = None
        for body in bodies:
            try:
                return self.query(endpoint, body)
            except ApiError as exc:
                last = exc
                if 'HTTP 400' not in str(exc):
                    raise
                self.log('IGDB rejected query (%s), trying a simpler one' % exc)
        raise last

    # -- high level ------------------------------------------------------
    def search(self, title, year=None, limit=30):
        """Find games, with the actual game ahead of DLC, skins and add-ons.

        IGDB's text search happily returns every DLC and cosmetic pack whose name
        contains the title, and with a short limit those crowd out the game itself.
        So: ask only for real games (main game, standalone expansion, remake,
        remaster, expanded edition, port), over a wider net, and rank by how
        closely the name matches. ``game_type`` is IGDB's current field and
        ``category`` the deprecated one; if both are rejected we fall back to an
        unfiltered query and rely on the ranking.
        """
        term = _quote(title)
        if not term:
            return []
        kinds = '(%s)' % ','.join(str(k) for k in REAL_GAME_TYPES)
        tiers = [
            'where game_type = %s & version_parent = null' % kinds,
            'where category = %s & version_parent = null' % kinds,
            'where version_parent = null',
            '',
        ]
        results = []
        for clause in tiers:
            body = 'search "%s"; fields %s; %s limit %d;' % (term, SEARCH_FIELDS, clause + ';' if clause else '', limit)
            try:
                results = self.query('games', body)
            except ApiError as exc:
                if 'HTTP 400' not in str(exc):
                    raise
                self.log('IGDB rejected search query (%s), trying a looser one' % exc)
                continue
            if results:
                break
        return rank_results(results, title, year)

    def get_game(self, game_id):
        bodies = [
            'fields %s; where id = %d;' % (FULL_FIELDS, int(game_id)),
            'fields %s; where id = %d;' % (MINIMAL_FIELDS, int(game_id)),
        ]
        results = self._query_with_fallback('games', bodies)
        return results[0] if results else None

    def get_game_by_slug(self, slug):
        slug = re.sub(r'[^a-z0-9\-_]', '', slug.lower())
        bodies = [
            'fields %s; where slug = "%s";' % (FULL_FIELDS, slug),
            'fields %s; where slug = "%s";' % (MINIMAL_FIELDS, slug),
        ]
        results = self._query_with_fallback('games', bodies)
        return results[0] if results else None
