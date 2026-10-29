# -*- coding: utf-8 -*-
"""Threaded mpv controller.

One worker thread owns the mpv process and its JSON IPC connection. The Kodi
service thread only tells it what it *wants* (which theme, audible or not) and
the worker moves towards that state with smooth, interruptible volume fades.

IPC is strictly request/reply on a single thread (write a command, read until
the matching reply). That avoids the Windows named-pipe problem where a
blocking read on one thread stalls writes on another.
"""
import json
import os
import random
import shlex
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import traceback

from . import paths
from .common import SELECT_RANDOM

IS_WINDOWS = os.name == 'nt'
CREATE_NO_WINDOW = 0x08000000


class IpcError(Exception):
    pass


def resolve_mpv_path(configured):
    """Return the path of mpv or None when it cannot be found."""
    p = (configured or '').strip().strip('"')
    if p:
        p = paths.translate(p)
        if os.path.isdir(p):
            for name in ('mpv.exe', 'mpv'):
                candidate = os.path.join(p, name)
                if os.path.isfile(candidate):
                    return candidate
            return None
        return p if os.path.isfile(p) else None
    return shutil.which('mpv') or shutil.which('mpv.exe')


def _make_kill_on_close_job():
    """Windows job object so mpv dies with Kodi, even if Kodi crashes."""
    import ctypes
    from ctypes import wintypes

    class BASIC(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', wintypes.LARGE_INTEGER),
                    ('PerJobUserTimeLimit', wintypes.LARGE_INTEGER),
                    ('LimitFlags', wintypes.DWORD),
                    ('MinimumWorkingSetSize', ctypes.c_size_t),
                    ('MaximumWorkingSetSize', ctypes.c_size_t),
                    ('ActiveProcessLimit', wintypes.DWORD),
                    ('Affinity', ctypes.c_size_t),
                    ('PriorityClass', wintypes.DWORD),
                    ('SchedulingClass', wintypes.DWORD)]

    class IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in (
            'ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
            'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

    class EXTENDED(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', BASIC),
                    ('IoInfo', IO),
                    ('ProcessMemoryLimit', ctypes.c_size_t),
                    ('JobMemoryLimit', ctypes.c_size_t),
                    ('PeakProcessMemoryUsed', ctypes.c_size_t),
                    ('PeakJobMemoryUsed', ctypes.c_size_t)]

    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]

    job = k32.CreateJobObjectW(None, None)
    if not job:
        raise OSError('CreateJobObject failed')
    info = EXTENDED()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        raise OSError('SetInformationJobObject failed')

    def assign(process_handle):
        return bool(k32.AssignProcessToJobObject(job, wintypes.HANDLE(int(process_handle))))

    return assign


class _Transport(object):
    """Newline delimited JSON over a Windows named pipe or a unix socket."""

    def __init__(self, path):
        self.path = path
        self._file = None
        self._sock = None
        self._buf = b''

    def connect(self):
        if IS_WINDOWS:
            self._file = open(self.path, 'r+b', buffering=0)
        else:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(8)
            try:
                sock.connect(self.path)
            except OSError:
                sock.close()
                raise
            self._sock = sock

    def write(self, data):
        try:
            if self._file is not None:
                view = memoryview(data)
                while view:
                    written = self._file.write(view)
                    view = view[written:]
            else:
                self._sock.sendall(data)
        except (OSError, ValueError, AttributeError) as exc:
            raise IpcError('write failed: %s' % exc)

    def read_line(self):
        while b'\n' not in self._buf:
            try:
                chunk = self._file.read(4096) if self._file is not None else self._sock.recv(4096)
            except (OSError, ValueError, AttributeError) as exc:
                raise IpcError('read failed: %s' % exc)
            if not chunk:
                raise IpcError('mpv closed the connection')
            self._buf += chunk
        line, self._buf = self._buf.split(b'\n', 1)
        return line

    def close(self):
        for handle in (self._file, self._sock):
            try:
                if handle is not None:
                    handle.close()
            except Exception:
                pass
        self._file = None
        self._sock = None
        self._buf = b''


class MpvThemePlayer(threading.Thread):
    TICK_BUSY = 0.03
    TICK_IDLE = 0.15
    COMMAND_TIMEOUT = 6.0

    def __init__(self, get_cfg, log, on_error=None):
        super(MpvThemePlayer, self).__init__(name='mpv-themes')
        self.daemon = True
        self._get_cfg = get_cfg
        self._log = log
        self._on_error = on_error

        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._halt = threading.Event()
        self._want_key = None
        self._want_files = []
        self._want_active = False

        self._proc = None
        self._tr = None
        self._proc_sig = None
        self._req = 0
        self._cmd_started = 0.0
        self._pipe_path = None
        self._job_assign = None
        self._job_tried = False
        self._idx_form = None          # does this mpv accept loadfile's index argument?

        self._fails = 0
        self._retry_at = 0.0
        self._last_error = None
        self._reset_state()

    # ------------------------------------------------------------------ public API
    def set_target(self, key, files, active):
        """Tell the player which theme should play and whether it should be audible."""
        with self._lock:
            changed = key != self._want_key or bool(active) != self._want_active
            self._want_key = key
            self._want_files = list(files) if key is not None else []
            self._want_active = bool(active)
        if changed:
            self._wake.set()

    def watchdog(self):
        """Called from the service thread: kill mpv if a command hangs."""
        started = self._cmd_started
        if started and time.monotonic() - started > self.COMMAND_TIMEOUT:
            self._log('mpv is not responding, restarting it')
            self._kill()

    def shutdown(self):
        self._halt.set()
        self._wake.set()
        if self.is_alive():
            self.join(2.0)
        self._kill()
        if self.is_alive():
            self.join(1.0)

    # ------------------------------------------------------------------ thread body
    def run(self):
        last = time.monotonic()
        try:
            while not self._halt.is_set():
                now = time.monotonic()
                dt = min(now - last, 0.25)
                last = now
                busy = False
                try:
                    busy = self._step(dt, now)
                except IpcError as exc:
                    self._drop()
                    self._record_failure('mpv connection lost: %s' % exc, now)
                except Exception:
                    self._log('Unexpected player error:\n%s' % traceback.format_exc())
                    self._drop()
                    self._record_failure('unexpected player error', now)
                self._wake.wait(self.TICK_BUSY if busy else self.TICK_IDLE)
                self._wake.clear()
        finally:
            self._stop_process()

    # ------------------------------------------------------------------ state machine
    def _reset_state(self):
        self._key = None          # theme key currently loaded in mpv
        self._loaded = False
        self._finished = False
        self._paused = True
        self._vol = 0.0
        self._count = 0
        self._applied_loop = None
        self._switch_in = False   # next fade-in belongs to a theme-to-theme switch
        self._load_time = 0.0
        self._idle_hits = 0
        self._next_poll = 0.0

    def _step(self, dt, now):
        cfg = self._get_cfg()
        with self._lock:
            key, files, active = self._want_key, self._want_files, self._want_active

        if key is None and self._proc is None:
            return False
        if not self._ensure_running(cfg, now):
            return False

        if key != self._key:
            audible = self._loaded and not self._finished and not self._paused and self._vol > 0.05
            if audible:
                # Fade the old theme out first. When another theme follows, the
                # "switch" fades are used; fading to silence uses the normal fade-out.
                switching = key is not None
                self._switch_in = switching
                self._fade_to(0.0, cfg, dt, cfg.switch_fade_out_ms if switching else cfg.fade_out_ms)
                return True
            self._swap(key, files, active, cfg, now)

        playable = self._loaded and not self._finished
        if active and playable and self._paused:
            self._ok(self.command('set_property', 'pause', False))
            self._paused = False

        target = float(cfg.volume) if (active and playable) else 0.0
        moved = self._fade_to(target, cfg, dt)
        if abs(target - self._vol) < 0.01:
            self._switch_in = False

        if self._loaded and not active and not self._paused and self._vol <= 0.05:
            self._ok(self.command('set_property', 'pause', True))
            self._paused = True
        if self._loaded and self._applied_loop != cfg.loop:
            self._apply_loop(cfg)
        self._poll_end(now)
        return moved or abs(target - self._vol) > 0.01

    def _swap(self, key, files, active, cfg, now):
        """Replace whatever is loaded with the requested theme (mpv is silent here)."""
        if self._vol > 0:
            self._set_volume(0.0)
        if not active:
            self._switch_in = False     # it will be resumed later with the normal fade-in
        self._key = key
        self._finished = False
        if not files:
            if self._loaded:
                self.command('stop')
            self._loaded = False
            return

        ordered = list(files)
        if cfg.selection_mode == SELECT_RANDOM:
            random.shuffle(ordered)
        start = 'start=%d%%' % random.randint(5, 70) if cfg.random_start else None

        if not self._loadfile(ordered[0], 'replace', start):
            self._log('mpv could not load %s' % ordered[0])
            self._loaded = False
            return
        for extra in ordered[1:]:
            self._loadfile(extra, 'append')

        self._count = len(ordered)
        self._apply_loop(cfg)
        self._ok(self.command('set_property', 'pause', not active))
        self._paused = not active
        self._loaded = True
        self._load_time = now
        self._idle_hits = 0
        self._next_poll = now + 1.0
        self._fails = 0
        self._last_error = None
        self._log('Playing theme (%d file%s): %s' % (len(ordered), '' if len(ordered) == 1 else 's', ordered[0]))

    def _fade_to(self, target, cfg, dt, ms=None):
        cur = self._vol
        if abs(cur - target) < 0.01:
            return False
        if ms is None:
            if target > cur:
                ms = cfg.switch_fade_in_ms if self._switch_in else cfg.fade_in_ms
            else:
                ms = cfg.fade_out_ms
        if ms <= 0:
            new = target
        else:
            step = max(float(cfg.volume), 1.0) * dt / (ms / 1000.0)
            new = min(cur + step, target) if target > cur else max(cur - step, target)
        self._set_volume(new)
        return True

    def _set_volume(self, value):
        value = max(0.0, value)
        self._ok(self.command('set_property', 'volume', round(value, 2)))
        self._vol = value

    def _apply_loop(self, cfg):
        single = self._count <= 1
        self._ok(self.command('set_property', 'loop-file', 'inf' if (single and cfg.loop) else 'no'))
        self._ok(self.command('set_property', 'loop-playlist', 'inf' if (not single and cfg.loop) else 'no'))
        self._applied_loop = cfg.loop

    def _poll_end(self, now):
        if not self._loaded or self._finished or self._paused or now < self._next_poll:
            return
        self._next_poll = now + 0.5
        reply = self.command('get_property', 'idle-active')
        if self._ok(reply) and reply.get('data') is True and now - self._load_time > 1.0:
            self._idle_hits += 1
            if self._idle_hits >= 2:
                self._finished = True
                self._log('Theme finished')
        else:
            self._idle_hits = 0

    def _loadfile(self, path, mode, options=None):
        if options is None:
            return self._ok(self.command('loadfile', path, mode))
        if self._idx_form is not False:             # mpv >= 0.38: loadfile <file> <flags> <index> <options>
            if self._ok(self.command('loadfile', path, mode, -1, options)):
                self._idx_form = True
                return True
            if self._idx_form is True:
                return False
            self._idx_form = False
        if self._ok(self.command('loadfile', path, mode, options)):   # older mpv
            return True
        return self._ok(self.command('loadfile', path, mode))

    # ------------------------------------------------------------------ process / IPC
    @staticmethod
    def _ok(reply):
        return isinstance(reply, dict) and reply.get('error') == 'success'

    def command(self, *args):
        """Send one command and wait for its reply (worker thread only)."""
        if self._tr is None:
            raise IpcError('not connected')
        self._req += 1
        rid = self._req
        payload = json.dumps({'command': list(args), 'request_id': rid}).encode('utf-8') + b'\n'
        self._cmd_started = time.monotonic()
        try:
            self._tr.write(payload)
            while True:
                line = self._tr.read_line()
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line.decode('utf-8', 'replace'))
                except ValueError:
                    continue
                if msg.get('request_id') == rid:
                    return msg
        finally:
            self._cmd_started = 0.0

    def _ensure_running(self, cfg, now):
        exe = resolve_mpv_path(cfg.mpv_path)
        sig = (exe, cfg.extra_args)
        if self._proc is not None:
            if self._proc.poll() is None and self._tr is not None and sig == self._proc_sig:
                return True
            self._drop()
        if now < self._retry_at:
            return False
        if not exe:
            self._record_failure('mpv was not found. Set the path to mpv.exe in the add-on settings.', now)
            return False
        try:
            self._spawn(exe, cfg)
        except (IpcError, OSError) as exc:
            self._drop()
            self._record_failure('could not start mpv: %s' % exc, now)
            return False
        self._proc_sig = sig
        return True

    def _spawn(self, exe, cfg):
        if IS_WINDOWS:
            self._pipe_path = r'\\.\pipe\kodi-mpv-themes-%d' % os.getpid()
        else:
            self._pipe_path = os.path.join(tempfile.gettempdir(), 'kodi-mpv-themes-%d.sock' % os.getpid())
            try:
                os.unlink(self._pipe_path)
            except OSError:
                pass

        args = [
            exe, '--no-config', '--no-video', '--audio-display=no', '--force-window=no',
            '--idle=yes', '--keep-open=no', '--pause=no', '--no-terminal', '--really-quiet',
            '--osc=no', '--no-input-default-bindings', '--ytdl=no', '--load-scripts=no',
            '--volume=0', '--volume-max=100',
            '--input-ipc-server=%s' % self._pipe_path,
        ]
        if cfg.extra_args:
            try:
                args += [a.strip('"') for a in shlex.split(cfg.extra_args, posix=not IS_WINDOWS)]
            except ValueError:
                self._log('Ignoring extra mpv arguments that could not be parsed')

        kwargs = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        folder = os.path.dirname(exe)
        if folder:
            kwargs['cwd'] = folder
        if IS_WINDOWS:
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            kwargs.update(startupinfo=startup, creationflags=CREATE_NO_WINDOW)
        else:
            kwargs['close_fds'] = True

        self._log('Starting mpv: %s' % exe)
        self._proc = subprocess.Popen(args, **kwargs)
        self._attach_job()

        tr = _Transport(self._pipe_path)
        deadline = time.monotonic() + 8.0
        while True:
            if self._proc.poll() is not None:
                raise IpcError('mpv exited immediately (code %s)' % self._proc.returncode)
            try:
                tr.connect()
                break
            except OSError as exc:
                if time.monotonic() > deadline:
                    raise IpcError('cannot connect to mpv: %s' % exc)
                time.sleep(0.05)
        self._tr = tr
        self._reset_state()
        self.command('disable_event', 'all')
        self.command('set_property', 'volume', 0)

    def _attach_job(self):
        if not IS_WINDOWS or self._proc is None:
            return
        try:
            if not self._job_tried:
                self._job_tried = True
                self._job_assign = _make_kill_on_close_job()
            if self._job_assign is not None:
                self._job_assign(self._proc._handle)
        except Exception as exc:
            self._log('Could not tie mpv to the Kodi process (%s); it is closed normally on exit' % exc)

    def _record_failure(self, message, now):
        self._fails += 1
        self._retry_at = now + min(30.0, 2.0 * (1.5 ** self._fails))
        self._log('Player problem: %s' % message)
        if message != self._last_error:
            self._last_error = message
            if self._on_error:
                self._on_error(message)

    def _kill(self):
        proc = self._proc
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass

    def _drop(self):
        self._kill()
        if self._tr is not None:
            self._tr.close()
        if self._proc is not None:
            try:
                self._proc.wait(timeout=2)
            except Exception:
                pass
        self._proc = None
        self._tr = None
        self._proc_sig = None
        self._cmd_started = 0.0
        self._reset_state()

    def _stop_process(self):
        try:
            if self._tr is not None and self._proc is not None and self._proc.poll() is None:
                try:
                    self.command('quit')
                except Exception:
                    pass
                try:
                    self._proc.wait(timeout=0.5)
                except Exception:
                    pass
        finally:
            self._drop()
            if not IS_WINDOWS and self._pipe_path:
                try:
                    os.unlink(self._pipe_path)
                except OSError:
                    pass
