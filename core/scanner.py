"""Read-only, intelligent system scanning with aggressive hardware caching."""
from __future__ import annotations

from datetime import datetime, timezone
import platform
import psutil

from .analyzer import BottleneckAnalysis, analyze_bottleneck
from .hardware import UNAVAILABLE, clear_hardware_cache, disk_kind, gpu_info, os_info, recycle_bin_info
from .monitor import LiveMonitor


def gib(value: float) -> str:
    return f"{value / 1024**3:.1f} GB"


class SystemScanner:
    def __init__(self, monitor: LiveMonitor | None = None) -> None:
        self.monitor = monitor or LiveMonitor()
        self._stable_cache: dict | None = None
        self._cached_drives: list[dict] | None = None

    def scan(
        self,
        mode: str = "quick",  # 'quick', 'full', 'custom'
        custom_categories: set[str] | None = None,
        startup_count: int = 0,
        heavy_procs: list[dict] | None = None,
    ) -> dict:
        """Intelligent scan. Reuses cached stable hardware to avoid expensive WMI/PowerShell queries."""
        is_quick = (mode == "quick")
        is_full = (mode == "full")

        if is_full:
            clear_hardware_cache()
            self._stable_cache = None
            self._cached_drives = None

        # 1. Live Performance
        live = self.monitor.snapshot()

        # 2. Dynamic Memory Status
        try:
            memory = psutil.virtual_memory()
            ram = {
                "total": memory.total,
                "used": memory.used,
                "available": memory.available,
                "percent": memory.percent,
            }
        except psutil.Error:
            ram = {"total": 0, "used": 0, "available": 0, "percent": 0.0}

        # 3. Stable CPU info
        if self._stable_cache and not is_full:
            cpu = self._stable_cache["cpu"]
        else:
            try:
                freq = psutil.cpu_freq()
                cpu = {
                    "name": platform.processor() or UNAVAILABLE,
                    "physical_cores": psutil.cpu_count(logical=False) or UNAVAILABLE,
                    "logical_processors": psutil.cpu_count(logical=True) or UNAVAILABLE,
                    "current_mhz": round(freq.current, 0) if freq else UNAVAILABLE,
                    "maximum_mhz": round(freq.max, 0) if freq and freq.max else UNAVAILABLE,
                }
            except psutil.Error:
                cpu = {
                    "name": UNAVAILABLE,
                    "physical_cores": UNAVAILABLE,
                    "logical_processors": UNAVAILABLE,
                    "current_mhz": UNAVAILABLE,
                    "maximum_mhz": UNAVAILABLE,
                }

        # 4. Storage Drives
        drives = []
        try:
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    # Media type is cached inside disk_kind
                    kind = disk_kind(part.mountpoint[0]) if platform.system() == "Windows" else UNAVAILABLE
                    drives.append({
                        "mount": part.mountpoint,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent,
                        "kind": kind,
                    })
                except (psutil.Error, OSError, SystemError, IndexError):
                    continue
        except psutil.Error:
            pass
        self._cached_drives = drives

        # 5. GPU and OS
        gpu = gpu_info(force_refresh=is_full) if platform.system() == "Windows" else {"name": UNAVAILABLE, "vram": UNAVAILABLE}
        os_data = os_info()

        # 6. Smart Bottleneck Analysis
        bottleneck = analyze_bottleneck(
            snapshot=live,
            storage=drives,
            ram_info=ram,
            cpu_info=cpu,
            gpu_info=gpu,
            startup_count=startup_count,
            heavy_procs=heavy_procs,
        )

        result = {
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "scan_mode": mode.title(),
            "cpu": cpu,
            "ram": ram,
            "gpu": gpu,
            "storage": drives,
            "os": os_data,
            "live": live,
            "score": bottleneck.score,
            "bottleneck": bottleneck,
        }

        self._stable_cache = {
            "cpu": cpu,
            "gpu": gpu,
            "os": os_data,
        }

        return result
