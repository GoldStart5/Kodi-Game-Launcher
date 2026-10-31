# -*- coding: utf-8 -*-
"""User interface flow for the add-on."""
import os
import sys
import traceback
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

from . import library, tools, util, ytapi

dialog = xbmcgui.Dialog()
NAME = util.ADDON_NAME


# ------------------------------------------------------------------ helpers
def _error(msg):
    util.log(msg, xbmc.LOGERROR)
    dialog.ok(NAME, msg)


def _busy(fn, *args):
    """Run fn with the busy spinner shown."""
    xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
    try:
        return fn(*args)
    finally:
        xbmc.executebuiltin('Dialog.Close(busydialognocancel)')


def _ensure_ytdlp():
    if os.path.isfile(tools.ytdlp_path()) or os.path.isfile(tools.binary_path()):
        return True
    if dialog.yesno(NAME, 'yt-dlp is not installed yet.\nDownload it now?'):
        tools.install_ytdlp(force=True)
        tools.set_version_labels()
    return os.path.isfile(tools.ytdlp_path()) or os.path.isfile(tools.binary_path())


# ------------------------------------------------------------------ search
def _queries(item, kind):
    t, y = item['title'], item.get('year')
    ty = '%s %s' % (t, y) if y and item['type'] == 'movie' else t
    if kind == 'theme':
        if item['type'] == 'movie':
            return ty + ' soundtrack', ty + ' main theme'
        return t + ' soundtrack', t + ' theme song'
    return ty + ' official trailer', None


def _build_results(item, kind, custom=None):
    pl_q, vid_q = _queries(item, kind)
    if custom:
        pl_q = vid_q = custom
    ytapi.prune_cache()
    if kind == 'theme':
        # playlists and single videos are searched at the same time
        res = ytapi.search_parallel([(ytapi.search_playlists, (pl_q,)),
                                     (ytapi.search_videos, (vid_q or pl_q, 8))])
        playlists = res[0] if isinstance(res[0], list) else []
        videos = res[1] if isinstance(res[1], list) else []
        if not playlists and not videos:
            err = [r for r in res if isinstance(r, Exception)]
            if err:
                raise err[0]
        return playlists + videos
    return ytapi.search_videos(pl_q, 10)


_MIME = {'m4a': 'audio/mp4', 'mp4': 'video/mp4', 'webm': 'audio/webm', 'opus': 'audio/ogg',
         'mp3': 'audio/mpeg', 'ogg': 'audio/ogg'}


def _preview(url, audio=False, title=''):
    """Play a preview. audio=True plays the soundtrack as music (no video)."""
    try:
        info = _busy(ytapi.stream_url, url, audio)
    except Exception as e:
        _error('Cannot preview this:\n%s' % e)
        return
    path = info['url']
    if info.get('ua'):
        path += '|' + urllib.parse.urlencode({'User-Agent': info['ua']})
    li = xbmcgui.ListItem(title or 'Preview', path=path)
    li.setContentLookup(False)
    mime = _MIME.get(info.get('ext', ''))
    if mime:
        li.setMimeType(mime if not (audio and mime.startswith('video')) else 'audio/mp4')
    if audio:
        li.getMusicInfoTag().setTitle(title or 'Preview')
        li.setProperty('IsPlayable', 'true')
    player = xbmc.Player()
    player.play(path, li)
    mon = xbmc.Monitor()
    waited = 0
    while not player.isPlaying() and waited < 20 and not mon.abortRequested():
        mon.waitForAbort(0.25)
        waited += 0.25
    while player.isPlaying() and not mon.abortRequested():
        mon.waitForAbort(0.5)


# ------------------------------------------------------------------ saving
def _destination(item, kind):
    folder, base = library.target_for(item)
    if kind == 'theme':
        return folder, folder + 'theme.mp3'
    return folder, folder + base + '-trailer.mp4'


def _do_download(item, kind, video):
    folder, dest = _destination(item, kind)
    if not xbmcvfs.exists(folder):
        _error('Folder not found or not reachable:\n%s' % folder)
        return False
    overwrite = False
    if xbmcvfs.exists(dest):
        name = dest.rstrip('/\\').replace('\\', '/').split('/')[-1]
        if not dialog.yesno(NAME, '%s already exists.\nOverwrite it?' % name, nolabel='Cancel', yeslabel='Overwrite'):
            return False
        overwrite = True

    if kind == 'theme' and not tools.ffmpeg_path():
        if dialog.yesno(NAME, 'ffmpeg is needed to create theme.mp3 but was not found.\nInstall it now?'):
            tools.install_ffmpeg()
        if not tools.ffmpeg_path():
            return False

    pd = xbmcgui.DialogProgress()
    pd.create(NAME, video['title'])

    def progress(pct, text):
        pd.update(pct, '%s\n%s' % (video['title'], text))
        return pd.iscanceled()

    try:
        tmpfile = ytapi.download(video['url'], kind, progress)
    except ytapi.Cancelled:
        pd.close()
        dialog.notification(NAME, 'Cancelled', xbmcgui.NOTIFICATION_INFO, 3000)
        return False
    except Exception as e:
        pd.close()
        _error('Download failed:\n%s' % e)
        return False

    pd.update(100, 'Copying to library folder...')
    try:
        if overwrite:
            xbmcvfs.delete(dest)
        ok = xbmcvfs.copy(tmpfile, dest)
    finally:
        pd.close()
        try:
            os.remove(tmpfile)
        except OSError:
            pass
    if not ok:
        _error('Could not write to:\n%s' % dest)
        return False
    dialog.notification(NAME, 'Saved %s' % dest.replace('\\', '/').split('/')[-1],
                        xbmcgui.NOTIFICATION_INFO, 5000)
    return True


# ------------------------------------------------------------------ plugin UI
BASE = sys.argv[0] if sys.argv and sys.argv[0].startswith('plugin://') else 'plugin://%s/' % util.ADDON_ID
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].lstrip('-').isdigit() else -1


def _url(**kw):
    return BASE + '?' + urllib.parse.urlencode({k: v for k, v in kw.items() if v not in (None, '')})


def _add(label, url, folder=True, art=None, plot='', label2=''):
    li = xbmcgui.ListItem(label, label2)
    if art:
        li.setArt(art)
    if plot:
        li.getVideoInfoTag().setPlot(plot)
    xbmcplugin.addDirectoryItem(HANDLE, url, li, folder)
    return li


def _end(ok=True, content=None):
    if content:
        xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.endOfDirectory(HANDLE, succeeded=ok, cacheToDisc=False)


def _done_action():
    """Non-folder items are invoked with a handle; close it quietly."""
    if HANDLE >= 0:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


def _root():
    if not (os.path.isfile(tools.ytdlp_path()) or os.path.isfile(tools.binary_path())):
        _add('[B]Install yt-dlp (required first step)[/B]', _url(action='install'), folder=False)
    _add('Movies', _url(action='list', type='movie'))
    _add('TV Shows', _url(action='list', type='tvshow'))
    _add('Settings (install / update yt-dlp, ffmpeg, Deno)', _url(action='settings'), folder=False)
    _end()


def _list(kind):
    items = library.get_movies() if kind == 'movie' else library.get_tvshows()
    if not items:
        dialog.ok(NAME, 'No %s found in your Kodi library.' % ('movies' if kind == 'movie' else 'TV shows'))
        _end(False)
        return
    for it in items:
        art = dict(it['art'])
        art.setdefault('thumb', art.get('poster', ''))
        _add(library.display_name(it), _url(action='title', type=kind, id=it['id']),
             art=art, plot=it['plot'])
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    _end(content='movies' if kind == 'movie' else 'tvshows')


def _title_menu(kind, item_id):
    item = library.get_item(kind, item_id)
    if not item:
        dialog.ok(NAME, 'That title is no longer in the library.')
        _end(False)
        return
    art = item['art']
    ident = dict(type=kind, id=item_id)
    _add('Themes  (soundtrack  ->  theme.mp3)', _url(action='results', kind='theme', **ident), art=art)
    _add('Trailers  (->  name-trailer.mp4)', _url(action='results', kind='trailer', **ident), art=art)
    _add('Paste a YouTube URL...', _url(action='paste', **ident), folder=False, art=art)
    _end()


def _video_url(vid):
    return 'https://www.youtube.com/watch?v=%s' % vid


def _playlist_url(pid):
    return 'https://www.youtube.com/playlist?list=%s' % pid


def _show_entries(entries, kind, ident):
    for r in entries:
        if r['kind'] == 'playlist':
            label = '[Playlist] %s' % r['title']
            l2 = '%s%s' % (r['channel'], ('  -  %s videos' % r['count']) if r['count'] else '')
            _add(label, _url(action='tracks', pid=r['id'], kind=kind, **ident), label2=l2)
        else:
            l2 = '%s%s' % (r['channel'], ('  -  %s' % r['duration']) if r['duration'] else '')
            thumb = 'https://i.ytimg.com/vi/%s/hqdefault.jpg' % r['id']
            _add(r['title'], _url(action='pick', vid=r['id'], t=r['title'], kind=kind, **ident),
                 folder=False, art={'thumb': thumb, 'icon': thumb}, label2=l2)


def _results(kind, ident, q):
    item = library.get_item(ident['type'], ident['id'])
    if not item:
        _end(False)
        return
    if not _ensure_ytdlp():
        _end(False)
        return
    try:
        results = _build_results(item, kind, q)
    except Exception as e:
        _error('Search failed:\n%s' % e)
        _end(False)
        return
    _add('[B]Search again...[/B]', _url(action='search', kind=kind, **ident), folder=False)
    _show_entries(results, kind, ident)
    _end()


def _tracks(pid, kind, ident):
    try:
        tracks = ytapi.playlist_tracks(_playlist_url(pid))
    except Exception as e:
        _error('Could not open playlist:\n%s' % e)
        _end(False)
        return
    _show_entries(tracks, kind, ident)
    _end()


def _pick(vid, title, kind, ident):
    item = library.get_item(ident['type'], ident['id'])
    video = {'title': title or vid, 'url': _video_url(vid)}
    try:
        while True:
            act = dialog.select(video['title'], ['Download', 'Preview', 'Back'])
            if act == 1:
                _preview(video['url'], audio=(kind == 'theme'), title=video['title'])
                continue
            break
        if act == 0 and item:
            _do_download(item, kind, video)
    finally:
        _done_action()


def _search(kind, ident):
    item = library.get_item(ident['type'], ident['id'])
    q = dialog.input('Search YouTube', defaultt=_queries(item, kind)[0]) if item else ''
    _done_action()
    if q:
        xbmc.executebuiltin('Container.Update(%s,replace)' % _url(action='results', kind=kind, q=q, **ident))


def _paste(ident):
    item = library.get_item(ident['type'], ident['id'])
    try:
        url = dialog.input('YouTube URL')
        if not url or not item:
            return
        kind = dialog.select('Save as', ['Theme (mp3)', 'Trailer (mp4)'])
        if kind < 0:
            return
        _do_download(item, 'theme' if kind == 0 else 'trailer', {'title': url, 'url': url})
    finally:
        _done_action()


def route():
    params = dict(urllib.parse.parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 else {}
    action = params.get('action', 'root')
    ident = {'type': params.get('type'), 'id': params.get('id')}
    kind = params.get('kind')
    try:
        if action == 'root':
            _root()
        elif action == 'list':
            _list(params['type'])
        elif action == 'title':
            _title_menu(params['type'], params['id'])
        elif action == 'results':
            _results(kind, ident, params.get('q'))
        elif action == 'tracks':
            _tracks(params['pid'], kind, ident)
        elif action == 'pick':
            _pick(params['vid'], params.get('t'), kind, ident)
        elif action == 'search':
            _search(kind, ident)
        elif action == 'paste':
            _paste(ident)
        elif action == 'install':
            tools.install_ytdlp(force=False)
            tools.set_version_labels()
            _done_action()
            xbmc.executebuiltin('Container.Refresh')
        elif action == 'settings':
            _done_action()
            util.ADDON.openSettings()
    except Exception:
        tb = traceback.format_exc()
        util.log(tb, xbmc.LOGERROR)
        dialog.textviewer(NAME, tb)
        _done_action()
