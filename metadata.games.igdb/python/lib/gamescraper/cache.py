"""Tiny JSON file cache living in the add-on's profile directory."""
import hashlib
import json
import os
import time

DEFAULT_TTL = 7 * 24 * 3600


class FileCache:
    def __init__(self, directory):
        self.directory = directory
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError:
            pass

    def _path(self, key):
        return os.path.join(self.directory, hashlib.sha1(key.encode('utf-8')).hexdigest() + '.json')

    def get(self, key, ttl=DEFAULT_TTL):
        path = self._path(key)
        try:
            if time.time() - os.path.getmtime(path) > ttl:
                return None
            with open(path, 'r', encoding='utf-8') as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return None

    def set(self, key, value):
        try:
            with open(self._path(key), 'w', encoding='utf-8') as handle:
                json.dump(value, handle)
        except OSError:
            pass
