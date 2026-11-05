# -*- coding: utf-8 -*-
"""PS2 Overlays - PlayStation 2 style clock, cubes and rings in one service.

Three independent transparent overlays are drawn on the Kodi Home window
(Window 10000) as non-focusable image controls, so input is never affected:

  * Clock - twelve translucent crystal bars that tip in 3D and shift from
            purple to cyan (23 s loop).
  * Cubes - translucent glass cubes crossing the whole screen from random
            directions.
  * Rings - glowing dots circling in orbiting rings.

Every overlay has its own on/off switch and its own settings (setting ids are
prefixed clock_ / cubes_ / rings_). Fade in / out times are global. There is no
3D movement: nothing rotates in 3D. Changing one overlay's settings rebuilds
only that overlay. All overlays are rebuilt after skin / theme / resolution
changes.
"""
import json
import math
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
CLOSE_FADE_CAP_MS = 400


def log(msg):
    xbmc.log('[script.service.ps2overlays] %s' % msg, xbmc.LOGINFO)


def argb(alpha_pct, rgb):
    a = max(0, min(255, int(255 * alpha_pct / 100.0)))
    return '%02X%s' % (a, rgb)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def skin_signature():
    return (xbmc.getSkinDir(),
            xbmc.getInfoLabel('Skin.CurrentTheme'),
            xbmc.getInfoLabel('Skin.CurrentColourTheme'),
            xbmc.getInfoLabel('System.ScreenWidth'),
            xbmc.getInfoLabel('System.ScreenHeight'))


# ----------------------------------------------------------------------
class Overlay(object):
    """Base class: control life-cycle, fading and settings handling."""

    PREFIX = ''          # 'clock', 'cubes', 'rings'
    # (key, default, min, max) integer settings, read as <PREFIX>_<key>
    INTS = []
    PALETTES = []        # (label, value) - value interpreted by subclass

    def __init__(self, mon):
        self.mon = mon
        self.win = None
        self.controls = []
        self.built = False
        self.probe_ok = True
        self.need = True
        self.settings_changed = False
        self.last_build = 0.0
        self.sig = None
        self.cfg = self.read()
        self.prop_on = 'ps2overlays.%s.on' % self.PREFIX
        self.prop_ids = 'ps2overlays.%s.ids' % self.PREFIX
        self.visible_cond = 'String.IsEqual(Window(Home).Property(%s),1)' % self.prop_on

    # -- settings ------------------------------------------------------
    def read(self):
        a = xbmcaddon.Addon()
        p = self.PREFIX + '_'
        cfg = {}
        try:
            cfg['enabled'] = a.getSettingBool(p + 'enabled')
        except Exception:
            cfg['enabled'] = True
        for key, default, lo, hi in ([('color', 0, 0, len(self.PALETTES) - 1),
                                      ('opacity', 100, 5, 100),
                                      ('speed', 100, 10, 1000),
                                      ('fade_in', 1000, 0, 10000),
                                      ('fade_out', 500, 0, 10000)] + self.INTS):
            try:
                # fade times are global (no prefix); everything else per overlay
                v = a.getSettingInt(key if key.startswith('fade_') else p + key)
            except Exception:
                v = default
            cfg[key] = clamp(v, lo, hi)
        return cfg

    def settings_differ(self):
        return self.read() != self.cfg

    def dur(self, seconds):
        return max(200, int(seconds * 1000 * 100.0 / self.cfg['speed']))

    # -- control management ---------------------------------------------
    def probe(self):
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
        try:
            win = xbmcgui.Window(HOME_WINDOW_ID)
        except Exception:
            win = None
        if win is not None:
            for c in self.controls:
                try:
                    win.getControl(c.getId())
                    win.removeControl(c)
                except Exception:
                    pass
            try:
                win.setProperty(self.prop_ids, '')
            except Exception:
                pass
        self.controls = []
        self.built = False

    def reap_old(self):
        """Remove controls left behind by a previous service instance."""
        try:
            win = xbmcgui.Window(HOME_WINDOW_ID)
            ids = win.getProperty(self.prop_ids)
            for i in [x for x in ids.split(',') if x]:
                try:
                    win.removeControl(win.getControl(int(i)))
                except Exception:
                    pass
            win.setProperty(self.prop_ids, '')
        except Exception:
            pass

    def fade_out_and_clear(self):
        if self.built and self.probe():
            try:
                xbmcgui.Window(HOME_WINDOW_ID).setProperty(self.prop_on, '0')
            except Exception:
                pass
            self.mon.waitForAbort(self.cfg['fade_out'] / 1000.0 + 0.15)
        self.clear_now()

    def fade_anims(self):
        a = []
        fin, fout = self.cfg['fade_in'], self.cfg['fade_out']
        if fin > 0:
            fi = 'effect=fade start=0 end=100 time=%d tween=sine easing=inout' % fin
            a.append(('WindowOpen', fi))
            a.append(('Visible', fi))
        if fout > 0:
            a.append(('Hidden', 'effect=fade start=100 end=0 time=%d '
                      'tween=sine easing=inout' % fout))
            a.append(('WindowClose', 'effect=fade start=100 end=0 time=%d'
                      % min(fout, CLOSE_FADE_CAP_MS)))
        return a

    def add(self, image, x, y, w, h, alpha_pct, colour, anims):
        ctrl = xbmcgui.ControlImage(
            int(x), int(y), max(1, int(w)), max(1, int(h)),
            os.path.join(MEDIA, image), 0,
            argb(clamp(alpha_pct, 0, 100), colour))
        self.win.addControl(ctrl)
        ctrl.setVisibleCondition(self.visible_cond)
        ctrl.setAnimations(self.fade_anims() +
                           [('conditional', a) for a in anims])
        self.controls.append(ctrl)
        return ctrl

    # -- animation strings ------------------------------------------------
    def a_fade(self, lo, hi, seconds):
        return ('effect=fade start=%d end=%d time=%d tween=sine '
                'easing=inout pulse=true condition=true'
                % (lo, hi, self.dur(seconds)))

    def a_spin(self, seconds, clockwise=True):
        s, e = (0, -360) if clockwise else (0, 360)
        return ('effect=rotate start=%d end=%d center=auto time=%d '
                'tween=linear loop=true condition=true'
                % (s, e, self.dur(seconds)))

    # -- build ------------------------------------------------------------
    def build(self):
        self.clear_now()
        self.cfg = self.read()
        self.sig = skin_signature()
        if not self.cfg['enabled']:
            return
        self.win = xbmcgui.Window(HOME_WINDOW_ID)
        self.win.setProperty(self.prop_on, '0')
        W = self.win.getWidth() or 1920
        H = self.win.getHeight() or 1080
        try:
            self.build_content(W, H)
        except Exception as e:
            log('%s build failed: %r' % (self.PREFIX, e))
            self.clear_now()
            raise
        try:
            self.win.setProperty(
                self.prop_ids, ','.join(str(c.getId()) for c in self.controls))
        except Exception:
            pass
        self.built = True
        self.mon.waitForAbort(0.2)
        self.win.setProperty(self.prop_on, '1')
        if not self.probe():
            self.probe_ok = False
            log('%s: control probing unavailable, relying on skin signature only'
                % self.PREFIX)
        log('%s built (%dx%d, %d controls)' % (self.PREFIX, W, H, len(self.controls)))

    def build_content(self, W, H):
        raise NotImplementedError


# ----------------------------------------------------------------------
class Clock(Overlay):
    PREFIX = 'clock'
    INTS = [('size', 90, 30, 150), ('shade', 45, 0, 100),
            ('pos_x', 50, 0, 100), ('pos_y', 50, 0, 100)]

    UNITS = 1300.0          # layout units of the artwork (see bars.json)
    LOOP_S = 23.0           # one purple -> cyan -> purple cycle
    PURPLE = '7C7FF0'
    CYAN = '63B5E0'

    # None = original two-colour crossfade (purple <-> cyan)
    PALETTES = [
        ('PS2 original (purple to cyan)', None),
        ('PlayStation blue', '4FA3FF'),
        ('White', 'FFFFFF'),
        ('Purple', 'B07CFF'),
        ('Teal', '3FE0C8'),
        ('Gold', 'FFC24A'),
        ('Pink', 'FF6B8A'),
        ('Green', '5CE05C'),
        ('Orange', 'FF8A3D'),
        ('Red', 'FF4D4D'),
        ('Ice', 'D6F2FF'),
    ]

    def __init__(self, mon):
        super(Clock, self).__init__(mon)
        self.bars = None

    def a_zoom(self, lo, hi, cx, cy, seconds):
        return ('effect=zoom start=%d end=%d center=%d,%d time=%d tween=sine '
                'easing=inout pulse=true condition=true'
                % (lo, hi, cx, cy, self.dur(seconds)))

    def build_content(self, W, H):
        if self.bars is None:
            with open(os.path.join(MEDIA, 'bars.json'), 'r') as f:
                self.bars = json.load(f)
        c = self.cfg
        op = c['opacity']
        d = min(W, H) * c['size'] / 100.0
        k = d / self.UNITS
        cx = int(W * c['pos_x'] / 100.0)
        cy = int(H * c['pos_y'] / 100.0)

        # dark backdrop behind the clock
        if c['shade'] > 0:
            sd = d * 1.9
            self.add('shade.png', cx - sd / 2, cy - sd / 2, sd, sd,
                     c['shade'], '000000', [])

        # crystal bars (two colour sets crossfade for the original palette)
        colour = self.PALETTES[c['color']][1]
        sets = ([(self.PURPLE, 100, 0), (self.CYAN, 0, 100)] if colour is None
                else [(colour, None, None)])
        for tint, f0, f1 in sets:
            for b in self.bars:
                w = b['w'] * k
                h = b['h'] * k
                x = cx + b['mx'] * k - w / 2.0
                y = cy + b['my'] * k - h / 2.0
                ix = int(cx + b['ix'] * k)
                iy = int(cy + b['iy'] * k)
                s = b['s']              # sin of the bar angle: -1 = 9 o'clock
                anims = []
                if f0 is not None:
                    anims.append(self.a_fade(f0, f1, self.LOOP_S / 2))
                # bar lengths swing between the two sides of the clock
                anims.append(self.a_zoom(int(100 - 34 * s), int(100 + 34 * s),
                                         ix, iy, self.LOOP_S * 1.1))
                self.add(b['f'], x, y, w, h, op, tint, anims)


# ----------------------------------------------------------------------
class Cubes(Overlay):
    PREFIX = 'cubes'
    INTS = [('count', 16, 1, 60), ('size', 100, 30, 250)]

    IMAGES = ['cube_a.png', 'cube_b.png', 'cube_c.png']
    PALETTES = [
        ('PS2 blue + white', ['4FA3FF', '8CCDFF', 'FFFFFF']),
        ('PlayStation blue', ['4FA3FF']),
        ('White', ['FFFFFF']),
        ('Purple', ['B07CFF']),
        ('Teal', ['3FE0C8']),
        ('Gold', ['FFC24A']),
        ('Pink', ['FF6B8A']),
        ('Green', ['5CE05C']),
        ('Orange', ['FF8A3D']),
        ('Red', ['FF4D4D']),
        ('Multi: Aurora', ['3FE0C8', '4FA3FF', 'B07CFF']),
        ('Multi: Sunset', ['FFB04A', 'FF5F8A', 'B07CFF']),
        ('Multi: Neon', ['FF4FD8', '4FD8FF', 'C6F135']),
    ]

    def build_content(self, W, H):
        """Every cube enters from beyond one screen edge, crosses the whole
        screen in a straight line and leaves beyond another edge, so the loop
        restart is never seen and no fading is needed."""
        c = self.cfg
        pal = self.PALETTES[c['color']][1]
        rnd = random.Random(2000)           # fixed seed = stable layout
        for i in range(c['count']):
            size = H * rnd.uniform(0.07, 0.20) * c['size'] / 100.0
            depth = size / (H * 0.20 * c['size'] / 100.0)      # ~0.35 .. 1
            m = size * 1.1                                      # off-screen margin
            ang = rnd.uniform(0, 2 * math.pi)
            ux, uy = math.cos(ang), math.sin(ang)
            # a point the path passes through (kept central so it crosses fully)
            qx = rnd.uniform(0.15, 0.85) * W
            qy = rnd.uniform(0.15, 0.85) * H
            # slab test against the screen grown by the margin
            t0, t1 = -1e9, 1e9
            for q, u, lo, hi in ((qx, ux, -m, W + m), (qy, uy, -m, H + m)):
                if abs(u) < 1e-6:
                    continue
                ta, tb = (lo - q) / u, (hi - q) / u
                if ta > tb:
                    ta, tb = tb, ta
                t0, t1 = max(t0, ta), min(t1, tb)
            sx, sy = qx + ux * t0, qy + uy * t0            # entry (off-screen)
            dx, dy = int(ux * (t1 - t0)), int(uy * (t1 - t0))
            dist = math.hypot(dx, dy)
            # pixels per second: nearer (bigger) cubes move faster
            v = W * rnd.uniform(0.035, 0.075) * (0.6 + 0.6 * depth)
            period = dist / v
            x, y = sx - size / 2.0, sy - size / 2.0
            colour = pal[i % len(pal)]
            alpha = c['opacity'] * (0.5 + 0.5 * depth)
            # stagger: wait off-screen before the first crossing
            delay = int(self.dur(rnd.uniform(0.0, 0.35) * period))
            anims = [
                ('effect=slide start=0,0 end=%d,%d time=%d delay=%d '
                 'tween=linear loop=true condition=true'
                 % (dx, dy, self.dur(period), delay)),
                # slow spin in the picture plane
                ('effect=rotate start=0 end=%d center=auto time=%d tween=linear '
                 'loop=true condition=true'
                 % (360 * rnd.choice((-1, 1)), self.dur(rnd.uniform(24, 70)))),
            ]
            # Draw the same random numbers the 3D version used so the cube
            # layout stays identical (the values themselves are unused now).
            for lo, hi in ((30, 55), (30, 55), (5, 11), (6, 13)):
                rnd.uniform(lo, hi)
            img = rnd.choice(self.IMAGES)
            self.add(img, x, y, size, size, alpha, colour, anims)


# ----------------------------------------------------------------------
class Rings(Overlay):
    PREFIX = 'rings'
    INTS = [('size', 90, 30, 150), ('pos_x', 50, 0, 100), ('pos_y', 50, 0, 100)]

    PALETTES = [
        ('PlayStation blue', ['4FA3FF']),
        ('White', ['FFFFFF']),
        ('Purple', ['B07CFF']),
        ('Teal', ['3FE0C8']),
        ('Gold', ['FFC24A']),
        ('Pink', ['FF6B8A']),
        ('Green', ['5CE05C']),
        ('Orange', ['FF8A3D']),
        ('Red', ['FF4D4D']),
        ('Ice', ['D6F2FF']),
        ('Multi: PS2 blue + white', ['4FA3FF', '8CCDFF', 'FFFFFF', 'B07CFF']),
        ('Multi: Aurora', ['3FE0C8', '4FA3FF', 'B07CFF']),
        ('Multi: Sunset', ['FFB04A', 'FF5F8A', 'B07CFF']),
        ('Multi: Neon', ['FF4FD8', '4FD8FF', 'C6F135']),
    ]

    def a_zoom(self, lo, hi, seconds):
        return ('effect=zoom start=%d end=%d center=auto time=%d tween=sine '
                'easing=inout pulse=true condition=true'
                % (lo, hi, self.dur(seconds)))

    def build_content(self, W, H):
        c = self.cfg
        op = c['opacity']
        pal = self.PALETTES[c['color']][1]
        layer = [0]

        def colour():
            col = pal[layer[0] % len(pal)]
            layer[0] += 1
            return col

        d = int(min(W, H) * c['size'] / 100.0)      # square ring canvas
        cx = int(W * c['pos_x'] / 100.0)
        cy = int(H * c['pos_y'] / 100.0)
        x = cx - d // 2
        y = cy - d // 2
        # soft centre glow
        g = int(d * 0.7)
        self.add('glow.png', cx - g // 2, cy - g // 2, g, g, op * 0.35, colour(),
                 [self.a_fade(50, 100, 5), self.a_zoom(92, 108, 7)])
        # comet-tail rings, each turning at its own speed / direction
        self.add('ring_outer.png', x, y, d, d, op, colour(),
                 [self.a_spin(9, True), self.a_fade(80, 100, 6)])
        self.add('ring_mid.png', x, y, d, d, op * 0.9, colour(),
                 [self.a_spin(6.5, False)])
        self.add('ring_dots.png', x, y, d, d, op * 0.8, colour(),
                 [self.a_spin(18, True), self.a_fade(60, 100, 4)])
        self.add('ring_inner.png', x, y, d, d, op * 0.9, colour(),
                 [self.a_spin(3.8, True)])


# ----------------------------------------------------------------------
class Watcher(xbmc.Monitor):
    def __init__(self):
        super(Watcher, self).__init__()
        self.dirty = False

    def onSettingsChanged(self):
        self.dirty = True


def main():
    mon = Watcher()
    overlays = [Clock(mon), Rings(mon), Cubes(mon)]
    if mon.waitForAbort(3):
        return
    for ov in overlays:
        ov.reap_old()

    settle_until = 0.0

    while not mon.abortRequested():
        active = xbmc.getCondVisibility('Window.IsActive(home)')
        now = time.time()

        if mon.dirty:
            mon.dirty = False
            for ov in overlays:
                if ov.settings_differ():
                    ov.need = True
                    ov.settings_changed = True

        sig = skin_signature()
        for ov in overlays:
            if ov.sig is not None and sig != ov.sig:
                log('skin/theme/resolution changed, will rebuild %s' % ov.PREFIX)
                ov.clear_now()
                ov.sig = None
                ov.need = True
                ov.settings_changed = False
                settle_until = now + 2.0

        if active and now >= settle_until:
            for ov in overlays:
                if (not ov.need and ov.cfg['enabled'] and ov.built
                        and not ov.alive() and now - ov.last_build >= 1.5):
                    log('%s controls lost, rebuilding' % ov.PREFIX)
                    ov.clear_now()
                    ov.need = True
                if ov.need:
                    try:
                        if ov.settings_changed:
                            ov.fade_out_and_clear()
                        ov.build()
                        ov.need = False
                        ov.settings_changed = False
                    except Exception:
                        settle_until = time.time() + 2.0
                    ov.last_build = time.time()

        if mon.waitForAbort(0.25 if active else 1.0):
            break

    for ov in overlays:
        ov.clear_now()


if __name__ == '__main__':
    main()
