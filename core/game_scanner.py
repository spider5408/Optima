"""Fast, lightweight installed game scanner for Steam, Epic Games, Roblox, and Windows libraries.

Never scans entire drives blindly; relies on known launcher manifests and verified registry paths.
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path
import re
import winreg
from typing import Any

from .database import OptimaDatabase
from .hardware import get_file_company


class GameScanner:
    def __init__(self, db: OptimaDatabase) -> None:
        self.db = db

    def scan_all(self) -> list[dict]:
        """Perform a targeted scan across all supported launchers and libraries."""
        found_games: list[dict] = []
        seen_exes: set[str] = set()

        # 1. Epic Games Library
        for g in self.scan_epic_games():
            exe_norm = os.path.normpath(g["exe_path"]).lower()
            if exe_norm not in seen_exes:
                seen_exes.add(exe_norm)
                found_games.append(g)

        # 2. Steam Library
        for g in self.scan_steam_games():
            exe_norm = os.path.normpath(g["exe_path"]).lower()
            if exe_norm not in seen_exes:
                seen_exes.add(exe_norm)
                found_games.append(g)

        # 3. Roblox
        for g in self.scan_roblox():
            exe_norm = os.path.normpath(g["exe_path"]).lower()
            if exe_norm not in seen_exes:
                seen_exes.add(exe_norm)
                found_games.append(g)

        # 4. Minecraft
        for g in self.scan_minecraft():
            exe_norm = os.path.normpath(g["exe_path"]).lower()
            if exe_norm not in seen_exes:
                seen_exes.add(exe_norm)
                found_games.append(g)

        # 5. Common Game Folders (Riot, GOG, Xbox)
        for g in self.scan_common_locations():
            exe_norm = os.path.normpath(g["exe_path"]).lower()
            if exe_norm not in seen_exes:
                seen_exes.add(exe_norm)
                found_games.append(g)

        # Save / Upsert to database
        results: list[dict] = []
        for g in found_games:
            gid = self.db.upsert_game(g)
            saved = self.db.get_game(gid)
            if saved:
                results.append(saved)

        return results

    def scan_epic_games(self) -> list[dict]:
        """Scan Epic Games Launcher manifest files."""
        games = []
        manifest_dir = r"C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests"
        if not os.path.exists(manifest_dir):
            return games

        for item_file in glob.glob(os.path.join(manifest_dir, "*.item")):
            try:
                with open(item_file, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)

                name = data.get("DisplayName", "")
                name = re.sub(r"[^\x20-\x7E]+", "", name).strip()  # Clean unicode artifacts
                install_dir = data.get("InstallLocation", "")
                launch_exe = data.get("LaunchExecutable", "")

                if not name or not install_dir or not launch_exe:
                    continue

                exe_full = os.path.normpath(os.path.join(install_dir, launch_exe))
                if os.path.exists(exe_full):
                    publisher = get_file_company(exe_full)
                    games.append({
                        "name": name,
                        "publisher": publisher if publisher != "Unknown" else "Epic Games",
                        "exe_path": exe_full,
                        "install_dir": install_dir,
                        "launcher": "Epic Games",
                        "detection_source": "Epic Manifest",
                    })
            except Exception:
                continue
        return games

    def scan_steam_games(self) -> list[dict]:
        """Scan Steam library manifests across all configured library drives."""
        games = []
        steam_paths = set()

        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(root, r"Software\Valve\Steam") as key:
                    path, _ = winreg.QueryValueEx(key, "SteamPath")
                    if path and os.path.exists(path):
                        steam_paths.add(os.path.normpath(path))
            except OSError:
                pass

        if not steam_paths:
            default_path = r"C:\Program Files (x86)\Steam"
            if os.path.exists(default_path):
                steam_paths.add(os.path.normpath(default_path))

        library_roots = set(steam_paths)
        for sp in steam_paths:
            vdf_path = os.path.join(sp, "steamapps", "libraryfolders.vdf")
            if os.path.exists(vdf_path):
                try:
                    with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    matches = re.findall(r'\"path\"\s+\"([^\"]+)\"', content)
                    for m in matches:
                        p_clean = os.path.normpath(m.replace("\\\\", "\\"))
                        if os.path.exists(p_clean):
                            library_roots.add(p_clean)
                except Exception:
                    pass

        for lib in library_roots:
            steamapps = os.path.join(lib, "steamapps")
            if not os.path.exists(steamapps):
                continue

            for acf in glob.glob(os.path.join(steamapps, "appmanifest_*.acf")):
                try:
                    with open(acf, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    name_match = re.search(r'\"name\"\s+\"([^\"]+)\"', content)
                    dir_match = re.search(r'\"installdir\"\s+\"([^\"]+)\"', content)
                    if not name_match or not dir_match:
                        continue

                    name = name_match.group(1).strip()
                    installdir = dir_match.group(1).strip()
                    game_dir = os.path.join(steamapps, "common", installdir)

                    if not os.path.exists(game_dir):
                        continue

                    # Find primary executable
                    candidate_exe = None
                    for root_dir, _, files in os.walk(game_dir):
                        for file in files:
                            if file.lower().endswith(".exe") and not any(w in file.lower() for w in ("crash", "report", "unins", "redist", "setup", "helper")):
                                candidate_exe = os.path.join(root_dir, file)
                                break
                        if candidate_exe:
                            break

                    if candidate_exe and os.path.exists(candidate_exe):
                        games.append({
                            "name": name,
                            "publisher": get_file_company(candidate_exe),
                            "exe_path": os.path.normpath(candidate_exe),
                            "install_dir": game_dir,
                            "launcher": "Steam",
                            "detection_source": "Steam Manifest",
                        })
                except Exception:
                    continue
        return games

    def scan_roblox(self) -> list[dict]:
        """Detect Roblox Player installations."""
        games = []
        local_app = os.environ.get("LOCALAPPDATA", "")
        if not local_app:
            return games

        pattern = os.path.join(local_app, "Roblox", "Versions", "*", "RobloxPlayerBeta.exe")
        matches = glob.glob(pattern)
        if matches:
            # Sort by mtime to pick the latest version
            matches.sort(key=os.path.getmtime, reverse=True)
            latest = matches[0]
            games.append({
                "name": "Roblox",
                "publisher": "Roblox Corporation",
                "exe_path": os.path.normpath(latest),
                "install_dir": os.path.dirname(latest),
                "launcher": "Roblox",
                "detection_source": "AppData Directory",
            })
        return games

    def scan_minecraft(self) -> list[dict]:
        """Detect Minecraft Launcher or Java installations."""
        games = []
        candidates = [
            (r"C:\Program Files (x86)\Minecraft Launcher\MinecraftLauncher.exe", "Minecraft Launcher"),
            (os.path.expandvars(r"%LOCALAPPDATA%\Packages\Microsoft.4297127D64C94_8wekyb3d8bbwe\LocalCache\Local\Microsoft\WritablePackageRoot\Minecraft.Windows.exe"), "Minecraft Bedrock"),
            (os.path.expandvars(r"%APPDATA%\.minecraft\runtime\java-runtime-gamma\windows\java-runtime-gamma\bin\javaw.exe"), "Minecraft Java Runtime"),
        ]
        for path, name in candidates:
            if os.path.exists(path):
                games.append({
                    "name": name,
                    "publisher": "Mojang / Microsoft",
                    "exe_path": os.path.normpath(path),
                    "install_dir": os.path.dirname(path),
                    "launcher": "Minecraft",
                    "detection_source": "System Directory",
                })
        return games

    def scan_common_locations(self) -> list[dict]:
        """Scan locations for Riot Games, GOG, and Xbox installations."""
        games = []
        search_dirs = [
            (r"C:\Riot Games\Riot Client\RiotClientServices.exe", "Riot Games Client", "Riot Games"),
            (r"C:\Riot Games\VALORANT\live\VALORANT.exe", "Valorant", "Riot Games"),
            (r"C:\Riot Games\League of Legends\LeagueClient.exe", "League of Legends", "Riot Games"),
            (r"C:\XboxGames", "Xbox", "Xbox"),
            (r"C:\GOG Games", "GOG", "GOG"),
        ]
        for path, name, launcher in search_dirs:
            if os.path.isfile(path):
                games.append({
                    "name": name,
                    "publisher": launcher,
                    "exe_path": os.path.normpath(path),
                    "install_dir": os.path.dirname(path),
                    "launcher": launcher,
                    "detection_source": "Common Path",
                })
            elif os.path.isdir(path):
                for sub in os.listdir(path):
                    sub_dir = os.path.join(path, sub)
                    if os.path.isdir(sub_dir):
                        for f in os.listdir(sub_dir):
                            if f.lower().endswith(".exe") and not any(w in f.lower() for w in ("unins", "setup", "crash")):
                                full_exe = os.path.join(sub_dir, f)
                                games.append({
                                    "name": sub,
                                    "publisher": launcher,
                                    "exe_path": os.path.normpath(full_exe),
                                    "install_dir": sub_dir,
                                    "launcher": launcher,
                                    "detection_source": f"{launcher} Directory",
                                })
                                break
        return games

    def add_manual_game(self, exe_path: str, display_name: str = "") -> dict | None:
        """Register a user-selected game executable (Section 23)."""
        exe_path = os.path.normpath(exe_path)
        if not os.path.isfile(exe_path) or not exe_path.lower().endswith(".exe"):
            return None

        name = display_name.strip()
        if not name:
            name = Path(exe_path).stem.replace("_", " ").title()

        publisher = get_file_company(exe_path)
        if publisher == "Unknown":
            publisher = "Custom Game"

        game_data = {
            "name": name,
            "publisher": publisher,
            "exe_path": exe_path,
            "install_dir": os.path.dirname(exe_path),
            "launcher": "Manual",
            "detection_source": "User Added",
            "optimization_profile": "Balanced",
            "overlay_enabled": 1,
            "auto_game_mode": 1,
        }
        gid = self.db.upsert_game(game_data)
        return self.db.get_game(gid)
