# -*- coding: utf-8 -*-
"""Home Waves Overlay - transparent animated overlay for the Kodi Home window.

Non-focusable image controls are added to Window(10000) (Home), so remote,
keyboard and mouse input are never affected.

Reliability: the service keeps checking that its controls still exist in the
Home window. If the skin / theme / resolution changes, or Kodi reloads the
window and drops the controls, the overlay is rebuilt automatically.

Fading: controls are shown/hidden through a window property, so changing
settings fades the old overlay out and the new one in. Fade durations are in
milliseconds (settings).
"""
import os
import random
import time

import xbmc
import xbmcaddon
import xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
MEDIA = os.path.join(ADDON_PATH, 'resources', 'media')
HOME_WINDOW_ID = 10000

PROP_ON = 'homewaves.on'
PROP_IDS = 'homewaves.ids'
VISIBLE_COND = 'String.IsEqual(Window(Home).Property(%s),1)' % PROP_ON

# Kodi waits for window-close animations before leaving a window, so a long
# fade-out there would freeze navigation. Leaving Home is therefore capped.
CLOSE_FADE_CAP_MS = 400

# Names are used to generate strings.po / settings.xml (see build script).
STYLES = [
    'Waves',
    'Silky ribbons',
    'Floating bokeh',
    'Aurora',
    'Glow orbs',
    'Light rays',
    'Stardust',
    'Ocean night (waves + stardust)',
]

# Each layer of a style takes the next colour of the palette, so multi-colour
# palettes give every layer its own hue.
PALETTES = [
    ('White', ['FFFFFF']),
    ('PlayStation blue', ['4FA3FF']),
    ('Purple', ['B07CFF']),
    ('Teal', ['3FE0C8']),
    ('Gold', ['FFC24A']),
    ('Pink', ['FF6B8A']),
    ('Sky', ['7FD4FF']),
    ('Mint', ['7CFFC4']),
    ('Green', ['5CE05C']),
    ('Lime', ['C6F135']),
    ('Orange', ['FF8A3D']),
    ('Red', ['FF4D4D']),
    ('Magenta', ['FF4FD8']),
    ('Indigo', ['5B6BFF']),
    ('Ice', ['D6F2FF']),
    ('Rose gold', ['F4A6A0']),
    ('Multi: Aurora', ['3FE0C8', '4FA3FF', 'B07CFF']),
    ('Multi: Sunset', ['FFB04A', 'FF5F8A', 'B07CFF']),
    ('Multi: Spectrum', ['FF4D4D', 'FFC24A', '5CE05C', '4FA3FF', 'B07CFF']),
    ('Multi: Ocean', ['3FE0C8', '4FA3FF', '5B6BFF']),
    ('Multi: Neon', ['FF4FD8', '4FD8FF', 'C6F135']),
    ('Multi: Fire', ['FFD166', 'FF8A3D', 'FF4D4D']),
    ('Multi: Forest', ['C6F135', '5CE05C', '3FE0C8']),
    ('Multi: PS Dawn', ['4FA3FF', 'FFFFFF', 'B07CFF']),
    ('Multi: Candy', ['FF6B8A', '7FD4FF', 'B07CFF', 'FFC24A']),
]


def log(msg):
    xbmc.log('[script.service.homewaves] %s' % msg, xbmc.LOGINFO)


def argb(alpha_pct, rgb):
    a = max(0, min(255, int(255 * alpha_pct / 100.0)))
    return '%02X%s' % (a, rgb)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class Overlay(object):
    def __init__(self, mon):
        self.mon = mon
        self.win = None
        self.controls = []
        self.sig = None
        self.built = False
        self.probe_ok = True
        self.layer_i = 0
        self.enabled = True
        self.style = 0
        self.pal = PALETTES[1][1]
        self.opacity = 60
        self.speed = 100
        self.fade_in = 3000
        self.fade_out = 3000

    # ------------------------------------------------------------------
    # settings
    def read_settings(self):
        a = xbmcaddon.Addon()

        def gi(key, default):
            try:
                return a.getSettingInt(key)
            except Exception:
                return default
        try:
            self.enabled = a.getSettingBool('enabled')
        except Exception:
            self.enabled = True
        self.style = clamp(gi('style', 0), 0, len(STYLES) - 1)
        pi = gi('color', 1)
        if pi < 0 or pi >= len(PALETTES):
            pi = 1
        self.pal = PALETTES[pi][1]
        self.opacity = clamp(gi('opacity', 60), 5, 100)
        self.speed = max(10, gi('speed', 100))
        self.fade_in = clamp(gi('fade_in', 3000), 0, 10000)
        self.fade_out = clamp(gi('fade_out', 3000), 0, 10000)

    def signature(self):
        return (xbmc.getSkinDir(),
                xbmc.getInfoLabel('Skin.CurrentTheme'),
                xbmc.getInfoLabel('Skin.CurrentColourTheme'),
                xbmc.getInfoLabel('System.ScreenWidth'),
                xbmc.getInfoLabel('System.ScreenHeight'))

    def dur(self, seconds):
        """Animation duration in ms, scaled by the speed setting."""
        return max(200, int(seconds * 1000 * 100.0 / self.speed))

    # ------------------------------------------------------------------
    # control life-cycle
    def probe(self):
        """True if our controls still exist in the live Home window."""
        if not self.controls:
            return False
        try:
            win = xbmcgui.Window(HOME_WINDOW_ID)
            for c in (self.controls[0], self.controls[-1]):
                win.getControl(c.getId())
            return True
        except Exception:
            return False

    def alive(self):
        if not self.built:
            return False
        if not self.probe_ok:
            return True
        return self.probe()

    def clear_now(self):
        """Remove whatever of our controls still exists. Controls that Kodi
        already dropped are skipped (never touch a stale control)."""
        try:
            win = xbmcgui.Window(HOME_WINDOW_ID)
        except Exception:
            win = None
        if win is not None:
            for c in self.controls:
                try:
                    win.getControl(c.getId())   # raises if it is gone
                    win.removeControl(c)
                except Exception:
                    pass
            try:
                win.setProperty(PROP_IDS, '')
            except Exception:
                pass
        self.controls = []
        self.built = False

    def reap_old(self):
        """Remove controls left behind by a previous instance of this
        service (e.g. after the add-on was updated)."""
        try:
            win = xbmcgui.Window(HOME_WINDOW_ID)
            ids = win.getProperty(PROP_IDS)
            for i in [x for x in ids.split(',') if x]:
                try:
                    win.removeControl(win.getControl(int(i)))
                except Exception:
                    pass
            win.setProperty(PROP_IDS, '')
        except Exception:
            pass

    def fade_out_and_clear(self):
        if self.built and self.probe():
            try:
                xbmcgui.Window(HOME_WINDOW_ID).setProperty(PROP_ON, '0')
            except Exception:
                pass
            self.mon.waitForAbort(self.fade_out / 1000.0 + 0.15)
        self.clear_now()

    def fade_anims(self):
        a = []
        if self.fade_in > 0:
            fi = 'effect=fade start=0 end=100 time=%d tween=sine easing=inout' % self.fade_in
            a.append(('WindowOpen', fi))
            a.append(('Visible', fi))
        if self.fade_out > 0:
            a.append(('Hidden', 'effect=fade start=100 end=0 time=%d '
                      'tween=sine easing=inout' % self.fade_out))
            a.append(('WindowClose', 'effect=fade start=100 end=0 time=%d'
                      % min(self.fade_out, CLOSE_FADE_CAP_MS)))
        return a

    def add(self, image, x, y, w, h, alpha_pct, anims):
        colour = self.pal[self.layer_i % len(self.pal)]
        self.layer_i += 1
        ctrl = xbmcgui.ControlImage(
            int(x), int(y), int(w), int(h),
            os.path.join(MEDIA, image),
            0,  # aspectRatio: 0 = stretch (no named constant in xbmcgui)
            argb(clamp(alpha_pct, 0, 100), colour))
        self.win.addControl(ctrl)
        ctrl.setVisibleCondition(VISIBLE_COND)
        ctrl.setAnimations(self.fade_anims() +
                           [('conditional', a) for a in anims])
        self.controls.append(ctrl)
        return ctrl

    # ------------------------------------------------------------------
    def build(self):
        self.clear_now()
        self.read_settings()
        self.sig = self.signature()
        if not self.enabled:
            return
        self.win = xbmcgui.Window(HOME_WINDOW_ID)
        self.win.setProperty(PROP_ON, '0')
        W = self.win.getWidth() or 1920
        H = self.win.getHeight() or 1080
        self.layer_i = 0
        builders = [self.build_waves, self.build_ribbons, self.build_bokeh,
                    self.build_aurora, self.build_orbs, self.build_rays,
                    self.build_stardust, self.build_ocean_night]
        try:
            builders[self.style](W, H, self.opacity)
        except Exception as e:
            log('build failed: %r' % (e,))
            self.clear_now()
            raise
        try:
            self.win.setProperty(
                PROP_IDS, ','.join(str(c.getId()) for c in self.controls))
        except Exception:
            pass
        self.built = True
        # Let Kodi register the hidden controls, then reveal -> fade in.
        self.mon.waitForAbort(0.2)
        self.win.setProperty(PROP_ON, '1')
        if not self.probe():
            self.probe_ok = False
            log('control probing unavailable, relying on skin signature only')
        log('overlay built (style=%s, %dx%d, %d layers)'
            % (STYLES[self.style], W, H, len(self.controls)))

    # ------------------------------------------------------------------
    # animation strings
    def a_slide_x(self, W, seconds, reverse=False):
        s, e = (-W, 0) if reverse else (0, -W)
        return ('effect=slide start=%d,0 end=%d,0 time=%d tween=linear '
                'loop=true condition=true' % (s, e, self.dur(seconds)))

    def a_up(self, H, seconds):
        return ('effect=slide start=0,0 end=0,-%d time=%d tween=linear '
                'loop=true condition=true' % (H, self.dur(seconds)))

    def a_drift(self, dx, dy, seconds):
        return ('effect=slide start=0,0 end=%d,%d time=%d tween=sine '
                'easing=inout pulse=true condition=true'
                % (dx, dy, self.dur(seconds)))

    def a_breathe(self, lo, hi, seconds):
        return ('effect=fade start=%d end=%d time=%d tween=sine '
                'easing=inout pulse=true condition=true'
                % (lo, hi, self.dur(seconds)))

    def a_zoom(self, lo, hi, seconds):
        return ('effect=zoom start=%d end=%d center=auto time=%d tween=sine '
                'easing=inout pulse=true condition=true'
                % (lo, hi, self.dur(seconds)))

    # ------------------------------------------------------------------
    # styles. Textures are 2x screen width and periodic every 1x width, so
    # sliding by exactly W loops seamlessly. Vertical tiles are 2x screen
    # height and periodic every 1x height.
    def build_waves(self, W, H, op):
        h = int(H * 0.5)
        y = H - h
        self.add('wave_back.png', 0, y - int(H * 0.04), W * 2, h, op * 0.55,
                 [self.a_slide_x(W, 80, True),
                  self.a_drift(0, int(H * 0.03), 7.5),
                  self.a_breathe(70, 100, 11)])
        self.add('wave_mid.png', 0, y, W * 2, h, op * 0.75,
                 [self.a_slide_x(W, 55),
                  self.a_drift(0, int(H * 0.024), 5.5),
                  self.a_breathe(80, 100, 8)])
        self.add('wave_front.png', 0, y + int(H * 0.04), W * 2, h, op,
                 [self.a_slide_x(W, 36, True),
                  self.a_drift(0, int(H * 0.018), 4.2)])

    def build_ribbons(self, W, H, op):
        self.add('ribbon_a.png', 0, 0, W * 2, H, op,
                 [self.a_slide_x(W, 110),
                  self.a_breathe(55, 100, 9),
                  self.a_drift(0, int(H * 0.03), 13)])
        self.add('ribbon_b.png', 0, 0, W * 2, H, op * 0.85,
                 [self.a_slide_x(W, 150, True),
                  self.a_breathe(100, 50, 12),
                  self.a_drift(0, int(H * 0.04), 17)])
        self.add('ribbon_c.png', 0, 0, W * 2, H, op * 0.7,
                 [self.a_slide_x(W, 190),
                  self.a_breathe(60, 100, 15),
                  self.a_drift(0, int(H * 0.025), 11)])

    def build_bokeh(self, W, H, op):
        self.add('bokeh_far.png', 0, 0, W, H * 2, op * 0.6,
                 [self.a_up(H, 90), self.a_breathe(60, 100, 7)])
        self.add('bokeh_mid.png', 0, 0, W, H * 2, op * 0.8,
                 [self.a_up(H, 62), self.a_breathe(100, 55, 9)])
        self.add('bokeh_near.png', 0, 0, W, H * 2, op,
                 [self.a_up(H, 40), self.a_breathe(70, 100, 11)])

    def build_aurora(self, W, H, op):
        self.add('aurora_a.png', 0, 0, W * 2, H, op * 0.85,
                 [self.a_slide_x(W, 170),
                  self.a_breathe(45, 100, 10),
                  self.a_drift(0, int(H * 0.04), 14)])
        self.add('aurora_b.png', 0, int(H * 0.04), W * 2, H, op * 0.7,
                 [self.a_slide_x(W, 230, True),
                  self.a_breathe(100, 40, 13),
                  self.a_drift(0, int(H * 0.05), 19)])
        self.add('aurora_c.png', 0, int(H * 0.08), W * 2, H, op * 0.55,
                 [self.a_slide_x(W, 300),
                  self.a_breathe(50, 100, 16),
                  self.a_drift(0, int(H * 0.03), 23)])

    def build_orbs(self, W, H, op):
        rnd = random.Random(11)
        for i in range(8):
            size = int(H * rnd.uniform(0.45, 0.95))
            x = rnd.uniform(-0.10, 0.90) * W
            y = rnd.uniform(-0.15, 0.75) * H
            dx = int(W * rnd.uniform(0.06, 0.18)) * rnd.choice((-1, 1))
            dy = int(H * rnd.uniform(0.06, 0.20)) * rnd.choice((-1, 1))
            self.add('glow.png', x, y, size, size, op * rnd.uniform(0.35, 0.6),
                     [self.a_drift(dx, 0, rnd.uniform(16, 30)),
                      self.a_drift(0, dy, rnd.uniform(13, 26)),
                      self.a_zoom(86, 114, rnd.uniform(9, 17)),
                      self.a_breathe(rnd.randint(35, 65), 100,
                                     rnd.uniform(7, 14))])

    def build_rays(self, W, H, op):
        self.add('rays_a.png', 0, 0, W * 2, H, op * 0.8,
                 [self.a_slide_x(W, 140),
                  self.a_breathe(40, 100, 9)])
        self.add('rays_b.png', 0, 0, W * 2, H, op * 0.65,
                 [self.a_slide_x(W, 200, True),
                  self.a_breathe(100, 35, 12)])
        self.add('rays_a.png', -int(W * 0.37), 0, W * 2, H, op * 0.45,
                 [self.a_slide_x(W, 260),
                  self.a_breathe(50, 100, 15)])

    def build_stardust(self, W, H, op):
        self.add('stars_far.png', 0, 0, W, H * 2, op * 0.8,
                 [self.a_up(H, 120), self.a_breathe(55, 100, 5)])
        self.add('stars_near.png', 0, 0, W, H * 2, op,
                 [self.a_up(H, 75), self.a_breathe(100, 45, 7)])

    def build_ocean_night(self, W, H, op):
        self.build_stardust(W, H, op)
        self.build_waves(W, H, op)


class Watcher(xbmc.Monitor):
    def __init__(self):
        super(Watcher, self).__init__()
        self.dirty = False

    def onSettingsChanged(self):
        self.dirty = True


def main():
    mon = Watcher()
    ov = Overlay(mon)
    # Give Kodi a moment to finish creating the Home window.
    if mon.waitForAbort(3):
        return
    ov.reap_old()
    ov.read_settings()

    need = True
    settings_changed = False
    settle_until = 0.0
    last_build = 0.0

    while not mon.abortRequested():
        active = xbmc.getCondVisibility('Window.IsActive(home)')
        now = time.time()

        if mon.dirty:
            mon.dirty = False
            need = True
            settings_changed = True

        # Skin / theme / resolution changed: Kodi reloads the window and
        # drops dynamically added controls. Wait for it to settle, rebuild.
        if ov.sig is not None and ov.signature() != ov.sig:
            log('skin/theme/resolution changed, will rebuild')
            ov.clear_now()
            ov.sig = None
            need = True
            settings_changed = False
            settle_until = now + 2.0

        if active and now >= settle_until:
            if (not need and ov.enabled and ov.built
                    and not ov.alive() and now - last_build >= 1.5):
                log('overlay controls lost, rebuilding')
                ov.clear_now()
                need = True
            if need:
                try:
                    if settings_changed:
                        ov.fade_out_and_clear()
                    ov.build()
                    need = False
                    settings_changed = False
                except Exception:
                    settle_until = time.time() + 2.0   # retry shortly
                last_build = time.time()

        if mon.waitForAbort(0.25 if active else 1.0):
            break

    ov.clear_now()


if __name__ == '__main__':
    main()
