import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
    QFileDialog,
    QMessageBox,
)

from core.database import OptimaDatabase
from core.game_scanner import GameScanner


class GameCenterPage(QWidget):
    """Game Center UI page.

    Provides:
    * "Scan for Games" – runs the GameScanner to discover installed games.
    * "Add Game Manually" – lets user pick an executable to add.
    * A scrollable list of game cards showing basic info.
    """

    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main = main_window
        # Database instance is shared with MainWindow
        self.db: OptimaDatabase = self.main.db
        self.scanner = GameScanner(self.db)

        self._build_ui()
        self.refresh()  # initial empty view

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)

        # Header
        header = QLabel("Game Center – Detect and Optimize Your Installed Games")
        header.setObjectName("title")
        layout.addWidget(header)

        # Action bar
        actions = QHBoxLayout()
        self.btn_scan = QPushButton("Scan for Games")
        self.btn_scan.clicked.connect(self.scan_games)
        actions.addWidget(self.btn_scan)

        self.btn_add = QPushButton("Add Game Manually")
        self.btn_add.clicked.connect(self.add_game_manual)
        actions.addWidget(self.btn_add)
        actions.addStretch()
        layout.addLayout(actions)

        # Scroll area for game cards
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.cards_container)
        layout.addWidget(self.scroll)

    def scan_games(self) -> None:
        """Run a full game scan and refresh the UI."""
        try:
            self.scanner.scan_all()
            self.main.toast("Game scan complete.")
        except Exception as e:
            QMessageBox.critical(self, "Game Scan Failed", str(e))
        self.refresh()

    def add_game_manual(self) -> None:
        """Open a file dialog to manually add a game executable."""
        exe_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Game Executable",
            str(Path.home()),
            "Executable Files (*.exe)"
        )
        if not exe_path:
            return
        try:
            self.scanner.add_manual_game(exe_path)
            self.main.toast(f"Added game: {os.path.basename(exe_path)}")
        except Exception as e:
            QMessageBox.warning(self, "Add Game Failed", str(e))
        self.refresh()

    def refresh(self) -> None:
        """Reload game cards from the database."""
        # Clear existing cards
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        games = self.db.get_games()
        if not games:
            placeholder = QLabel("No games detected. Use \"Scan for Games\" or add one manually.")
            placeholder.setObjectName("muted")
            self.cards_layout.addWidget(placeholder)
            return

        for game in games:
            card = self._make_game_card(game)
            self.cards_layout.addWidget(card)
        self.cards_layout.addStretch()

    def _make_game_card(self, game: dict) -> QFrame:
        """Create a UI card widget for a single game entry.

        Expected keys in *game* dict (as defined in core/database):
        - id, name, exe_path, install_dir, publisher, last_launched, profile, enabled
        """
        card = QFrame()
        card.setObjectName('card')
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)

        title = QLabel(game.get('name', os.path.basename(game.get('exe_path', ''))))
        title.setObjectName('title')
        layout.addWidget(title)

        details = []
        publisher = game.get('publisher')
        if publisher:
            details.append(f"Publisher: {publisher}")
        exe = game.get('exe_path')
        if exe:
            details.append(f"Exe: {os.path.basename(exe)}")
        profile = game.get('profile') or "(default)"
        details.append(f"Profile: {profile}")
        enabled = "Enabled" if game.get('enabled', 1) else "Disabled"
        details.append(f"Status: {enabled}")
        detail_lbl = QLabel(" • ".join(details))
        detail_lbl.setObjectName('muted')
        layout.addWidget(detail_lbl)

        # Action buttons row
        btn_row = QHBoxLayout()
        btn_opt = QPushButton("Optimize")
        btn_opt.clicked.connect(lambda _, gid=game['id']: self._optimise_game(gid))
        btn_row.addWidget(btn_opt)

        btn_launch = QPushButton("Launch")
        btn_launch.clicked.connect(lambda _, path=game['exe_path']: os.startfile(path))
        btn_row.addWidget(btn_launch)

        btn_settings = QPushButton("Settings")
        btn_settings.clicked.connect(lambda _, gid=game['id']: self._open_game_settings(gid))
        btn_row.addWidget(btn_settings)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        return card

    # Placeholder slots – real implementations will be added later
    def _optimise_game(self, game_id: int) -> None:
        QMessageBox.information(self, "Optimize Game", f"Optimization flow for game ID {game_id} not yet implemented.")

    def _open_game_settings(self, game_id: int) -> None:
        QMessageBox.information(self, "Game Settings", f"Settings dialog for game ID {game_id} not yet implemented.")
