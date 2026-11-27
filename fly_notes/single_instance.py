"""
Single-instance guard — no Tkinter dependency.

Two copies of Fly Notes using the same tasks file would each load it and the
last one to save would silently win. The first instance owns a named Windows
mutex derived from the tasks file path; a second launch finds the mutex
taken, signals a named event so the first instance comes to the front, and
exits.

Instances that use *different* tasks files don't share a mutex, so they can
run side by side. On other platforms the guard does nothing.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys

logger = logging.getLogger(__name__)

_ERROR_ALREADY_EXISTS = 183
_WAIT_OBJECT_0 = 0
_ASFW_ANY = 0xFFFFFFFF  # (DWORD)-1


def instance_key(tasks_file: str) -> str:
    """A name-safe key for *tasks_file* (case- and separator-insensitive on Windows)."""
    path = os.path.normcase(os.path.abspath(tasks_file))
    return "FlyNotes-" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:32]


class SingleInstance:
    """Named mutex (ownership) plus a named auto-reset event (show requests)."""

    def __init__(self, key: str) -> None:
        self.key = key
        self._mutex = None
        self._event = None
        self._kernel32 = None
        if sys.platform == "win32":
            self._kernel32 = _load_kernel32()

    def acquire(self) -> bool:
        """True if this is the only instance for the key (or the guard is unavailable)."""
        k32 = self._kernel32
        if k32 is None:
            return True
        import ctypes

        mutex = k32.CreateMutexW(None, False, f"Local\\{self.key}-lock")
        if not mutex:
            # Fail open: refusing to start would be worse than the risk it guards.
            logger.warning(
                "Could not create the single-instance mutex (error %s)", ctypes.get_last_error()
            )
            return True
        if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
            k32.CloseHandle(mutex)
            return False
        self._mutex = mutex
        self._event = k32.CreateEventW(None, False, False, f"Local\\{self.key}-show")
        if not self._event:
            logger.warning(
                "Could not create the show-window event (error %s)", ctypes.get_last_error()
            )
        return True

    def notify_existing(self) -> bool:
        """Ask the running instance to come to the front. True if the request was sent."""
        k32 = self._kernel32
        if k32 is None:
            return False
        event = k32.CreateEventW(None, False, False, f"Local\\{self.key}-show")
        if not event:
            return False
        try:
            # We were just launched by the user, so we may hand the foreground on.
            user32 = _load_user32()
            if user32 is not None:
                user32.AllowSetForegroundWindow(_ASFW_ANY)
            return bool(k32.SetEvent(event))
        finally:
            k32.CloseHandle(event)

    def show_requested(self) -> bool:
        """Non-blocking: True once per request sent by :meth:`notify_existing`."""
        if self._kernel32 is None or not self._event:
            return False
        return self._kernel32.WaitForSingleObject(self._event, 0) == _WAIT_OBJECT_0

    def release(self) -> None:
        k32 = self._kernel32
        for attr in ("_event", "_mutex"):
            handle = getattr(self, attr)
            if handle and k32 is not None:
                k32.CloseHandle(handle)
            setattr(self, attr, None)


def _load_kernel32():
    try:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        k32.CreateMutexW.restype = wintypes.HANDLE
        k32.CreateEventW.argtypes = [
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        k32.CreateEventW.restype = wintypes.HANDLE
        k32.SetEvent.argtypes = [wintypes.HANDLE]
        k32.SetEvent.restype = wintypes.BOOL
        k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k32.WaitForSingleObject.restype = wintypes.DWORD
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        k32.CloseHandle.restype = wintypes.BOOL
        return k32
    except (ImportError, AttributeError, OSError):
        logger.warning("Single-instance guard unavailable", exc_info=True)
        return None


def _load_user32():
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
        user32.AllowSetForegroundWindow.restype = wintypes.BOOL
        return user32
    except (ImportError, AttributeError, OSError):
        return None
