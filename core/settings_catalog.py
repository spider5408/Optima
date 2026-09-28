"""Optima 0.5 setting catalogue and hardware-aware profiles.

`action` identifies a tested, supported change. A None action is intentionally
detection-only: it may be useful information but cannot be applied from Optima.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Setting:
    id: str
    category: str
    name: str
    description: str
    risk: str          # 'LOW', 'MEDIUM', 'HIGH'
    benefit: str
    reversible: bool
    action: str | None = None
    priority: str = "Recommended"  # 'Recommended', 'Optional', 'Low Impact', 'Detection Only'


SETTINGS = (
    # Power
    Setting('power-performance', 'Power', 'High performance power mode', 'Uses the Windows High performance plan when available.', 'MEDIUM', 'May favor performance over power efficiency.', True, 'power', 'Optional'),
    Setting('power-balanced', 'Power', 'Balanced power mode', 'Shows the currently active plan and restore history.', 'LOW', 'May reduce power use and heat.', True, None, 'Optional'),

    # Visual Effects
    Setting('visual-animation', 'Visual Effects', 'Disable window animations', 'Reduces the supported client-area animation preference.', 'LOW', 'May reduce visual overhead on older GPUs.', True, 'visual', 'Recommended'),
    Setting('visual-transparency', 'Visual Effects', 'Reduce transparency', 'Checks transparency support; manual Windows review remains required.', 'LOW', 'May reduce graphical compositor overhead.', True, None, 'Low Impact'),
    Setting('visual-menu', 'Visual Effects', 'Reduce menu animations', 'Reports the Windows animation setting where available.', 'LOW', 'May reduce visual overhead.', True, None, 'Low Impact'),
    Setting('visual-taskbar', 'Visual Effects', 'Reduce taskbar effects', 'Reports taskbar effects; no shell setting is changed automatically.', 'LOW', 'May reduce visual overhead.', True, None, 'Low Impact'),

    # Startup
    Setting('startup-review', 'Startup', 'Review startup applications', 'Lists supported current-user Run entries; selected non-protected entries can be disabled and restored.', 'LOW', 'Reduces sign-in boot time and idle memory usage.', True, 'startup', 'Recommended'),
    Setting('startup-impact', 'Startup', 'Startup impact classification', 'Displays startup source, safety grouping, and impact ratings.', 'LOW', 'Helps prioritize which startup programs to disable.', False, None, 'Detection Only'),

    # CPU
    Setting('cpu-heavy', 'CPU', 'Identify CPU-heavy processes', 'Detects processes using high CPU; Optima does not terminate them automatically.', 'LOW', 'Helps identify workload sources transparently.', False, None, 'Detection Only'),
    Setting('cpu-background', 'CPU', 'Reduce background activity', 'Provides review recommendations for non-critical background apps.', 'LOW', 'May reduce CPU competition.', False, None, 'Detection Only'),
    Setting('cpu-priority', 'CPU', 'Gaming process priority', 'Detection only: Windows scheduling varies; no priority is changed automatically.', 'MEDIUM', 'May help a selected game in some cases.', True, None, 'Detection Only'),
    Setting('cpu-monitor', 'CPU', 'Adaptive CPU monitoring', 'Live monitoring adapts frequency dynamically to minimize Optima overhead.', 'LOW', 'Prevents monitoring from consuming CPU.', False, None, 'Low Impact'),

    # RAM
    Setting('ram-heavy', 'RAM', 'Identify memory-heavy processes', 'Detects memory consumers without fake RAM-clearing behavior.', 'LOW', 'Targets unnecessary applications accurately.', False, None, 'Detection Only'),
    Setting('ram-pressure', 'RAM', 'Memory pressure warning', 'Raises a recommendation only when measurable RAM pressure is elevated.', 'LOW', 'Helps avoid disk paging thrashing.', False, None, 'Detection Only'),
    Setting('ram-startup', 'RAM', 'Startup memory reduction', 'Uses the startup review workflow for optional applications.', 'LOW', 'Reduces idle memory footprint at sign-in.', True, 'startup', 'Recommended'),
    Setting('ram-monitor', 'RAM', 'RAM usage monitoring', 'Shows live RAM usage and available memory accurately.', 'LOW', 'Makes memory pressure visible.', False, None, 'Low Impact'),

    # Storage & Cleanup
    Setting('storage-temp', 'Storage', 'Temporary file cleanup', 'Removes only selected contents of supported temporary locations and Recycle Bin.', 'LOW', 'Safely recovers gigabytes of storage space.', False, 'cleanup', 'Recommended'),
    Setting('storage-recycle', 'Storage', 'Recycle Bin management', 'Queries and empties Recycle Bin via native Windows Shell API.', 'LOW', 'Recovers storage immediately.', False, 'cleanup', 'Recommended'),
    Setting('storage-large', 'Storage', 'Large-file analyzer', 'Detection only: personal files are never auto-deleted.', 'LOW', 'Helps investigate storage use.', False, None, 'Detection Only'),
    Setting('storage-health', 'Storage', 'Drive media & capacity', 'Detects drive type (SSD vs HDD) and free storage capacity.', 'LOW', 'Adapts recommendations to drive technology.', False, None, 'Detection Only'),
    Setting('storage-trim', 'Storage', 'SSD TRIM status', 'Confirms SSD TRIM is active and defragmentation is safely skipped.', 'LOW', 'Prevents NAND flash wear.', False, None, 'Detection Only'),
    Setting('storage-hdd', 'Storage', 'HDD seek optimization', 'Guidance on reducing concurrent disk I/O on mechanical drives.', 'LOW', 'Provides safe HDD performance guidance.', False, None, 'Detection Only'),
    Setting('cleanup-temp', 'Cleanup', 'Cleanup Center', 'Review supported temporary locations and their recoverable size.', 'LOW', 'May recover storage space.', False, 'cleanup', 'Recommended'),
    Setting('cleanup-cache', 'Cleanup', 'Application cache scan', 'Scans only supported temporary cache locations.', 'LOW', 'Identifies safe cleanup candidates.', False, 'cleanup', 'Optional'),
    Setting('cleanup-logs', 'Cleanup', 'Old log review', 'Detection only: reports temporary logs in user AppData.', 'LOW', 'Identifies recoverable storage.', False, None, 'Detection Only'),

    # Network
    Setting('network-info', 'Network', 'Network adapter diagnostics', 'Shows live throughput via the non-blocking monitor.', 'LOW', 'Makes network activity visible.', False, None, 'Detection Only'),
    Setting('network-dns', 'Network', 'Flush DNS cache', 'Detection only until elevation/verification is added.', 'LOW', 'May refresh local DNS resolution.', False, None, 'Detection Only'),
    Setting('network-heavy', 'Network', 'Network-heavy process review', 'Identifies active network consumers without terminating processes.', 'LOW', 'Pinpoints background download activity.', False, None, 'Detection Only'),

    # Gaming
    Setting('gaming-power', 'Gaming', 'Gaming power configuration', 'Uses the explicit High performance power plan during games.', 'MEDIUM', 'Prevents processor downclocking during games.', True, 'power', 'Recommended'),
    Setting('gaming-monitor', 'Gaming', 'Game resource monitor', 'Shows live CPU, RAM, and disk measurements while playing.', 'LOW', 'Makes resource contention visible.', False, None, 'Detection Only'),
    Setting('gaming-mode', 'Gaming', 'Gaming Resource Mode', 'Automatically reduces Optima overhead when a game is detected.', 'LOW', 'Ensures Optima never steals gaming FPS.', False, None, 'Recommended'),
    Setting('gaming-custom', 'Gaming', 'Custom game detection', 'Registers custom game executables for automatic gaming mode.', 'LOW', 'Enables personalized game detection.', False, None, 'Optional'),

    # Windows
    Setting('windows-notify', 'Windows', 'Notification review', 'Detection only; no notifications are disabled silently.', 'LOW', 'May reduce distractions.', False, None, 'Detection Only'),
    Setting('windows-background', 'Windows', 'Background permission review', 'Detection only; preserves Windows app behavior.', 'LOW', 'Helps guide manual review.', False, None, 'Detection Only'),

    # Advanced
    Setting('performance-score', 'Performance', 'System condition score', 'Transparent condition scoring based on measurable load, not hardware benchmarks.', 'LOW', 'Makes system contention visible.', False, None, 'Detection Only'),
    Setting('advanced-safe', 'Advanced', 'Advanced safeguards', 'Explains strictly excluded features: registry cleaners, firmware, overclocking, security tampering.', 'HIGH', 'Guarantees system safety and reversibility.', False, None, 'Detection Only'),
)

PROFILES = {
    'Safe Mode': ('visual-animation', 'startup-review', 'storage-temp'),
    'Balanced Mode': ('visual-animation', 'startup-review', 'storage-temp', 'power-performance'),
    'Performance Mode': ('visual-animation', 'startup-review', 'power-performance', 'gaming-power', 'storage-temp'),
    'Gaming Mode': ('visual-animation', 'power-performance', 'gaming-power'),
    'Custom Mode': (),
}


def resolve_hardware_aware_profile(profile_name: str, has_ssd: bool = True, low_ram: bool = False) -> list[str]:
    """Adapt profile settings to the machine's actual hardware (Section 6 & 9)."""
    base = list(PROFILES.get(profile_name, ()))
    if low_ram and 'startup-review' not in base:
        base.append('startup-review')
    return base
