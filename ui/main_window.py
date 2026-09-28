"""Optima 0.5 — Smart Optimization + Ultra-Low Resource Engine application shell."""
from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.analyzer import BottleneckAnalysis, analyze_bottleneck
from core.database import OptimaDatabase
from core.game_detector import GameDetector
from core.hardware import clear_hardware_cache, disk_kind, gpu_info, os_info, recycle_bin_info
from core.monitor import LiveMonitor
from core.optimizer import OptimizationEngine, Recommendation
from core.process_analyzer import ProcessAnalyzer
from core.resource_guard import ResourceGuard
from core.scanner import SystemScanner, gib
from core.settings_catalog import SETTINGS, Setting
from ui.optimization_page import OptimizationPage, ReviewDialog
from ui.game_center_page import GameCenterPage

STYLE = """
QMainWindow, QWidget { background: #0d1119; color: #edf2fb; font-family: 'Segoe UI'; font-size: 14px; }
QFrame#sidebar { background: #111827; border-right: 1px solid #263246; }
QFrame#topbar { background: #111827; border-bottom: 1px solid #263246; }
QFrame#card { background: #171f2d; border: 1px solid #29364b; border-radius: 14px; }
QFrame#quick { background: #182235; border: 1px solid #2a3850; border-radius: 12px; }
QFrame#banner { background: #1f1d38; border: 1px solid #7465ff; border-radius: 14px; }
QPushButton { background: #202d42; border: 1px solid #33445f; border-radius: 8px; padding: 8px 14px; color: #dce7f7; font-weight: 500; }
QPushButton:hover { background: #293a57; border-color: #7669ff; }
QPushButton:pressed { background: #182338; }
QPushButton#nav { border: 0; background: transparent; text-align: left; padding: 10px 14px; font-size: 14px; }
QPushButton#nav:hover { background: #1b2739; }
QPushButton#nav:checked { background: #282348; color: #fff; border-left: 3px solid #8b7cff; font-weight: 700; }
QPushButton#accent { background: #7465ff; border: 0; color: white; font-weight: 700; }
QPushButton#accent:hover { background: #8b7cff; }
QPushButton#danger { background: #dc2626; border: 0; color: white; }
QLabel#title { font-size: 22px; font-weight: 700; color: #fff; }
QLabel#metric { font-size: 24px; font-weight: 700; color: #fff; }
QLabel#muted { color: #94a3b8; font-size: 13px; }
QLabel#badge { color: #c4bdff; font-weight: 700; font-size: 12px; letter-spacing: 0.5px; }
QLabel#quickTitle { font-size: 15px; font-weight: 700; color: #fff; }
QLineEdit { background: #192334; border: 1px solid #314058; border-radius: 8px; padding: 8px 12px; color: #fff; }
QProgressBar { background: #263247; border: 0; border-radius: 7px; height: 10px; }
QProgressBar::chunk { background: #7869ff; border-radius: 7px; }
QComboBox { background: #192334; border: 1px solid #314058; border-radius: 8px; padding: 6px 12px; color: #fff; }
"""

ICONS = {
    'Dashboard': '◉',
    'System': '▣',
    'Performance': '⌁',
    'Optimization': '✦',
    'Processes': '⚡',
    'Gaming': '◈',
    'Game Center': '🕹',
    'Cleanup': '♲',
    'Startup': '↗',
    'Network': '◌',
    'Benchmarks': '◫',
    'Restore Center': '↶',
    'Settings': '⚙',
}

PAGES = {

    'Dashboard': 'Your system condition, current bottlenecks, and smart recommendations.',
    'System': 'Detected hardware, drive media types, and Windows information.',
    'Performance': 'Lightweight live resource monitoring and overhead metrics.',
    'Optimization': 'Review supported safe improvements and hardware-aware profiles.',
    'Processes': 'On-demand background process intelligence and resource impact.',
    'Gaming': 'Gaming session resource mode; zero game-file modification.',
    'Game Center': 'Detect and optimise your installed games.',
    'Cleanup': 'Safe temporary file and cache recovery; personal files excluded.',
    'Startup': 'Startup intelligence with impact ratings and reversibility.',
    'Network': 'Connection diagnostics and throughput without internet booster claims.',
    'Benchmarks': 'System condition baseline and honest before/after verifications.',
    'Restore Center': 'Restore individual optimizations or entire sessions.',
    'Settings': 'Resource budget, background activity mode, and auto-maintenance.',
}



class Card(QFrame):
    def __init__(self, title: str = '', text: str = '') -> None:
        super().__init__()
        self.setObjectName('card')
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 16, 18, 16)
        if title:
            self.header = QLabel(title)
            self.header.setObjectName('muted')
            self.layout.addWidget(self.header)
        self.value = QLabel(text or '—')
        self.value.setObjectName('metric')
        self.layout.addWidget(self.value)
        self.detail = QLabel()
        self.detail.setObjectName('muted')
        self.detail.setWordWrap(True)
        self.layout.addWidget(self.detail)


class CustomScanDialog(QDialog):
    """Custom scan category selection modal (Section 4)."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Custom Scan — Select Categories")
        self.resize(440, 340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        t = QLabel("Select Categories to Analyze")
        t.setObjectName("title")
        layout.addWidget(t)

        self.cb_cpu = QCheckBox("CPU Load & Clock Contention")
        self.cb_cpu.setChecked(True)
        self.cb_ram = QCheckBox("Memory & RAM Pressure")
        self.cb_ram.setChecked(True)
        self.cb_storage = QCheckBox("Storage Partitions & Temporary Files")
        self.cb_storage.setChecked(True)
        self.cb_startup = QCheckBox("Startup Programs & Boot Impact")
        self.cb_startup.setChecked(True)
        self.cb_procs = QCheckBox("Background Process Resource Consumers")
        self.cb_procs.setChecked(True)

        for cb in (self.cb_cpu, self.cb_ram, self.cb_storage, self.cb_startup, self.cb_procs):
            layout.addWidget(cb)

        layout.addStretch()
        box = QDialogButtonBox()
        btn = box.addButton("Start Custom Scan", QDialogButtonBox.AcceptRole)
        btn.setObjectName("accent")
        box.addButton("Cancel", QDialogButtonBox.RejectRole)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def categories(self) -> set[str]:
        cats = set()
        if self.cb_cpu.isChecked(): cats.add("cpu")
        if self.cb_ram.isChecked(): cats.add("ram")
        if self.cb_storage.isChecked(): cats.add("storage")
        if self.cb_startup.isChecked(): cats.add("startup")
        if self.cb_procs.isChecked(): cats.add("processes")
        return cats


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Optima 0.5")
        self.resize(1300, 840)
        self.setMinimumSize(1000, 680)
        self.setStyleSheet(STYLE)

        # Core Engines
        self.monitor = LiveMonitor()
        self.game_detector = GameDetector()
        self.scanner = SystemScanner(self.monitor)
        self.engine = OptimizationEngine()
        self.guard = ResourceGuard(self.game_detector)
        db_path = Path(__file__).resolve().parents[1] / 'database' / 'optima.db'
        self.db = OptimaDatabase(db_path)
        self.process_analyzer = ProcessAnalyzer(self.db.get_ignored_items('process'))
        self.engine.set_ignored_startup(self.db.get_ignored_items('startup'))

        # Load persisted preferences
        self.guard.mode = self.db.get_preference('background_mode', 'Full')
        self.guard.budget = self.db.get_preference('resource_budget', 'Balanced')
        self.game_detector.minimize_setting = self.db.get_preference('minimize_gaming', 'Balanced')
        self.auto_maintenance_mode = self.db.get_preference('auto_maintenance', 'Hourly')

        self.scan_data: dict | None = None
        self.buttons: dict[str, QPushButton] = {}

        # Shell & Navigation
        self.pages = QStackedWidget()
        self.page_names = list(PAGES)
        self.build_shell()
        self.build_pages()
        self.show_page('Dashboard')

        # Live Adaptive Timer (Zero-waste: non-blocking microsecond poll)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_live)
        self.timer.start(3500)

        # Auto-maintenance timer (Safe hourly / daily periodic checks)
        self.maintenance_timer = QTimer(self)
        self.maintenance_timer.timeout.connect(self.run_auto_maintenance)
        self.maintenance_timer.start(3600 * 1000)  # hourly check

        # Initial fast snapshot
        self.refresh_live()

        # Check for existing baseline
        self.update_baseline_display()

    def build_shell(self) -> None:
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Sidebar
        side = QFrame()
        side.setObjectName('sidebar')
        side.setFixedWidth(225)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(16, 20, 16, 16)
        sl.setSpacing(4)

        brand = QLabel("✦  OPTIMA 0.5\nPC CARE")
        brand.setStyleSheet("font-size: 19px; font-weight: 700; color: #fff; line-height: 1.25;")
        brand.setWordWrap(True)
        sl.addWidget(brand)

        tagline = QLabel("Smart & Ultra-Low Resource Engine")
        tagline.setObjectName("muted")
        tagline.setWordWrap(True)
        sl.addWidget(tagline)
        sl.addSpacing(14)

        for name in self.page_names:
            b = QPushButton(f"{ICONS[name]}   {name}")
            b.setObjectName('nav')
            b.setCheckable(True)
            b.clicked.connect(lambda checked=False, n=name: self.show_page(n))
            sl.addWidget(b)
            self.buttons[name] = b

        sl.addStretch()
        self.lbl_status = QLabel("●  Resource Guard: Active\nOptima 0.5")
        self.lbl_status.setObjectName("muted")
        sl.addWidget(self.lbl_status)
        outer.addWidget(side)

        # Content Area
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        top = QFrame()
        top.setObjectName('topbar')
        tl = QHBoxLayout(top)
        tl.setContentsMargins(28, 12, 28, 12)

        self.top_title = QLabel()
        self.top_title.setObjectName('title')
        self.top_desc = QLabel()
        self.top_desc.setObjectName('muted')
        left = QVBoxLayout()
        left.addWidget(self.top_title)
        left.addWidget(self.top_desc)
        tl.addLayout(left)
        tl.addStretch()

        self.global_search = QLineEdit()
        self.global_search.setPlaceholderText("Search Optima settings & pages...")
        self.global_search.setMaximumWidth(280)
        self.global_search.returnPressed.connect(self.search)
        tl.addWidget(self.global_search)

        btn_settings = QPushButton("⚙")
        btn_settings.setToolTip("Open Settings")
        btn_settings.clicked.connect(lambda: self.show_page('Settings'))
        tl.addWidget(btn_settings)

        cl.addWidget(top)
        cl.addWidget(self.pages, 1)
        outer.addWidget(content, 1)
        self.setCentralWidget(root)

    def build_pages(self) -> None:
        self.dashboard = self.dashboard_page()
        self.system = self.system_page()
        self.performance = self.performance_page()
        self.optimization = OptimizationPage(self)
        self.processes = self.processes_page()
        self.gaming = self.gaming_page()
        self.cleanup = self.cleanup_page()
        self.startup = self.startup_page()
        self.network = self.network_page()
        self.benchmarks = self.benchmarks_page()
        self.restore = self.restore_page()
        self.settings = self.settings_page()
        self.game_center = GameCenterPage(self)
        for p in (
            self.dashboard, self.system, self.performance, self.optimization,
            self.processes, self.gaming, self.game_center, self.cleanup, self.startup,
            self.network, self.benchmarks, self.restore, self.settings,
        ):
            self.pages.addWidget(p)

    def page(self, title: str, description: str) -> tuple[QWidget, QVBoxLayout]:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(28, 22, 28, 22)
        l.setSpacing(14)
        return w, l

    def show_page(self, name: str) -> None:
        i = self.page_names.index(name)
        self.pages.setCurrentIndex(i)
        self.top_title.setText(name)
        self.top_desc.setText(PAGES[name])
        for key, b in self.buttons.items():
            b.setChecked(key == name)

        if name == 'Optimization':
            self.optimization.refresh()
        elif name == 'Processes':
            self.refresh_processes()
        elif name == 'Startup':
            self.refresh_startup()
        elif name == 'Cleanup':
            self.refresh_cleanup()
        elif name == 'Restore Center':
            self.refresh_restore()
        elif name == 'Benchmarks':
            self.refresh_benchmarks()

    def toast(self, message: str) -> None:
        self.statusBar().showMessage(message, 5000)

    # =========================================================================
    # Section 23: SMART DASHBOARD
    # =========================================================================
    def dashboard_page(self) -> QWidget:
        w, l = self.page('Dashboard', '')

        # 1. System Condition Hero Card
        hero = QFrame()
        hero.setObjectName('card')
        h = QHBoxLayout(hero)
        h.setContentsMargins(22, 18, 22, 18)

        ring = QVBoxLayout()
        self.score_ring = QProgressBar()
        self.score_ring.setRange(0, 100)
        self.score_ring.setValue(100)
        self.score_ring.setFormat("System Condition  —  %v / 100")
        self.score_ring.setTextVisible(True)
        self.score_ring.setFixedHeight(34)
        ring.addWidget(self.score_ring)

        # Baseline Comparison Subtext (Section 13)
        self.lbl_baseline_diff = QLabel("Baseline: Run a scan to establish comparative baseline.")
        self.lbl_baseline_diff.setObjectName("muted")
        ring.addWidget(self.lbl_baseline_diff)

        scan_row = QHBoxLayout()
        btn_quick = QPushButton("Quick Scan (<1s)")
        btn_quick.clicked.connect(lambda: self.run_scan(mode="quick"))
        btn_full = QPushButton("Full Deep Scan")
        btn_full.setObjectName("accent")
        btn_full.clicked.connect(lambda: self.run_scan(mode="full"))
        btn_custom = QPushButton("Custom Scan...")
        btn_custom.clicked.connect(self.run_custom_scan)
        scan_row.addWidget(btn_quick)
        scan_row.addWidget(btn_full)
        scan_row.addWidget(btn_custom)
        ring.addLayout(scan_row)
        h.addLayout(ring, 2)

        health = QGridLayout()
        self.health: dict[str, Card] = {}
        for i, n in enumerate(('CPU', 'RAM', 'Storage', 'GPU', 'Windows')):
            c = Card(n, 'Ready')
            c.setMinimumWidth(110)
            self.health[n] = c
            health.addWidget(c, i // 3, i % 3)
        h.addLayout(health, 3)
        l.addWidget(hero)

        # 2. Current Bottleneck Card (Section 5)
        self.bottleneck_card = Card("CURRENT BOTTLENECK", "System Resources Balanced")
        self.bottleneck_card.detail.setText(
            "Evidence: CPU and RAM within nominal load. Storage throughput optimal.\nObservation: No primary constraints detected."
        )
        l.addWidget(self.bottleneck_card)

        # 3. Top Recommendations Card with One-Click Smart Optimization (Section 7 & 8)
        self.recommendations_card = QFrame()
        self.recommendations_card.setObjectName('banner')
        rc_layout = QVBoxLayout(self.recommendations_card)
        rc_layout.setContentsMargins(20, 16, 20, 16)

        rec_header = QHBoxLayout()
        rec_title = QLabel("TOP RECOMMENDATIONS & ONE-CLICK OPTIMIZATION")
        rec_title.setObjectName("badge")
        rec_header.addWidget(rec_title)
        rec_header.addStretch()

        self.btn_dashboard_opt = QPushButton("✦  Optimize Recommended Settings")
        self.btn_dashboard_opt.setObjectName("accent")
        self.btn_dashboard_opt.clicked.connect(self.one_click_smart_optimization)
        rec_header.addWidget(self.btn_dashboard_opt)
        rc_layout.addLayout(rec_header)

        self.lbl_rec_summary = QLabel("Scan your PC to generate evidence-based, hardware-aware recommendations.")
        self.lbl_rec_summary.setObjectName("muted")
        self.lbl_rec_summary.setWordWrap(True)
        rc_layout.addWidget(self.lbl_rec_summary)
        l.addWidget(self.recommendations_card)

        # 4. Quick Actions
        qa_label = QLabel("QUICK ACTIONS")
        qa_label.setObjectName("badge")
        l.addWidget(qa_label)

        qgrid = QGridLayout()
        actions = [
            ("Scan PC", "Refresh hardware condition", "scan"),
            ("Optimize PC", "Review safe improvements", "optimization"),
            ("Process Intelligence", "Analyze memory & CPU tasks", "processes"),
            ("Gaming Mode", "Switch to gaming resource mode", "gaming"),
            ("Cleanup Center", "Review safe temporary files", "cleanup"),
            ("Startup Manager", "Review sign-in programs", "startup"),
        ]
        for i, (title, text, action) in enumerate(actions):
            c = QFrame()
            c.setObjectName("quick")
            x = QVBoxLayout(c)
            t = QLabel(title)
            t.setObjectName("quickTitle")
            x.addWidget(t)
            d = QLabel(text)
            d.setObjectName("muted")
            x.addWidget(d)
            b = QPushButton("Open" if action != "scan" else "Quick Scan")
            b.clicked.connect(lambda checked=False, a=action: self.quick_action(a))
            x.addWidget(b)
            qgrid.addWidget(c, i // 3, i % 3)
        l.addLayout(qgrid)

        # 5. Live Performance Snapshot
        snap_label = QLabel("LIVE PERFORMANCE SNAPSHOT")
        snap_label.setObjectName("badge")
        l.addWidget(snap_label)

        pgrid = QGridLayout()
        self.live_cards: dict[str, Card] = {}
        for i, n in enumerate(('CPU', 'RAM', 'Disk', 'Network')):
            c = Card(n + ' usage', '—')
            self.live_cards[n] = c
            pgrid.addWidget(c, 0, i)
        l.addLayout(pgrid)

        # 6. Optima Resource Usage (Section 21)
        self.overhead = Card("OPTIMA SELF-RESOURCE OVERHEAD", "Measuring…")
        self.overhead.detail.setText("Zero-waste engine: Polling is dynamically throttled to ensure Optima consumes minimal CPU and RAM.")
        l.addWidget(self.overhead)

        l.addStretch()
        return w

    def quick_action(self, action: str) -> None:
        if action == "scan":
            self.run_scan(mode="quick")
        else:
            self.show_page(
                {
                    'optimization': 'Optimization',
                    'processes': 'Processes',
                    'gaming': 'Gaming',
                    'cleanup': 'Cleanup',
                    'startup': 'Startup',
                }[action]
            )

    # =========================================================================
    # Section 10: BACKGROUND PROCESS INTELLIGENCE PAGE
    # =========================================================================
    def processes_page(self) -> QWidget:
        w, l = self.page('Processes', '')

        top_ctrl = QHBoxLayout()
        self.proc_search = QLineEdit()
        self.proc_search.setPlaceholderText("Filter processes by name or publisher...")
        self.proc_search.textChanged.connect(self.render_processes)
        top_ctrl.addWidget(self.proc_search, 1)

        self.proc_filter = QComboBox()
        self.proc_filter.addItems(("All Processes", "High CPU", "High RAM", "High Disk", "Ignored"))
        self.proc_filter.currentTextChanged.connect(self.render_processes)
        top_ctrl.addWidget(self.proc_filter)

        btn_refresh = QPushButton("⟳ Refresh Processes")
        btn_refresh.setObjectName("accent")
        btn_refresh.clicked.connect(self.refresh_processes)
        top_ctrl.addWidget(btn_refresh)
        l.addLayout(top_ctrl)

        note = QLabel("Optima analyzes resident resource usage transparently. Optima NEVER terminates processes automatically.")
        note.setObjectName("muted")
        l.addWidget(note)

        self.proc_list_layout = QVBoxLayout()
        box = QWidget()
        box.setLayout(self.proc_list_layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(box)
        l.addWidget(scroll)

        self.cached_processes: list[dict] = []
        return w

    def refresh_processes(self) -> None:
        self.statusBar().showMessage("Analyzing background processes on-demand…")
        QApplication.processEvents()
        startup_items = self.engine.startup_items()
        self.cached_processes = self.process_analyzer.analyze_processes(startup_items=startup_items, limit=60)
        self.render_processes()
        self.toast(f"Analyzed {len(self.cached_processes)} active processes.")

    def render_processes(self) -> None:
        while self.proc_list_layout.count():
            item = self.proc_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        query = self.proc_search.text().lower().strip()
        filt = self.proc_filter.currentText()

        shown = []
        for p in self.cached_processes:
            name_match = (not query) or (query in p['name'].lower()) or (query in p['publisher'].lower())
            if not name_match:
                continue
            if filt == "High CPU" and "High CPU" not in p['tags']:
                continue
            if filt == "High RAM" and "High RAM" not in p['tags']:
                continue
            if filt == "High Disk" and "High Disk" not in p['tags']:
                continue
            if filt == "Ignored" and not p['ignored']:
                continue
            shown.append(p)

        if not shown:
            self.proc_list_layout.addWidget(QLabel("No processes match the current filter."))
            self.proc_list_layout.addStretch()
            return

        for p in shown:
            card = QFrame()
            card.setObjectName("card")
            cl = QHBoxLayout(card)
            cl.setContentsMargins(16, 10, 16, 10)

            info_layout = QVBoxLayout()
            h_row = QHBoxLayout()
            name_lbl = QLabel(f"{p['name']} (PID: {p['pid']})")
            name_lbl.setObjectName("quickTitle")
            h_row.addWidget(name_lbl)

            for tag in p['tags']:
                color = "#eab308" if "High" in tag else "#94a3b8"
                tag_lbl = QLabel(f" {tag} ")
                tag_lbl.setStyleSheet(f"background: #1e293b; color: {color}; border: 1px solid {color}; border-radius: 4px; font-size: 11px; font-weight: bold;")
                h_row.addWidget(tag_lbl)

            if p['starts_with_windows']:
                sw_lbl = QLabel(" Starts at sign-in ")
                sw_lbl.setStyleSheet("background: #27272a; color: #a1a1aa; border-radius: 4px; font-size: 11px;")
                h_row.addWidget(sw_lbl)

            h_row.addStretch()
            info_layout.addLayout(h_row)

            detail_txt = (
                f"Publisher: {p['publisher']}  •  RAM: {p['ram_mb']:.0f} MB  •  CPU: {p['cpu_percent']:.1f}%  •  "
                f"Disk: {p['disk_bps'] / 1024**2:.1f} MB/s\nExplanation: {p['explanation']}"
            )
            detail_lbl = QLabel(detail_txt)
            detail_lbl.setObjectName("muted")
            detail_lbl.setWordWrap(True)
            info_layout.addWidget(detail_lbl)
            cl.addLayout(info_layout, 1)

            btn_ignore = QPushButton("Unignore" if p['ignored'] else "Ignore Process")
            btn_ignore.setFixedWidth(130)
            btn_ignore.clicked.connect(lambda checked=False, pr=p: self.toggle_ignore_process(pr))
            cl.addWidget(btn_ignore)

            self.proc_list_layout.addWidget(card)

        self.proc_list_layout.addStretch()

    def toggle_ignore_process(self, p: dict) -> None:
        name = p['name']
        if p['ignored']:
            self.process_analyzer.unignore_process(name)
            self.db.remove_ignored_item('process', name)
            p['ignored'] = False
            self.toast(f"Removed '{name}' from ignore list.")
        else:
            self.process_analyzer.ignore_process(name)
            self.db.add_ignored_item('process', name)
            p['ignored'] = True
            self.toast(f"Added '{name}' to trusted ignore list.")
        self.render_processes()

    # =========================================================================
    # Section 3: GAMING RESOURCE MODE PAGE
    # =========================================================================
    def gaming_page(self) -> QWidget:
        w, l = self.page('Gaming', '')

        # Game Status Banner
        self.gaming_banner = QFrame()
        self.gaming_banner.setObjectName('banner')
        bl = QVBoxLayout(self.gaming_banner)
        bl.setContentsMargins(20, 16, 20, 16)
        self.lbl_game_title = QLabel("🎮  GAMING RESOURCE MODE")
        self.lbl_game_title.setObjectName("title")
        bl.addWidget(self.lbl_game_title)
        self.lbl_game_status = QLabel("No game currently detected. Optima monitors running processes safely in the background.")
        self.lbl_game_status.setObjectName("muted")
        self.lbl_game_status.setWordWrap(True)
        bl.addWidget(self.lbl_game_status)
        l.addWidget(self.gaming_banner)

        # Principles card
        c_safe = Card("ANTI-CHEAT & SAFETY ASSURANCE", "100% Passive & Anti-Cheat Safe")
        c_safe.detail.setText(
            "Optima strictly observes anti-cheat integrity: It NEVER injects DLLs, never touches game memory or files, and never provides cheats. "
            "Its only action is reducing Optima's own background CPU and disk activity so your PC can dedicate all resources to the game."
        )
        l.addWidget(c_safe)

        # Gaming Setting
        c_set = Card("GAMING BEHAVIOR SETTING", "Minimize Optima During Gaming")
        c_set.detail.setText("Configure how aggressively Optima conserves resources when a game is launched.")
        self.combo_gaming_min = QComboBox()
        self.combo_gaming_min.addItems(("Off", "Balanced", "Maximum Resource Saving"))
        self.combo_gaming_min.setCurrentText(self.game_detector.minimize_setting)
        self.combo_gaming_min.currentTextChanged.connect(self.set_gaming_minimize_mode)
        c_set.layout.addWidget(self.combo_gaming_min)
        l.addWidget(c_set)

        # Live gaming telemetry
        self.gaming_stats = Card("LIVE GAMING RESOURCE LOAD", "Monitoring active")
        l.addWidget(self.gaming_stats)

        l.addStretch()
        return w

    def set_gaming_minimize_mode(self, mode: str) -> None:
        self.game_detector.minimize_setting = mode
        self.db.set_preference('minimize_gaming', mode)
        self.toast(f"Gaming Mode minimization set to: {mode}.")

    # =========================================================================
    # Section 12: SMART CLEANUP PAGE
    # =========================================================================
    def cleanup_page(self) -> QWidget:
        w, l = self.page('Cleanup', '')

        self.cleanup_summary = Card("POTENTIALLY RECLAIMABLE SPACE", "Scan for cleanup")
        self.cleanup_summary.detail.setText(
            "Safely identifies verified temporary files, cache, and Recycle Bin items. Personal documents, downloads, and desktop files are strictly excluded."
        )
        l.addWidget(self.cleanup_summary)

        # Categories list
        self.cleanup_categories_layout = QVBoxLayout()
        box = QWidget()
        box.setLayout(self.cleanup_categories_layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(box)
        l.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_scan = QPushButton("Scan for Cleanup")
        btn_scan.clicked.connect(self.refresh_cleanup)
        self.btn_clean_selected = QPushButton("Clean Selected Categories")
        self.btn_clean_selected.setObjectName("accent")
        self.btn_clean_selected.clicked.connect(self.clean_selected_categories)
        btn_row.addWidget(btn_scan)
        btn_row.addWidget(self.btn_clean_selected)
        l.addLayout(btn_row)

        self.cleanup_entries: list[dict] = []
        self.cleanup_checkboxes: list[tuple[QCheckBox, dict]] = []
        return w

    def refresh_cleanup(self) -> None:
        while self.cleanup_categories_layout.count():
            x = self.cleanup_categories_layout.takeAt(0)
            if x.widget():
                x.widget().deleteLater()

        self.cleanup_entries = self.engine.temporary_locations()
        total_bytes = sum(x['bytes'] for x in self.cleanup_entries)
        self.cleanup_summary.value.setText(gib(total_bytes))
        self.cleanup_summary.detail.setText(
            f"Found {len(self.cleanup_entries)} safe target categories. Select which items to clean."
        )

        self.cleanup_checkboxes.clear()
        for entry in self.cleanup_entries:
            card = QFrame()
            card.setObjectName("card")
            cl = QHBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)

            cb = QCheckBox(f"{entry['label']} — {gib(entry['bytes'])} ({entry.get('count', 0)} items)")
            cb.setChecked(True)
            cb.setStyleSheet("font-weight: 700; color: #fff;")
            cl.addWidget(cb, 1)

            path_lbl = QLabel(str(entry['path']))
            path_lbl.setObjectName("muted")
            cl.addWidget(path_lbl)

            self.cleanup_categories_layout.addWidget(card)
            self.cleanup_checkboxes.append((cb, entry))

        self.cleanup_categories_layout.addStretch()
        self.btn_clean_selected.setEnabled(total_bytes > 0)
        self.toast("Cleanup scan complete.")

    def clean_selected_categories(self) -> None:
        selected = [entry for cb, entry in self.cleanup_checkboxes if cb.isChecked() and entry['bytes'] > 0]
        if not selected:
            QMessageBox.information(self, "Cleanup", "No categories with recoverable files are selected.")
            return

        total_bytes = sum(x['bytes'] for x in selected)
        names = "\n".join(f"• {x['label']} ({gib(x['bytes'])})" for x in selected)
        msg = (
            f"Safely remove approximately {gib(total_bytes)} from the following locations?\n\n"
            f"{names}\n\n"
            f"Personal folders (Documents, Downloads, Desktop, Media) are excluded.\n"
            f"Deleted temporary files cannot be restored."
        )
        if QMessageBox.question(self, "Confirm Safe Cleanup", msg) != QMessageBox.Yes:
            return

        self.perform(
            "cleanup",
            f"{len(selected)} temporary location(s)",
            lambda: self.engine.clean_temporary(selected),
            reversible=False,
        )
        self.refresh_cleanup()

    # =========================================================================
    # Section 11: STARTUP INTELLIGENCE PAGE
    # =========================================================================
    def startup_page(self) -> QWidget:
        w, l = self.page('Startup', '')

        note = QLabel(
            "Optima evaluates startup applications for boot and memory impact. "
            "Disabled items can be restored at any time in the Restore Center. System and driver components are protected."
        )
        note.setObjectName("muted")
        l.addWidget(note)

        self.startup_list_layout = QVBoxLayout()
        box = QWidget()
        box.setLayout(self.startup_list_layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(box)
        l.addWidget(scroll)

        return w

    def refresh_startup(self) -> None:
        while self.startup_list_layout.count():
            x = self.startup_list_layout.takeAt(0)
            if x.widget():
                x.widget().deleteLater()

        items = self.engine.startup_items()
        if not items:
            self.startup_list_layout.addWidget(QLabel("No current-user startup applications found."))
            self.startup_list_layout.addStretch()
            return

        for item in items:
            card = QFrame()
            card.setObjectName("card")
            cl = QHBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)

            vl = QVBoxLayout()
            h = QHBoxLayout()
            title = QLabel(item['name'])
            title.setObjectName("quickTitle")
            h.addWidget(title)

            # Impact badge
            impact = item['impact']
            color = "#ef4444" if impact == "High" else ("#f59e0b" if impact == "Medium" else ("#10b981" if impact == "Low" else "#64748b"))
            impact_lbl = QLabel(f" {impact.upper()} IMPACT ")
            impact_lbl.setStyleSheet(f"background: #1e293b; color: {color}; border: 1px solid {color}; border-radius: 4px; font-size: 11px; font-weight: bold;")
            h.addWidget(impact_lbl)
            h.addStretch()
            vl.addLayout(h)

            desc = (
                f"Publisher: {item['publisher']}  •  Group: {item['group']}\n"
                f"Command: {item['command']}\n{item['recommendation']}"
            )
            lbl_desc = QLabel(desc)
            lbl_desc.setObjectName("muted")
            lbl_desc.setWordWrap(True)
            vl.addWidget(lbl_desc)
            cl.addLayout(vl, 1)

            btn_box = QVBoxLayout()
            btn_disable = QPushButton("Disable at Sign-in")
            btn_disable.setEnabled(item['safe'])
            btn_disable.clicked.connect(lambda checked=False, it=item: self.disable_startup(it))
            btn_box.addWidget(btn_disable)

            btn_ignore = QPushButton("Unignore" if item['ignored'] else "Ignore Item")
            btn_ignore.clicked.connect(lambda checked=False, it=item: self.toggle_ignore_startup(it))
            btn_box.addWidget(btn_ignore)
            cl.addLayout(btn_box)

            self.startup_list_layout.addWidget(card)

        self.startup_list_layout.addStretch()

    def disable_startup(self, item: dict) -> None:
        msg = (
            f"Disable '{item['name']}' from launching at sign-in?\n\n"
            f"This change is 100% reversible in the Restore Center."
        )
        if QMessageBox.question(self, "Confirm Startup Change", msg) == QMessageBox.Yes:
            self.perform("startup", item['name'], lambda: self.engine.disable_startup(item), reversible=True)
            self.refresh_startup()

    def toggle_ignore_startup(self, item: dict) -> None:
        name = item['name']
        if item['ignored']:
            self.engine.ignored_startup.discard(name.lower())
            self.db.remove_ignored_item('startup', name)
            self.toast(f"'{name}' removed from startup ignore list.")
        else:
            self.engine.ignored_startup.add(name.lower())
            self.db.add_ignored_item('startup', name)
            self.toast(f"'{name}' marked as trusted/ignored.")
        self.refresh_startup()

    # =========================================================================
    # Section 16: RESTORE CENTER PAGE
    # =========================================================================
    def restore_page(self) -> QWidget:
        w, l = self.page('Restore Center', '')

        note = QLabel(
            "Every reversible optimization saves its exact prior state before modifying Windows. "
            "Temporary file cleanup is permanent and cannot be restored."
        )
        note.setObjectName("muted")
        l.addWidget(note)

        row = QHBoxLayout()
        row.addStretch()
        self.btn_restore_all = QPushButton("Restore All Available Changes")
        self.btn_restore_all.setObjectName("accent")
        self.btn_restore_all.clicked.connect(self.restore_all)
        row.addWidget(self.btn_restore_all)
        l.addLayout(row)

        self.restore_list_layout = QVBoxLayout()
        box = QWidget()
        box.setLayout(self.restore_list_layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(box)
        l.addWidget(scroll)

        return w

    def refresh_restore(self) -> None:
        while self.restore_list_layout.count():
            x = self.restore_list_layout.takeAt(0)
            if x.widget():
                x.widget().deleteLater()

        actions = self.db.restorable_actions()
        self.btn_restore_all.setEnabled(bool(actions))

        if not actions:
            self.restore_list_layout.addWidget(QLabel("No completed reversible changes available to restore."))
            self.restore_list_layout.addStretch()
            return

        for a in actions:
            card = QFrame()
            card.setObjectName("card")
            cl = QHBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)

            vl = QVBoxLayout()
            title = QLabel(f"Session #{a['optimization_id']} — {a['action_type'].title()} on {a['target']}")
            title.setObjectName("quickTitle")
            vl.addWidget(title)

            desc = f"Applied: {a['time']}\nPrior Value: {a['previous']}\nStatus: Ready to restore"
            lbl_desc = QLabel(desc)
            lbl_desc.setObjectName("muted")
            vl.addWidget(lbl_desc)
            cl.addLayout(vl, 1)

            btn = QPushButton("Restore This Change")
            btn.setObjectName("accent")
            btn.clicked.connect(lambda checked=False, act=a: self.restore_action(act))
            cl.addWidget(btn)

            self.restore_list_layout.addWidget(card)

        self.restore_list_layout.addStretch()

    def restore_action(self, action: dict) -> None:
        if QMessageBox.question(self, "Restore Setting", f"Restore '{action['target']}' to its recorded prior state?") != QMessageBox.Yes:
            return
        try:
            self.engine.restore(action)
            self.db.mark_restored(action['id'])
            self.toast(f"'{action['target']}' restored successfully.")
        except Exception as exc:
            self.info("Restore Failed", f"Could not restore the setting:\n\n{exc}")
        self.refresh_restore()

    def restore_all(self) -> None:
        actions = self.db.restorable_actions()
        if not actions:
            return
        if QMessageBox.question(self, "Restore All Changes", f"Restore {len(actions)} recorded change(s) to their prior state?") != QMessageBox.Yes:
            return
        restored, failed = 0, []
        for a in actions:
            try:
                self.engine.restore(a)
                self.db.mark_restored(a['id'])
                restored += 1
            except Exception as exc:
                failed.append(f"{a['target']}: {exc}")
        self.refresh_restore()
        if failed:
            self.info("Restore Completed with Notices", f"Restored {restored} changes. {len(failed)} items could not be restored:\n\n" + "\n".join(failed))
        else:
            self.info("Restore Complete", f"Successfully restored {restored} change(s) to their original state.")

    # =========================================================================
    # Section 13 & 15: BENCHMARKS & BASELINE PAGE
    # =========================================================================
    def benchmarks_page(self) -> QWidget:
        w, l = self.page('Benchmarks', '')

        self.card_baseline = Card("PERFORMANCE BASELINE", "No baseline established")
        self.card_baseline.detail.setText("Save your current system condition as a baseline to compare future scans honestly.")
        btn_set_base = QPushButton("✦ Set Current Scan as Baseline")
        btn_set_base.setObjectName("accent")
        btn_set_base.clicked.connect(self.set_current_as_baseline)
        self.card_baseline.layout.addWidget(btn_set_base)
        l.addWidget(self.card_baseline)

        # Optimization History List (Section 15)
        h_lbl = QLabel("OPTIMIZATION & MEASUREMENT HISTORY")
        h_lbl.setObjectName("badge")
        l.addWidget(h_lbl)

        self.history_layout = QVBoxLayout()
        box = QWidget()
        box.setLayout(self.history_layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(box)
        l.addWidget(scroll)

        return w

    def refresh_benchmarks(self) -> None:
        self.update_baseline_display()
        while self.history_layout.count():
            x = self.history_layout.takeAt(0)
            if x.widget():
                x.widget().deleteLater()

        records = self.db.get_history(limit=40)
        if not records:
            self.history_layout.addWidget(QLabel("No optimizations recorded yet."))
            self.history_layout.addStretch()
            return

        for r in records:
            card = QFrame()
            card.setObjectName("card")
            cl = QHBoxLayout(card)
            cl.setContentsMargins(16, 10, 16, 10)

            vl = QVBoxLayout()
            t = QLabel(f"#{r['session_id']} — {r['type'].title()} ({r['target']})")
            t.setObjectName("quickTitle")
            vl.addWidget(t)

            d = f"Time: {r['time']}  •  Status: {r['status']}  •  Reversible: {'Yes' if r['reversible'] else 'No'}\nPrior: {r['previous']} → New: {r['new']}"
            dl = QLabel(d)
            dl.setObjectName("muted")
            vl.addWidget(dl)
            cl.addLayout(vl)

            self.history_layout.addWidget(card)

        self.history_layout.addStretch()

    def set_current_as_baseline(self) -> None:
        if not self.scan_data:
            self.run_scan(mode="quick")
        if self.scan_data:
            live = self.scan_data.get('live', {})
            ram = self.scan_data.get('ram', {})
            storage = sum(d.get('free', 0) for d in self.scan_data.get('storage', []))
            score = self.scan_data.get('score', 100)
            self.db.save_baseline(live.get('cpu', 0), ram.get('percent', 0), storage, score)
            self.toast("Saved current metrics as permanent baseline.")
            self.update_baseline_display()

    def update_baseline_display(self) -> None:
        base = self.db.get_baseline()
        if base:
            self.card_baseline.value.setText(f"Score: {base['score']}/100  •  CPU: {base['cpu']:.0f}%  •  RAM: {base['ram']:.0f}%")
            self.card_baseline.detail.setText(f"Established: {base['created_at']}\nFree Storage: {gib(base['free_storage'])}")

            if self.scan_data:
                cur_score = self.scan_data.get('score', 100)
                cur_cpu = self.scan_data.get('live', {}).get('cpu', 0)
                cur_ram = self.scan_data.get('ram', {}).get('percent', 0)
                score_diff = cur_score - base['score']
                score_sign = f"+{score_diff}" if score_diff > 0 else f"{score_diff}"
                self.lbl_baseline_diff.setText(
                    f"Compared with baseline: Score {cur_score} ({score_sign})  •  CPU {cur_cpu:.0f}% (was {base['cpu']:.0f}%)  •  RAM {cur_ram:.0f}% (was {base['ram']:.0f}%)"
                )
        else:
            prev = self.db.get_previous_scan()
            if prev and self.scan_data:
                cur_score = self.scan_data.get('score', 100)
                cur_cpu = self.scan_data.get('live', {}).get('cpu', 0)
                cur_ram = self.scan_data.get('ram', {}).get('percent', 0)
                self.lbl_baseline_diff.setText(
                    f"Compared with previous scan: Score {cur_score} (was {prev['score']})  •  CPU {cur_cpu:.0f}% (was {prev['cpu']:.0f}%)  •  RAM {cur_ram:.0f}% (was {prev['ram']:.0f}%)"
                )

    # =========================================================================
    # Sections 18, 19, 20: SETTINGS PAGE
    # =========================================================================
    def settings_page(self) -> QWidget:
        w, l = self.page('Settings', '')

        # Safety & Privacy
        c_priv = Card("SAFETY & PRIVACY GUARANTEE", "Local, Transparent & Explicit")
        c_priv.detail.setText(
            "Optima operates entirely locally without telemetry. It excludes registry cleaners, Windows service modification, "
            "overclocking, firmware flashing, and anti-cheat interference."
        )
        l.addWidget(c_priv)

        # Background Activity Mode (Section 18)
        c_mode = Card("OPTIMA BACKGROUND MODE", self.guard.mode)
        c_mode.detail.setText(
            "• Full: Normal monitoring when window is open.\n"
            "• Light: Reduced background activity.\n"
            "• Minimal: Only essential system telemetry.\n"
            "• Paused: Halts background monitoring when Optima is minimized or unfocused."
        )
        self.combo_bg = QComboBox()
        self.combo_bg.addItems(('Full', 'Light', 'Minimal', 'Paused'))
        self.combo_bg.setCurrentText(self.guard.mode)
        self.combo_bg.currentTextChanged.connect(self.set_background_mode)
        c_mode.layout.addWidget(self.combo_bg)
        l.addWidget(c_mode)

        # Resource Budget (Section 19)
        c_budget = Card("OPTIMA RESOURCE BUDGET", self.guard.budget)
        c_budget.detail.setText(
            "• Lowest Resource Usage: Prioritizes host PC performance over live detail; throttles timers.\n"
            "• Balanced: Balances responsive graphs with near-zero CPU usage.\n"
            "• Maximum Monitoring: More frequent updates when viewing Performance."
        )
        self.combo_budget = QComboBox()
        self.combo_budget.addItems(('Lowest Resource Usage', 'Balanced', 'Maximum Monitoring'))
        self.combo_budget.setCurrentText(self.guard.budget)
        self.combo_budget.currentTextChanged.connect(self.set_resource_budget)
        c_budget.layout.addWidget(self.combo_budget)
        l.addWidget(c_budget)

        # Smart Auto-Maintenance (Section 20)
        c_maint = Card("SMART AUTO-MAINTENANCE", self.auto_maintenance_mode)
        c_maint.detail.setText(
            "Runs safe read-only checks periodically (storage capacity, new startup apps). Never modifies system settings without explicit confirmation."
        )
        self.combo_maint = QComboBox()
        self.combo_maint.addItems(('Hourly', 'Daily', 'Disabled'))
        self.combo_maint.setCurrentText(self.auto_maintenance_mode)
        self.combo_maint.currentTextChanged.connect(self.set_auto_maintenance)
        c_maint.layout.addWidget(self.combo_maint)
        l.addWidget(c_maint)

        # Database Pruning & Hardware Cache Clear
        btn_row = QHBoxLayout()
        btn_prune = QPushButton("Prune Old Scan History")
        btn_prune.clicked.connect(self.prune_database)
        btn_clear_hw = QPushButton("Clear Hardware Discovery Cache")
        btn_clear_hw.clicked.connect(self.clear_hw_cache)
        btn_row.addWidget(btn_prune)
        btn_row.addWidget(btn_clear_hw)
        l.addLayout(btn_row)

        l.addStretch()
        return w

    def set_background_mode(self, mode: str) -> None:
        self.guard.mode = mode
        self.db.set_preference('background_mode', mode)
        self.toast(f"Background Mode updated to: {mode}")

    def set_resource_budget(self, budget: str) -> None:
        self.guard.budget = budget
        self.db.set_preference('resource_budget', budget)
        self.toast(f"Resource Budget updated to: {budget}")

    def set_auto_maintenance(self, mode: str) -> None:
        self.auto_maintenance_mode = mode
        self.db.set_preference('auto_maintenance', mode)
        self.toast(f"Auto-maintenance set to: {mode}")

    def prune_database(self) -> None:
        self.db.prune_history(keep_scans=30, keep_optimizations=30)
        self.toast("Database pruned to retain the 30 most recent records.")

    def clear_hw_cache(self) -> None:
        clear_hardware_cache()
        self.toast("Hardware discovery cache cleared. Next scan will query devices.")

    # =========================================================================
    # Other Pages: System, Performance, Network
    # =========================================================================
    def system_page(self) -> QWidget:
        w, l = self.page('System', '')
        self.system_text = QLabel("Run a Quick or Full Scan to display detected hardware.")
        self.system_text.setWordWrap(True)
        self.system_text.setTextFormat(Qt.RichText)
        c = Card("DETECTED SYSTEM")
        c.layout.addWidget(self.system_text)
        l.addWidget(c)
        l.addStretch()
        return w

    def performance_page(self) -> QWidget:
        w, l = self.page('Performance', '')
        g = QGridLayout()
        self.perf_cards: dict[str, Card] = {}
        for i, n in enumerate(('CPU', 'RAM', 'Disk read', 'Disk write', 'Network', 'GPU')):
            c = Card(n)
            self.perf_cards[n] = c
            g.addWidget(c, i // 3, i % 3)
        l.addLayout(g)

        # Section 21: Dedicated Overhead Section
        self.perf_overhead = Card("OPTIMA SELF-OVERHEAD", "Measuring…")
        l.addWidget(self.perf_overhead)

        note = QLabel(
            "Adaptive monitoring: Polling frequency dynamically accelerates when you view Performance and throttles when minimized or gaming."
        )
        note.setObjectName("muted")
        l.addWidget(note)
        l.addStretch()
        return w

    def network_page(self) -> QWidget:
        w, l = self.page('Network', '')
        c = Card("NETWORK DIAGNOSTICS", "Monitoring active")
        c.detail.setText(
            "Displays active network throughput via the non-blocking monitor. DNS flushing and adapter tweaks are detection-only to avoid unsafe internet booster claims."
        )
        l.addWidget(c)
        l.addStretch()
        return w

    # =========================================================================
    # Live Adaptive Loop & Game Detection
    # =========================================================================
    def refresh_live(self) -> None:
        d = self.monitor.snapshot()
        is_idle = self.monitor.is_pc_idle(60.0)

        values = {
            'CPU': f"{d['cpu']:.0f}%",
            'RAM': f"{d['ram']:.0f}%",
            'Disk': f"{gib(d['disk_read'] + d['disk_write'])}/s",
            'Network': f"{gib(d['network'])}/s",
        }
        for k, v in values.items():
            if k in self.live_cards:
                self.live_cards[k].value.setText(v)

        for k, v in {
            'CPU': values['CPU'],
            'RAM': values['RAM'],
            'Disk read': f"{gib(d['disk_read'])}/s",
            'Disk write': f"{gib(d['disk_write'])}/s",
            'Network': values['Network'],
            'GPU': 'Information unavailable',
        }.items():
            if k in self.perf_cards:
                self.perf_cards[k].value.setText(v)

        # Sampling Optima's self overhead
        active_page = self.top_title.text() or 'Dashboard'
        overhead = self.guard.sample(self.isMinimized(), active_page, d['cpu'], is_idle=is_idle)

        self.overhead.value.setText(f"CPU {overhead['cpu']:.1f}%  •  RAM {overhead['ram_mb']:.0f} MB")
        self.overhead.detail.setText(f"Disk: {overhead['disk_bps'] / 1024:.1f} KB/s  •  Background Activity: {overhead['background']}")
        if hasattr(self, 'perf_overhead'):
            self.perf_overhead.value.setText(f"Optima CPU: {overhead['cpu']:.1f}%  •  RAM: {overhead['ram_mb']:.0f} MB")
            self.perf_overhead.detail.setText(f"Disk I/O: {overhead['disk_bps'] / 1024:.1f} KB/s  •  State: {overhead['background']}")

        # Gaming detection handling
        if overhead.get('is_gaming'):
            game_name = overhead.get('game_name') or "Game"
            self.lbl_game_title.setText(f"🎮  GAMING RESOURCE MODE — {game_name}")
            self.lbl_game_status.setText(f"Active game '{game_name}' detected. Optima background work and database writes are throttled.")
            self.gaming_stats.value.setText(f"CPU {values['CPU']}  •  RAM {values['RAM']}  •  Disk {values['Disk']}")

            if self.game_detector.minimize_setting == "Maximum Resource Saving" and not self.isMinimized():
                self.showMinimized()
        else:
            self.lbl_game_title.setText("🎮  GAMING RESOURCE MODE")
            self.lbl_game_status.setText("No game currently detected. Ready to activate when a supported game launches.")
            self.gaming_stats.value.setText(f"CPU {values['CPU']}  •  RAM {values['RAM']}  •  Disk {values['Disk']}")

        # Adjust interval adaptively
        target_interval = self.guard.interval_ms(self.isMinimized(), active_page, d['cpu'], is_idle=is_idle)
        if self.timer.interval() != target_interval:
            self.timer.setInterval(target_interval)

    # =========================================================================
    # Scanning Workflows (Quick, Full, Custom)
    # =========================================================================
    def run_scan(self, mode: str = "quick", categories: set[str] | None = None) -> None:
        self.show_page('Dashboard')
        self.statusBar().showMessage(f"Running {mode.title()} scan…")
        QApplication.processEvents()

        try:
            startup_items = self.engine.startup_items()
            top_procs = self.process_analyzer.analyze_processes(startup_items=startup_items, limit=5)

            self.scan_data = self.scanner.scan(
                mode=mode,
                custom_categories=categories,
                startup_count=len([s for s in startup_items if s['safe']]),
                heavy_procs=top_procs,
            )

            score = self.scan_data['score']
            bottleneck: BottleneckAnalysis = self.scan_data['bottleneck']
            self.db.save_scan(self.scan_data, score, bottleneck.issues)

            # Update UI
            self.score_ring.setValue(score)
            self.health['CPU'].value.setText('Healthy' if self.scan_data['live']['cpu'] < 70 else 'Elevated')
            self.health['RAM'].value.setText('Healthy' if self.scan_data['ram']['percent'] < 70 else 'High pressure')
            self.health['Storage'].value.setText(f"{len(self.scan_data['storage'])} drive(s)")
            self.health['GPU'].value.setText(self.scan_data['gpu']['name'] if self.scan_data['gpu']['name'] != 'Unavailable' else 'Unavailable')
            self.health['Windows'].value.setText('Detected')

            # Bottleneck card
            self.bottleneck_card.value.setText(bottleneck.headline)
            notes_str = ("\nHardware note: " + " ".join(bottleneck.hardware_notes)) if bottleneck.hardware_notes else ""
            self.bottleneck_card.detail.setText(
                f"Metric: {bottleneck.current_metric}\nObservation: {bottleneck.observation}\nRecommendation: {bottleneck.recommendation}{notes_str}"
            )

            # Recommendations
            recs = self.engine.recommendations(self.scan_data)
            rec_titles = [f"• {r.title} [{r.priority}]" for r in recs[:3]]
            self.lbl_rec_summary.setText("\n".join(rec_titles) if rec_titles else "No immediate recommendations; PC is well optimized.")

            self.update_system_text()
            self.update_baseline_display()
            self.toast(f"{mode.title()} scan complete. Score: {score}/100. {len(recs)} recommendation(s) found.")
            self.show_scan_result_dialog(score, bottleneck)

        except Exception as exc:
            self.info("Scan Error", f"Optima could not complete the scan:\n\n{exc}")

    def run_custom_scan(self) -> None:
        dlg = CustomScanDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.run_scan(mode="custom", categories=dlg.categories())

    def update_system_text(self) -> None:
        if not self.scan_data:
            return
        d = self.scan_data
        c, r, g = d['cpu'], d['ram'], d['gpu']
        dr = '<br>'.join(f"{x['mount']} — {gib(x['free'])} free of {gib(x['total'])} ({x['kind']})" for x in d['storage']) or 'Unavailable'
        self.system_text.setText(
            f"<b>Operating System:</b> {d['os']['name']} ({d['os']['architecture']})<br><br>"
            f"<b>Processor (CPU):</b> {c['name']}<br>"
            f"Cores: {c['physical_cores']} Physical / {c['logical_processors']} Logical Processors<br><br>"
            f"<b>System Memory (RAM):</b> {gib(r['total'])} Total, {gib(r['available'])} Available ({r['percent']}%)<br><br>"
            f"<b>Graphics (GPU):</b> {g['name']} — VRAM: {g['vram']}<br><br>"
            f"<b>Storage Partitions:</b><br>{dr}"
        )

    def show_scan_result_dialog(self, score: int, bottleneck: BottleneckAnalysis) -> None:
        d = QDialog(self)
        d.setWindowTitle("Scan Complete")
        l = QVBoxLayout(d)
        l.setContentsMargins(24, 20, 24, 20)
        l.setSpacing(12)

        t = QLabel("Scan Complete")
        t.setObjectName("title")
        l.addWidget(t)

        msg = (
            f"System Condition Score: {score} / 100\n\n"
            f"Primary Constraint: {bottleneck.headline}\n"
            f"Observation: {bottleneck.observation}\n"
            f"Action: {bottleneck.recommendation}\n\n"
            f"Review the recommendations below before applying any changes."
        )
        lbl = QLabel(msg)
        lbl.setWordWrap(True)
        l.addWidget(lbl)

        box = QDialogButtonBox()
        btn_rev = box.addButton("Review Recommendations", QDialogButtonBox.AcceptRole)
        btn_rev.setObjectName("accent")
        btn_close = box.addButton("Close", QDialogButtonBox.RejectRole)
        btn_rev.clicked.connect(lambda: (d.accept(), self.show_page('Optimization')))
        btn_close.clicked.connect(d.reject)
        l.addWidget(box)
        d.exec()

    # =========================================================================
    # Section 8: ONE-CLICK SMART OPTIMIZATION FLOW
    # =========================================================================
    def one_click_smart_optimization(self) -> None:
        """One-click smart optimization with explicit preview modal (Section 8)."""
        recommended_settings = [s for s in SETTINGS if s.priority == "Recommended" and s.action]
        if not recommended_settings:
            QMessageBox.information(self, "Optimization", "System condition is healthy. No urgent optimizations are currently recommended.")
            return

        dlg = ReviewDialog(recommended_settings, self)
        if dlg.exec() == QDialog.Accepted:
            chosen = dlg.get_selected()
            if not chosen:
                return

            ident = self.db.start_optimization('SMART_RECOMMENDED')
            before = self.engine.snapshot()
            self.toast("Applying chosen optimizations safely…")
            QApplication.processEvents()

            results_log = []
            for s in chosen:
                try:
                    if s.action == 'startup':
                        startup_items = [it for it in self.engine.startup_items() if it['safe'] and it['impact'] in ('High', 'Medium')]
                        for item in startup_items[:2]:
                            res = self.engine.disable_startup(item)
                            self.db.record_action(ident, 'startup', item['name'], res['previous'], res['new'], 'APPLIED', True, res.get('backup'))
                            results_log.append(f"Disabled startup item '{item['name']}'")
                    elif s.action == 'cleanup':
                        res = self.engine.clean_temporary()
                        self.db.record_action(ident, 'cleanup', 'temporary locations', res['previous'], res['new'], 'APPLIED', False, res.get('backup'))
                        results_log.append(f"Cleaned temporary data ({res['new']})")
                    elif s.action == 'visual':
                        res = self.engine.set_visual_performance()
                        self.db.record_action(ident, 'visual', 'client area animation', res['previous'], res['new'], 'APPLIED', True, res.get('backup'))
                        results_log.append("Reduced client-area window animations")
                    elif s.action == 'power':
                        res = self.engine.set_high_performance()
                        self.db.record_action(ident, 'power', 'active power plan', res['previous'], res['new'], 'APPLIED', True, res.get('backup'))
                        results_log.append("Configured High performance power plan")
                except Exception as exc:
                    self.db.record_action(ident, s.action or 'unknown', s.name, '', '', 'FAILED', False, {}, str(exc))

            after = self.engine.snapshot()
            self.db.record_benchmarks(ident, before, after)
            self.db.finish_optimization(ident, 'APPLIED')

            # Honest Before/After Verification (Section 14)
            verification = self.engine.verify_measurement(before, after)
            self.show_verification_dialog(verification, results_log)
            self.toast("Smart optimizations completed.")
            self.refresh_live()

    def show_verification_dialog(self, verification: dict, applied_list: list[str]) -> None:
        d = QDialog(self)
        d.setWindowTitle("Optimization Results & Verification")
        l = QVBoxLayout(d)
        l.setContentsMargins(24, 20, 24, 20)
        l.setSpacing(12)

        t = QLabel("Optimization Summary")
        t.setObjectName("title")
        l.addWidget(t)

        applied_str = "\n".join(f"✓  {a}" for a in applied_list) if applied_list else "No actions executed."
        lbl_actions = QLabel(f"Applied Changes:\n{applied_str}")
        lbl_actions.setObjectName("muted")
        l.addWidget(lbl_actions)

        # Honest assessment
        status_box = QFrame()
        status_box.setObjectName("card")
        sbl = QVBoxLayout(status_box)
        sbl.setContentsMargins(14, 12, 14, 12)

        v_head = QLabel(f"Verification: {verification['summary']}")
        v_head.setObjectName("quickTitle")
        sbl.addWidget(v_head)

        v_det = QLabel(verification['details'])
        v_det.setObjectName("muted")
        v_det.setWordWrap(True)
        sbl.addWidget(v_det)

        v_note = QLabel("Note: Optima reports factual measurable changes and does not claim synthetic FPS multipliers.")
        v_note.setStyleSheet("color: #64748b; font-size: 11px;")
        sbl.addWidget(v_note)

        l.addWidget(status_box)

        box = QDialogButtonBox()
        btn = box.addButton("Done", QDialogButtonBox.AcceptRole)
        btn.setObjectName("accent")
        btn.clicked.connect(d.accept)
        l.addWidget(box)
        d.exec()

    def apply(self, r: Recommendation) -> None:
        if r.key == 'startup':
            self.show_page('Startup')
        elif r.key == 'cleanup':
            self.show_page('Cleanup')
        elif r.key == 'visual':
            if QMessageBox.question(self, "Confirm Visual Change", "Reduce client-area window animations? This is 100% reversible in Restore Center.") == QMessageBox.Yes:
                self.perform('visual', 'client area animation', self.engine.set_visual_performance, True)
        elif r.key == 'power':
            if QMessageBox.question(self, "Confirm Power Plan", "Switch to Windows High performance power plan? Your prior plan will be preserved and can be restored.") == QMessageBox.Yes:
                self.perform('power', 'active power plan', self.engine.set_high_performance, True)

    def perform(self, typ: str, target: str, op, reversible: bool) -> None:
        ident = self.db.start_optimization('SAFE')
        before = self.engine.snapshot()
        self.toast(f"Applying: {typ}…")
        QApplication.processEvents()

        try:
            result = op()
            fails = result.get('failures', [])
            status = 'APPLIED' if not fails else 'PARTIAL'
            self.db.record_action(
                ident, typ, target, result.get('previous', ''), result.get('new', ''),
                status, reversible, result.get('backup'), '; '.join(fails) if fails else None,
            )
            after = self.engine.snapshot()
            self.db.record_benchmarks(ident, before, after)
            self.db.finish_optimization(ident, status)

            verification = self.engine.verify_measurement(before, after)
            self.info(
                "Optimization Complete",
                f"{typ.title()} operation completed.\n\n"
                f"{verification['summary']}\n{verification['details']}\n\n"
                f"{('Reversible in Restore Center.' if reversible else 'Action is permanent.')}",
            )
            self.toast("Optimization completed successfully.")
        except Exception as exc:
            self.db.record_action(ident, typ, target, '', '', 'FAILED', reversible, {}, str(exc))
            self.db.finish_optimization(ident, 'FAILED')
            self.info("Action Failed", f"Optima could not apply the setting:\n\n{exc}")

    def run_auto_maintenance(self) -> None:
        """Section 20: Safe, optional periodic maintenance check."""
        if self.auto_maintenance_mode == "Disabled":
            return
        try:
            # Check storage
            temp_locs = self.engine.temporary_locations()
            total_temp = sum(x['bytes'] for x in temp_locs)
            if total_temp >= 2 * 1024**3:
                self.toast(f"Auto-maintenance notice: Approximately {gib(total_temp)} of safe recoverable files detected.")
        except Exception:
            pass

    def search(self) -> None:
        term = self.global_search.text().lower().strip()
        matches = [n for n in self.page_names if term and term in (n + ' ' + PAGES[n]).lower()]
        if matches:
            self.show_page(matches[0])
            self.toast(f"Opened {matches[0]}.")
        else:
            self.show_page('Optimization')
            self.optimization.search.setText(term)
            self.toast("Showing matching optimization settings.")

    def info(self, title: str, text: str) -> None:
        QMessageBox.information(self, title, text)
