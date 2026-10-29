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
import time

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

INTRO_LEAD = 0.35      # pause the intro this many seconds before its end (holds the last frame)
FADE_SECONDS = 0.7     # length of the black fade-in; Kodi runs it, frame by frame
_now = time.monotonic


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
    name = os.path.basename(os.path.normpath(folder)).lower()
    return _find_image(folder, ("clearlogo", "logo", name + "-clearlogo", name + "-logo"))


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


def library_item_playing():
    """Library details of the video item now playing: {id, type, art, playcount} or {}."""
    for p in _rpc_list("Player.GetActivePlayers") or []:
        if p.get("type") == "video":
            item = _rpc("Player.GetItem", {"playerid": p.get("playerid", 1),
                                           "properties": ["art", "playcount"]}).get("item", {})
            return item
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


def library_movie_for_folder(folder):
    """Find the game in the video library by its folder. Returns the movie dict or {}."""
    name = os.path.basename(os.path.normpath(folder))
    if not name:
        return {}
    res = _rpc("VideoLibrary.GetMovies", {
        "filter": {"field": "path", "operator": "contains", "value": name},
        "properties": ["art", "file", "playcount"]})
    for m in res.get("movies", []):
        f = m.get("file") or ""
        if f and _same_folder(os.path.dirname(f), folder):
            return m
    return {}


def mark_played(movie_id, original_playcount):
    """Make the game sort as 'last played' without leaving it marked as watched.

    Kodi marks Play.avi watched if the intro plays to the end, so first put the play
    count back, then write the last-played time (in that order, so the date is not
    cleared by the play-count change).
    """
    if movie_id is None:
        return
    d = _rpc("VideoLibrary.GetMovieDetails",
             {"movieid": movie_id, "properties": ["playcount"]}).get("moviedetails", {})
    if (d.get("playcount") or 0) > original_playcount:
        _rpc("VideoLibrary.SetMovieDetails",
             {"movieid": movie_id, "playcount": original_playcount})
    _rpc("VideoLibrary.SetMovieDetails",
         {"movieid": movie_id, "lastplayed": time.strftime("%Y-%m-%d %H:%M:%S")})
    log("Updated last played for library item %s" % movie_id)


def _art_pair(art):
    art = art or {}
    logo = (art.get("clearlogo") or art.get("logo")
            or art.get("set.clearlogo") or art.get("tvshow.clearlogo") or "")
    return art.get("fanart") or "", logo


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
def black_texture():
    """Path of a solid black image (an image control with no texture draws nothing)."""
    path = os.path.join(xbmcvfs.translatePath(ADDON.getAddonInfo("path")),
                        "resources", "media", "black.png")
    if not os.path.exists(path):
        log("black.png missing - splash will not have a solid background", xbmc.LOGWARNING)
        return ""
    return path


class Splash(xbmcgui.WindowDialog):
    def __init__(self, fanart, logo, title, animate=True, black_delay_ms=3000):
        super(Splash, self).__init__()
        self.closed_by_user = False
        w, h = self.getWidth(), self.getHeight()

        # Whole-window fade in / fade out (applies to every control)
        black = black_texture()
        bg = xbmcgui.ControlImage(0, 0, w, h, black)
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

        fade_in = "effect=fade start=0 end=100 time=%d tween=sine easing=out"
        fade_out = "effect=fade start=100 end=0 time=500 tween=sine easing=in"

        art_anims, mark_anims, status_anims = [], [], []
        if animate:
            bg.setAnimations([("WindowOpen", fade_in % 600), ("WindowClose", fade_out)])
            art_anims += [
                ("WindowOpen", fade_in % 900),
                ("WindowClose", fade_out),
                # slow "Ken Burns" push-in that eases back out, repeating
                ("Conditional",
                 "effect=zoom start=100 end=112 center=auto time=14000 "
                 "tween=sine easing=inout pulse=true condition=true"),
            ]
            # logo / title appears a moment after the fanart, with a small rise
            mark_anims += [
                ("WindowOpen", "effect=fade start=0 end=100 delay=500 time=900 tween=sine easing=out"),
                ("WindowOpen", "effect=slide start=0,20 end=0,0 delay=500 time=900 tween=cubic easing=out"),
                ("WindowClose", fade_out),
            ]
            # status text gently pulses so the screen feels alive while waiting
            status_anims += [
                ("WindowOpen", "effect=fade start=0 end=100 delay=900 time=600"),
                ("Conditional",
                 "effect=fade start=100 end=45 time=1400 tween=sine easing=inout "
                 "pulse=true condition=true"),
                ("WindowClose", fade_out),
            ]

        for ctl, anims in ((art, art_anims), (mark, mark_anims), (status, status_anims)):
            if ctl is not None and anims:
                ctl.setAnimations(anims)

        # Black overlay on top of everything. Kodi's animation engine keeps it fully
        # transparent for `black_delay_ms`, then fades it in smoothly (every rendered
        # frame) and leaves it black. The splash stays underneath until the window closes.
        overlay = xbmcgui.ControlImage(0, 0, w, h, black)
        self.addControl(overlay)
        overlay.setAnimations([(
            "WindowOpen",
            "effect=fade start=0 end=100 delay=%d time=%d tween=sine easing=inout"
            % (black_delay_ms, int(FADE_SECONDS * 1000)))])

    def onAction(self, action):
        if action.getId() in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK, ACTION_STOP):
            self.closed_by_user = True
            self.close()


# --------------------------------------------------------------------------
# Player + service loop
# --------------------------------------------------------------------------
class FadeCover(xbmcgui.WindowDialog):
    """Black layer that fades in over whatever is on screen (used over the paused last
    frame of the intro video). Kodi runs the fade, so it is drawn every frame."""

    def __init__(self):
        super(FadeCover, self).__init__()
        self.closed_by_user = False
        w, h = self.getWidth(), self.getHeight()
        cover = xbmcgui.ControlImage(0, 0, w, h, black_texture())
        self.addControl(cover)
        cover.setAnimations([(
            "WindowOpen",
            "effect=fade start=0 end=100 time=%d tween=sine easing=inout"
            % int(FADE_SECONDS * 1000))])

    def onAction(self, action):
        if action.getId() in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK, ACTION_STOP):
            self.closed_by_user = True
            self.close()


class GamePlayer(xbmc.Player):
    def __init__(self):
        super(GamePlayer, self).__init__()
        self.pending = None       # path of Play.avi that should trigger a launch
        self.pending_intro = False  # True when the launch comes at the end of the intro video
        self._armed_for = None    # trigger file seen playing (for "after intro" mode)
        self.item = {}            # library item that started the launch

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
            "track": a.getSetting("track_lastplayed") != "false",
            "splash_time": min(7, max(1, int(a.getSetting("splash_time") or 3))),
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
        self.item = library_item_playing()
        if cfg["mode"] == 0:      # launch immediately
            self.pending_intro = False
            self.pending = path
        else:                     # wait for the intro to end
            self._armed_for = path

    def onAVStarted(self):
        self._on_started()

    def onPlayBackEnded(self):
        # Fallback: the intro ended before poll_intro_end() could hold its last frame.
        if self._armed_for:
            self.pending_intro = True
            self.pending = self._armed_for
            self._armed_for = None

    def poll_intro_end(self):
        """'After the intro' mode: hold the intro's last frame by pausing just before the end."""
        if not self._armed_for or self.pending:
            return
        try:
            if not self.isPlaying():
                return
            total, cur = self.getTotalTime(), self.getTime()
        except RuntimeError:
            return
        if total <= 0:
            return
        if total - cur <= min(INTRO_LEAD, total * 0.25):
            self.pause()
            log("Intro paused on its last frame (%.2f of %.2f s)" % (cur, total))
            self.pending_intro = True
            self.pending = self._armed_for
            self._armed_for = None

    def onPlayBackStopped(self):
        self._armed_for = None


def _resolve_item(player, folder, need_art):
    """Library item for the game being launched: {id, playcount, art} or {}."""
    item = player.item if (player.item.get("type") == "movie"
                           and player.item.get("id") is not None) else {}
    if not item or (need_art and not _art_pair(item.get("art"))[0]):
        m = library_movie_for_folder(folder)
        if m:
            if not item:
                item = {"id": m.get("movieid"), "playcount": m.get("playcount") or 0,
                        "art": m.get("art") or {}}
            else:
                item = dict(item, art=m.get("art") or item.get("art") or {})
    return item


def launch(player, path, from_intro=False):
    """Launch the game for `path`.

    from_intro=False: stop the video, show the fanart splash, then fade to black and launch.
    from_intro=True : the intro is paused on its last frame; fade black over it (no splash),
                      launch, then stop the video once the game has the foreground.
    """
    cfg = player._settings()
    folder = os.path.dirname(path)

    def release_video():
        if from_intro and player.isPlaying():
            player.stop()

    if player.isPlaying() and not from_intro:
        player.stop()

    lnk = find_lnk(folder)
    if not lnk:
        log("No .lnk found in %s" % folder, xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Game Launcher", ADDON.getLocalizedString(30101),
                                      xbmcgui.NOTIFICATION_ERROR, 5000)
        release_video()
        return

    title = os.path.splitext(os.path.basename(lnk))[0]
    need_art = cfg["splash"] and cfg["art_source"] != 2 and not from_intro
    item = {}
    if need_art or cfg["track"]:
        item = _resolve_item(player, folder, need_art)
    movie_id = item.get("id") if item else None
    original_playcount = item.get("playcount") or 0 if item else 0
    if cfg["track"] and movie_id is None:
        log("Game is not in the Kodi library - last played not updated")

    splash = None
    shown_at = None
    if from_intro:
        splash = FadeCover()
        splash.show()
        shown_at = _now()
    elif cfg["splash"]:
        fanart, logo = resolve_art(folder, item.get("art") or {}, cfg["art_source"])
        log("Library art keys: %s" % (", ".join(sorted(item.get("art") or {})) or "-"))
        log("Splash art: fanart=%s logo=%s" % (fanart or "-", logo or "-"))
        if not logo:
            log("No clearlogo found (library or local) - showing the game title instead")
        splash = Splash(fanart, logo, title, cfg["animate"], cfg["splash_time"] * 1000)
        splash.show()
        shown_at = _now()

    monitor = xbmc.Monitor()

    # Splash time, then the black layer fades in over the splash (Kodi animates it),
    # then the game starts from the black screen. Back skips the rest of the wait.
    if splash:
        hold = 0.0 if from_intro else cfg["splash_time"]
        launch_at = shown_at + hold + FADE_SECONDS + 0.1
        while (_now() < launch_at and not monitor.abortRequested()
               and not splash.closed_by_user):
            monitor.waitForAbort(0.05)
        if monitor.abortRequested():
            release_video()
            splash.close()
            return

    log("Launching %s" % lnk)
    try:
        os.startfile(lnk)  # Windows only
    except Exception as exc:
        log("Launch failed: %s" % exc, xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Game Launcher", str(exc),
                                      xbmcgui.NOTIFICATION_ERROR, 5000)
        release_video()
        if splash:
            splash.close()
        return

    tracked = cfg["track"] and movie_id is not None
    if tracked:
        mark_played(movie_id, original_playcount)   # now
    final_pass_at = 2.5   # again shortly after, in case Kodi's own "watched" update lands late
    final_done = not tracked

    if splash:
        waited = 0.0
        grace = 2.0    # give the new app time to take focus before we check
        step = 0.25
        while waited < cfg["timeout"] and not monitor.abortRequested() and not splash.closed_by_user:
            monitor.waitForAbort(step)
            waited += step
            if not final_done and waited >= final_pass_at:
                mark_played(movie_id, original_playcount)
                final_done = True
            if waited > grace and not foreground_is_kodi():
                log("Another app has the foreground - closing splash")
                break
        release_video()   # intro mode: stop the (paused) video only now, behind the black layer
        splash.close()
        if cfg["animate"] and not from_intro:
            monitor.waitForAbort(0.6)   # let the close animation finish
        del splash
    elif not final_done:
        monitor.waitForAbort(final_pass_at)
        mark_played(movie_id, original_playcount)
        final_done = True

    if not final_done:   # splash ended before the second pass
        monitor.waitForAbort(max(0.0, final_pass_at - 1.0))
        mark_played(movie_id, original_playcount)


def service_tick(player):
    if player.pending:
        path, from_intro = player.pending, player.pending_intro
        player.pending, player.pending_intro = None, False
        try:
            launch(player, path, from_intro)
        except Exception as exc:  # never let the service die
            log("Unexpected error: %s" % exc, xbmc.LOGERROR)
    player.poll_intro_end()


def main():
    monitor = xbmc.Monitor()
    player = GamePlayer()
    log("Service started")
    while not monitor.abortRequested():
        service_tick(player)
        # poll quickly while waiting for the end of an intro video
        if monitor.waitForAbort(0.05 if player._armed_for else 0.2):
            break
    log("Service stopped")


if __name__ == "__main__":
    main()
