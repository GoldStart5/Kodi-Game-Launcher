# -*- coding: utf-8 -*-
"""PS2 Overlays - PlayStation 2 style clock, cubes and rings in one service.

Independent transparent overlays are drawn on the Kodi Home window
(Window 10000) as non-focusable image controls, so input is never affected:

  * Clock - twelve translucent crystal bars that tip in 3D and shift from
            purple to cyan (23 s loop).
  * Cubes - translucent glass cubes crossing the whole screen from random
            directions.
  * Rings - glowing dots circling in orbiting rings.
  * Light sweep - two slow anamorphic light streaks (top / bottom, opposite
            directions) drifting behind the others.
  * Backdrop - the dark shade behind the clock; its own layer.
  * Waves - PSP / XMB style rolling wave background in many colours (also
            automatic by month); the very bottom layer.
  * Sparkles - PS5-style background (breathing top light, floor haze, hovering
            and twinkling specks and bokeh) measured from a reference clip;
            the very bottom layer.

Two ways of drawing (setting "skin_patch"):
  * inside the skin (default on a supported skin, see skinpatch.py): the overlays
    are written into the skin as an include, so they are drawn BEHIND all of the
    skin's widgets, menus and text, in every window that uses its background.
  * on top of the skin: live controls on the Home window (the original method).

Layer order (bottom to top): waves, sparkles, backdrop, light sweep, clock, rings, cubes. When an
overlay is rebuilt, everything above it is rebuilt too, so the order holds.
The clock lights the bar of the current hour (12 o'clock = top bar).

Every overlay has its own on/off switch and its own settings (setting ids are
prefixed clock_ / cubes_ / rings_). Fade in / out times are global. There is no
3D movement: nothing rotates in 3D. Changing one overlay's settings rebuilds
only that overlay. All overlays are rebuilt after skin / theme / resolution
changes.
"""
import colorsys
import json
import math
import os
import random
import time

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

import skinpatch
from focus import FocusWatcher

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
MEDIA = os.path.join(ADDON_PATH, 'resources', 'media')
HOME_WINDOW_ID = 10000
CLOSE_FADE_CAP_MS = 400
PROP_HOUR = 'ps2overlays.hour'      # 0-11, 0 = 12 o'clock = top bar


def log(msg):
    xbmc.log('[script.service.ps2overlays] %s' % msg, xbmc.LOGINFO)


def argb(alpha_pct, rgb):
    a = max(0, min(255, int(255 * alpha_pct / 100.0)))
    return '%02X%s' % (a, rgb)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def set_hour_property():
    """Publish the current hour (0-11) for the clock's shine layers."""
    try:
        h = str(time.localtime().tm_hour % 12)
        win = xbmcgui.Window(HOME_WINDOW_ID)
        if win.getProperty(PROP_HOUR) != h:
            win.setProperty(PROP_HOUR, h)
    except Exception:
        pass


def set_focus_property(win, focused):
    """Publish whether Kodi is the foreground app ('1'/'0') for the skin include."""
    try:
        win.setProperty(skinpatch.FOCUS_PROP, '1' if focused else '0')
    except Exception:
        pass


def focus_fade_cfg():
    """(fade_in_ms, fade_out_ms) of the focus fade (always on, uses the Fading sliders)."""
    a = xbmcaddon.Addon()
    try:
        return (clamp(a.getSettingInt('fade_in'), 0, 10000), clamp(a.getSettingInt('fade_out'), 0, 10000))
    except Exception:
        return (1000, 500)


def skin_signature():
    return (xbmc.getSkinDir(),
            xbmc.getInfoLabel('Skin.CurrentTheme'),
            xbmc.getInfoLabel('Skin.CurrentColourTheme'),
            xbmc.getInfoLabel('System.ScreenWidth'),
            xbmc.getInfoLabel('System.ScreenHeight'))


# ----------------------------------------------------------------------
class Overlay(object):
    """Base class: control life-cycle, fading and settings handling."""

    PREFIX = ''          # 'clock', 'cubes', 'rings', ...
    READ_OPACITY = True  # False: overlay has no opacity setting
    # (key, default, min, max) integer settings, read as <PREFIX>_<key>
    INTS = []
    # (key, default) boolean settings, read as <PREFIX>_<key>
    BOOLS = []
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
        self.rec = None             # list = record specs for the skin include
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
        for key, default, lo, hi in ([('color', 0, 0, len(self.PALETTES) - 1)] +
                                     ([('opacity', 100, 5, 100)] if self.READ_OPACITY else []) +
                                     [('speed', 100, 10, 1000),
                                      ('fade_in', 1000, 0, 10000),
                                      ('fade_out', 500, 0, 10000)] + self.INTS):
            try:
                # fade times are global (no prefix); everything else per overlay
                v = a.getSettingInt(key if key.startswith('fade_') else p + key)
            except Exception:
                v = default
            cfg[key] = clamp(v, lo, hi)
        for key, default in self.BOOLS:
            try:
                cfg[key] = a.getSettingBool(p + key)
            except Exception:
                cfg[key] = default
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

    def add(self, image, x, y, w, h, alpha_pct, colour, anims, extra_cond=None):
        if self.rec is not None:
            # skin mode: only record; the skin draws it (always behind its widgets).
            # Window change: the overlay fades out with the old window, then fades
            # in with the new one (Kodi runs the two one after the other, and
            # skin animations restart in each window, so this hides the restart).
            # The hour-shine layers also cross-fade when the hour changes.
            fin, fout = self.cfg['fade_in'], self.cfg['fade_out']
            fades = []
            if fout > 0:
                fades.append(('WindowClose', 'effect=fade start=100 end=0 time=%d '
                              'tween=sine easing=inout' % min(fout, 2000)))
            if fin > 0:
                fades.append(('WindowOpen', 'effect=fade start=0 end=100 time=%d '
                              'tween=sine easing=inout' % fin))
            if extra_cond:
                fades += [a for a in self.fade_anims() if a[0] in ('Visible', 'Hidden')]
            self.rec.append(dict(image=image, x=x, y=y, w=w, h=h,
                                 colour=argb(clamp(alpha_pct, 0, 100), colour),
                                 cond=extra_cond,
                                 anims=fades + [('Conditional', a) for a in anims],
                                 **(dict(group=self._grp[0], group_anims=[('Conditional', a) for a in self._grp[1]])
                                    if getattr(self, '_grp', None) else {})))
            return None
        ctrl = xbmcgui.ControlImage(
            int(x), int(y), max(1, int(w)), max(1, int(h)),
            os.path.join(MEDIA, image), 0,
            argb(clamp(alpha_pct, 0, 100), colour))
        self.win.addControl(ctrl)
        ctrl.setVisibleCondition(
            self.visible_cond + (' + ' + extra_cond if extra_cond else ''))
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
        if self.rec is not None:
            self.build_content(1920, 1080)      # skin layout is 1920x1080
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
    INTS = [('size', 80, 30, 150),
            ('pos_x', 50, 0, 100), ('pos_y', 50, 0, 100)]
    BOOLS = [('shine', True)]

    UNITS = 1300.0          # layout units of the artwork (see bars.json)
    LOOP_S = 23.0           # one purple -> cyan -> purple cycle
    SHINE_TINT = 'F2FAFF'
    GLEAMS = 4              # gleam bands per bar, travelling inner -> outer end
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

        # crystal bars (two colour sets crossfade for the original palette)
        colour = self.PALETTES[c['color']][1]
        sets = ([(self.PURPLE, 100, 0), (self.CYAN, 0, 100)] if colour is None
                else [(colour, None, None)])
        zooms = {}
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
                zoom = self.a_zoom(int(100 - 34 * s), int(100 + 34 * s),
                                   ix, iy, self.LOOP_S * 1.1)
                zooms[b['f']] = (zoom, x, y, w, h)
                anims.append(zoom)
                self.add(b['f'], x, y, w, h, op, tint, anims)

        # shine on the bar of the current hour. One set of layers per bar is
        # built; only the one matching the Home window property is visible
        # (the service updates it), so hour changes cross-fade smoothly.
        if c['shine']:
            set_hour_property()
            for hour, b in enumerate(self.bars):
                zoom, x, y, w, h = zooms[b['f']]
                cond = 'String.IsEqual(Window(Home).Property(%s),%d)' % (PROP_HOUR, hour)
                # glossy glass, breathing slowly
                self.add('shine_%02d.png' % hour, x, y, w, h, op * 0.8,
                         self.SHINE_TINT, [zoom, self.a_fade(55, 100, 2.0)], cond)
                # sharp gleam running along the bar every ~4 s; the cubic
                # ease-in pulse makes each band flash briefly, and the
                # staggered delays turn the bands into a sweep
                for k in range(self.GLEAMS):
                    gleam = ('effect=fade start=0 end=100 time=%d tween=cubic '
                             'easing=in pulse=true condition=true delay=%d'
                             % (self.dur(2.0), self.dur(0.28 * k)))
                    self.add('gleam_%02d_%d.png' % (hour, k), x, y, w, h, op,
                             'FFFFFF', [zoom, gleam], cond)


# ----------------------------------------------------------------------
class Waves(Overlay):
    """PSP / XMB style background: a blue gradient with soft translucent waves
    rolling across it. Gradient, wave shapes, speeds and colours were measured
    from a reference loop (about one wavelength per screen width, the main wave
    travelling left in ~14 s, the whole group swaying every ~10 s). Colours are
    the reference's own hue-rotated, so every theme keeps the same contrast."""
    PREFIX = 'waves'
    READ_OPACITY = False
    INTS = [('strength', 60, 0, 100), ('height', 50, 0, 100)]

    # reference colours: dark sky, mid sky, light sky, left ground, wave tint
    BASE = [(0, 2, 75), (0, 98, 186), (6, 176, 221), (54, 151, 212), (48, 182, 229)]
    # (label, hue shift in degrees, saturation x, value x); None = by month
    PALETTES = [
        ('Automatic (by month)', None, None, None),
        ('PSP blue', 0, 1.0, 1.0),
        ('Cyan', -22, 0.95, 1.0),
        ('Teal', -48, 0.85, 0.95),
        ('Green', -68, 0.78, 0.9),
        ('Lime', -108, 0.72, 0.92),
        ('Gold', -165, 0.82, 0.95),
        ('Orange', -180, 0.88, 0.97),
        ('Red', -205, 0.88, 0.92),
        ('Pink', 140, 0.72, 1.0),
        ('Magenta', 112, 0.82, 0.92),
        ('Purple', 80, 0.82, 0.92),
        ('Violet', 52, 0.9, 0.98),
        ('Silver', 0, 0.08, 1.0),
        ('Graphite', 0, 0.15, 0.6),
    ]
    # theme for each month (index into PALETTES), January first
    MONTHS = [13, 9, 5, 4, 3, 2, 1, 12, 11, 7, 8, 6]
    # (image, direction: -1 = moves left, +1 = moves right, seconds per screen width)
    LAYERS = [('wave_layer_0.png', -1, 14.0), ('wave_layer_1.png', -1, 19.0),
              ('wave_layer_2.png', 1, 44.0)]

    def read(self):
        cfg = super(Waves, self).read()
        theme = cfg['color']
        if self.PALETTES[theme][1] is None:
            theme = self.MONTHS[time.localtime().tm_mon - 1]
        cfg['theme'] = theme
        return cfg

    def colours(self, theme):
        """The reference colours moved to the theme's hue. The original blue
        keeps the reference's exact hue spread (navy -> blue -> cyan); other
        themes keep only 30% of it so the gradient stays one clean colour."""
        _, hue, sat, val = self.PALETTES[theme]
        spread = 1.0 if hue == 0 and sat == 1.0 else 0.3
        mid_h = colorsys.rgb_to_hsv(*[x / 255.0 for x in self.BASE[1]])[0]
        out = []
        for r, g, b in self.BASE:
            h, sv, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            d = ((h - mid_h + 0.5) % 1.0) - 0.5                 # offset from the mid colour
            h = (mid_h + hue / 360.0 + d * spread) % 1.0
            sv = clamp(sv * sat, 0.0, 1.0)
            v = clamp(v * val, 0.0, 1.0)
            out.append('%02X%02X%02X' % tuple(int(round(x * 255)) for x in colorsys.hsv_to_rgb(h, sv, v)))
        return out

    def build_content(self, W, H):
        c = self.cfg
        st = c['strength']
        if st <= 0:
            return
        dark, mid, light, accent, tint = self.colours(c['theme'])
        off = int((c['height'] - 50) / 100.0 * 0.5 * H)     # +-25 % of the screen
        # three-stop sky gradient, then the lighter ground on the left
        self.add('solid.png', 0, 0, W, H, st, dark, [])
        self.add('wave_sky1.png', 0, 0, W, H, st, mid, [])
        self.add('wave_sky2.png', 0, 0, W, H, st, light, [])
        self.add('wave_ground.png', 0, 0, W, H, st, accent, [])
        # translucent waves: each image is two screen widths of a seamless wave,
        # slid by exactly one screen width per loop, plus a slow vertical sway
        for i, (img, direction, period) in enumerate(self.LAYERS):
            x0 = 0 if direction < 0 else -W
            slide = ('effect=slide start=0,0 end=%d,0 time=%d tween=linear '
                     'loop=true condition=true'
                     % (direction * W, self.dur(period)))
            sway = ('effect=slide start=0,0 end=0,%d time=%d delay=%d tween=sine '
                    'easing=inout pulse=true condition=true'
                    % (int(0.025 * H), self.dur(5.0 + 1.3 * i), self.dur(1.7 * i)))
            self.add(img, x0, off, 2 * W, int(1.5 * H), st, tint, [slide, sway])


# ----------------------------------------------------------------------
class Sparkles(Overlay):
    """PS5-style background, rebuilt from a reference recording: a warm light
    cone from the top left that slowly breathes, a grey-blue haze on the floor,
    and a cloud of tiny glowing specks and soft gold bokeh that hover and
    twinkle (specks flash, bokeh breathe, everything floats). Light, haze and the particle layout (sparks.json: position, size
    and colour of every particle) were measured from the recording."""
    PREFIX = 'sparkles'
    INTS = [('count', 110, 10, 250), ('size', 100, 30, 250),
            ('light', 100, 0, 100), ('dim', 40, 0, 90)]
    BEAM_HALF_S = 3.5               # light breathes dim -> bright -> dim in ~7 s
    NAVY = '050513'
    # (label, colour multiplied onto the light/haze and, when the third item is
    # None, onto the particles' original colours; or a list of particle colours)
    PALETTES = [
        ('PS5 original', 'FFFFFF', None),
        ('Ice blue', 'B8D8FF', None),
        ('Cyan', 'A8F0FF', None),
        ('Teal', 'B0FFF0', None),
        ('Green', 'C0FFC0', None),
        ('Lime', 'E0FFA0', None),
        ('Gold', 'FFE0A0', None),
        ('Orange', 'FFC890', None),
        ('Red', 'FFB0B0', None),
        ('Rose', 'FFC0D0', None),
        ('Pink', 'FFB8E8', None),
        ('Purple', 'D2B8FF', None),
        ('Violet', 'C0B0FF', None),
        ('Multi: Aurora', 'B8D8FF', ['3FE0C8', '4FA3FF', 'B07CFF', 'FFFFFF']),
        ('Multi: Sunset', 'FFD0B0', ['FFB04A', 'FF5F8A', 'B07CFF', 'FFFFFF']),
        ('Multi: Neon', 'D8C8FF', ['FF4FD8', '4FD8FF', 'C6F135', 'FFFFFF']),
        ('Multi: Candy', 'FFD8EC', ['FF8AD8', '8AE0FF', 'FFE08A', 'C8A0FF']),
        ('Multi: Rainbow', 'FFFFFF', ['FF5A5A', 'FFB04A', 'FFE45A', '5AE07A', '4FA3FF', 'B07CFF']),
    ]

    def __init__(self, mon):
        super(Sparkles, self).__init__(mon)
        self.sparks = None

    @staticmethod
    def mul(a, b):
        """Multiply two RRGGBB colours."""
        return ''.join('%02X' % (int(a[i:i + 2], 16) * int(b[i:i + 2], 16) // 255)
                       for i in (0, 2, 4))

    def build_content(self, W, H):
        if self.sparks is None:
            with open(os.path.join(MEDIA, 'sparks.json'), 'r') as f:
                self.sparks = json.load(f)
        c = self.cfg
        _, tint, multi = self.PALETTES[c['color']]
        # dark navy tint (the reference is near-black; the skin behind is not)
        if c['dim'] > 0:
            self.add('solid.png', 0, 0, W, H, c['dim'], self.NAVY, [])
        # light cone + floor haze, and the breathing of the light
        if c['light'] > 0:
            self.add('ps5_plate.png', 0, 0, W, H, c['light'], tint, [])
            self.add('ps5_beam.png', 0, 0, W, H, c['light'], tint,
                     [self.a_fade(0, 100, self.BEAM_HALF_S)])
        # particles, most important first, so the count slider keeps the best
        rnd = random.Random(5050)           # fixed seed = stable motion
        scale = c['size'] / 100.0
        for n, sp in enumerate(self.sparks[:c['count']]):
            d = sp['d'] * H * scale
            if sp['k'] == 'disc':
                img, size, alpha = 'spark_disc.png', max(10.0, d * 1.3), sp['a'] * 0.95
            else:
                img, size, alpha = 'spark_dot.png', max(7.0, d * 4.0 * min(1.0, scale + 0.2)), min(1.0, sp['a'] * 1.2)
            x = sp['u'] * W - size / 2.0
            y = sp['v'] * H - size / 2.0
            colour = multi[n % len(multi)] if multi else self.mul(sp['c'], tint)
            # smooth float along a sine path: tens of pixels, back and forth
            amp = H * rnd.uniform(0.03, 0.08)
            ang = rnd.uniform(0, 6.2832)
            anims = [('effect=slide start=0,0 end=%d,%d time=%d delay=%d tween=sine '
                      'easing=inout pulse=true condition=true'
                      % (int(amp * math.cos(ang)), int(amp * math.sin(ang)),
                         self.dur(rnd.uniform(7, 16)), self.dur(rnd.uniform(0, 8))))]
            if sp['k'] == 'disc':
                # bokeh breathe gently
                period = rnd.uniform(3.0, 7.0)
                anims.append('effect=fade start=%d end=100 time=%d delay=%d tween=sine '
                             'easing=inout pulse=true condition=true'
                             % (rnd.randint(45, 70), self.dur(period),
                                self.dur(rnd.uniform(0, 2 * period))))
            else:
                # specks shine: flash from nearly dark to full brightness with a
                # small bloom, then fade away again
                period = rnd.uniform(1.2, 3.8)
                delay = self.dur(rnd.uniform(0, 2 * period))
                anims.append('effect=fade start=%d end=100 time=%d delay=%d tween=sine '
                             'easing=inout pulse=true condition=true'
                             % (rnd.randint(3, 20), self.dur(period), delay))
                anims.append('effect=zoom start=%d end=%d center=auto time=%d delay=%d '
                             'tween=sine easing=inout pulse=true condition=true'
                             % (rnd.randint(55, 75), rnd.randint(120, 160),
                                self.dur(period), delay))
            self.add(img, x, y, size, size, c['opacity'] * alpha, colour, anims)


# ----------------------------------------------------------------------
class Backdrop(Overlay):
    """Dark shade behind the clock. Own layer, always built first so it sits
    behind every other overlay. Uses the clock's size / position / darkness
    settings and follows the clock's on/off switch."""
    PREFIX = 'backdrop'

    def read(self):
        a = xbmcaddon.Addon()

        def gi(key, default, lo, hi):
            try:
                return clamp(a.getSettingInt(key), lo, hi)
            except Exception:
                return default
        try:
            on = a.getSettingBool('clock_enabled')
        except Exception:
            on = True
        cfg = {'shade': gi('clock_shade', 45, 0, 100),
               'size': gi('clock_size', 80, 30, 150),
               'pos_x': gi('clock_pos_x', 50, 0, 100),
               'pos_y': gi('clock_pos_y', 50, 0, 100),
               'fade_in': gi('fade_in', 1000, 0, 10000),
               'fade_out': gi('fade_out', 500, 0, 10000),
               'speed': 100}
        cfg['enabled'] = on and cfg['shade'] > 0
        return cfg

    def build_content(self, W, H):
        c = self.cfg
        d = min(W, H) * c['size'] / 100.0
        cx = int(W * c['pos_x'] / 100.0)
        cy = int(H * c['pos_y'] / 100.0)
        sd = d * 1.9
        self.add('shade.png', cx - sd / 2, cy - sd / 2, sd, sd,
                 c['shade'], '000000', [])


# ----------------------------------------------------------------------
class Sweep(Overlay):
    """Two anamorphic light streaks (top and bottom) gliding across the screen
    in opposite directions, each off-screen for roughly half of its pass."""
    PREFIX = 'sweep'
    INTS = [('size', 100, 30, 200), ('top_y', 8, 0, 100),
            ('bottom_y', 92, 0, 100), ('drift', 6, 0, 30)]
    PERIOD_S = 40.0
    PALETTES = [
        ('Ice white', 'D6F2FF'),
        ('PlayStation blue', '4FA3FF'),
        ('Purple', 'B07CFF'),
        ('Teal', '3FE0C8'),
        ('Gold', 'FFC24A'),
        ('Pink', 'FF6B8A'),
        ('Orange', 'FF8A3D'),
        ('Green', '5CE05C'),
    ]

    def build_content(self, W, H):
        c = self.cfg
        op = c['opacity']
        colour = self.PALETTES[c['color']][1]
        sw = int(W * 0.9 * c['size'] / 100.0)        # streak width
        sh = max(8, int(sw * 112 / 1600.0))          # keeps the artwork's ratio
        g = int(sw * 0.16)                           # hot core of the flare
        run = W + 3 * sw                             # path length, fully off-screen both ends
        drift = int(H * c['drift'] / 100.0)
        # (start x, y, dx, dy, delay in seconds)
        #   top streak:    left -> right, drifting up towards the top-right corner
        #   bottom streak: right -> left, drifting down towards the bottom-left corner
        # The bottom one runs half a cycle later so they never peak together.
        paths = [(-2 * sw, int(H * c['top_y'] / 100.0), run, -drift, 0.0),
                 (W + sw, int(H * c['bottom_y'] / 100.0), -run, drift, self.PERIOD_S / 2)]
        for x0, y0, dx, dy, delay in paths:
            slide = ('effect=slide start=0,0 end=%d,%d time=%d delay=%d tween=linear '
                     'loop=true condition=true'
                     % (dx, dy, self.dur(self.PERIOD_S), self.dur(delay) if delay else 0))
            self.add('sweep_streak.png', x0, y0 - sh / 2.0, sw, sh, op, colour,
                     [slide, self.a_fade(70, 100, 3.0)])
            self.add('glow.png', x0 + sw / 2.0 - g / 2.0, y0 - g / 2.0, g, g,
                     op * 0.8, colour, [slide, self.a_fade(60, 100, 2.5)])


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


class Crystal(Overlay):
    """Faceted glass emblem (four diamond tiles) with light shining inside: crystal body, inner
    light (the whole glass glows, as on the clock bars), bright facet edges,
    slanted gleams running through the crystal and a star flare, with an
    optional halo. Optional bounce and zoom."""
    PREFIX = 'crystal'
    INTS = [('size', 22, 5, 100), ('pos_x', 82, 0, 100), ('pos_y', 22, 0, 100),
            ('light_color', 0, 0, 10), ('glow', 55, 0, 100),
            ('bounce_h', 16, 1, 40), ('zoom_amt', 10, 1, 30)]
    BOOLS = [('bounce', True), ('zoom', True), ('shine', True)]
    PALETTES = [
        ('Sapphire blue', '4F8FFF'),
        ('Ice blue', '8CCDFF'),
        ('Cyan', '3FD8F0'),
        ('Emerald', '3FE0A0'),
        ('Green', '5CE05C'),
        ('Lime', 'C6F135'),
        ('Gold', 'FFC24A'),
        ('Orange', 'FF8A3D'),
        ('Ruby red', 'FF4D5A'),
        ('Rose', 'FF7FB0'),
        ('Pink', 'FF5FD0'),
        ('Amethyst purple', 'B07CFF'),
        ('Violet', '7C7FF0'),
        ('Diamond white', 'FFFFFF'),
    ]
    LIGHTS = [
        ('Automatic (matches the crystal)', None),
        ('White', 'FFFFFF'),
        ('Warm gold', 'FFD98A'),
        ('Ice blue', 'BFE3FF'),
        ('Cyan', '9FF4FF'),
        ('Mint', 'A8FFD8'),
        ('Lime', 'E4FF8A'),
        ('Orange', 'FFB070'),
        ('Red', 'FF8A8A'),
        ('Pink', 'FFA8DC'),
        ('Purple', 'D2A8FF'),
    ]
    SPOT = (216 / 512.0, 82 / 512.0)       # where the star flare sits on the artwork

    @staticmethod
    def mix(a, b, t):
        """Blend RRGGBB a towards b by t."""
        return ''.join('%02X' % int(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t)
                       for i in (0, 2, 4))

    def build_content(self, W, H):
        c = self.cfg
        op = c['opacity']
        crystal = self.PALETTES[c['color']][1]
        light = self.LIGHTS[c['light_color']][1] or self.mix(crystal, 'FFFFFF', 0.55)
        edge = self.mix(crystal, 'FFFFFF', 0.75)
        glint = self.mix(light, 'FFFFFF', 0.5)
        d = int(min(W, H) * c['size'] / 100.0)
        cx = int(W * c['pos_x'] / 100.0)
        cy = int(H * c['pos_y'] / 100.0)
        x, y = cx - d // 2, cy - d // 2
        motion = []
        # Kodi snaps unrotated images to whole pixels, so a slow, small move or zoom
        # advances one pixel at a time and looks like skipped frames. Motions here
        # are bigger and quicker, and a tiny sway (rotation) is added: rotated
        # images are not pixel-snapped, which keeps the move smooth.
        if c['zoom']:
            motion.append('effect=zoom start=%d end=%d center=%d,%d time=%d tween=sine '
                          'easing=inout pulse=true condition=true'
                          % (100 - c['zoom_amt'], 100 + c['zoom_amt'], cx, cy, self.dur(2.4)))
        if c['bounce']:
            motion.append('effect=slide start=0,0 end=0,%d time=%d tween=sine '
                          'easing=inout pulse=true condition=true'
                          % (-int(d * c['bounce_h'] / 100.0), self.dur(1.2)))
        if c['zoom'] or c['bounce']:
            motion.append('effect=rotate start=-1 end=1 center=%d,%d time=%d tween=sine '
                          'easing=inout pulse=true condition=true' % (cx, cy, self.dur(2.4)))
        if self.rec is not None:
            # skin mode: one animated group, so every layer moves rigidly together
            self._grp = ('crystal', motion)
            motion = []
        else:
            self._grp = None
        # halo
        if c['glow'] > 0:
            g = int(d * 1.9)
            self.add('glow.png', cx - g // 2, cy - g // 2, g, g, op * c['glow'] / 100.0 * 0.6,
                     light, [self.a_fade(50, 100, 4.0)] + motion)
        self.add('crystal_body.png', x, y, d, d, op, crystal, list(motion))
        self.add('crystal_light.png', x, y, d, d, op * 0.95, light,
                 [self.a_fade(55, 100, 2.0)] + motion)
        self.add('crystal_edges.png', x, y, d, d, op, edge, list(motion))
        if c['shine']:
            # sharp slanted gleams running through the glass, one band after
            # another (staggered delays), like the shine on the clock bars
            for k in range(5):
                glint_a = ('effect=fade start=0 end=100 time=%d tween=cubic easing=in '
                           'pulse=true condition=true delay=%d'
                           % (self.dur(2.0), self.dur(0.28 * k)))
                self.add('crystal_gleam_%d.png' % k, x, y, d, d, op, glint,
                         [glint_a] + motion)
            f = int(d * 0.5)
            fx = x + int(d * self.SPOT[0]) - f // 2
            fy = y + int(d * self.SPOT[1]) - f // 2
            flare = ('effect=fade start=0 end=100 time=%d tween=cubic easing=in pulse=true '
                     'condition=true delay=%d' % (self.dur(1.8), self.dur(0.5)))
            self.add('crystal_flare.png', fx, fy, f, f, op, 'FFFFFF', [flare] + motion)
        self._grp = None


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def collect_specs(overlays):
    """What every enabled overlay would draw, bottom to top, as plain data."""
    specs = []
    for ov in overlays:
        ov.rec = specs
        try:
            ov.build()
        finally:
            ov.rec = None
        ov.built = False                    # nothing live: the skin draws it
    return specs


def media_base():
    """Texture folder as the skin should name it."""
    media = os.path.normpath(MEDIA)
    try:
        home = os.path.normpath(xbmcvfs.translatePath('special://home/'))
        if media.startswith(home + os.sep):
            return 'special://home/' + os.path.relpath(media, home).replace(os.sep, '/') + '/'
    except Exception:
        pass
    return media.replace(os.sep, '/') + '/'


def notify(message):
    try:
        xbmcgui.Dialog().notification('PS2 Overlays', message, xbmcgui.NOTIFICATION_WARNING, 7000)
    except Exception:
        pass


class Watcher(xbmc.Monitor):
    def __init__(self):
        super(Watcher, self).__init__()
        self.dirty = False

    def onSettingsChanged(self):
        self.dirty = True


def main():
    mon = Watcher()
    # bottom -> top; in python mode a rebuilt overlay also rebuilds those above it
    overlays = [Waves(mon), Sparkles(mon), Backdrop(mon), Sweep(mon), Clock(mon), Rings(mon), Crystal(mon), Cubes(mon)]
    if mon.waitForAbort(3):
        return
    for ov in overlays:
        ov.reap_old()

    settle_until = 0.0
    last_theme_check = 0.0
    mode = None                 # 'skin' (inside the skin) or 'python' (on top)
    next_eval = 0.0
    skin_pending = None         # when to (re)write the skin include
    blocked_skin = None         # skin we failed to patch (until settings change)
    skin_id = None
    patcher = None
    focus = FocusWatcher(log)
    home = xbmcgui.Window(HOME_WINDOW_ID)
    applied_focus = None        # focus-fade config the include was written with
    last_focus = None           # last value published to the skin
    last_slow = 0.0

    while not mon.abortRequested():
        now = time.time()
        # Behind the skin, most ticks only look at window focus (a plain Windows
        # call, no Kodi API) and publish it when it changes. Every Kodi API call
        # takes the GUI/Python locks and can make animations stutter, so the rest
        # of the bookkeeping runs about once a second.
        if mode == 'skin' and not mon.dirty and now - last_slow < 1.0:
            f = focus.has_focus()
            if f != last_focus:
                last_focus = f
                set_focus_property(home, f)
            if mon.waitForAbort(0.25):
                break
            continue
        last_slow = now
        dirty = mon.dirty
        mon.dirty = False
        set_hour_property()

        cur = xbmc.getSkinDir()
        if cur != skin_id:
            skin_id = cur
            patcher = skinpatch.SkinPatcher(skin_id)
            next_eval = 0.0
        if dirty:
            blocked_skin = None
            next_eval = 0.0

        # ---- which way to draw
        if now >= next_eval:
            next_eval = now + 60
            try:
                wants = xbmcaddon.Addon().getSettingBool('skin_patch')
            except Exception:
                wants = True
            want = 'skin' if (wants and blocked_skin != skin_id and patcher.supported()) else 'python'
            if want != mode:
                if mode == 'skin':
                    # switching away: take the patch out of the skin again
                    try:
                        if skinpatch.remove_everywhere():
                            xbmc.executebuiltin('ReloadSkin()')
                            settle_until = now + 4.0
                    except Exception as e:
                        log('unpatch failed: %r' % e)
                mode = want
                log('drawing mode: %s' % mode)
                if mode == 'skin':
                    for ov in overlays:
                        ov.clear_now()
                    skin_pending = now
                else:
                    for ov in overlays:
                        ov.need = True
                        ov.settings_changed = False
                        ov.sig = None

        if mode == 'skin':
            # ---- inside the skin: regenerate the include when something changed
            ff = focus_fade_cfg()
            f = focus.has_focus()
            if f != last_focus:
                last_focus = f
                set_focus_property(home, f)
            if skin_pending is None and ff != applied_focus:
                skin_pending = now + 2.0
            if skin_pending is None and (dirty or now - last_theme_check >= 30):
                last_theme_check = now
                if any(ov.settings_differ() for ov in overlays):
                    skin_pending = now + 2.0            # let several slider moves settle
            if (skin_pending is not None and now >= skin_pending and now >= settle_until
                    and not xbmc.getCondVisibility('Window.IsVisible(addonsettings)')):
                skin_pending = None
                try:
                    specs = collect_specs(overlays)
                    applied_focus = focus_fade_cfg()
                    text = skinpatch.render_include(
                        specs, media_base(), 'skin %s %s' % (skin_id, patcher.version),
                        focus_fade=applied_focus)
                    ok, changed, msg = patcher.apply(text)
                except Exception as e:
                    ok, changed, msg = False, False, repr(e)
                if not ok:
                    log('skin patch failed: %s' % msg)
                    notify('Could not patch the skin (%s). Drawing the overlays on top instead.' % msg)
                    blocked_skin = skin_id
                    next_eval = 0.0
                elif changed:
                    log('skin patched (%d controls), reloading skin' % len(specs))
                    xbmc.executebuiltin('ReloadSkin()')
                    settle_until = time.time() + 4.0
            if mon.waitForAbort(0.25):
                break
            continue

        # ---- on top of the skin (live controls)
        active = xbmc.getCondVisibility('Window.IsActive(home)')
        if dirty:
            for ov in overlays:
                if ov.settings_differ():
                    ov.need = True
                    ov.settings_changed = True

        if now - last_theme_check >= 30:
            last_theme_check = now
            for ov in overlays:
                if isinstance(ov, Waves) and ov.built and ov.settings_differ():
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
                    if ov.read()['enabled']:
                        # keep the layer order: redraw everything above too
                        for upper in overlays[overlays.index(ov) + 1:]:
                            if upper.built:
                                upper.need = True
                                upper.settings_changed = True
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
