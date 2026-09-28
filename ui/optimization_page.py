"""Searchable, hardware-aware Optimization Center with transparent priority badges and review flows."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from core.optimizer import Recommendation
from core.settings_catalog import SETTINGS, PROFILES, Setting, resolve_hardware_aware_profile


PRIORITY_COLORS = {
    'Recommended': '#8b7cff',
    'Optional': '#5b8bf7',
    'Low Impact': '#96a5bb',
    'Detection Only': '#eab308',
}


class ReviewDialog(QDialog):
    """Transparent preview modal allowing users to confirm exactly what changes will be made (Section 8)."""
    def __init__(self, settings: list[Setting], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Review Recommended Optimizations")
        self.resize(620, 520)
        self.selected_settings: list[Setting] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel(f"Review {len(settings)} Recommended Changes")
        title.setObjectName("title")
        layout.addWidget(title)

        desc = QLabel("Optima never makes silent changes. Review the operations below and select which to apply:")
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        box = QWidget()
        box_layout = QVBoxLayout(box)
        box_layout.setSpacing(10)

        self.checkboxes: list[tuple[QCheckBox, Setting]] = []
        for s in settings:
            item_frame = QFrame()
            item_frame.setObjectName("card")
            il = QHBoxLayout(item_frame)
            il.setContentsMargins(14, 10, 14, 10)

            cb = QCheckBox(f"✓  {s.name}")
            cb.setChecked(True)
            cb.setStyleSheet("font-weight: 700; font-size: 14px; color: #fff;")
            il.addWidget(cb, 1)

            prio_lbl = QLabel(f"[{s.priority}]")
            prio_lbl.setStyleSheet(f"color: {PRIORITY_COLORS.get(s.priority, '#fff')}; font-weight: bold;")
            il.addWidget(prio_lbl)

            rev_lbl = QLabel("Reversible" if s.reversible else "Permanent")
            rev_lbl.setObjectName("muted")
            il.addWidget(rev_lbl)

            box_layout.addWidget(item_frame)
            self.checkboxes.append((cb, s))

        box_layout.addStretch()
        scroll.setWidget(box)
        layout.addWidget(scroll)

        btn_box = QDialogButtonBox()
        self.apply_btn = btn_box.addButton("Apply Selected Optimizations", QDialogButtonBox.AcceptRole)
        self.apply_btn.setObjectName("accent")
        self.cancel_btn = btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        self.apply_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btn_box)

    def get_selected(self) -> list[Setting]:
        return [s for cb, s in self.checkboxes if cb.isChecked()]


class OptimizationPage(QWidget):
    """Searchable catalogue; only cards with an action can invoke Optima."""

    def __init__(self, host) -> None:
        super().__init__()
        self.host = host
        self.selected: dict[str, Setting] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)

        top_row = QHBoxLayout()
        title = QLabel("Optimization Center")
        title.setObjectName("title")
        top_row.addWidget(title)
        top_row.addStretch()

        self.btn_optimize_all = QPushButton("✦  Optimize Recommended Settings")
        self.btn_optimize_all.setObjectName("accent")
        self.btn_optimize_all.clicked.connect(self.optimize_recommended)
        top_row.addWidget(self.btn_optimize_all)
        layout.addLayout(top_row)

        self.summary = QLabel("Select a profile or individual supported settings, then preview changes.")
        self.summary.setObjectName("muted")
        layout.addWidget(self.summary)

        controls = QHBoxLayout()
        self.profile = QComboBox()
        self.profile.addItems(PROFILES)
        self.profile.currentTextChanged.connect(self.apply_profile)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search optimization settings...")
        self.search.textChanged.connect(self.refresh)

        preview = QPushButton("Review Selected")
        preview.clicked.connect(self.review_selected)

        controls.addWidget(self.profile)
        controls.addWidget(self.search, 1)
        controls.addWidget(preview)
        layout.addLayout(controls)

        self.cards = QVBoxLayout()
        box = QWidget()
        box.setLayout(self.cards)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(box)
        layout.addWidget(scroll)

        self.refresh()

    def apply_profile(self, name: str) -> None:
        has_ssd = True
        if self.host.scan_data and self.host.scan_data.get("storage"):
            has_ssd = all("SSD" in (d.get("kind") or "").upper() for d in self.host.scan_data["storage"])
        low_ram = False
        if self.host.scan_data and self.host.scan_data.get("ram"):
            low_ram = (self.host.scan_data["ram"].get("total", 0) / 1024**3) <= 8.5

        enabled = set(resolve_hardware_aware_profile(name, has_ssd, low_ram))
        self.selected = {s.id: s for s in SETTINGS if s.id in enabled and s.action}
        self.refresh()

    def refresh(self) -> None:
        while self.cards.count():
            item = self.cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        query = self.search.text().lower().strip()
        shown = [
            s for s in SETTINGS
            if not query or query in (s.category + " " + s.name + " " + s.description + " " + s.priority).lower()
        ]

        categories = []
        for s in shown:
            if s.category not in categories:
                categories.append(s.category)

        supported_count = sum(bool(s.action) for s in SETTINGS)
        self.summary.setText(
            f"{len(shown)} settings across {len(categories)} categories • {supported_count} supported actions • others are detection only"
        )

        for cat in categories:
            heading = QLabel(cat.upper())
            heading.setObjectName("badge")
            self.cards.addWidget(heading)
            for s in [x for x in shown if x.category == cat]:
                self.cards.addWidget(self.card(s))

        self.cards.addStretch()

    def card(self, s: Setting) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)

        text = QVBoxLayout()
        header_row = QHBoxLayout()
        title = QLabel(s.name)
        title.setObjectName("quickTitle")
        header_row.addWidget(title)

        prio_badge = QLabel(f" {s.priority.upper()} ")
        color = PRIORITY_COLORS.get(s.priority, "#fff")
        prio_badge.setStyleSheet(f"background: #1e293b; color: {color}; border: 1px solid {color}; border-radius: 4px; font-size: 11px; font-weight: bold; padding: 2px 5px;")
        header_row.addWidget(prio_badge)
        header_row.addStretch()
        text.addLayout(header_row)

        desc = QLabel(s.description)
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        text.addWidget(desc)

        summary = QLabel(
            f"{s.category}  •  {s.risk} risk  •  {'Reversible' if s.reversible else 'Permanent'}  •  {'Supported' if s.action else 'Detection only'}"
        )
        summary.setObjectName("muted")
        text.addWidget(summary)
        layout.addLayout(text, 1)

        check = QCheckBox("Select")
        check.setEnabled(bool(s.action))
        check.setChecked(s.id in self.selected)
        check.toggled.connect(lambda on, setting=s: self.toggle(setting, on))
        layout.addWidget(check)

        details = QPushButton("⋯")
        details.setToolTip("View setting details")
        details.setFixedWidth(38)
        details.clicked.connect(lambda checked=False, setting=s: self.details(setting))
        layout.addWidget(details)

        if s.action:
            apply = QPushButton("Apply")
            apply.setObjectName("accent")
            apply.clicked.connect(lambda checked=False, setting=s: self.apply_one(setting))
            layout.addWidget(apply)

        return card

    def toggle(self, s: Setting, on: bool) -> None:
        if on:
            self.selected[s.id] = s
        else:
            self.selected.pop(s.id, None)

    def details(self, s: Setting) -> None:
        QMessageBox.information(
            self,
            "Optimization details",
            f"{s.name}\n\nWhat it does:\n{s.description}\n\n"
            f"Priority: {s.priority}\nRisk: {s.risk}\nReversible: {'Yes' if s.reversible else 'No'}\n"
            f"Expected Benefit: {s.benefit}\n\n"
            f"{('This action is supported and requires explicit confirmation.' if s.action else 'Detection only — diagnostic insight; cannot modify Windows in this release.')}",
        )

    def apply_one(self, s: Setting) -> None:
        self.host.apply(
            Recommendation(
                s.action,
                s.name,
                s.category,
                s.description,
                "Applied individually from Optimization Center.",
                s.risk,
                s.benefit,
                s.priority,
            )
        )
        self.refresh()

    def review_selected(self) -> None:
        settings = list(self.selected.values())
        if not settings:
            QMessageBox.information(self, "Optimization review", "No supported settings are selected.")
            return

        dlg = ReviewDialog(settings, self)
        if dlg.exec() == QDialog.Accepted:
            chosen = dlg.get_selected()
            if not chosen:
                return
            for s in chosen:
                self.apply_one(s)

    def optimize_recommended(self) -> None:
        """One-Click Smart Optimization from the Optimization Page (Section 8)."""
        recommended_settings = [s for s in SETTINGS if s.priority == "Recommended" and s.action]
        dlg = ReviewDialog(recommended_settings, self)
        if dlg.exec() == QDialog.Accepted:
            chosen = dlg.get_selected()
            if not chosen:
                return
            for s in chosen:
                self.apply_one(s)
