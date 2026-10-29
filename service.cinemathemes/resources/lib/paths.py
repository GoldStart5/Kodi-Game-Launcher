# -*- coding: utf-8 -*-
"""Path helpers that work on Windows paths, Kodi VFS paths and Kodi wrapper paths.

Deliberately free of Kodi imports (except a lazy xbmcvfs call in translate) so
the logic is easy to test.
"""
import os
import re
from urllib.parse import unquote

AUDIO_EXTENSIONS = (
    '.mp3', '.flac', '.ogg', '.oga', '.opus', '.m4a', '.aac', '.wav', '.wma',
    '.ape', '.mka', '.mp2', '.wv', '.aif', '.aiff', '.mpc', '.dsf',
)

_SEPS = '/\\'
_WRAPPERS = ('bluray://', 'udf://', 'rar://', 'zip://', 'archive://', 'iso9660://')
_DISC_FOLDERS = ('bdmv', 'video_ts')


def translate(path):
    """Resolve special:// paths and environment variables to a real path."""
    if not path:
        return path
    if path.startswith('special://'):
        try:
            import xbmcvfs
            return xbmcvfs.translatePath(path)
        except Exception:
            return path
    if '://' in path:
        return path
    return os.path.expandvars(os.path.expanduser(path))


def strip_sep(path):
    """Remove trailing separators, but keep the root of a drive (D:\\)."""
    p = path.rstrip(_SEPS)
    if re.fullmatch(r'[A-Za-z]:', p):
        return p + '\\'
    return p or path


def parent(path):
    p = strip_sep(path)
    idx = max(p.rfind('/'), p.rfind('\\'))
    if idx < 0:
        return ''
    par = p[:idx]
    if re.fullmatch(r'[A-Za-z]:', par):
        par += p[idx]
    return par


def basename(path):
    p = strip_sep(path)
    return p[max(p.rfind('/'), p.rfind('\\')) + 1:]


def join(folder, name):
    sep = '\\' if ('\\' in folder and '://' not in folder) else '/'
    return folder.rstrip(_SEPS) + sep + name


def norm(path):
    """Normalised form used for comparing paths and as a theme key."""
    return strip_sep(path).replace('\\', '/').lower().rstrip('/')


def is_under(path, root):
    np_, nr = norm(path), norm(root)
    if not nr:
        return False
    return np_ == nr or np_.startswith(nr + '/')


def unwrap_path(path):
    """Turn stack:// and disc/archive wrapper URLs into the underlying path."""
    p = path or ''
    if p.startswith('stack://'):
        p = p[len('stack://'):].split(' , ')[0]
    for _ in range(4):
        low = p.lower()
        wrapper = next((w for w in _WRAPPERS if low.startswith(w)), None)
        if not wrapper:
            break
        p = unquote(p[len(wrapper):])
    return p


def movie_folder(file_path):
    """Folder that should hold a movie's theme file."""
    p = unwrap_path(file_path)
    if not p:
        return ''
    # Plain files live in their parent folder, directory-style paths are the folder.
    folder = strip_sep(p) if p[-1] in _SEPS else parent(p)
    if basename(folder).lower() in _DISC_FOLDERS:
        folder = parent(folder)
    return strip_sep(folder) if folder else ''


def show_folder(file_path):
    p = unwrap_path(file_path)
    return strip_sep(p) if p else ''


def expand_source(path):
    """A Kodi source may be a multipath:// made of several real paths."""
    if not path:
        return []
    if path.lower().startswith('multipath://'):
        parts = [unquote(x) for x in path[len('multipath://'):].split('/') if x]
        return [x for x in parts if x]
    return [path]
