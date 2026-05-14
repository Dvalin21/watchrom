"""
core/pipeline.py — Pipeline and task graph system

Turns procedural scripts into composable, resumable, auditable workflows.

Usage:
    pipeline = Pipeline("root-device")
    pipeline.run(device, context={})

    # Or from CLI:
    watchrom pipeline root-device
    watchrom pipeline flash-rom --parts-dir ./dumps/
    watchrom pipeline wearos-setup
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional, Any
import time
import json
import traceback
from core.interfaces import Result, Status, DeviceInfo


# ── Task state ────────────────────────────────────────────────────────────────

class TaskStatus(Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"
    SKIPPED  = "skipped"


@dataclass
class TaskRecord:
    name:      str
    status:    TaskStatus = TaskStatus.PENDING
    result:    Optional[Result] = None
    started:   float = 0.0
    finished:  float = 0.0
    attempt:   int   = 0

    @property
    def elapsed(self) -> float:
        if self.finished and self.started:
            return self.finished - self.started
        return 0.0


# ── Task node ─────────────────────────────────────────────────────────────────

@dataclass
class Task:
    """
    A single step in a pipeline.

    fn:           callable(context: dict) -> Result
    name:         human-readable step name
    description:  what this task does
    required:     if False, pipeline continues on failure
    condition:    callable(context) -> bool, skip task if returns False
    rollback:     callable(context) -> None, undo this task if pipeline fails later
    retries:      how many times to retry on failure (default 0)
    """
    name:        str
    fn:          Callable[[dict], Result]
    description: str      = ""
    required:    bool     = True
    condition:   Optional[Callable[[dict], bool]] = None
    rollback:    Optional[Callable[[dict], None]] = None
    retries:     int      = 0
    timeout:     float    = 300.0  # seconds

    def should_run(self, context: dict) -> bool:
        if self.condition is None:
            return True
        try:
            return bool(self.condition(context))
        except Exception:
            return True

    def execute(self, context: dict) -> Result:
        """Execute the task, handling retries and timeout."""
        last_result = Result.fail("not run")
        for attempt in range(self.retries + 1):
            try:
                t0 = time.time()
                result = self.fn(context)
                result.elapsed = time.time() - t0
                if result or not self.required:
                    return result
                last_result = result
            except Exception as e:
                last_result = Result.fail(
                    str(e),
                    f"Exception in task '{self.name}' (attempt {attempt+1})"
                )
                if attempt < self.retries:
                    time.sleep(1.0)
        return last_result


# ── Pipeline ──────────────────────────────────────────────────────────────────

class Pipeline:
    """
    Ordered list of Tasks with state tracking, rollback, and persistence.
    """

    def __init__(self, name: str, description: str = ""):
        self.name        = name
        self.description = description
        self.tasks:       list[Task]       = []
        self.records:     list[TaskRecord] = []
        self._hooks_pre:  list[Callable]   = []
        self._hooks_post: list[Callable]   = []

    def add(self, task: Task) -> "Pipeline":
        """Add a task to the pipeline (fluent API)."""
        self.tasks.append(task)
        return self

    def step(self, name: str, description: str = "",
             required: bool = True, retries: int = 0,
             condition: Callable = None, rollback: Callable = None):
        """Decorator to add a function as a pipeline step."""
        def decorator(fn: Callable) -> Callable:
            self.add(Task(name, fn, description, required,
                         condition, rollback, retries))
            return fn
        return decorator

    def on_start(self, fn: Callable) -> Callable:
        self._hooks_pre.append(fn)
        return fn

    def on_finish(self, fn: Callable) -> Callable:
        self._hooks_post.append(fn)
        return fn

    def run(self, context: dict = None, resume_from: str = None,
            state_file: Path = None) -> "PipelineResult":
        """
        Execute all tasks in order.

        context:     shared mutable dict passed to every task
        resume_from: task name to restart from (skip preceding tasks)
        state_file:  persist progress to this JSON file
        """
        ctx = context or {}
        ctx.setdefault("_pipeline", self.name)
        ctx.setdefault("_started", time.time())

        self.records = [TaskRecord(t.name) for t in self.tasks]
        done_tasks   = []
        skip_until   = resume_from

        for hook in self._hooks_pre:
            try:
                hook(ctx)
            except Exception:
                pass

        for task, record in zip(self.tasks, self.records):
            # Resume logic
            if skip_until:
                if task.name == skip_until:
                    skip_until = None
                else:
                    record.status = TaskStatus.SKIPPED
                    continue

            # Condition check
            if not task.should_run(ctx):
                record.status = TaskStatus.SKIPPED
                record.result = Result.skip(f"Condition not met")
                _print_step(task.name, TaskStatus.SKIPPED, "condition false")
                continue

            # Execute
            _print_step(task.name, TaskStatus.RUNNING)
            record.status  = TaskStatus.RUNNING
            record.started = time.time()
            record.attempt = 1

            result = task.execute(ctx)

            record.result   = result
            record.finished = time.time()
            record.status   = TaskStatus.DONE if result else TaskStatus.FAILED

            # Store result in context for downstream tasks
            ctx[f"_result_{task.name}"] = result
            if result.data:
                ctx.update(result.data)

            _print_step(task.name,
                        TaskStatus.DONE if result else TaskStatus.FAILED,
                        result.message or result.error or "")

            if state_file:
                _save_state(state_file, self.records)

            if not result and task.required:
                # Rollback completed tasks in reverse
                for done_task, done_record in reversed(done_tasks):
                    if done_task.rollback:
                        try:
                            done_task.rollback(ctx)
                        except Exception:
                            pass
                break

            done_tasks.append((task, record))

        for hook in self._hooks_post:
            try:
                hook(ctx, self.records)
            except Exception:
                pass

        return PipelineResult(self.name, self.records, ctx)

    def dry_run(self, context: dict = None) -> list[dict]:
        """Return what would be executed without running anything."""
        ctx = context or {}
        plan = []
        for task in self.tasks:
            plan.append({
                "name":        task.name,
                "description": task.description,
                "required":    task.required,
                "would_run":   task.should_run(ctx),
                "retries":     task.retries,
            })
        return plan


@dataclass
class PipelineResult:
    pipeline_name: str
    records:       list[TaskRecord]
    context:       dict

    @property
    def success(self) -> bool:
        return all(
            r.status in (TaskStatus.DONE, TaskStatus.SKIPPED)
            for r in self.records
        )

    @property
    def failed_tasks(self) -> list[TaskRecord]:
        return [r for r in self.records if r.status == TaskStatus.FAILED]

    @property
    def summary(self) -> str:
        done    = sum(1 for r in self.records if r.status == TaskStatus.DONE)
        skipped = sum(1 for r in self.records if r.status == TaskStatus.SKIPPED)
        failed  = sum(1 for r in self.records if r.status == TaskStatus.FAILED)
        total   = len(self.records)
        return (f"{done}/{total} done, {skipped} skipped, {failed} failed "
                f"({sum(r.elapsed for r in self.records):.1f}s total)")


# ── Helpers ───────────────────────────────────────────────────────────────────

_STATUS_ICONS = {
    TaskStatus.PENDING:  "○",
    TaskStatus.RUNNING:  "→",
    TaskStatus.DONE:     "✓",
    TaskStatus.FAILED:   "✗",
    TaskStatus.SKIPPED:  "—",
}
_STATUS_COLORS = {
    TaskStatus.DONE:    "\033[32m",  # green
    TaskStatus.FAILED:  "\033[31m",  # red
    TaskStatus.RUNNING: "\033[36m",  # cyan
    TaskStatus.SKIPPED: "\033[2m",   # dim
    TaskStatus.PENDING: "",
}
_RESET = "\033[0m"


def _print_step(name: str, status: TaskStatus, note: str = ""):
    icon  = _STATUS_ICONS.get(status, "?")
    color = _STATUS_COLORS.get(status, "")
    note_str = f"  {note}" if note else ""
    print(f"  {color}{icon} {name}{note_str}{_RESET}", flush=True)


def _save_state(path: Path, records: list[TaskRecord]):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [{"name": r.name, "status": r.status.value,
             "elapsed": r.elapsed} for r in records]
    path.write_text(json.dumps(data, indent=2))


# ── Built-in pipeline registry ────────────────────────────────────────────────

_REGISTRY: dict[str, Pipeline] = {}


def register_pipeline(pipeline: Pipeline) -> Pipeline:
    _REGISTRY[pipeline.name] = pipeline
    return pipeline


def get_pipeline(name: str) -> Optional[Pipeline]:
    return _REGISTRY.get(name)


def list_pipelines() -> dict[str, Pipeline]:
    return dict(_REGISTRY)


# ═══════════════════════════════════════════════════════════════════════════════
# BUILT-IN PIPELINES
# ═══════════════════════════════════════════════════════════════════════════════

def _make_root_device_pipeline() -> Pipeline:
    """root-device: detect → backup → patch-boot → flash → verify"""
    p = Pipeline("root-device",
                 "Full root workflow: detect → backup → Magisk patch → flash → verify")

    def detect(ctx: dict) -> Result:
        from modules import adb_devices, get_device_props, detect_chipset_from_props, check_battery_level
        devs = adb_devices()
        online = [s for s, st in devs if st == "device"]
        if not online:
            return Result.fail("No ADB device connected")
        serial = ctx.get("serial") or online[0]
        props  = get_device_props(serial)
        vendor, chipset = detect_chipset_from_props(props)
        # Check for Samsung (overrides vendor for KVB handling)
        try:
            from modules.samsung import is_samsung_device
            if is_samsung_device(props):
                ctx["is_samsung"] = True
                console.print("  [yellow]⚠ Samsung device detected — KVB not AVB[/yellow]")
                console.print("  [yellow]  Standard vbmeta disable will NOT work.[/yellow]")
        except ImportError:
            pass
        ctx["serial"]  = serial
        ctx["vendor"]  = vendor
        ctx["chipset"] = chipset
        ctx["props"]   = props
        # Battery pre-flight — warn if low
        bat_ok, bat_pct, bat_msg = check_battery_level(serial)
        if not bat_ok:
            return Result.fail(bat_msg)
        if bat_pct >= 0 and bat_pct < 30:
            console.print(f"  [yellow]⚠ Battery: {bat_pct}%[/yellow]")
        return Result.ok(f"Device: {serial} ({chipset})",
                         serial=serial, vendor=vendor, chipset=chipset,
                         is_samsung=ctx.get("is_samsung", False))

    def backup(ctx: dict) -> Result:
        serial = ctx["serial"]
        from modules import OUTPUT_DIR
        from modules.partition import dump_partition_adb
        import time
        bk_dir = OUTPUT_DIR / "backups" / serial / time.strftime("%Y%m%d_%H%M%S")
        bk_dir.mkdir(parents=True, exist_ok=True)
        boot_path = bk_dir / "boot.img"
        ok = dump_partition_adb("boot", boot_path, serial=serial)
        if not ok or not boot_path.exists():
            return Result.fail("Could not dump boot partition")
        ctx["stock_boot"] = boot_path
        ctx["backup_dir"] = bk_dir
        return Result.ok(f"Boot backed up: {boot_path}",
                         stock_boot=str(boot_path), backup_dir=str(bk_dir))

    def check_magisk(ctx: dict) -> Result:
        from modules.root import MAGISK_PKG, MAGISK_PKG_OFFICIAL
        from modules import run_adb
        serial = ctx["serial"]
        for pkg in (MAGISK_PKG, MAGISK_PKG_OFFICIAL):
            _, out, _ = run_adb(["shell", f"pm path {pkg} 2>/dev/null"],
                                 serial=serial, check=False)
            if "package:" in out:
                ctx["magisk_pkg"] = pkg
                return Result.ok(f"Magisk found: {pkg}", magisk_pkg=pkg)
        return Result.fail(
            "Magisk not installed on device.\n"
            "  Install Magisk APK, open it once, then re-run this pipeline."
        )

    def patch_boot(ctx: dict) -> Result:
        from modules.root import magisk_patch_boot
        try:
            patched = magisk_patch_boot(ctx["stock_boot"], serial=ctx["serial"])
            ctx["patched_boot"] = patched
            return Result.ok(f"Patched: {patched}", patched_boot=str(patched))
        except Exception as e:
            return Result.fail(str(e))

    def disable_avb(ctx: dict) -> Result:
        """Create blank vbmeta to prevent AVB verification rejecting patched boot."""
        from modules.avb import create_blank_vbmeta
        from modules import OUTPUT_DIR
        vbmeta_out = OUTPUT_DIR / "vbmeta_blank.img"
        try:
            create_blank_vbmeta(vbmeta_out)
            ctx["blank_vbmeta"] = vbmeta_out
            return Result.ok(f"Blank vbmeta: {vbmeta_out}",
                             blank_vbmeta=str(vbmeta_out))
        except Exception as e:
            return Result.fail(str(e))

    def flash_boot(ctx: dict) -> Result:
        from modules import run_adb, run_fastboot, wait_for_fastboot
        serial = ctx["serial"]
        patched = Path(ctx["patched_boot"])
        run_adb(["reboot", "bootloader"], serial=serial, check=False)
        fb_serial = wait_for_fastboot(serial, timeout=30)
        if not fb_serial:
            return Result.fail("No fastboot device after reboot")
        # Flash blank vbmeta first if we have it
        if ctx.get("blank_vbmeta"):
            run_fastboot(["flash", "vbmeta", str(ctx["blank_vbmeta"])],
                         serial=fb_serial, check=False)
        rc, _, err = run_fastboot(["flash", "boot", str(patched)],
                                   serial=fb_serial, check=False, timeout=120)
        if rc != 0:
            return Result.fail(f"fastboot flash failed: {err}")
        run_fastboot(["reboot"], serial=fb_serial, check=False)
        return Result.ok("Boot flashed, device rebooting")

    def verify_root(ctx: dict) -> Result:
        from modules import run_adb, wait_for_boot
        serial = ctx["serial"]
        if not wait_for_boot(serial, timeout=120):
            return Result.fail("Device did not boot within 120s")
        _, out, _ = run_adb(["shell", "su -c id 2>/dev/null"],
                             serial=serial, check=False)
        if "uid=0" in out:
            return Result.ok("Root verified — uid=0 ✓")
        return Result.fail("Root not detected after flash — may need longer boot time")

    p.add(Task("detect",     detect,     "Detect device and chipset", required=True))
    p.add(Task("backup",     backup,     "Dump stock boot.img",       required=True,
               rollback=lambda ctx: None))  # backup is read-only, no rollback needed
    p.add(Task("check-magisk", check_magisk, "Verify Magisk is installed", required=True))
    p.add(Task("patch-boot", patch_boot,  "Patch boot.img with Magisk", required=True))
    p.add(Task("disable-avb", disable_avb, "Create blank vbmeta",       required=False))
    p.add(Task("flash-boot", flash_boot,  "Flash via fastboot",         required=True))
    p.add(Task("verify",     verify_root, "Verify root access",         required=False))
    return p


def _make_full_backup_pipeline() -> Pipeline:
    """full-backup: detect → dump-all → backup-apps → manifest"""
    p = Pipeline("full-backup",
                 "Complete device backup: all partitions + apps + manifest")

    def detect(ctx: dict) -> Result:
        from modules import adb_devices, get_device_props, detect_chipset_from_props, PARTITION_MAPS
        devs = adb_devices()
        online = [s for s, st in devs if st == "device"]
        if not online:
            return Result.fail("No ADB device")
        serial = ctx.get("serial") or online[0]
        props  = get_device_props(serial)
        vendor, chipset = detect_chipset_from_props(props)
        parts = PARTITION_MAPS.get(vendor, PARTITION_MAPS["unknown"])
        ctx.update({"serial": serial, "vendor": vendor,
                    "chipset": chipset, "partitions": parts})
        return Result.ok(f"{chipset} ({len(parts)} partitions)",
                         serial=serial, vendor=vendor, partitions=parts)

    def dump_partitions(ctx: dict) -> Result:
        from modules.partition import dump_partition_adb
        from modules import OUTPUT_DIR, sha256_file, file_size_mb
        import time
        serial = ctx["serial"]
        out_dir = OUTPUT_DIR / "backups" / serial / time.strftime("%Y%m%d_%H%M%S") / "partitions"
        out_dir.mkdir(parents=True, exist_ok=True)
        ctx["backup_parts_dir"] = out_dir
        results = {}
        for part in ctx.get("partitions", []):
            img = out_dir / f"{part}.img"
            ok  = dump_partition_adb(part, img, serial=serial)
            results[part] = "ok" if (ok and img.exists()) else "failed"
        ok_count = sum(1 for v in results.values() if v == "ok")
        ctx["dump_results"] = results
        if ok_count == 0:
            return Result.fail("No partitions could be dumped")
        return Result.ok(f"{ok_count}/{len(results)} partitions dumped",
                         dump_results=results, backup_parts_dir=str(out_dir))

    def backup_apps(ctx: dict) -> Result:
        import subprocess
        from modules import OUTPUT_DIR
        serial = ctx["serial"]
        out_dir = Path(str(ctx.get("backup_parts_dir","output"))).parent
        ab_path = out_dir / "apps.ab"
        try:
            r = subprocess.run(
                ["adb", "-s", serial, "backup", "-apk", "-shared",
                 "-all", "-f", str(ab_path)],
                timeout=600, capture_output=True
            )
            if ab_path.exists():
                from modules import file_size_mb
                return Result.ok(f"Apps backup: {file_size_mb(ab_path):.1f} MB",
                                 apps_backup=str(ab_path))
            return Result.skip("ADB backup produced no output")
        except subprocess.TimeoutExpired:
            return Result.skip("App backup timed out — skipping")
        except Exception as e:
            return Result.fail(str(e))

    def write_manifest(ctx: dict) -> Result:
        import json, time
        from modules import OUTPUT_DIR, sha256_file, file_size_mb
        parts_dir = Path(str(ctx.get("backup_parts_dir", ".")))
        manifest  = {
            "watchrom_backup": "2.0",
            "created":   time.strftime("%Y-%m-%d %H:%M:%S"),
            "serial":    ctx.get("serial","?"),
            "vendor":    ctx.get("vendor","?"),
            "chipset":   ctx.get("chipset","?"),
            "partitions": {},
        }
        for img in sorted(parts_dir.glob("*.img")):
            manifest["partitions"][img.stem] = {
                "file":   img.name,
                "size":   img.stat().st_size,
                "sha256": sha256_file(img),
            }
        mf_path = parts_dir.parent / "manifest.json"
        mf_path.write_text(json.dumps(manifest, indent=2))
        return Result.ok(f"Manifest: {mf_path}", manifest=str(mf_path))

    p.add(Task("detect",          detect,          "Detect device",             required=True))
    p.add(Task("dump-partitions", dump_partitions, "Dump all partitions",       required=True))
    p.add(Task("backup-apps",     backup_apps,     "Backup apps via ADB",       required=False))
    p.add(Task("write-manifest",  write_manifest,  "Write backup manifest",     required=False))
    return p


def _make_avb_disable_pipeline() -> Pipeline:
    """avb-disable: detect → backup-vbmeta → create-blank → flash"""
    p = Pipeline("avb-disable",
                 "Disable AVB verification: backup vbmeta → create blank → flash")

    def detect(ctx: dict) -> Result:
        from modules import adb_devices, get_device_props, detect_chipset_from_props
        devs = adb_devices()
        online = [s for s, st in devs if st == "device"]
        if not online:
            return Result.fail("No ADB device")
        serial = ctx.get("serial") or online[0]
        props = get_device_props(serial)
        vendor, chipset = detect_chipset_from_props(props)
        ctx.update({"serial": serial, "vendor": vendor,
                     "chipset": chipset, "props": props})
        # Samsung KVB check
        try:
            from modules.samsung import is_samsung_device
            if is_samsung_device(props):
                ctx["is_samsung"] = True
                ctx["samsung_kvb"] = True
                console.print("  [yellow]⚠ Samsung KVB device — AVB disable not supported[/yellow]")
                console.print("  [yellow]  Samsung uses Knox Verified Boot, not standard AVB.[/yellow]")
                console.print("  [yellow]  Unlock via: Settings → Developer Options → OEM Unlock[/yellow]")
                console.print("  [yellow]  Then: Reboot to Download Mode, long-press Vol+[/yellow]")
        except ImportError:
            pass
        return Result.ok(f"{serial} ({chipset})",
                         is_samsung=ctx.get("is_samsung", False))

    def backup_vbmeta(ctx: dict) -> Result:
        from modules.partition import dump_partition_adb
        from modules import OUTPUT_DIR
        import time
        serial  = ctx["serial"]
        out_dir = OUTPUT_DIR / "backups" / serial / time.strftime("%Y%m%d_%H%M%S")
        out_dir.mkdir(parents=True, exist_ok=True)
        vm_path = out_dir / "vbmeta.img"
        ok = dump_partition_adb("vbmeta", vm_path, serial=serial)
        if ok and vm_path.exists():
            ctx["stock_vbmeta"] = vm_path
            return Result.ok(f"vbmeta backed up: {vm_path}")
        return Result.skip("Could not dump vbmeta — may not exist on this device")

    def create_blank(ctx: dict) -> Result:
        from modules.avb import create_blank_vbmeta
        from modules import OUTPUT_DIR
        blank = OUTPUT_DIR / "vbmeta_blank.img"
        create_blank_vbmeta(blank)
        ctx["blank_vbmeta"] = blank
        return Result.ok(f"Blank vbmeta: {blank}", blank_vbmeta=str(blank))

    def flash_vbmeta(ctx: dict) -> Result:
        from modules import run_adb, run_fastboot, wait_for_fastboot

        # Samsung KVB devices cannot use fastboot vbmeta disable
        if ctx.get("samsung_kvb") or ctx.get("is_samsung"):
            console.print("  [yellow]  Samsung KVB: fastboot vbmeta flash will NOT work.[/yellow]")
            console.print("  [yellow]  Bootloader must be unlocked via Download Mode.[/yellow]")
            console.print("  [yellow]  See: https://forum.xda-developers.com/t/how-to-unlock-samsung-bootloader[/yellow]")
            if ctx.get("skip_vbmeta"):
                return Result.skip("Samsung KVB — vbmeta flash skipped (use Magisk)")
            # Try anyway (some users use custom vbmeta)
            console.print("  [yellow]  Attempting flash anyway (likely to fail)...[/yellow]")

        serial = ctx["serial"]
        blank  = Path(ctx["blank_vbmeta"])
        run_adb(["reboot", "bootloader"], serial=serial, check=False)
        fb_serial = wait_for_fastboot(serial, timeout=30)
        if not fb_serial:
            return Result.fail("No fastboot device after reboot")
        rc, _, err = run_fastboot(
            ["--disable-verity", "--disable-verification",
             "flash", "vbmeta", str(blank)],
            serial=fb_serial, check=False
        )
        if rc != 0:
            # Try without flags (older fastboot)
            rc, _, err = run_fastboot(
                ["flash", "vbmeta", str(blank)],
                serial=fb_serial, check=False
            )
        if rc == 0:
            run_fastboot(["reboot"], serial=fb_serial, check=False)
            return Result.ok("vbmeta flashed, device rebooting")
        return Result.fail(f"fastboot flash vbmeta failed: {err}")

    def _rollback_vbmeta(ctx: dict) -> None:
        """Rollback: re-flash the backed-up stock vbmeta."""
        stock = ctx.get("stock_vbmeta")
        if not stock or not Path(stock).exists():
            return  # No backup to restore from — can't roll back
        from modules import run_fastboot, fastboot_devices
        import time
        fb = fastboot_devices()
        if not fb:
            return  # Not in fastboot mode — can't roll back
        run_fastboot(["flash", "vbmeta", str(stock)], serial=fb[0], check=False)

    p.add(Task("detect",        detect,        "Detect device",          required=True))
    p.add(Task("backup-vbmeta", backup_vbmeta, "Backup stock vbmeta",    required=False))
    p.add(Task("create-blank",  create_blank,  "Create blank vbmeta",    required=True))
    p.add(Task("flash-vbmeta",  flash_vbmeta,  "Flash via fastboot",     required=True,
               rollback=_rollback_vbmeta))
    return p


def _make_flash_rom_pipeline() -> Pipeline:
    """flash-rom: validate → backup → disable-avb → flash-all → verify"""
    p = Pipeline("flash-rom",
                 "Flash a complete ROM: validate → backup → disable AVB → flash all → verify")

    def validate(ctx: dict) -> Result:
        from modules import check_battery_level, console
        parts_dir = Path(ctx.get("parts_dir", "."))
        if not parts_dir.is_dir():
            return Result.fail(f"Parts directory not found: {parts_dir}")
        imgs = list(parts_dir.glob("*.img"))
        if not imgs:
            return Result.fail(f"No .img files in {parts_dir}")
        ctx["parts_dir"] = parts_dir
        ctx["images"]    = {img.stem: img for img in imgs}
        # Battery pre-flight
        if ctx.get("serial"):
            bat_ok, bat_pct, bat_msg = check_battery_level(ctx["serial"])
            if not bat_ok:
                return Result.fail(bat_msg)
            if bat_pct >= 0 and bat_pct < 30:
                console.print(f"  [yellow]⚠ Battery: {bat_pct}% — charge before flashing[/yellow]")
        return Result.ok(f"Found {len(imgs)} images: {[i.stem for i in imgs]}",
                         image_count=len(imgs))

    def backup(ctx: dict) -> Result:
        # Run the full-backup pipeline as a sub-pipeline
        sub = _make_full_backup_pipeline()
        result = sub.run({"serial": ctx.get("serial")})
        if result.success:
            return Result.ok("Pre-flash backup complete")
        return Result.skip("Backup had issues — proceeding with caution")

    def disable_avb(ctx: dict) -> Result:
        sub = _make_avb_disable_pipeline()
        result = sub.run({"serial": ctx.get("serial")})
        return Result.ok("AVB disabled") if result.success else Result.skip("AVB disable skipped")

    def flash_all(ctx: dict) -> Result:
        from modules import run_adb, run_fastboot, wait_for_fastboot
        serial = ctx.get("serial")
        images = ctx.get("images", {})

        # Safe flash order: vbmeta/avb first, then system, then boot last
        FLASH_ORDER = ["vbmeta","dtbo","persist","modem","vendor",
                       "system","product","odm","recovery","boot"]

        fb_serial = None
        if serial:
            fb_serial = wait_for_fastboot(serial, timeout=30)
        if not fb_serial:
            fb_serial = wait_for_fastboot(None, timeout=5)

        if not fb_serial:
            return Result.fail("No fastboot device for flashing")
        results   = {}

        # Flash in safe order, then any remaining
        ordered = [p for p in FLASH_ORDER if p in images]
        remaining = [p for p in images if p not in ordered]
        for part in ordered + remaining:
            img = images[part]
            rc, _, err = run_fastboot(
                ["flash", part, str(img)],
                serial=fb_serial, check=False, timeout=300
            )
            results[part] = "ok" if rc == 0 else f"FAIL: {err[:60]}"

        ok_count = sum(1 for v in results.values() if v == "ok")
        run_fastboot(["reboot"], serial=fb_serial, check=False)

        if ok_count == 0:
            return Result.fail("All partition flashes failed")
        return Result.ok(f"{ok_count}/{len(results)} partitions flashed",
                         flash_results=results)

    p.add(Task("validate",    validate,    "Validate ROM images",     required=True))
    p.add(Task("backup",      backup,      "Backup current device",   required=False))
    p.add(Task("disable-avb", disable_avb, "Disable AVB",             required=False))
    p.add(Task("flash-all",   flash_all,   "Flash all partitions",    required=True))
    return p


def _make_wearos_setup_pipeline() -> Pipeline:
    """wearos-setup: detect → check-root → backup → configure → module → verify"""
    p = Pipeline("wearos-setup",
                 "WearOS compatibility: detect → root check → backup → Magisk module → verify")

    def detect(ctx: dict) -> Result:
        from modules import adb_devices, get_device_props, detect_chipset_from_props
        devs  = adb_devices()
        online = [s for s, st in devs if st == "device"]
        if not online:
            return Result.fail("No ADB device")
        serial = ctx.get("serial") or online[0]
        props  = get_device_props(serial)
        vendor, chipset = detect_chipset_from_props(props)
        ctx.update({"serial": serial, "vendor": vendor,
                    "chipset": chipset, "props": props})
        return Result.ok(f"{serial} — {chipset}")

    def check_root(ctx: dict) -> Result:
        from modules import run_adb
        _, out, _ = run_adb(["shell", "su -c id 2>/dev/null"],
                             serial=ctx["serial"], check=False)
        if "uid=0" in out:
            ctx["rooted"] = True
            return Result.ok("Device is rooted")
        ctx["rooted"] = False
        return Result.fail(
            "Device is not rooted.\n"
            "  Run first: watchrom pipeline root-device"
        )

    def backup_props(ctx: dict) -> Result:
        from modules import run_adb, OUTPUT_DIR
        import time
        serial  = ctx["serial"]
        bk_dir  = OUTPUT_DIR / "wearos_backups" / serial / time.strftime("%Y%m%d_%H%M%S")
        bk_dir.mkdir(parents=True, exist_ok=True)
        _, props_out, _ = run_adb(["shell", "getprop"], serial=serial, check=False)
        (bk_dir / "props_backup.txt").write_text(props_out)
        ctx["props_backup"] = bk_dir
        return Result.ok(f"Props backed up: {bk_dir}")

    def build_module(ctx: dict) -> Result:
        from modules.wearos import _setup_magisk_module
        from modules.wearos import WEAROS_PROPS
        props_to_set = dict(WEAROS_PROPS)
        screen = ctx.get("screen_density", 240)
        props_to_set["ro.sf.lcd_density"] = str(screen)
        try:
            _setup_magisk_module(props_to_set)
            from modules import OUTPUT_DIR
            zip_path = OUTPUT_DIR / "magisk_modules" / "watchrom_wearos.zip"
            ctx["wearos_module"] = zip_path
            return Result.ok(f"WearOS module: {zip_path}",
                             wearos_module=str(zip_path))
        except Exception as e:
            return Result.fail(str(e))

    def install_module(ctx: dict) -> Result:
        from modules import run_adb
        serial   = ctx["serial"]
        zip_path = Path(ctx["wearos_module"])
        remote   = f"/sdcard/Download/{zip_path.name}"
        rc, _, err = run_adb(["push", str(zip_path), remote],
                              serial=serial, check=False, timeout=60)
        if rc != 0:
            return Result.fail(f"Push failed: {err}")
        _, out, _ = run_adb(
            ["shell", f"su -c 'magisk --install-module {remote}'"],
            serial=serial, check=False, timeout=60
        )
        if "Done" in out or "success" in out.lower():
            return Result.ok("WearOS module installed — reboot to activate")
        return Result.ok("Module pushed — install via Magisk app if needed")

    def verify_wearos(ctx: dict) -> Result:
        from modules import run_adb
        _, out, _ = run_adb(
            ["shell", "getprop ro.build.characteristics"],
            serial=ctx["serial"], check=False
        )
        if "watch" in out:
            return Result.ok(f"WearOS props active: {out.strip()}")
        return Result.skip("Reboot required for WearOS props to take effect")

    p.add(Task("detect",         detect,        "Detect device",               required=True))
    p.add(Task("check-root",     check_root,    "Verify device is rooted",     required=True))
    p.add(Task("backup-props",   backup_props,  "Backup current properties",   required=False))
    p.add(Task("build-module",   build_module,  "Build WearOS Magisk module",  required=True))
    p.add(Task("install-module", install_module,"Install module via Magisk",   required=True))
    p.add(Task("verify",         verify_wearos, "Verify WearOS props active",  required=False))
    return p


def _make_band_config_pipeline() -> Pipeline:
    """configure-bands: detect → backup → apply-carrier → verify"""
    p = Pipeline("configure-bands",
                 "Configure LTE/5G bands: detect vendor → backup → apply preset → verify")

    def detect(ctx: dict) -> Result:
        from modules import adb_devices, get_device_props, detect_chipset_from_props
        devs = adb_devices()
        online = [s for s, st in devs if st == "device"]
        if not online:
            return Result.fail("No ADB device")
        serial = ctx.get("serial") or online[0]
        props  = get_device_props(serial)
        vendor, chipset = detect_chipset_from_props(props)
        ctx.update({"serial": serial, "vendor": vendor, "chipset": chipset})
        return Result.ok(f"{serial} — {chipset} ({vendor})")

    def backup_bands(ctx: dict) -> Result:
        from modules.modem_bands import _backup_band_config
        from modules import OUTPUT_DIR
        import time
        bk_dir = OUTPUT_DIR / "band_backups" / ctx["serial"] / time.strftime("%Y%m%d_%H%M%S")
        _backup_band_config(ctx["serial"], ctx["vendor"], bk_dir)
        ctx["band_backup_dir"] = bk_dir
        return Result.ok(f"Band config backed up: {bk_dir}")

    def apply_bands(ctx: dict) -> Result:
        from modules.modem_bands import _apply_carrier_profile, CARRIER_PROFILES
        carrier = ctx.get("carrier", "global_roaming")
        profile = CARRIER_PROFILES.get(carrier)
        if not profile:
            return Result.fail(f"Unknown carrier: {carrier}")
        ctx["_no_reboot"] = True  # We'll reboot in the next step
        _apply_carrier_profile(ctx["serial"], profile)
        return Result.ok(f"Band profile applied: {profile['display']}")

    def reboot_and_verify(ctx: dict) -> Result:
        from modules import run_adb, wait_for_boot
        serial = ctx["serial"]
        run_adb(["reboot"], serial=serial, check=False)
        if not wait_for_boot(serial, timeout=120):
            return Result.ok("Reboot initiated — verify signal in Settings")
        from modules.modem_bands import get_current_bands_at
        bands_info = get_current_bands_at(serial, ctx["vendor"])
        return Result.ok("Device rebooted — verify signal in Settings",
                         bands_detected=bands_info)

    p.add(Task("detect",           detect,         "Detect chipset vendor",  required=True))
    p.add(Task("backup-bands",     backup_bands,   "Backup current bands",   required=True))
    p.add(Task("apply-bands",      apply_bands,    "Apply carrier profile",  required=True))
    p.add(Task("reboot-verify",    reboot_and_verify, "Reboot and verify",   required=False))
    return p


# ── Register all built-in pipelines ──────────────────────────────────────────
register_pipeline(_make_root_device_pipeline())
register_pipeline(_make_full_backup_pipeline())
register_pipeline(_make_avb_disable_pipeline())
register_pipeline(_make_flash_rom_pipeline())
register_pipeline(_make_wearos_setup_pipeline())
register_pipeline(_make_band_config_pipeline())
