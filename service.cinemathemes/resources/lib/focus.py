# -*- coding: utf-8 -*-
"""Detect whether Kodi is the foreground application (Windows, via ctypes)."""
import os


class FocusWatcher(object):
    def __init__(self, log):
        self._pid = os.getpid()      # the add-on runs inside the Kodi process
        self._ok = False
        self._last = True
        if os.name != 'nt':
            log('Focus detection is only available on Windows; assuming Kodi is focused')
            return
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            user32.GetForegroundWindow.argtypes = []
            user32.GetForegroundWindow.restype = wintypes.HWND
            user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            user32.GetWindowThreadProcessId.restype = wintypes.DWORD
            self._ctypes = ctypes
            self._wintypes = wintypes
            self._user32 = user32
            self._ok = True
        except Exception as exc:  # ctypes missing or user32 unavailable
            log('Focus detection unavailable (%s); assuming Kodi is focused' % exc)

    def has_focus(self):
        if not self._ok:
            return True
        try:
            hwnd = self._user32.GetForegroundWindow()
            if not hwnd:
                # Momentary state while windows are switching: keep the last answer.
                return self._last
            pid = self._wintypes.DWORD(0)
            self._user32.GetWindowThreadProcessId(hwnd, self._ctypes.byref(pid))
            self._last = (pid.value == self._pid)
        except Exception:
            self._last = True
        return self._last
