"""Typed access to add-on settings.

Credentials always come from the global add-on settings. Every other option
can be overridden per library source: Kodi passes those as a JSON
``pathSettings`` dict, already typed (bool/int/str).
"""


class Settings:
    def __init__(self, addon, path_settings=None):
        self._addon = addon
        self._path = path_settings if isinstance(path_settings, dict) else {}

    # credentials --------------------------------------------------------
    def credential(self, key):
        """Look in the per-source settings first, then the add-on's global settings.

        Kodi's "Set content" dialog stores scraper settings per library source
        and hands them to the scraper as ``pathSettings``; the global add-on
        settings page is a separate store. Users fill in whichever they find
        first, so accept both (a non-empty source value wins).
        """
        value = self._path.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return (self._addon.getSettingString(key) or '').strip()

    # overridable values -------------------------------------------------
    def get_str(self, key, default=''):
        if key in self._path and isinstance(self._path[key], str):
            return self._path[key]
        value = self._addon.getSettingString(key)
        return value if value else default

    def get_bool(self, key):
        if key in self._path:
            value = self._path[key]
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() == 'true'
        return self._addon.getSettingBool(key)

    def get_int(self, key, default=0):
        if key in self._path:
            try:
                return int(self._path[key])
            except (TypeError, ValueError):
                pass
        try:
            return self._addon.getSettingInt(key)
        except Exception:  # noqa: BLE001 - Kodi raises generic errors
            return default
