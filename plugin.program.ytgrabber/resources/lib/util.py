# -*- coding: utf-8 -*-
"""Shared helpers: logging, paths, settings, HTTP download."""
import os
import platform
import re
import ssl
import urllib.request

import xbmc
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
UA = 'Mozilla/5.0 (Kodi %s add-on)' % ADDON_ID


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


def get_setting(key, default=''):
    val = xbmcaddon.Addon().getSetting(key)
    return val if val != '' else default


def get_int(key, default=0):
    try:
        return int(float(get_setting(key, str(default))))
    except ValueError:
        return default


def get_bool(key, default=False):
    val = get_setting(key, 'true' if default else 'false')
    return val.lower() == 'true'


def set_setting(key, value):
    xbmcaddon.Addon().setSetting(key, str(value))


def profile_dir():
    path = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def bin_dir():
    path = os.path.join(profile_dir(), 'bin')
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def temp_dir():
    path = os.path.join(xbmcvfs.translatePath('special://temp/'), 'ytgrabber')
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def is_windows():
    return platform.system() == 'Windows'


def is_android():
    return xbmc.getCondVisibility('System.Platform.Android')


def safe_filename(name):
    name = re.sub(r'[\\/:*?"<>|]+', ' ', name)
    return re.sub(r'\s+', ' ', name).strip(' .')


def ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as r:
        return r.read()


def http_download(url, dest, progress_cb=None, timeout=30):
    """Download url to dest. progress_cb(done, total) may raise to abort."""
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as r:
        total = int(r.headers.get('Content-Length') or 0)
        done = 0
        with open(dest, 'wb') as f:
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)
    return dest
