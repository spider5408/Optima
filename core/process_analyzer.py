"""Lightweight background process intelligence analyzer.

Runs strictly on-demand. Never terminates processes automatically.
Provides transparent resource explanations and publisher verification.
"""
from __future__ import annotations

import os
from pathlib import Path
import psutil

from .hardware import get_file_company

# In-memory cache for publisher lookups by exe path to ensure microsecond lookup
_PUBLISHER_CACHE: dict[str, str] = {}


class ProcessInfo:
    def __init__(
        self,
        pid: int,
        name: str,
        cpu_percent: float,
        ram_mb: float,
        disk_bps: float,
        publisher: str,
        exe: str,
        starts_with_windows: bool,
        tags: list[str],
        explanation: str,
        ignored: bool = False,
    ) -> None:
        self.pid = pid
        self.name = name
        self.cpu_percent = cpu_percent
        self.ram_mb = ram_mb
        self.disk_bps = disk_bps
        self.publisher = publisher
        self.exe = exe
        self.starts_with_windows = starts_with_windows
        self.tags = tags
        self.explanation = explanation
        self.ignored = ignored

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "name": self.name,
            "cpu_percent": self.cpu_percent,
            "ram_mb": self.ram_mb,
            "disk_bps": self.disk_bps,
            "publisher": self.publisher,
            "exe": self.exe,
            "starts_with_windows": self.starts_with_windows,
            "tags": self.tags,
            "explanation": self.explanation,
            "ignored": self.ignored,
        }


class ProcessAnalyzer:
    def __init__(self, ignored_names: set[str] | None = None) -> None:
        self.ignored_names: set[str] = set(ignored_names or [])

    def ignore_process(self, name: str) -> None:
        self.ignored_names.add(name.lower())

    def unignore_process(self, name: str) -> None:
        self.ignored_names.discard(name.lower())

    def is_ignored(self, name: str) -> bool:
        return name.lower() in self.ignored_names

    def analyze_processes(
        self,
        startup_items: list[dict] | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Perform an on-demand scan of running processes.

        Extracts CPU, RAM, publisher, startup status, and tags.
        """
        startup_names = set()
        if startup_items:
            for s in startup_items:
                startup_names.add(s.get("name", "").lower())
                cmd = (s.get("command") or "").lower()
                for part in cmd.replace('"', '').split():
                    if part.endswith(".exe"):
                        startup_names.add(os.path.basename(part).lower())

        results: list[dict] = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'io_counters', 'exe']):
                try:
                    info = proc.info
                    pid = info.get('pid', 0)
                    if pid == 0 or not info.get('name'):
                        continue

                    name = info['name']
                    exe = info.get('exe') or ''
                    mem = info.get('memory_info')
                    ram_mb = (mem.rss / (1024 * 1024)) if mem else 0.0
                    cpu = info.get('cpu_percent') or 0.0

                    # Disk throughput
                    io = info.get('io_counters')
                    disk_bps = float(io.read_bytes + io.write_bytes) if io else 0.0

                    # Publisher lookup (cached)
                    if exe in _PUBLISHER_CACHE:
                        publisher = _PUBLISHER_CACHE[exe]
                    else:
                        publisher = get_file_company(exe) if exe else "Unknown"
                        if exe:
                            _PUBLISHER_CACHE[exe] = publisher

                    starts_with_windows = (
                        name.lower() in startup_names or
                        (exe and os.path.basename(exe).lower() in startup_names)
                    )

                    ignored = name.lower() in self.ignored_names

                    # Determine resource tags
                    tags: list[str] = []
                    if cpu >= 15.0:
                        tags.append("High CPU")
                    if ram_mb >= 500.0:
                        tags.append("High RAM")
                    if disk_bps >= 50 * 1024 * 1024:
                        tags.append("High Disk")
                    if publisher == "Unknown":
                        tags.append("Unknown")
                    if not tags:
                        tags.append("Normal")

                    # Explanation
                    explanations = []
                    if "High CPU" in tags:
                        explanations.append(f"Actively utilizing {cpu:.1f}% CPU.")
                    if "High RAM" in tags:
                        explanations.append(f"Consuming {ram_mb:.0f} MB of memory.")
                    if "High Disk" in tags:
                        explanations.append("Significant disk I/O activity.")
                    if starts_with_windows:
                        explanations.append("Configured to launch automatically with Windows.")
                    if not explanations:
                        explanations.append("Nominal resource consumption.")

                    results.append(ProcessInfo(
                        pid=pid,
                        name=name,
                        cpu_percent=cpu,
                        ram_mb=ram_mb,
                        disk_bps=disk_bps,
                        publisher=publisher,
                        exe=exe,
                        starts_with_windows=starts_with_windows,
                        tags=tags,
                        explanation=" ".join(explanations),
                        ignored=ignored,
                    ).to_dict())
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except (psutil.Error, OSError):
            pass

        # Sort primarily by RAM usage descending, then CPU
        results.sort(key=lambda x: (x["ram_mb"], x["cpu_percent"]), reverse=True)
        return results[:limit]
