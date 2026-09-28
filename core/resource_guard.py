"""Measure Optima's own overhead, trim memory when minimized, and dynamically adapt polling cadences."""
from __future__ import annotations

import ctypes
import os
import time
import psutil

from .game_detector import GameDetector


def trim_working_set() -> None:
    """Trim Optima's working set memory when minimized on Windows."""
    try:
        current_process = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.psapi.EmptyWorkingSet(current_process)
    except Exception:
        pass


class ResourceGuard:
    """Intelligent guardian ensuring Optima consumes minimal system resources."""

    BASE_INTERVALS = {
        'Full': 1500,
        'Light': 3500,
        'Minimal': 7000,
        'Paused': 30000,
    }

    BUDGET_MAP = {
        'Lowest Resource Usage': {'perf': 3000, 'dash': 5000, 'static': 8000, 'minimized': 20000},
        'Balanced': {'perf': 1500, 'dash': 3500, 'static': 5000, 'minimized': 15000},
        'Maximum Monitoring': {'perf': 1000, 'dash': 2500, 'static': 4000, 'minimized': 10000},
    }

    def __init__(self, game_detector: GameDetector | None = None) -> None:
        self.process = psutil.Process(os.getpid())
        # Prime psutil's non-blocking CPU calculation
        self.process.cpu_percent(None)
        try:
            self.last_io = self.process.io_counters()
        except (psutil.Error, OSError):
            self.last_io = None
        self.last_at = time.monotonic()

        self.mode = 'Full'  # 'Full', 'Light', 'Minimal', 'Paused'
        self.budget = 'Balanced'  # 'Lowest Resource Usage', 'Balanced', 'Maximum Monitoring'
        self.game_detector = game_detector or GameDetector()

        self.last = {
            'cpu': 0.0,
            'ram_mb': 0.0,
            'disk_bps': 0.0,
            'background': 'Active',
            'is_gaming': False,
            'game_name': None,
        }
        self._was_minimized = False

    def sample(self, minimized: bool, page: str, system_cpu: float, is_idle: bool = False) -> dict:
        """Sample Optima's own resource consumption accurately and non-blockingly."""
        # Trim working set when transitioning to minimized state
        if minimized and not self._was_minimized:
            trim_working_set()
        self._was_minimized = minimized

        now = time.monotonic()
        elapsed = max(now - self.last_at, 0.001)

        # Measure disk I/O rate
        disk_rate = 0.0
        try:
            io = self.process.io_counters()
            if self.last_io:
                disk_delta = (io.read_bytes + io.write_bytes) - (self.last_io.read_bytes + self.last_io.write_bytes)
                disk_rate = max(0.0, disk_delta / elapsed)
            self.last_io = io
        except (psutil.Error, OSError):
            pass

        # Check self CPU and RAM
        try:
            cpu = self.process.cpu_percent(None)
            ram_mb = self.process.memory_info().rss / 1024**2
        except (psutil.Error, OSError):
            cpu, ram_mb = 0.0, 0.0

        # Check active game
        is_gaming, game_name = self.game_detector.check_active_game()

        # Determine background state
        if self.mode == 'Paused':
            bg_state = 'Paused'
        elif is_gaming:
            bg_state = f'Gaming ({game_name})' if game_name else 'Gaming'
        elif minimized or self.mode in ('Light', 'Minimal') or system_cpu >= 80 or is_idle:
            bg_state = 'Reduced'
        else:
            bg_state = 'Active'

        self.last = {
            'cpu': cpu,
            'ram_mb': ram_mb,
            'disk_bps': disk_rate,
            'background': bg_state,
            'is_gaming': is_gaming,
            'game_name': game_name,
        }
        self.last_at = now
        return self.last

    def interval_ms(self, minimized: bool, page: str, system_cpu: float, is_idle: bool = False) -> int:
        """Calculate adaptive monitoring interval dynamically balancing responsiveness and resource usage."""
        if self.mode == 'Paused':
            return self.BASE_INTERVALS['Paused'] if minimized else 10000

        budget_cfg = self.BUDGET_MAP.get(self.budget, self.BUDGET_MAP['Balanced'])

        # 1. When minimized: dramatically throttle
        if minimized:
            if self.mode == 'Minimal':
                return 25000
            if self.mode == 'Light':
                return 20000
            return budget_cfg['minimized']

        # 2. When system is under heavy load (system CPU >= 80%): don't add to contention
        if system_cpu >= 80:
            return 7000

        # 3. When game is detected: throttle background activity
        if self.last.get('is_gaming'):
            # If user is on Performance or Gaming page, still show essential metrics at reduced cadence
            if page in ('Performance', 'Gaming'):
                return 4000
            return 8000

        # 4. When PC is idle: reduce activity
        if is_idle:
            return 8000

        # 5. When Optima detects its own CPU is elevated (> 2.5%): auto-throttle
        if self.last.get('cpu', 0.0) > 2.5:
            return 6000

        # 6. Normal foreground page-adaptive cadence
        if page == 'Performance':
            return budget_cfg['perf']
        elif page == 'Dashboard':
            return budget_cfg['dash']
        else:
            return budget_cfg['static']
