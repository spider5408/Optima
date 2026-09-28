"""Lightweight, non-blocking snapshots and idle detection for Qt's adaptive live monitor."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import time
import psutil


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def get_idle_duration_seconds() -> float:
    """Return how many seconds the PC has been idle without mouse or keyboard input.

    Uses native Win32 GetLastInputInfo; microseconds overhead.
    """
    try:
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return max(0.0, millis / 1000.0)
    except Exception:
        pass
    return 0.0


class LiveMonitor:
    def __init__(self) -> None:
        self._last_disk = psutil.disk_io_counters()
        self._last_net = psutil.net_io_counters()
        self._last_at = time.monotonic()
        psutil.cpu_percent(interval=None)  # prime psutil's non-blocking measurement

    @staticmethod
    def _rate(previous: float, current: float, elapsed: float) -> float:
        if elapsed <= 0 or current < previous:
            return 0.0
        return max(0.0, (current - previous) / elapsed)

    def is_pc_idle(self, threshold_seconds: float = 60.0) -> bool:
        """True if no keyboard or mouse activity occurred in the last threshold_seconds."""
        return get_idle_duration_seconds() >= threshold_seconds

    def snapshot(self) -> dict[str, float]:
        try:
            now = time.monotonic()
            elapsed = max(now - self._last_at, 0.001)
            disk, net = psutil.disk_io_counters(), psutil.net_io_counters()
            values = {
                "cpu": psutil.cpu_percent(interval=None),
                "ram": psutil.virtual_memory().percent,
                "disk_read": self._rate(self._last_disk.read_bytes if self._last_disk else 0, disk.read_bytes if disk else 0, elapsed),
                "disk_write": self._rate(self._last_disk.write_bytes if self._last_disk else 0, disk.write_bytes if disk else 0, elapsed),
                "network": self._rate(
                    ((self._last_net.bytes_sent + self._last_net.bytes_recv) if self._last_net else 0),
                    ((net.bytes_sent + net.bytes_recv) if net else 0),
                    elapsed,
                ),
            }
            self._last_disk, self._last_net, self._last_at = disk, net, now
            return values
        except (psutil.Error, OSError):
            return {"cpu": 0.0, "ram": 0.0, "disk_read": 0.0, "disk_write": 0.0, "network": 0.0}
