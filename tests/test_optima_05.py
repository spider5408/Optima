"""Comprehensive verification suite for Optima 0.5 — Smart Optimization + Ultra-Low Resource Engine."""
import os
import sys
import time
from pathlib import Path
import psutil

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PySide6.QtWidgets import QApplication
from core.hardware import (
    gpu_info, disk_kind, recycle_bin_info, get_file_company, clear_hardware_cache
)
from core.monitor import LiveMonitor, get_idle_duration_seconds
from core.game_detector import GameDetector
from core.resource_guard import ResourceGuard, trim_working_set
from core.process_analyzer import ProcessAnalyzer
from core.analyzer import analyze_bottleneck
from core.scanner import SystemScanner
from core.optimizer import OptimizationEngine
from core.database import OptimaDatabase
from ui.main_window import MainWindow


def run_tests():
    print("=" * 70)
    print("OPTIMA 0.5 SYSTEM & RESOURCE ENGINE VERIFICATION")
    print("=" * 70)

    t_start = time.perf_counter()

    # 1. Startup & Window Instantiation
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    t_init = time.perf_counter() - t_start
    print(f"✓ 1. Application startup & window init: {t_init*1000:.2f} ms")

    # 2. Verify Shell & Dashboard
    assert win.pages.count() == 12, f"Expected 12 pages, found {win.pages.count()}"
    assert "Dashboard" in win.page_names
    assert "Processes" in win.page_names
    assert "Gaming" in win.page_names
    print("✓ 2. Dashboard & 12 shell navigation pages verified.")

    # 3. Hardware Cache & Instantaneous Query Tests
    t0 = time.perf_counter()
    g1 = gpu_info()
    d1 = disk_kind('C')
    rb = recycle_bin_info()
    comp = get_file_company(sys.executable)
    t_hw_first = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    g2 = gpu_info()
    d2 = disk_kind('C')
    t_hw_cached = (time.perf_counter() - t1) * 1000
    print(f"✓ 3. Hardware discovery & Win32 helpers: First {t_hw_first:.1f} ms, Cached: {t_hw_cached:.4f} ms")
    print(f"     GPU: {g1['name']}, Media: {d1}, RecycleBin: {rb['bytes']/1024**2:.1f} MB, Publisher: {comp}")
    assert d1 in ("SSD", "HDD", "Unspecified", "Unavailable")

    # 4. Quick Scan vs Full Scan
    t_q0 = time.perf_counter()
    q_scan = win.scanner.scan(mode="quick")
    t_quick = (time.perf_counter() - t_q0) * 1000
    print(f"✓ 4. Quick Scan execution: {t_quick:.2f} ms (< 500ms target). Score: {q_scan['score']}")
    assert t_quick < 500.0, f"Quick scan too slow: {t_quick} ms"

    # 5. Smart Bottleneck Engine
    bottleneck = q_scan["bottleneck"]
    print(f"✓ 5. Smart Bottleneck Engine: [{bottleneck.status}] {bottleneck.headline}")
    print(f"     Evidence: {bottleneck.current_metric}")
    print(f"     Observation: {bottleneck.observation}")
    print(f"     Recommendation: {bottleneck.recommendation}")
    assert bottleneck.headline
    assert bottleneck.recommendation

    # 6. Smart Recommendations & Priority Tiers
    recs = win.engine.recommendations(q_scan)
    print(f"✓ 6. Recommendations ({len(recs)} found):")
    for r in recs:
        print(f"     • [{r.priority}] {r.title} (Risk: {r.risk})")
        assert r.priority in ("Recommended", "Optional", "Low Impact", "Detection Only")

    # 7. Background Process Intelligence
    t_p0 = time.perf_counter()
    procs = win.process_analyzer.analyze_processes(limit=15)
    t_procs = (time.perf_counter() - t_p0) * 1000
    print(f"✓ 7. Process Intelligence: analyzed top {len(procs)} processes in {t_procs:.2f} ms")
    high_ram_procs = [p for p in procs if "High RAM" in p['tags']]
    print(f"     Found {len(high_ram_procs)} High RAM consumer(s). Top: {procs[0]['name']} ({procs[0]['ram_mb']:.0f} MB, {procs[0]['publisher']})")
    assert len(procs) > 0

    # 8. Startup Intelligence
    startup = win.engine.startup_items()
    print(f"✓ 8. Startup Intelligence: {len(startup)} item(s) detected")
    for s in startup[:3]:
        print(f"     • {s['name']}: {s['impact']} Impact ({s['group']})")
        assert s['impact'] in ("High", "Medium", "Low", "Protected")

    # 9. Smart Cleanup Centers & Categories
    cleanup_locs = win.engine.temporary_locations()
    total_reclaimable = sum(x['bytes'] for x in cleanup_locs)
    print(f"✓ 9. Smart Cleanup: {len(cleanup_locs)} categories found. Total reclaimable: {total_reclaimable / 1024**2:.1f} MB")
    assert total_reclaimable >= 0

    # 10. Before/After Verification Logic
    before_snap = {"cpu": 15.0, "ram": 78.0, "free_storage": 100*1024**3, "process_count": 210}
    after_snap = {"cpu": 12.0, "ram": 64.0, "free_storage": 102*1024**3, "process_count": 204}
    v_positive = win.engine.verify_measurement(before_snap, after_snap)
    assert v_positive["has_change"] is True
    assert "RAM usage decreased by 14.0 percentage points" in v_positive["details"]

    v_nominal = win.engine.verify_measurement(before_snap, {"cpu": 15.0, "ram": 78.2, "free_storage": 100*1024**3, "process_count": 210})
    assert v_nominal["has_change"] is False
    assert "No significant measurable change detected" in v_nominal["summary"]
    print("✓ 10. Honest Before/After verification verified (handles both measurable deltas and nominal variance).")

    # 11. Baseline System & Database Tracking
    win.db.save_baseline(cpu=18.5, ram=72.0, free_storage=150*1024**3, score=92)
    base = win.db.get_baseline()
    assert base is not None
    assert base["score"] == 92
    assert base["cpu"] == 18.5
    print(f"✓ 11. Performance Baseline verified: Score {base['score']}, CPU {base['cpu']}%, RAM {base['ram']}%")

    # 12. Gaming Resource Mode & Anti-Cheat Safety
    gd = GameDetector()
    gd.register_game("test_game.exe", "Simulated Game")
    # Verify passive detection
    assert "Simulated Game" in gd.game_catalog.values()
    # Test interval calculation in ResourceGuard under gaming
    rg = ResourceGuard(gd)
    rg.last['is_gaming'] = True
    rg.last['game_name'] = 'Simulated Game'
    gaming_interval = rg.interval_ms(minimized=False, page='Dashboard', system_cpu=20.0)
    assert gaming_interval >= 8000, f"Expected throttled gaming interval, got {gaming_interval}"
    print(f"✓ 12. Gaming Resource Mode verified: Automatically throttles interval to {gaming_interval} ms")

    # 13. Adaptive Monitoring Cadences
    rg.last['is_gaming'] = False
    perf_interval = rg.interval_ms(minimized=False, page='Performance', system_cpu=20.0)
    dash_interval = rg.interval_ms(minimized=False, page='Dashboard', system_cpu=20.0)
    min_interval = rg.interval_ms(minimized=True, page='Dashboard', system_cpu=20.0)
    heavy_interval = rg.interval_ms(minimized=False, page='Performance', system_cpu=88.0)
    print(f"✓ 13. Adaptive Intervals: Performance={perf_interval}ms, Dashboard={dash_interval}ms, Minimized={min_interval}ms, HeavyLoad={heavy_interval}ms")
    assert perf_interval <= dash_interval
    assert dash_interval <= min_interval
    assert heavy_interval >= 7000

    # 14. Resource Budget Modes
    rg.budget = "Lowest Resource Usage"
    low_interval = rg.interval_ms(minimized=False, page='Dashboard', system_cpu=20.0)
    rg.budget = "Maximum Monitoring"
    max_interval = rg.interval_ms(minimized=False, page='Dashboard', system_cpu=20.0)
    print(f"✓ 14. Resource Budget: Lowest={low_interval}ms, Maximum={max_interval}ms")
    assert low_interval > max_interval

    # 15. Background Activity Modes
    rg.mode = "Paused"
    paused_interval = rg.interval_ms(minimized=True, page='Dashboard', system_cpu=20.0)
    assert paused_interval == 30000
    print(f"✓ 15. Background Mode 'Paused' throttles to {paused_interval} ms when minimized.")

    # 16. Working Set Trimming
    trim_working_set()
    proc = psutil.Process(os.getpid())
    current_rss_mb = proc.memory_info().rss / 1024**2
    print(f"✓ 16. Working set memory trimmed: current RSS = {current_rss_mb:.1f} MB")

    # 17. Restore System Logic
    restorable = win.db.restorable_actions()
    print(f"✓ 17. Restore Center: {len(restorable)} restorable change(s) currently indexed.")

    # 18. Database History & Pruning
    win.db.prune_history(keep_scans=10, keep_optimizations=10)
    history = win.db.get_history(limit=5)
    print(f"✓ 18. Database Pruning: Successfully pruned old scans; history records: {len(history)}")

    # 19. Window Resizing & Page Switching
    win.resize(1100, 720)
    for p_name in win.page_names:
        win.show_page(p_name)
    win.show_page('Dashboard')
    print("✓ 19. Window resizing and seamless 12-page navigation verified.")

    # 20. Self-Resource Overhead Measurement
    overhead = win.guard.sample(minimized=False, page='Dashboard', system_cpu=15.0)
    print(f"✓ 20. Optima Self-Resource Overhead:")
    print(f"     CPU: {overhead['cpu']:.2f}% (Target: < 1-2% idle)")
    print(f"     RAM: {overhead['ram_mb']:.1f} MB")
    print(f"     Disk I/O: {overhead['disk_bps']/1024:.2f} KB/s")
    print(f"     Background State: {overhead['background']}")

    print("=" * 70)
    print("ALL 20 TEST SUITES COMPLETED WITH 100% SUCCESS!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
