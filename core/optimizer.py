"""Safe, local, evidence-based Windows optimizations.

No changes occur automatically; every modification requires explicit review and confirmation.
Never touches personal user files, security components, firmware, or anti-cheat software.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import winreg
import psutil

from .hardware import empty_recycle_bin, get_file_company, recycle_bin_info

PROTECTED_STARTUP = (
    "security", "defender", "windows", "intel", "realtek",
    "nvidia", "amd", "driver", "audio", "synaptics", "elan"
)

HIGH_IMPACT_NAMES = (
    "steam", "discord", "spotify", "teams", "onedrive", "epicgames",
    "adobe", "dropbox", "battle.net", "riotclient", "slack", "chrome"
)


@dataclass
class Recommendation:
    key: str
    title: str
    category: str
    description: str
    reason: str
    risk: str          # 'LOW', 'MEDIUM', 'HIGH'
    benefit: str
    priority: str = "Recommended"  # 'Recommended', 'Optional', 'Low Impact', 'Detection Only'
    supported: bool = True
    action: str | None = None


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size if path.is_file() else 0
    except OSError:
        return 0


class OptimizationEngine:
    def __init__(self) -> None:
        self.ignored_startup: set[str] = set()

    def set_ignored_startup(self, items: set[str]) -> None:
        self.ignored_startup = {i.lower() for i in items}

    def startup_items(self) -> list[dict]:
        """Examine current-user Run entries with impact and safety classification (Section 11)."""
        items = []
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                count = winreg.QueryInfoKey(key)[1]
                for i in range(count):
                    name, value, kind = winreg.EnumValue(key, i)
                    name_lower = name.lower()
                    val_lower = str(value).lower()

                    protected = any(w in name_lower or w in val_lower for w in PROTECTED_STARTUP)
                    ignored = name_lower in self.ignored_startup

                    # Estimate startup impact
                    if protected:
                        impact = "Protected"
                    elif any(w in name_lower or w in val_lower for w in HIGH_IMPACT_NAMES):
                        impact = "High"
                    elif "update" in name_lower or "helper" in name_lower or "tray" in name_lower:
                        impact = "Medium"
                    else:
                        impact = "Low"

                    # Extract path if possible
                    exe_path = ""
                    clean_val = str(value).strip().strip('"')
                    parts = clean_val.split('"')
                    first_part = parts[0] if parts else clean_val
                    if first_part.lower().endswith(".exe") and os.path.exists(first_part):
                        exe_path = first_part
                    else:
                        tokens = clean_val.split()
                        if tokens and tokens[0].lower().endswith(".exe") and os.path.exists(tokens[0]):
                            exe_path = tokens[0]

                    publisher = get_file_company(exe_path) if exe_path else "Unknown"

                    if protected:
                        group = "Protected / Windows"
                        rec = "Protected system or driver component; do not disable."
                    elif ignored:
                        group = "Ignored by user"
                        rec = "Marked as trusted by user."
                    elif impact == "High":
                        group = "Recommended to review"
                        rec = "High impact on boot time and idle memory."
                    elif impact == "Medium":
                        group = "Medium impact"
                        rec = "Optional background updater or helper."
                    else:
                        group = "Low impact"
                        rec = "Lightweight startup helper."

                    items.append({
                        "name": name,
                        "command": str(value),
                        "source": "Current user registry Run",
                        "safe": not protected,
                        "impact": impact,
                        "group": group,
                        "publisher": publisher,
                        "exe_path": exe_path,
                        "ignored": ignored,
                        "recommendation": rec,
                    })
        except OSError:
            pass
        return items

    def temporary_locations(self) -> list[dict]:
        """Scan safe cleanup targets strictly excluding all personal user files (Section 12)."""
        roots: list[tuple[str, Path, str]] = [
            ("User temporary files", Path(tempfile.gettempdir()), "temp"),
            ("Application caches", Path(os.getenv("LOCALAPPDATA", "")) / "Temp", "cache"),
        ]

        # Windows Temp if readable
        win_temp = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "Temp"
        if win_temp.exists() and os.access(win_temp, os.R_OK):
            roots.append(("Windows temporary data", win_temp, "windows_temp"))

        # Crash dumps in AppData if exists
        crash_dumps = Path(os.getenv("LOCALAPPDATA", "")) / "CrashDumps"
        if crash_dumps.exists() and os.access(crash_dumps, os.R_OK):
            roots.append(("Application crash dumps", crash_dumps, "dumps"))

        output = []
        for label, root, category in roots:
            total = 0
            file_count = 0
            try:
                for path in root.iterdir():
                    try:
                        if path.is_file():
                            total += _safe_size(path)
                            file_count += 1
                        elif path.is_dir():
                            for sub in path.rglob("*"):
                                total += _safe_size(sub)
                                file_count += 1
                    except (OSError, PermissionError):
                        continue
            except (OSError, PermissionError):
                pass
            output.append({
                "label": label,
                "path": root,
                "bytes": total,
                "count": file_count,
                "category": category,
            })

        # Recycle Bin via instantaneous Win32 API
        rb = recycle_bin_info()
        output.append({
            "label": "Recycle Bin",
            "path": Path("C:\\$Recycle.Bin"),
            "bytes": rb["bytes"],
            "count": rb["items"],
            "category": "recycle_bin",
        })

        return output

    def snapshot(self) -> dict:
        """Capture measurable system state for before/after verification (Section 14)."""
        memory = psutil.virtual_memory()
        try:
            root = Path(os.environ.get("SystemDrive", "C:")) / "\\"
            free = shutil.disk_usage(root).free
        except OSError:
            free = 0
        return {
            "cpu": psutil.cpu_percent(interval=None),
            "ram": memory.percent,
            "available_ram": memory.available,
            "free_storage": free,
            "process_count": len(psutil.pids()),
        }

    def verify_measurement(self, before: dict, after: dict) -> dict:
        """Produce an honest, factual before/after comparison without exaggerated claims (Section 14)."""
        ram_delta = before["ram"] - after["ram"]
        proc_delta = before["process_count"] - after["process_count"]
        storage_delta = after["free_storage"] - before["free_storage"]

        details = []
        has_change = False

        if abs(ram_delta) >= 1.0:
            direction = "decreased" if ram_delta > 0 else "increased"
            details.append(f"RAM usage {direction} by {abs(ram_delta):.1f} percentage points ({before['ram']:.0f}% → {after['ram']:.0f}%).")
            has_change = True

        if storage_delta >= 10 * 1024 * 1024:  # > 10 MB
            details.append(f"Storage space recovered: {storage_delta / 1024**2:.1f} MB.")
            has_change = True

        if abs(proc_delta) >= 1:
            direction = "fewer" if proc_delta > 0 else "more"
            details.append(f"Active process count: {abs(proc_delta)} {direction} ({before['process_count']} → {after['process_count']}).")
            has_change = True

        if not has_change:
            summary = "No significant measurable change detected."
            detail_str = "Immediate system metrics remained within nominal variance. Changes may take effect upon application restart or user sign-in."
        else:
            summary = "Measurable improvements recorded."
            detail_str = " ".join(details)

        return {
            "has_change": has_change,
            "summary": summary,
            "details": detail_str,
            "ram_before": before["ram"],
            "ram_after": after["ram"],
            "storage_recovered": max(0, storage_delta),
            "processes_before": before["process_count"],
            "processes_after": after["process_count"],
        }

    def recommendations(self, scan: dict | None = None) -> list[Recommendation]:
        """Generate hardware-aware recommendations with transparent priorities (Sections 6 & 7)."""
        live = (scan or {}).get("live", {})
        ram_info = (scan or {}).get("ram", {})
        storage = (scan or {}).get("storage", [])

        recs: list[Recommendation] = []

        # 1. Startup Recommendations
        startup = self.startup_items()
        safe_startup = [item for item in startup if item["safe"] and not item["ignored"]]
        high_startup = [item for item in safe_startup if item["impact"] in ("High", "Medium")]

        if high_startup:
            recs.append(Recommendation(
                key="startup",
                title=f"Review {len(high_startup)} high-impact startup items",
                category="Startup",
                description=f"Identified {len(high_startup)} startup programs with elevated boot impact. Selected items can be disabled and restored at any time.",
                reason=f"Fact: {len(safe_startup)} non-protected startup items are enabled at sign-in.",
                risk="LOW",
                benefit="May reduce boot time and idle background memory usage.",
                priority="Recommended",
                supported=True,
                action="startup",
            ))
        elif safe_startup:
            recs.append(Recommendation(
                key="startup",
                title="Optional: review startup items",
                category="Startup",
                description=f"{len(safe_startup)} optional startup items detected.",
                reason=f"Fact: {len(safe_startup)} non-protected startup item(s) are enabled.",
                risk="LOW",
                benefit="Minor memory reduction.",
                priority="Optional",
                supported=True,
                action="startup",
            ))

        # 2. Cleanup Recommendations
        temp_locs = self.temporary_locations()
        total_temp = sum(x["bytes"] for x in temp_locs)
        has_low_space = any(d.get("total", 0) and (d.get("free", 0) / d["total"]) < 0.15 for d in storage)

        if total_temp >= 100 * 1024 * 1024:  # >= 100 MB
            prio = "Recommended" if has_low_space or total_temp >= 1024**3 else "Optional"
            recs.append(Recommendation(
                key="cleanup",
                title=f"Clean safe temporary data ({total_temp / 1024**3:.2f} GB recoverable)",
                category="Storage",
                description="Safely removes verified temporary files, cache locations, and Recycle Bin items. Personal files are never touched.",
                reason=f"Fact: approximately {total_temp / 1024**3:.2f} GB of temporary data detected across safe locations.",
                risk="LOW",
                benefit="Recovers disk space and reduces filesystem clutter.",
                priority=prio,
                supported=True,
                action="cleanup",
            ))

        # 3. Hardware-Aware Storage Guidance
        has_hdd = any("HDD" in (d.get("kind") or "").upper() for d in storage)
        all_ssd = storage and all("SSD" in (d.get("kind") or "").upper() for d in storage)

        if all_ssd:
            recs.append(Recommendation(
                key="storage-trim",
                title="SSD TRIM verification",
                category="Storage",
                description="Windows handles SSD optimization via TRIM automatically. Traditional disk defragmentation is safely excluded to protect NAND flash lifespan.",
                reason="Fact: System uses Solid State Storage (SSD).",
                risk="LOW",
                benefit="Ensures optimal SSD health and prevents unnecessary write wear.",
                priority="Detection Only",
                supported=False,
                action=None,
            ))
        elif has_hdd:
            recs.append(Recommendation(
                key="storage-hdd",
                title="Mechanical drive (HDD) optimization",
                category="Storage",
                description="Mechanical hard drives suffer from seek latency under concurrent access. Limiting background apps and startup programs reduces disk head contention.",
                reason="Fact: System utilizes a mechanical hard disk.",
                risk="LOW",
                benefit="Reduces disk queue length and seek latency.",
                priority="Optional",
                supported=False,
                action=None,
            ))

        # 4. Visual Performance
        recs.append(Recommendation(
            key="visual",
            title="Reduce client-area window animations",
            category="Visual Effects",
            description="Reduces Windows client-area animation transitions. Completely reversible in Restore Center.",
            reason="Supported native Windows UI performance preference.",
            risk="LOW",
            benefit="May reduce GPU and compositor overhead on older graphics hardware.",
            priority="Optional",
            supported=True,
            action="visual",
        ))

        # 5. Power Plan
        recs.append(Recommendation(
            key="power",
            title="High performance power configuration",
            category="Power",
            description="Switches to the Windows High performance power plan to avoid CPU clock throttling. Prior power plan is preserved and fully restorable.",
            reason="Prevents aggressive CPU downclocking during heavy workloads.",
            risk="MEDIUM",
            benefit="May reduce processor throttling under burst workloads; may increase heat and fan noise.",
            priority="Optional",
            supported=True,
            action="power",
        ))

        # 6. Memory pressure notification if RAM is high
        if live.get("ram", 0) >= 75:
            recs.append(Recommendation(
                key="memory",
                title="Elevated background memory pressure",
                category="RAM",
                description="Multiple applications are consuming resident memory. Review the Processes tab to identify high-memory tasks.",
                reason=f"Fact: RAM usage is currently {live.get('ram', 0):.0f}%.",
                risk="LOW",
                benefit="Closes inactive tasks to reduce memory paging.",
                priority="Detection Only",
                supported=False,
                action=None,
            ))

        return recs

    def disable_startup(self, item: dict) -> dict:
        if not item["safe"]:
            raise PermissionError("Protected startup item cannot be modified.")
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
            value, kind = winreg.QueryValueEx(key, item["name"])
            winreg.DeleteValue(key, item["name"])
        return {
            "previous": str(value),
            "new": "disabled",
            "backup": {"name": item["name"], "value": value, "kind": kind},
        }

    def clean_temporary(self, selected_categories: list[dict] | None = None) -> dict:
        """Safely clean only approved temporary locations (Section 12)."""
        locations = selected_categories or self.temporary_locations()
        deleted = 0
        failures: list[str] = []

        for loc in locations:
            category = loc.get("category", "")
            if category == "recycle_bin":
                ok, msg = empty_recycle_bin()
                if ok:
                    deleted += loc.get("bytes", 0)
                else:
                    failures.append(f"Recycle Bin: {msg}")
                continue

            root: Path = loc.get("path")
            if not root or not root.exists():
                continue

            try:
                for path in root.iterdir():
                    try:
                        sz = sum(_safe_size(p) for p in path.rglob("*")) if path.is_dir() else _safe_size(path)
                        if path.is_dir():
                            shutil.rmtree(path, ignore_errors=False)
                        else:
                            path.unlink()
                        deleted += sz
                    except (OSError, PermissionError) as exc:
                        failures.append(f"{path.name}: in use")
            except (OSError, PermissionError) as exc:
                failures.append(f"{root.name}: {exc}")

        return {
            "previous": f"{sum(x['bytes'] for x in locations)} bytes selected",
            "new": f"{deleted} bytes removed",
            "backup": {},
            "failures": failures,
            "deleted_bytes": deleted,
        }

    def set_visual_performance(self) -> dict:
        SPI_GETCLIENTAREAANIMATION, SPI_SETCLIENTAREAANIMATION, SPIF_SENDCHANGE = 0x1042, 0x1043, 2
        current = ctypes.c_int()
        if not ctypes.windll.user32.SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(current), 0):
            raise OSError("Windows does not support this visual-effect setting.")
        if not ctypes.windll.user32.SystemParametersInfoW(SPI_SETCLIENTAREAANIMATION, 0, ctypes.byref(ctypes.c_int(0)), SPIF_SENDCHANGE):
            raise OSError("Windows rejected the visual-effect change.")
        return {
            "previous": str(bool(current.value)),
            "new": "False",
            "backup": {"enabled": bool(current.value)},
        }

    def set_high_performance(self) -> dict:
        old = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True, timeout=8)
        if old.returncode != 0:
            raise OSError(old.stderr.strip() or "Could not identify the active power plan.")
        previous = old.stdout.strip()
        result = subprocess.run(["powercfg", "/setactive", "SCHEME_MIN"], capture_output=True, text=True, timeout=8)
        if result.returncode != 0:
            raise OSError(result.stderr.strip() or "Windows could not activate High performance.")
        match = re.search(r"([0-9a-fA-F-]{36})", previous)
        return {
            "previous": previous,
            "new": "High performance",
            "backup": {"scheme": match.group(1) if match else ""},
        }

    def restore(self, action: dict) -> None:
        typ, backup = action["action_type"], action["backup"]
        if typ == "startup":
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, backup["name"], 0, backup["kind"], backup["value"])
        elif typ == "visual":
            value = ctypes.c_int(int(backup["enabled"]))
            if not ctypes.windll.user32.SystemParametersInfoW(0x1043, 0, ctypes.byref(value), 2):
                raise OSError("Windows rejected visual setting restore.")
        elif typ == "power":
            if not backup.get("scheme"):
                raise OSError("Previous power plan GUID was not recorded.")
            result = subprocess.run(["powercfg", "/setactive", backup["scheme"]], capture_output=True, text=True, timeout=8)
            if result.returncode != 0:
                raise OSError(result.stderr.strip() or "Windows rejected power plan restore.")
        else:
            raise OSError("This action cannot be restored because temporary files are permanently removed.")
