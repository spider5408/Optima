"""Transparent, evidence-based Smart Bottleneck Engine and system condition scoring."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BottleneckAnalysis:
    score: int
    component: str  # "RAM", "CPU", "Storage", "Startup", "Background", "GPU", "Balanced"
    status: str     # "Optimal", "Moderate Load", "Bottleneck Pressure", "High Contention"
    headline: str
    current_metric: str
    observation: str
    recommendation: str
    issues: list[str] = field(default_factory=list)
    hardware_notes: list[str] = field(default_factory=list)


def analyze_bottleneck(
    snapshot: dict,
    storage: list[dict],
    ram_info: dict | None = None,
    cpu_info: dict | None = None,
    gpu_info: dict | None = None,
    startup_count: int = 0,
    heavy_procs: list[dict] | None = None,
) -> BottleneckAnalysis:
    """Smart Bottleneck Engine: Determines system constraints using factual evidence.

    Never claims guaranteed performance improvements. Adapts to actual hardware (SSD vs HDD, RAM size).
    """
    score = 100
    issues: list[str] = []
    hardware_notes: list[str] = []

    cpu = snapshot.get("cpu", 0.0)
    ram = snapshot.get("ram", 0.0)
    disk_read = snapshot.get("disk_read", 0.0)
    disk_write = snapshot.get("disk_write", 0.0)
    throughput = disk_read + disk_write
    network = snapshot.get("network", 0.0)

    # Hardware facts
    ram_total_gb = (ram_info.get("total", 0) / 1024**3) if ram_info else 0.0
    ram_used_gb = (ram_info.get("used", 0) / 1024**3) if ram_info else 0.0
    is_low_ram = 0 < ram_total_gb <= 8.5

    has_hdd = any("HDD" in (d.get("kind") or "").upper() for d in storage)
    all_ssd = storage and all("SSD" in (d.get("kind") or "").upper() for d in storage)

    if all_ssd:
        hardware_notes.append("Solid State Drive (SSD) detected: traditional defragmentation is safely excluded to prevent unnecessary drive wear.")
    elif has_hdd:
        hardware_notes.append("Mechanical Hard Drive (HDD) detected: startup items and random disk I/O significantly impact responsiveness.")

    if is_low_ram:
        hardware_notes.append(f"System has {ram_total_gb:.1f} GB total RAM: background application memory usage directly impacts multitasking.")

    # Storage space evaluation
    critically_full_drives = []
    low_space_drives = []
    for d in storage:
        total = d.get("total", 0)
        free = d.get("free", 0)
        if total > 0:
            free_pct = free / total
            if free_pct < 0.10:
                critically_full_drives.append(d)
            elif free_pct < 0.15:
                low_space_drives.append(d)

    # Calculate score penalties
    if cpu >= 85:
        score -= 20
        issues.append(f"High CPU utilization ({cpu:.0f}%)")
    elif cpu >= 70:
        score -= 10
        issues.append(f"Elevated CPU utilization ({cpu:.0f}%)")

    if ram >= 85:
        score -= 20
        issues.append(f"High memory pressure ({ram:.0f}%)")
    elif ram >= 70:
        score -= 10
        issues.append(f"Elevated memory usage ({ram:.0f}%)")

    if throughput >= 100 * 1024 * 1024:
        score -= 20
        issues.append(f"High disk throughput ({throughput / 1024**2:.1f} MB/s)")
    elif throughput >= 40 * 1024 * 1024:
        score -= 10
        issues.append(f"Moderate disk activity ({throughput / 1024**2:.1f} MB/s)")

    if critically_full_drives:
        score -= 20
        mounts = ", ".join(d["mount"] for d in critically_full_drives)
        issues.append(f"Critically low storage space (<10% free) on {mounts}")
    elif low_space_drives:
        score -= 10
        mounts = ", ".join(d["mount"] for d in low_space_drives)
        issues.append(f"Low storage space (<15% free) on {mounts}")

    if startup_count >= 8:
        score -= 10
        issues.append(f"{startup_count} startup applications enabled at sign-in")

    score = max(0, min(100, score))

    # Identify Primary Bottleneck
    # Hierarchy of evidence:
    # 1. Critically full storage (<10%)
    # 2. RAM Pressure (>= 80% or >= 70% with low total RAM)
    # 3. CPU Contention (>= 80%)
    # 4. Disk I/O Saturation (>= 40 MB/s)
    # 5. Startup Programs (>= 6 non-protected)
    # 6. Balanced / Healthy

    if critically_full_drives:
        d = critically_full_drives[0]
        free_gb = d.get("free", 0) / 1024**3
        total_gb = d.get("total", 0) / 1024**3
        return BottleneckAnalysis(
            score=score,
            component="Storage",
            status="Bottleneck Pressure",
            headline="Storage Space Constraint",
            current_metric=f"{d['mount']} has {free_gb:.1f} GB free of {total_gb:.1f} GB ({(free_gb/total_gb)*100:.1f}%)",
            observation="When system drives have less than 10% free space, Windows paging files, temp allocations, and updates experience fragmentation and slowdowns.",
            recommendation="Review safe temporary cleanup and empty the Recycle Bin to recover space.",
            issues=issues,
            hardware_notes=hardware_notes,
        )

    if ram >= 78 or (ram >= 70 and is_low_ram):
        heavy_desc = ""
        if heavy_procs:
            top_names = [f"{p.get('name')} ({p.get('ram_mb', 0):.0f} MB)" for p in heavy_procs[:3]]
            heavy_desc = f" Top consumers: {', '.join(top_names)}."
        return BottleneckAnalysis(
            score=score,
            component="RAM",
            status="Bottleneck Pressure" if ram >= 85 else "Moderate Load",
            headline="Possible RAM Pressure",
            current_metric=f"{ram:.0f}% RAM usage ({ram_used_gb:.1f} GB / {ram_total_gb:.1f} GB used)" if ram_total_gb else f"{ram:.0f}% RAM usage",
            observation=f"Multiple background applications are holding resident memory.{heavy_desc} High memory pressure can cause Windows to page data to disk.",
            recommendation="Review unneeded background processes and reduce sign-in startup programs.",
            issues=issues,
            hardware_notes=hardware_notes,
        )

    if cpu >= 75:
        return BottleneckAnalysis(
            score=score,
            component="CPU",
            status="High Contention" if cpu >= 85 else "Moderate Load",
            headline="Elevated CPU Utilization",
            current_metric=f"CPU load at {cpu:.0f}% across active cores",
            observation="Active processes are competing for processor cycles, which may cause latency in user interface and background tasks.",
            recommendation="Inspect CPU-heavy applications in the Processes tab and close unnecessary tasks.",
            issues=issues,
            hardware_notes=hardware_notes,
        )

    if throughput >= 40 * 1024 * 1024:
        rate_mb = throughput / (1024 * 1024)
        return BottleneckAnalysis(
            score=score,
            component="Storage",
            status="High Contention",
            headline="High Disk Activity Contention",
            current_metric=f"Current disk throughput: {rate_mb:.1f} MB/s (Read: {disk_read/1024**2:.1f} MB/s, Write: {disk_write/1024**2:.1f} MB/s)",
            observation="Active storage reads or writes are saturating drive queues, which can make file operations and window responsiveness sluggish.",
            recommendation="Allow ongoing updates or large transfers to finish, or review background disk-intensive processes.",
            issues=issues,
            hardware_notes=hardware_notes,
        )

    if startup_count >= 6:
        return BottleneckAnalysis(
            score=score,
            component="Startup",
            status="Moderate Load",
            headline="Startup Overhead Detected",
            current_metric=f"{startup_count} startup applications configured at sign-in",
            observation="Applications launching at Windows sign-in increase initial boot time and continue consuming background memory.",
            recommendation="Review startup applications in Startup Manager and disable non-essential items.",
            issues=issues,
            hardware_notes=hardware_notes,
        )

    # Healthy / Balanced
    return BottleneckAnalysis(
        score=score,
        component="Balanced",
        status="Optimal",
        headline="System Resources Balanced",
        current_metric=f"CPU {cpu:.0f}%  •  RAM {ram:.0f}%  •  Free Storage Healthy",
        observation="No primary resource bottlenecks detected. Memory, processor utilization, and storage throughput are within optimal ranges.",
        recommendation="No urgent changes required. Use Optima's Safe profile for periodic maintenance if desired.",
        issues=issues or ["No potential bottleneck detected in this snapshot"],
        hardware_notes=hardware_notes,
    )


def analyze(snapshot: dict, storage: list[dict]) -> tuple[int, list[str]]:
    """Backward-compatible scoring function for Optima 0.1-0.4 callers."""
    analysis = analyze_bottleneck(snapshot, storage)
    return analysis.score, analysis.issues
