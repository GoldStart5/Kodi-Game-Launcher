# -*- coding: utf-8 -*-
"""Game Launcher service for Kodi (Windows).

Watches the player. When the file being played is named like the trigger file
(default: Play.avi) it:
  1. stops playback (or waits for the intro to finish, depending on settings),
  2. finds the .lnk in the same folder (prefers "<folder name>.lnk"),
  3. shows the game's fanart full screen while the game loads (artwork comes from
     the Kodi library first, e.g. scraped online art, then the local folder),
  4. launches the shortcut with os.startfile().

The splash closes when another application takes the foreground (the game or
its launcher), when the timeout expires, or when the user presses Back.
"""
import json
import os

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")

ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92
ACTION_STOP = 13

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def log(msg, level=xbmc.LOGINFO):
    xbmc.log("[%s] %s" % (ADDON_ID, msg), level)


# --------------------------------------------------------------------------
# Pure helpers (no Kodi UI) - easy to test
# --------------------------------------------------------------------------
def find_lnk(folder):
    """Return the shortcut to launch: '<folder name>.lnk' first, else the first .lnk."""
    try:
        names = sorted(os.listdir(folder))
    except OSError as exc:
        log("Cannot list %s: %s" % (folder, exc), xbmc.LOGERROR)
        return None
    lnks = [n for n in names if n.lower().endswith(".lnk")]
    if not lnks:
        return None
    wanted = os.path.basename(os.path.normpath(folder)).lower() + ".lnk"
    for n in lnks:
        if n.lower() == wanted:
            return os.path.join(folder, n)
    return os.path.join(folder, lnks[0])


def _find_image(folder, bases):
    try:
        names = os.listdir(folder)
    except OSError:
        return ""
    lower = {n.lower(): n for n in names}
    for base in bases:
        for ext in IMAGE_EXTS:
            hit = lower.get(base + ext)
            if hit:
                return os.path.join(folder, hit)
    return ""


def find_fanart(folder):
    name = os.path.basename(os.path.normpath(folder)).lower()
    return _find_image(folder, ("fanart", "background", "backdrop", name + "-fanart"))


def find_logo(folder):
    return _find_image(folder, ("clearlogo", "logo"))


# --------------------------------------------------------------------------
# Artwork: Kodi library (scraped) and local files
# --------------------------------------------------------------------------
def _rpc(method, params):
    try:
        raw = xbmc.executeJSONRPC(json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}))
        return json.loads(raw).get("result") or {}
    except Exception as exc:
        log("JSON-RPC %s failed: %s" % (method, exc), xbmc.LOGWARNING)
        return {}


def library_art_playing():
    """Art dict of the video item currently playing ({} if it has none)."""
    for p in _rpc_list("Player.GetActivePlayers") or []:
        if p.get("type") == "video":
            item = _rpc("Player.GetItem", {"playerid": p.get("playerid", 1),
                                           "properties": ["art"]}).get("item", {})
            return item.get("art") or {}
    return {}


def _rpc_list(method):
    try:
        raw = xbmc.executeJSONRPC(json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": {}}))
        return json.loads(raw).get("result")
    except Exception as exc:
        log("JSON-RPC %s failed: %s" % (method, exc), xbmc.LOGWARNING)
        return None


def _same_folder(a, b):
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def library_art_for_folder(folder):
    """Look the game up in the video library by its folder and return its art."""
    name = os.path.basename(os.path.normpath(folder))
    if not name:
        return {}
    res = _rpc("VideoLibrary.GetMovies", {
        "filter": {"field": "path", "operator": "contains", "value": name},
        "properties": ["art", "file"]})
    for m in res.get("movies", []):
        f = m.get("file") or ""
        if f and _same_folder(os.path.dirname(f), folder):
            return m.get("art") or {}
    return {}


def _art_pair(art):
    art = art or {}
    return art.get("fanart") or "", art.get("clearlogo") or art.get("logo") or ""


def resolve_art(folder, lib_art, source):
    """Pick (fanart, logo). source: 0 library first, 1 local first, 2 local only."""
    local = (find_fanart(folder), find_logo(folder))
    lib = _art_pair(lib_art) if source != 2 else ("", "")
    first, second = (local, lib) if source in (1, 2) else (lib, local)
    fanart = first[0] or second[0]
    logo = first[1] or second[1]
    return fanart, logo


def foreground_is_kodi():
    """True if Kodi owns the foreground window (or we cannot tell)."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return True
        pid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == os.getpid()
    except Exception:  # not Windows / ctypes missing -> rely on timeout
        return True


# --------------------------------------------------------------------------
# Splash window
# --------------------------------------------------------------------------
class Splash(xbmcgui.WindowDialog):
    def __init__(self, fanart, logo, title, animate=True, zoom=100):
        super(Splash, self).__init__()
        self.closed_by_user = False
        w, h = self.getWidth(), self.getHeight()

        # Whole-window fade in / fade out (applies to every control)
        bg = xbmcgui.ControlImage(0, 0, w, h, "", colorDiffuse="0xFF000000")
        self.addControl(bg)

        art = None
        if fanart:
            # aspectRatio 1 = scale to fill, cropping the overflow
            art = xbmcgui.ControlImage(0, 0, w, h, fanart, aspectRatio=1)
            self.addControl(art)

        mark = None
        if logo:
            lw, lh = int(w * 0.4), int(h * 0.25)
            mark = xbmcgui.ControlImage(
                (w - lw) // 2, int(h * 0.50) - lh // 2, lw, lh, logo, aspectRatio=2)
        else:
            mark = xbmcgui.ControlLabel(
                0, int(h * 0.42), w, 80, title, font="font30_title",
                textColor="0xFFFFFFFF", alignment=6)
        self.addControl(mark)

        status = xbmcgui.ControlLabel(
            0, int(h * 0.86), w, 40, ADDON.getLocalizedString(30100),
            font="font13", textColor="0xCCFFFFFF", alignment=6)
        self.addControl(status)

        if art:
            # Constant zoom pushes baked-in black bars off screen; with animation on it
            # then drifts slowly outward from that size and back ("Ken Burns").
            anims = []
            if animate:
                anims += [("WindowOpen", "effect=fade start=0 end=100 time=900 tween=sine easing=out"),
                          ("WindowClose", "effect=fade start=100 end=0 time=500 tween=sine easing=in"),
                          ("Conditional",
                           "effect=zoom start=%d end=%d center=auto time=14000 "
                           "tween=sine easing=inout pulse=true condition=true" % (zoom, zoom + 12))]
            elif zoom > 100:
                anims += [("Conditional",
                           "effect=zoom start=100 end=%d center=auto time=1 condition=true" % zoom)]
            if anims:
                art.setAnimations(anims)

        if animate:
            fade_in = "effect=fade start=0 end=100 time=%d tween=sine easing=out"
            fade_out = "effect=fade start=100 end=0 time=500 tween=sine easing=in"
            bg.setAnimations([("WindowOpen", fade_in % 600), ("WindowClose", fade_out)])
            # logo / title appears a moment after the fanart, with a small rise
            mark.setAnimations([
                ("WindowOpen", "effect=fade start=0 end=100 delay=500 time=900 tween=sine easing=out"),
                ("WindowOpen", "effect=slide start=0,20 end=0,0 delay=500 time=900 tween=cubic easing=out"),
                ("WindowClose", fade_out),
            ])
            # status text gently pulses so the screen feels alive while waiting
            status.setAnimations([
                ("WindowOpen", "effect=fade start=0 end=100 delay=900 time=600"),
                ("Conditional",
                 "effect=fade start=100 end=45 time=1400 tween=sine easing=inout "
                 "pulse=true condition=true"),
                ("WindowClose", fade_out),
            ])

    def onAction(self, action):
        if action.getId() in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK, ACTION_STOP):
            self.closed_by_user = True
            self.close()


# --------------------------------------------------------------------------
# Player + service loop
# --------------------------------------------------------------------------
class GamePlayer(xbmc.Player):
    def __init__(self):
        super(GamePlayer, self).__init__()
        self.pending = None       # path of Play.avi that should trigger a launch
        self._armed_for = None    # trigger file seen playing (for "after intro" mode)
        self.item_art = {}        # library art of the item that started the launch

    @staticmethod
    def _settings():
        a = xbmcaddon.Addon()
        return {
            "trigger": (a.getSetting("trigger_name") or "play.avi").strip().lower(),
            "mode": int(a.getSetting("launch_mode") or 0),
            "splash": a.getSetting("show_splash") != "false",
            "timeout": int(a.getSetting("splash_timeout") or 30),
            "animate": a.getSetting("animate_splash") != "false",
            "art_source": int(a.getSetting("art_source") or 0),
            "zoom": int(a.getSetting("fill_zoom") or 115),
        }

    def _current_trigger_path(self):
        cfg = self._settings()
        try:
            path = self.getPlayingFile()
        except RuntimeError:
            return None
        if not path:
            return None
        local = xbmcvfs.translatePath(path) if path.startswith("special://") else path
        if os.path.basename(local).lower() != cfg["trigger"]:
            return None
        return local

    def _on_started(self):
        path = self._current_trigger_path()
        if not path:
            self._armed_for = None
            return
        cfg = self._settings()
        log("Trigger file playing: %s" % path)
        self.item_art = library_art_playing() if cfg["art_source"] != 2 else {}
        if cfg["mode"] == 0:      # launch immediately
            self.pending = path
        else:                     # wait for the intro to end
            self._armed_for = path

    def onAVStarted(self):
        self._on_started()

    def onPlayBackEnded(self):
        if self._armed_for:
            self.pending = self._armed_for
            self._armed_for = None

    def onPlayBackStopped(self):
        self._armed_for = None


def launch(player, path):
    cfg = player._settings()
    folder = os.path.dirname(path)

    if player.isPlaying():
        player.stop()

    lnk = find_lnk(folder)
    if not lnk:
        log("No .lnk found in %s" % folder, xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Game Launcher", ADDON.getLocalizedString(30101),
                                      xbmcgui.NOTIFICATION_ERROR, 5000)
        return

    title = os.path.splitext(os.path.basename(lnk))[0]
    splash = None
    if cfg["splash"]:
        lib_art = player.item_art
        if cfg["art_source"] != 2 and not _art_pair(lib_art)[0]:
            lib_art = library_art_for_folder(folder) or lib_art
        fanart, logo = resolve_art(folder, lib_art, cfg["art_source"])
        log("Splash art: fanart=%s logo=%s" % (fanart or "-", logo or "-"))
        splash = Splash(fanart, logo, title, cfg["animate"], cfg["zoom"])
        splash.show()

    log("Launching %s" % lnk)
    try:
        os.startfile(lnk)  # Windows only
    except Exception as exc:
        log("Launch failed: %s" % exc, xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Game Launcher", str(exc),
                                      xbmcgui.NOTIFICATION_ERROR, 5000)
        if splash:
            splash.close()
        return

    if not splash:
        return

    monitor = xbmc.Monitor()
    waited = 0.0
    grace = 2.0    # give the new app time to take focus before we check
    step = 0.25
    while waited < cfg["timeout"] and not monitor.abortRequested() and not splash.closed_by_user:
        monitor.waitForAbort(step)
        waited += step
        if waited > grace and not foreground_is_kodi():
            log("Another app has the foreground - closing splash")
            break
    splash.close()
    if cfg["animate"]:
        monitor.waitForAbort(0.6)   # let the fade-out finish
    del splash


def main():
    monitor = xbmc.Monitor()
    player = GamePlayer()
    log("Service started")
    while not monitor.abortRequested():
        if player.pending:
            path, player.pending = player.pending, None
            try:
                launch(player, path)
            except Exception as exc:  # never let the service die
                log("Unexpected error: %s" % exc, xbmc.LOGERROR)
        if monitor.waitForAbort(0.2):
            break
    log("Service stopped")


if __name__ == "__main__":
    main()
