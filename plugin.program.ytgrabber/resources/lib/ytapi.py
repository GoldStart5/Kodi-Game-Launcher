# -*- coding: utf-8 -*-
"""Thin wrapper around the yt-dlp Python API: search, preview URL, download."""
import glob
import hashlib
import json
import os
import re
import subprocess
import threading
import time
import urllib.parse

import xbmc

from . import tools, util


SEARCH_TTL = 3600


class Cancelled(Exception):
    pass


class _Logger(object):
    def debug(self, msg):
        if not msg.startswith('[debug]'):
            util.log('yt-dlp: %s' % msg, xbmc.LOGDEBUG)

    def info(self, msg):
        util.log('yt-dlp: %s' % msg, xbmc.LOGDEBUG)

    def warning(self, msg):
        util.log('yt-dlp warning: %s' % msg, xbmc.LOGWARNING)

    def error(self, msg):
        util.log('yt-dlp error: %s' % msg, xbmc.LOGERROR)


def _base_opts():
    opts = {
        'quiet': True,
        'no_warnings': True,
        'logger': _Logger(),
        'socket_timeout': 20,
        'retries': 3,
        'extractor_retries': 2,
        'noprogress': True,
        'cachedir': os.path.join(util.profile_dir(), 'cache'),
        'remote_components': ['ejs:github'],
    }
    name, path = tools.js_runtime()
    if name:
        opts['js_runtimes'] = {name: {'path': path}}
    ff = tools.ffmpeg_path()
    if ff:
        opts['ffmpeg_location'] = ff
    proxy = util.get_setting('proxy', '').strip()
    if proxy:
        opts['proxy'] = proxy
    cookies = util.get_setting('cookies_file', '').strip()
    if cookies and os.path.isfile(cookies):
        opts['cookiefile'] = cookies
    return opts


def _fmt_duration(sec):
    if not sec:
        return ''
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return '%d:%02d:%02d' % (h, m, s) if h else '%d:%02d' % (m, s)


def _entry(e, kind):
    vid = e.get('id') or ''
    url = e.get('url') or ''
    if kind == 'video' and (not url.startswith('http')):
        url = 'https://www.youtube.com/watch?v=%s' % vid
    return {
        'kind': kind,
        'id': vid,
        'title': e.get('title') or '(untitled)',
        'channel': e.get('channel') or e.get('uploader') or '',
        'duration': _fmt_duration(e.get('duration')),
        'count': e.get('playlist_count') or e.get('n_entries') or 0,
        'url': url,
    }


def _extract(url, extra=None):
    yt_dlp = tools.load_ytdlp()
    opts = _base_opts()
    opts.update(extra or {})
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def _py_search_videos(query, count=10):
    info = _extract('ytsearch%d:%s' % (count, query), {'extract_flat': True})
    return [_entry(e, 'video') for e in (info or {}).get('entries', []) if e and e.get('id')]


def _py_search_playlists(query, count=8):
    url = 'https://www.youtube.com/results?search_query=%s&sp=EgIQAw%%253D%%253D' % urllib.parse.quote_plus(query)
    try:
        info = _extract(url, {'extract_flat': True, 'playlist_items': '1-%d' % count})
    except Exception as e:
        util.log('playlist search failed: %s' % e, xbmc.LOGWARNING)
        return []
    out = []
    for e in (info or {}).get('entries', []) or []:
        if not e:
            continue
        u = e.get('url') or ''
        if 'list=' in u or u.startswith('https://www.youtube.com/playlist'):
            out.append(_entry(e, 'playlist'))
    return out


def _py_playlist_tracks(url):
    info = _extract(url, {'extract_flat': True})
    return [_entry(e, 'video') for e in (info or {}).get('entries', []) if e and e.get('id')]


_PREVIEW_FMT_AUDIO = 'bestaudio[ext=m4a]/bestaudio/b'
_PREVIEW_FMT_VIDEO = 'b[ext=mp4]/b'


def _py_stream_url(url, audio=False):
    """Direct progressive URL for in-Kodi preview."""
    info = _extract(url, {'noplaylist': True,
                          'format': _PREVIEW_FMT_AUDIO if audio else _PREVIEW_FMT_VIDEO})
    if not info.get('url'):
        for f in info.get('requested_formats') or []:
            if f.get('url'):
                info = f
                break
    if not info.get('url'):
        raise RuntimeError('No playable stream found')
    headers = info.get('http_headers') or {}
    return {'url': info['url'], 'ext': info.get('ext') or '',
            'ua': headers.get('User-Agent', '')}


def _plan(kind, ffmpeg):
    if kind == 'theme':
        if not ffmpeg:
            raise RuntimeError('ffmpeg is required to create theme.mp3.\n'
                               'Install it from the add-on settings.')
        return {'format': 'bestaudio/best', 'ext': 'mp3'}
    h = util.get_int('video_height', 1080)
    if ffmpeg:
        return {'format': ('bv*[height<=%(h)d][vcodec^=avc1]+ba[ext=m4a]/'
                           'bv*[height<=%(h)d]+ba/b[height<=%(h)d]/b' % {'h': h}),
                'ext': 'mp4', 'merge': True}
    return {'format': 'b[ext=mp4][height<=%d]/b[ext=mp4]' % h, 'ext': 'mp4'}


def _clean_temp(prefix):
    for f in glob.glob(os.path.join(util.temp_dir(), prefix + '.*')):
        try:
            os.remove(f)
        except OSError:
            pass


def _py_download(url, kind, progress):
    """Download into the temp dir and return the finished file path.

    kind: 'theme' -> mp3, 'trailer' -> mp4
    progress(percent:int, text:str) -> returns True if cancelled.
    """
    yt_dlp = tools.load_ytdlp()
    ffmpeg = tools.ffmpeg_path()
    prefix = kind
    _clean_temp(prefix)
    opts = _base_opts()
    opts.update({
        'noplaylist': True,
        'outtmpl': os.path.join(util.temp_dir(), prefix + '.%(ext)s'),
        'overwrites': True,
        'continuedl': False,
    })

    plan = _plan(kind, ffmpeg)
    opts['format'] = plan['format']
    if kind == 'theme':
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': str(util.get_int('audio_bitrate', 192)),
        }]
    elif plan.get('merge'):
        opts['merge_output_format'] = 'mp4'
    final_ext = plan['ext']

    state = {'cancelled': False}

    def hook(d):
        if progress is None:
            return
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            done = d.get('downloaded_bytes') or 0
            pct = int(done * 100 / total) if total else 0
            speed = d.get('speed')
            text = 'Downloading  %d%%' % pct
            if speed:
                text += '  (%.1f MB/s)' % (speed / 1048576.0)
            if progress(pct, text):
                state['cancelled'] = True
                raise Cancelled()
        elif d['status'] == 'finished':
            progress(100, 'Processing...')

    def pp_hook(d):
        if progress and d.get('status') == 'started':
            progress(100, 'Converting (%s)...' % d.get('postprocessor', ''))

    opts['progress_hooks'] = [hook]
    opts['postprocessor_hooks'] = [pp_hook]

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception:
        if state['cancelled']:
            _clean_temp(prefix)
            raise Cancelled()
        raise
    out = os.path.join(util.temp_dir(), '%s.%s' % (prefix, final_ext))
    if not os.path.isfile(out):
        files = glob.glob(os.path.join(util.temp_dir(), prefix + '.*'))
        files = [f for f in files if not f.endswith(('.part', '.ytdl'))]
        if not files:
            raise RuntimeError('Download finished but no output file was found.')
        out = files[0]
    return out


# ====================================================================
# Standalone binary backend (yt-dlp with its own bundled Python)
# ====================================================================
def _cli_base():
    args = [tools.binary_path(), '--ignore-config', '--no-warnings', '--no-colors',
            '--socket-timeout', '20', '--cache-dir', os.path.join(util.profile_dir(), 'cache'),
            '--remote-components', 'ejs:github']
    name, path = tools.js_runtime()
    if name:
        args += ['--js-runtimes', '%s:%s' % (name, path)]
    ff = tools.ffmpeg_path()
    if ff:
        args += ['--ffmpeg-location', ff]
    proxy = util.get_setting('proxy', '').strip()
    if proxy:
        args += ['--proxy', proxy]
    cookies = util.get_setting('cookies_file', '').strip()
    if cookies and os.path.isfile(cookies):
        args += ['--cookies', cookies]
    return args


def _popen_kwargs():
    kw = {}
    if util.is_windows():
        kw['creationflags'] = 0x08000000  # CREATE_NO_WINDOW
    return kw


def _cli_run(args, timeout=120):
    if not os.path.isfile(tools.binary_path()):
        raise RuntimeError('Standalone yt-dlp is not installed. Install it from the add-on settings.')
    cmd = _cli_base() + args
    util.log('exec: %s' % ' '.join(cmd), xbmc.LOGDEBUG)
    p = subprocess.run(cmd, capture_output=True, timeout=timeout, **_popen_kwargs())
    out = p.stdout.decode('utf-8', 'replace')
    err = p.stderr.decode('utf-8', 'replace')
    if p.returncode != 0:
        lines = [l for l in err.strip().splitlines() if l.strip()]
        raise RuntimeError('\n'.join(lines[-3:]) or 'yt-dlp exited with code %d' % p.returncode)
    return out


def _cli_json(args):
    return json.loads(_cli_run(args + ['-J']))


def _cli_search_videos(query, count=10):
    info = _cli_json(['--flat-playlist', 'ytsearch%d:%s' % (count, query)])
    return [_entry(e, 'video') for e in info.get('entries', []) if e and e.get('id')]


def _cli_search_playlists(query, count=8):
    url = 'https://www.youtube.com/results?search_query=%s&sp=EgIQAw%%253D%%253D' % urllib.parse.quote_plus(query)
    try:
        info = _cli_json(['--flat-playlist', '-I', '1:%d' % count, url])
    except Exception as e:
        util.log('playlist search failed: %s' % e, xbmc.LOGWARNING)
        return []
    out = []
    for e in info.get('entries', []) or []:
        u = (e or {}).get('url') or ''
        if 'list=' in u or u.startswith('https://www.youtube.com/playlist'):
            out.append(_entry(e, 'playlist'))
    return out


def _cli_playlist_tracks(url):
    info = _cli_json(['--flat-playlist', url])
    return [_entry(e, 'video') for e in info.get('entries', []) if e and e.get('id')]


def _cli_stream_url(url, audio=False):
    out = _cli_run(['--no-playlist', '-f', _PREVIEW_FMT_AUDIO if audio else _PREVIEW_FMT_VIDEO,
                    '--print', '%(url)s\t%(ext)s\t%(http_headers.User-Agent)s', url])
    for line in out.splitlines():
        parts = line.split('\t')
        if parts[0].startswith('http'):
            return {'url': parts[0], 'ext': parts[1] if len(parts) > 1 else '',
                    'ua': parts[2] if len(parts) > 2 and parts[2] != 'NA' else ''}
    raise RuntimeError('No playable stream found')


_PROG_RE = re.compile(r'^\[ytg\]\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)')


def _num(x):
    try:
        return float(x)
    except ValueError:
        return 0.0


def _cli_download(url, kind, progress):
    plan = _plan(kind, tools.ffmpeg_path())
    _clean_temp(kind)
    args = _cli_base() + [
        '--no-playlist', '--force-overwrites', '--no-continue', '--newline',
        '--progress-template', 'download:[ytg] %(progress.downloaded_bytes)s %(progress.total_bytes)s '
                               '%(progress.total_bytes_estimate)s %(progress.speed)s',
        '-f', plan['format'],
        '-o', os.path.join(util.temp_dir(), kind + '.%(ext)s'),
    ]
    if kind == 'theme':
        args += ['-x', '--audio-format', 'mp3', '--audio-quality', '%dK' % util.get_int('audio_bitrate', 192)]
    elif plan.get('merge'):
        args += ['--merge-output-format', 'mp4']
    args.append(url)
    util.log('exec: %s' % ' '.join(args), xbmc.LOGDEBUG)
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **_popen_kwargs())
    tail = []
    try:
        for raw in iter(proc.stdout.readline, b''):
            line = raw.decode('utf-8', 'replace').strip()
            m = _PROG_RE.match(line)
            if m:
                done, total, est, speed = (_num(g) for g in m.groups())
                total = total or est
                pct = int(done * 100 / total) if total else 0
                text = 'Downloading  %d%%' % pct
                if speed:
                    text += '  (%.1f MB/s)' % (speed / 1048576.0)
                if progress and progress(pct, text):
                    raise Cancelled()
                continue
            if line:
                tail.append(line)
                tail = tail[-6:]
            if progress and line.startswith(('[ExtractAudio]', '[Merger]', '[VideoRemuxer]')):
                if progress(100, 'Converting...'):
                    raise Cancelled()
        proc.wait()
    except Cancelled:
        proc.terminate()
        proc.wait()
        _clean_temp(kind)
        raise
    except BaseException:
        proc.kill()
        raise
    if proc.returncode != 0:
        errs = [l for l in tail if l.startswith('ERROR')] or tail[-2:]
        raise RuntimeError('\n'.join(errs) or 'yt-dlp exited with code %d' % proc.returncode)
    out = os.path.join(util.temp_dir(), '%s.%s' % (kind, plan['ext']))
    if not os.path.isfile(out):
        files = [f for f in glob.glob(os.path.join(util.temp_dir(), kind + '.*'))
                 if not f.endswith(('.part', '.ytdl'))]
        if not files:
            raise RuntimeError('Download finished but no output file was found.')
        out = files[0]
    return out


# ====================================================================
# Public API: pick backend automatically
# ====================================================================
def _cache_file(key):
    d = os.path.join(util.profile_dir(), 'results')
    if not os.path.isdir(d):
        os.makedirs(d)
    return os.path.join(d, hashlib.sha1(key.encode('utf-8')).hexdigest() + '.json')


def _cached(key, ttl, fn):
    """Return fn() but reuse a recent result so going Back in Kodi is instant."""
    path = _cache_file(key)
    try:
        if time.time() - os.path.getmtime(path) < ttl:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (OSError, ValueError):
        pass
    data = fn()
    if data:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except OSError:
            pass
    return data


def prune_cache(max_age=6 * 3600):
    d = os.path.join(util.profile_dir(), 'results')
    if not os.path.isdir(d):
        return
    now = time.time()
    for name in os.listdir(d):
        p = os.path.join(d, name)
        try:
            if now - os.path.getmtime(p) > max_age:
                os.remove(p)
        except OSError:
            pass


def search_videos(query, count=10):
    fn = _cli_search_videos if tools.use_binary() else _py_search_videos
    return _cached('v|%s|%d' % (query, count), SEARCH_TTL, lambda: fn(query, count))


def search_playlists(query, count=8):
    fn = _cli_search_playlists if tools.use_binary() else _py_search_playlists
    return _cached('p|%s|%d' % (query, count), SEARCH_TTL, lambda: fn(query, count))


def playlist_tracks(url):
    fn = _cli_playlist_tracks if tools.use_binary() else _py_playlist_tracks
    return _cached('t|%s' % url, SEARCH_TTL, lambda: fn(url))


def search_parallel(jobs):
    """jobs: list of (callable, args). Runs them in threads, returns list of results
    (an exception instance in place of a result if that job failed)."""
    results = [None] * len(jobs)

    def run(i, fn, args):
        try:
            results[i] = fn(*args)
        except Exception as e:  # noqa
            results[i] = e

    threads = [threading.Thread(target=run, args=(i, fn, args)) for i, (fn, args) in enumerate(jobs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def stream_url(url, audio=False):
    return (_cli_stream_url if tools.use_binary() else _py_stream_url)(url, audio)


def download(url, kind, progress):
    return (_cli_download if tools.use_binary() else _py_download)(url, kind, progress)
