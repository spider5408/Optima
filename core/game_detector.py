"""Passive, anti-cheat safe game detection engine.

Never hooks into game memory, never injects DLLs, and never modifies game files.
Purely inspects running process names against known signatures.
"""
from __future__ import annotations

import os
import psutil

# Common known game executables
DEFAULT_GAME_EXECUTABLES: dict[str, str] = {
    "cs2.exe": "Counter-Strike 2",
    "csgo.exe": "Counter-Strike: Global Offensive",
    "dota2.exe": "Dota 2",
    "valorant.exe": "Valorant",
    "fortniteclient-win64-shipping.exe": "Fortnite",
    "gta5.exe": "Grand Theft Auto V",
    "cyberpunk2077.exe": "Cyberpunk 2077",
    "overwatch.exe": "Overwatch",
    "r5apex.exe": "Apex Legends",
    "apex.exe": "Apex Legends",
    "genshinimpact.exe": "Genshin Impact",
    "starrail.exe": "Honkai: Star Rail",
    "leagueclient.exe": "League of Legends",
    "minecraft.exe": "Minecraft",
    "robloxplayerbeta.exe": "Roblox",
    "witcher3.exe": "The Witcher 3",
    "eldenring.exe": "Elden Ring",
    "rocketleague.exe": "Rocket League",
    "baldursgate3.exe": "Baldur's Gate 3",
    "bg3.exe": "Baldur's Gate 3",
    "destiny2.exe": "Destiny 2",
    "warframe.x64.exe": "Warframe",
    "rainbowsix.exe": "Rainbow Six Siege",
}


class GameDetector:
    def __init__(self, custom_games: dict[str, str] | None = None) -> None:
        self.game_catalog = dict(DEFAULT_GAME_EXECUTABLES)
        if custom_games:
            self.game_catalog.update({k.lower(): v for k, v in custom_games.items()})
        self.active_game: str | None = None
        self.minimize_setting: str = "Balanced"  # 'Off', 'Balanced', 'Maximum Resource Saving'

    def register_game(self, exe_name: str, display_name: str) -> None:
        self.game_catalog[exe_name.lower().strip()] = display_name.strip()

    def check_active_game(self) -> tuple[bool, str | None]:
        """Passive check of running process names.

        Fast and non-intrusive.
        """
        try:
            for p in psutil.process_iter(["name"]):
                name = (p.info.get("name") or "").lower()
                if name in self.game_catalog:
                    self.active_game = self.game_catalog[name]
                    return True, self.active_game
        except (psutil.Error, OSError):
            pass
        self.active_game = None
        return False, None
