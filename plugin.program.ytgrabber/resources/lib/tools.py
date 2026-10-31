# -*- coding: utf-8 -*-
"""Install / locate yt-dlp (python zipapp), ffmpeg and a JS runtime (deno)."""
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import traceback
import zipfile

import xbmcgui

from . import util

YTDLP_URLS = {
    'stable': 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp',
    'nightly': 'https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp',
}
YTDLP_API = {
    'stable': 'https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest',
    'nightly': 'https://api.github.com/repos/yt-dlp/yt-dlp-nightly-builds/releases/latest',
}
FFMPEG_BASE = 'https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/'
DENO_BASE = 'https://github.com/denoland/deno/releases/latest/download/'


class ToolError(Exception):
    pass


class Cancelled(Exception):
    pass


# --------------------------------------------------------------- helpers
def _exe(name):
    return name + ('.exe' if util.is_windows() else '')


def _machine():
    m = platform.machine().lower()
    if m in ('x86_64', 'amd64'):
        return 'x64'
    if m in ('aarch64', 'arm64'):
        return 'arm64'
    return m


def _chmod_x(path):
    if not util.is_windows():
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _download_with_dialog(url, dest, title):
    dlg = xbmcgui.DialogProgress()
    dlg.create(util.ADDON_NAME, title)

    def cb(done, total):
        if dlg.iscanceled():
            raise Cancelled()
        pct = int(done * 100 / total) if total else 0
        dlg.update(pct, '%s\n%.1f / %.1f MB' % (title, done / 1048576.0, total / 1048576.0))

    try:
        util.http_download(url, dest, cb)
    except Cancelled:
        if os.path.exists(dest):
            os.remove(dest)
        raise
    finally:
        dlg.close()


# --------------------------------------------------------------- yt-dlp
def ytdlp_path():
    """The downloaded yt-dlp zipapp (kept as the source of truth)."""
    return os.path.join(util.bin_dir(), 'yt-dlp')


def ytdlp_pkg_dir():
    """Folder the zipapp is extracted into; imported as a normal package."""
    return os.path.join(util.bin_dir(), 'yt_dlp_pkg')


def _purge_ytdlp_modules():
    for name in [n for n in sys.modules if n.split('.')[0] in ('yt_dlp', 'yt_dlp_ejs')]:
        del sys.modules[name]
    for p in (ytdlp_path(), ytdlp_pkg_dir()):
        while p in sys.path:
            sys.path.remove(p)


def _extract_ytdlp():
    """Unpack the zipapp so Python never has to use zipimport."""
    dest = ytdlp_pkg_dir()
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    with zipfile.ZipFile(ytdlp_path()) as z:
        z.extractall(dest)


def load_ytdlp():
    """Import yt_dlp. Returns the module or raises ToolError with the real reason."""
    if not os.path.isfile(ytdlp_path()):
        raise ToolError('yt-dlp is not installed. Open the add-on settings and press "Install / update yt-dlp".')
    try:
        if not os.path.isdir(os.path.join(ytdlp_pkg_dir(), 'yt_dlp')):
            _extract_ytdlp()
        if ytdlp_pkg_dir() not in sys.path:
            sys.path.insert(0, ytdlp_pkg_dir())
        import yt_dlp  # noqa
        return yt_dlp
    except Exception as e:
        util.log('yt-dlp import failed:\n%s' % traceback.format_exc(), 3)
        raise ToolError('Could not load yt-dlp (%s: %s)\nPython %s on %s' % (
            type(e).__name__, e, platform.python_version(), platform.platform()))


def installed_ytdlp_version():
    if not os.path.isfile(ytdlp_path()):
        return ''
    try:
        _purge_ytdlp_modules()
        load_ytdlp()
        from yt_dlp.version import __version__
        return __version__
    except Exception:
        return ''
    finally:
        _purge_ytdlp_modules()


def latest_ytdlp_version(channel):
    data = json.loads(util.http_get(YTDLP_API[channel]).decode('utf-8'))
    return data.get('tag_name', '')


# ---- standalone binary (bundles its own Python, ignores Kodi's Python) ----
BIN_RELEASES = {
    'stable': 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/',
    'nightly': 'https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/',
}


def binary_path():
    return os.path.join(util.bin_dir(), 'yt-dlp-standalone' + ('.exe' if util.is_windows() else ''))


def _binary_asset():
    if util.is_android():
        return None
    sysname = platform.system()
    mach = platform.machine().lower()
    if sysname == 'Windows':
        return 'yt-dlp.exe' if _machine() == 'x64' else None
    if sysname == 'Darwin':
        return 'yt-dlp_macos'
    if sysname == 'Linux':
        if _machine() == 'x64':
            return 'yt-dlp_linux'
        if _machine() == 'arm64':
            return 'yt-dlp_linux_aarch64'
        if mach.startswith('armv7'):
            return 'yt-dlp_linux_armv7l'
    return None


def binary_version():
    p = binary_path()
    if not os.path.isfile(p):
        return ''
    try:
        kw = {}
        if util.is_windows():
            kw['creationflags'] = 0x08000000
        out = subprocess.run([p, '--version'], capture_output=True, timeout=60, **kw)
        return out.stdout.decode('utf-8', 'replace').strip() if out.returncode == 0 else ''
    except Exception as e:
        util.log('binary check failed: %s' % e)
        return ''


def python_usable():
    """Can Kodi's Python run the yt-dlp module? Result is remembered on disk so we don't
    re-try the (slow) failing import on every page."""
    stamp = '%s|%s|%s' % (int(os.path.getmtime(ytdlp_path())) if os.path.isfile(ytdlp_path()) else 0,
                          platform.python_version(), 'v1')
    memo = os.path.join(util.profile_dir(), 'pymode.txt')
    try:
        with open(memo, 'r') as f:
            saved_stamp, saved = f.read().strip().rsplit('|', 1)
        if saved_stamp == stamp:
            return saved == '1'
    except (OSError, ValueError):
        pass
    try:
        load_ytdlp()
        ok = True
    except ToolError:
        ok = False
    try:
        with open(memo, 'w') as f:
            f.write('%s|%s' % (stamp, '1' if ok else '0'))
    except OSError:
        pass
    return ok


def use_binary():
    """Decide which yt-dlp to run: 'binary' (own Python) or the in-Kodi Python module."""
    mode = util.get_setting('ytdlp_mode', 'auto')
    if mode == 'binary':
        return True
    if mode == 'python':
        return False
    # auto: prefer the module if Kodi's Python can run it, else the standalone binary
    if os.path.isfile(ytdlp_path()) and python_usable():
        return False
    return os.path.isfile(binary_path())


def _install_python(channel):
    tmp = ytdlp_path() + '.part'
    _download_with_dialog(YTDLP_URLS[channel], tmp, 'Downloading yt-dlp (%s)' % channel)
    os.replace(tmp, ytdlp_path())
    _purge_ytdlp_modules()
    shutil.rmtree(ytdlp_pkg_dir(), ignore_errors=True)
    return installed_ytdlp_version()


def _install_binary(channel):
    asset = _binary_asset()
    if not asset:
        raise ToolError('No standalone yt-dlp exists for this platform (%s %s).' % (platform.system(), platform.machine()))
    tmp = binary_path() + '.part'
    _download_with_dialog(BIN_RELEASES[channel] + asset, tmp, 'Downloading yt-dlp standalone (%s)' % channel)
    os.replace(tmp, binary_path())
    _chmod_x(binary_path())
    ver = binary_version()
    if not ver:
        raise ToolError('The standalone yt-dlp was downloaded but does not run on this device.')
    return ver


def install_ytdlp(force=False):
    channel = 'nightly' if util.get_setting('ytdlp_channel', 'stable') == 'nightly' else 'stable'
    mode = util.get_setting('ytdlp_mode', 'auto')
    current = (binary_version() if use_binary() else installed_ytdlp_version())
    if current and not force:
        try:
            latest = latest_ytdlp_version(channel)
            if latest and latest == current:
                set_version_labels()
                xbmcgui.Dialog().ok(util.ADDON_NAME, 'yt-dlp is already up to date (%s).' % current)
                return
        except Exception as e:
            util.log('version check failed: %s' % e)
    notes = []
    try:
        if mode in ('auto', 'python'):
            try:
                ver = _install_python(channel)
            except Cancelled:
                return
            if ver:
                set_version_labels()
                xbmcgui.Dialog().ok(util.ADDON_NAME, 'yt-dlp %s installed (%s channel, runs in Kodi\'s Python).' % (ver, channel))
                return
            try:
                load_ytdlp()
            except ToolError as e:
                notes.append(str(e))
            if mode == 'python':
                xbmcgui.Dialog().textviewer(util.ADDON_NAME, 'yt-dlp could not be loaded by Kodi\'s Python:\n\n' + '\n'.join(notes))
                return
            notes.append('Switching to the standalone yt-dlp, which has its own Python.')
        ver = _install_binary(channel)
        set_version_labels()
        msg = 'yt-dlp %s installed (%s channel, standalone with its own Python).' % (ver, channel)
        xbmcgui.Dialog().ok(util.ADDON_NAME, '\n'.join(notes[-1:] + [msg]) if notes else msg)
    except Cancelled:
        return
    except Exception as e:
        util.log(traceback.format_exc(), 3)
        xbmcgui.Dialog().textviewer(util.ADDON_NAME, 'Install failed:\n\n%s\n%s' % ('\n'.join(notes), e))


# --------------------------------------------------------------- ffmpeg
def ffmpeg_path():
    custom = util.get_setting('ffmpeg_custom', '').strip()
    if custom and os.path.isfile(custom):
        return custom
    local = os.path.join(util.bin_dir(), _exe('ffmpeg'))
    if os.path.isfile(local):
        return local
    return shutil.which('ffmpeg') or ''


def ffmpeg_version():
    p = ffmpeg_path()
    if not p:
        return ''
    try:
        out = subprocess.run([p, '-version'], capture_output=True, timeout=15).stdout.decode('utf-8', 'replace')
        parts = out.split('\n', 1)[0].split()
        return parts[2] if len(parts) > 2 else 'installed'
    except Exception:
        return ''


def _ffmpeg_asset():
    sysname = platform.system()
    m = _machine()
    if util.is_android():
        return None
    if sysname == 'Windows' and m == 'x64':
        return 'ffmpeg-master-latest-win64-gpl.zip'
    if sysname == 'Linux' and m == 'x64':
        return 'ffmpeg-master-latest-linux64-gpl.tar.xz'
    if sysname == 'Linux' and m == 'arm64':
        return 'ffmpeg-master-latest-linuxarm64-gpl.tar.xz'
    return None


def _extract_member(archive, wanted_names, dest_dir):
    """Extract files whose basename is in wanted_names from a zip/tar.xz."""
    found = []
    if archive.endswith('.zip'):
        with zipfile.ZipFile(archive) as z:
            for n in z.namelist():
                base = os.path.basename(n)
                if base in wanted_names and '/bin/' in '/' + n:
                    with z.open(n) as src, open(os.path.join(dest_dir, base), 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    found.append(base)
        return found
    try:
        with tarfile.open(archive, 'r:xz') as t:
            for mem in t.getmembers():
                base = os.path.basename(mem.name)
                if mem.isfile() and base in wanted_names and '/bin/' in '/' + mem.name:
                    with t.extractfile(mem) as src, open(os.path.join(dest_dir, base), 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    found.append(base)
        return found
    except Exception as e:
        util.log('python tar.xz failed (%s), trying system tar' % e)
    tmpx = os.path.join(util.temp_dir(), 'ffx')
    shutil.rmtree(tmpx, ignore_errors=True)
    os.makedirs(tmpx)
    subprocess.run(['tar', '-xJf', archive, '-C', tmpx], check=True, timeout=600)
    for root, _d, files in os.walk(tmpx):
        for f in files:
            if f in wanted_names and os.path.basename(root) == 'bin':
                shutil.copy(os.path.join(root, f), os.path.join(dest_dir, f))
                found.append(f)
    shutil.rmtree(tmpx, ignore_errors=True)
    return found


def install_ffmpeg():
    asset = _ffmpeg_asset()
    if not asset:
        xbmcgui.Dialog().ok(util.ADDON_NAME,
                            'No ffmpeg build is available for this platform (%s %s).\n'
                            'Install ffmpeg yourself and set its path in the add-on settings.'
                            % (platform.system(), platform.machine()))
        return
    archive = os.path.join(util.temp_dir(), asset)
    try:
        _download_with_dialog(FFMPEG_BASE + asset, archive, 'Downloading ffmpeg')
    except Cancelled:
        return
    except Exception as e:
        xbmcgui.Dialog().ok(util.ADDON_NAME, 'Download failed:\n%s' % e)
        return
    try:
        found = _extract_member(archive, {_exe('ffmpeg'), _exe('ffprobe')}, util.bin_dir())
        if _exe('ffmpeg') not in found:
            raise ToolError('ffmpeg binary not found in archive')
        for f in found:
            _chmod_x(os.path.join(util.bin_dir(), f))
    except Exception as e:
        xbmcgui.Dialog().ok(util.ADDON_NAME, 'Could not extract ffmpeg:\n%s' % e)
        return
    finally:
        if os.path.exists(archive):
            os.remove(archive)
    ver = ffmpeg_version()
    set_version_labels()
    if ver:
        xbmcgui.Dialog().ok(util.ADDON_NAME, 'ffmpeg installed (%s).' % ver)
    else:
        xbmcgui.Dialog().ok(util.ADDON_NAME, 'ffmpeg was extracted but does not run on this device. '
                            'Install it yourself and set the path in the settings.')


# --------------------------------------------------------------- JS runtime
def deno_local():
    return os.path.join(util.bin_dir(), _exe('deno'))


def js_runtime():
    """Return (name, path) of a usable JS runtime or (None, None)."""
    custom = util.get_setting('js_custom', '').strip()
    if custom and os.path.isfile(custom):
        name = os.path.basename(custom).lower().replace('.exe', '')
        for known in ('deno', 'node', 'bun', 'qjs'):
            if known in name:
                return ('quickjs' if known == 'qjs' else known), custom
        return 'deno', custom
    if os.path.isfile(deno_local()):
        return 'deno', deno_local()
    for exe, name in (('deno', 'deno'), ('node', 'node'), ('bun', 'bun'), ('qjs', 'quickjs')):
        p = shutil.which(exe)
        if p:
            return name, p
    return None, None


def js_version():
    name, path = js_runtime()
    if not path:
        return ''
    try:
        out = subprocess.run([path, '--version'], capture_output=True, timeout=15).stdout.decode('utf-8', 'replace')
        return '%s %s' % (name, out.strip().split('\n')[0].replace('deno ', ''))
    except Exception:
        return ''


def _deno_asset():
    sysname = platform.system()
    m = _machine()
    if util.is_android():
        return None
    if sysname == 'Windows' and m == 'x64':
        return 'deno-x86_64-pc-windows-msvc.zip'
    if sysname == 'Linux' and m == 'x64':
        return 'deno-x86_64-unknown-linux-gnu.zip'
    if sysname == 'Linux' and m == 'arm64':
        return 'deno-aarch64-unknown-linux-gnu.zip'
    if sysname == 'Darwin' and m == 'arm64':
        return 'deno-aarch64-apple-darwin.zip'
    if sysname == 'Darwin' and m == 'x64':
        return 'deno-x86_64-apple-darwin.zip'
    return None


def install_js_runtime():
    asset = _deno_asset()
    if not asset:
        xbmcgui.Dialog().ok(util.ADDON_NAME,
                            'Deno is not available for this platform (%s %s).\n'
                            'yt-dlp still works for many videos without it. If you have Node.js, '
                            'Bun or QuickJS, set its path in the settings.'
                            % (platform.system(), platform.machine()))
        return
    archive = os.path.join(util.temp_dir(), asset)
    try:
        _download_with_dialog(DENO_BASE + asset, archive, 'Downloading Deno')
    except Cancelled:
        return
    except Exception as e:
        xbmcgui.Dialog().ok(util.ADDON_NAME, 'Download failed:\n%s' % e)
        return
    try:
        with zipfile.ZipFile(archive) as z:
            with z.open(_exe('deno')) as src, open(deno_local(), 'wb') as dst:
                shutil.copyfileobj(src, dst)
        _chmod_x(deno_local())
    except Exception as e:
        xbmcgui.Dialog().ok(util.ADDON_NAME, 'Could not extract Deno:\n%s' % e)
        return
    finally:
        if os.path.exists(archive):
            os.remove(archive)
    ver = js_version()
    set_version_labels()
    if ver:
        xbmcgui.Dialog().ok(util.ADDON_NAME, 'JavaScript runtime installed (%s).' % ver)
    else:
        xbmcgui.Dialog().ok(util.ADDON_NAME, 'Deno was extracted but does not run on this device '
                            '(it needs a glibc based system).')


# --------------------------------------------------------------- settings labels
def ytdlp_status_text():
    if use_binary():
        v = binary_version()
        return ('%s (standalone)' % v) if v else 'Not installed'
    v = installed_ytdlp_version()
    return ('%s (Kodi Python)' % v) if v else 'Not installed'


def set_version_labels():
    util.set_setting('ytdlp_status', ytdlp_status_text())
    util.set_setting('ffmpeg_status', ffmpeg_version() or 'Not installed')
    util.set_setting('js_status', js_version() or 'Not installed')


def diagnostics():
    lines = ['Python: %s' % platform.python_version(),
             'Platform: %s %s' % (platform.system(), platform.machine()),
             'Android: %s' % bool(util.is_android()),
             'yt-dlp file: %s' % (('%d bytes' % os.path.getsize(ytdlp_path())) if os.path.isfile(ytdlp_path()) else 'missing'),
             'yt-dlp mode: %s' % ('standalone binary' if use_binary() else 'Kodi Python module'),
             'yt-dlp standalone: %s' % (binary_version() or 'not installed'),
             'yt-dlp module: %s' % (installed_ytdlp_version() or 'cannot load in Kodi Python'),
             'ffmpeg: %s' % (ffmpeg_path() or 'not found'),
             'JS runtime: %s' % (js_version() or 'not found')]
    try:
        _purge_ytdlp_modules()
        load_ytdlp()
    except ToolError as e:
        lines += ['', 'Load error:', str(e)]
    finally:
        _purge_ytdlp_modules()
    xbmcgui.Dialog().textviewer(util.ADDON_NAME, '\n'.join(lines))
