"""Windows-aware, defensive hardware discovery and Win32 helpers with aggressive caching."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import platform
import subprocess
from typing import Any

UNAVAILABLE = "Unavailable"

# In-memory hardware cache to avoid expensive WMI/PowerShell queries during normal operation
_HARDWARE_CACHE: dict[str, Any] = {}


def powershell_value(script: str) -> str:
    """Return a small PowerShell query result; hardware APIs vary by Windows edition."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        value = result.stdout.strip()
        return value if result.returncode == 0 and value else UNAVAILABLE
    except (OSError, subprocess.SubprocessError):
        return UNAVAILABLE


def gpu_info(force_refresh: bool = False) -> dict[str, str]:
    """Return GPU name and VRAM. Cached to prevent PowerShell startup overhead."""
    if not force_refresh and "gpu" in _HARDWARE_CACHE:
        return _HARDWARE_CACHE["gpu"]

    name = powershell_value("(Get-CimInstance Win32_VideoController | Select-Object -First 1 -Expand Name)")
    vram = powershell_value("(Get-CimInstance Win32_VideoController | Select-Object -First 1 -Expand AdapterRAM)")
    try:
        vram_str = f"{int(vram) / 1024**3:.1f} GB" if vram != UNAVAILABLE else UNAVAILABLE
    except ValueError:
        vram_str = UNAVAILABLE
    info = {"name": name, "vram": vram_str}
    _HARDWARE_CACHE["gpu"] = info
    return info


def disk_kind(letter: str, force_refresh: bool = False) -> str:
    """Map a Windows physical-disk media type (SSD vs HDD). Cached per drive letter."""
    letter = letter.upper().rstrip(":\\")
    cache_key = f"disk_kind_{letter}"
    if not force_refresh and cache_key in _HARDWARE_CACHE:
        return _HARDWARE_CACHE[cache_key]

    # Try mapping partition to physical disk media type
    script = f"$p = (Get-Partition -DriveLetter '{letter}' -ErrorAction SilentlyContinue | Get-Disk | Get-PhysicalDisk); if ($p.MediaType) {{ $p.MediaType }} else {{ (Get-PhysicalDisk | Select-Object -First 1).MediaType }}"
    kind = powershell_value(script)
    if "SSD" in kind.upper():
        detected = "SSD"
    elif "HDD" in kind.upper():
        detected = "HDD"
    elif kind in {"Unspecified", "SCM"}:
        detected = kind
    else:
        detected = UNAVAILABLE

    _HARDWARE_CACHE[cache_key] = detected
    return detected


def os_info() -> dict[str, str]:
    if "os" in _HARDWARE_CACHE:
        return _HARDWARE_CACHE["os"]
    info = {"name": platform.platform(), "architecture": platform.architecture()[0]}
    _HARDWARE_CACHE["os"] = info
    return info


def clear_hardware_cache() -> None:
    """Clear hardware cache to force fresh discovery on Full Scan."""
    _HARDWARE_CACHE.clear()


# =========================================================================
# Lightweight Native Win32 Helpers (Zero Subprocess / Zero PowerShell Overhead)
# =========================================================================

def get_file_company(filepath: str | Path | None) -> str:
    """Extract publisher/company name from Windows PE executable using version.dll.

    Zero subprocess overhead; executes in microseconds.
    """
    if not filepath:
        return "Unknown"
    filepath_str = str(filepath)
    if not os.path.exists(filepath_str):
        return "Unknown"

    try:
        ver_size = ctypes.windll.version.GetFileVersionInfoSizeW(filepath_str, None)
        if not ver_size:
            return "Unknown"
        res = ctypes.create_string_buffer(ver_size)
        if not ctypes.windll.version.GetFileVersionInfoW(filepath_str, 0, ver_size, res):
            return "Unknown"

        # Try default US English codepage
        p_val = ctypes.c_wchar_p()
        v_len = ctypes.c_uint()
        sub_block_default = "\\StringFileInfo\\040904b0\\CompanyName"
        if ctypes.windll.version.VerQueryValueW(res, sub_block_default, ctypes.byref(p_val), ctypes.byref(v_len)) and p_val.value:
            return p_val.value.strip()

        # Query translation block if default didn't hit
        p_trans = ctypes.c_void_p()
        u_len = ctypes.c_uint()
        if ctypes.windll.version.VerQueryValueW(res, "\\VarFileInfo\\Translation", ctypes.byref(p_trans), ctypes.byref(u_len)):
            trans_arr = ctypes.cast(p_trans, ctypes.POINTER(wintypes.WORD))
            lang = trans_arr[0]
            codepage = trans_arr[1]
            sub_block = f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\CompanyName"
            if ctypes.windll.version.VerQueryValueW(res, sub_block, ctypes.byref(p_val), ctypes.byref(v_len)) and p_val.value:
                return p_val.value.strip()
    except Exception:
        pass
    return "Unknown"


class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("i64Size", ctypes.c_int64),
        ("i64NumItems", ctypes.c_int64),
    ]


def recycle_bin_info() -> dict[str, int]:
    """Query Recycle Bin byte size and item count using Windows Shell API.

    Instantaneous Win32 API call without spawning PowerShell or disk crawling.
    """
    try:
        info = _SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(_SHQUERYRBINFO)
        hr = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
        if hr == 0:
            return {"bytes": max(0, int(info.i64Size)), "items": max(0, int(info.i64NumItems))}
    except Exception:
        pass
    return {"bytes": 0, "items": 0}


def empty_recycle_bin() -> tuple[bool, str]:
    """Safely empty the Recycle Bin without UI prompt using Shell API."""
    try:
        SHERB_NOCONFIRMATION = 0x00000001
        SHERB_NOPROGRESSUI = 0x00000002
        SHERB_NOSOUND = 0x00000004
        flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        hr = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
        if hr == 0:
            return True, "Recycle Bin emptied successfully"
        return False, f"Recycle Bin returned code {hr}"
    except Exception as exc:
        return False, str(exc)
