"""
diag.py — Device diagnostics, logcat analysis, HAL inspection, crash reporting
"""
import click
import subprocess
import re
from pathlib import Path
from datetime import datetime
from modules import run_adb, adb_devices, get_device_props, OUTPUT_DIR, console


@click.group()
def diag():
    """Device diagnostics: logcat, HAL status, crash logs, hardware inventory."""
    pass


@diag.command("full")
@click.option("--serial", "-s", default=None)
@click.option("--out",    "-o", default=None, help="Save report to file")
def diag_full(serial, out):
    """
    Run a full device diagnostic and generate a report.

    Collects: device info, partition state, HAL status, memory,
    storage, running services, SELinux state, logcat errors.
    """
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    console.print(f"\n[bold cyan]Full Device Diagnostic — {target}[/bold cyan]\n")
    report = []
    report.append(f"WatchROM Diagnostic Report")
    report.append(f"Generated: {datetime.now().isoformat()}")
    report.append(f"Device:    {target}\n")

    def section(title):
        console.print(f"[bold yellow]── {title} ──[/bold yellow]")
        report.append(f"\n=== {title} ===")

    def shell_collect(label, cmd):
        _, out, _ = run_adb(["shell", cmd], serial=target, check=False)
        val = out.strip()
        console.print(f"  [cyan]{label:30s}[/cyan] {val[:70]}")
        report.append(f"{label}: {val}")
        return val

    # Device identity
    section("Device Identity")
    props = get_device_props(target)
    for key in ["ro.product.model","ro.product.device","ro.board.platform",
                "ro.build.version.release","ro.build.version.security_patch",
                "ro.build.fingerprint","ro.treble.enabled","ro.boot.avb_version",
                "ro.crypto.state","ro.boot.verifiedbootstate"]:
        val = props.get(key,"?")
        console.print(f"  [cyan]{key:40s}[/cyan] {val}")
        report.append(f"{key} = {val}")

    # Memory
    section("Memory")
    shell_collect("Total RAM",     "cat /proc/meminfo | grep MemTotal")
    shell_collect("Available RAM", "cat /proc/meminfo | grep MemAvailable")
    shell_collect("Swap",          "cat /proc/meminfo | grep SwapTotal")

    # Storage
    section("Storage")
    shell_collect("df -h /data", "df -h /data 2>/dev/null | tail -1")
    shell_collect("df -h /system","df -h /system 2>/dev/null | tail -1")
    shell_collect("eMMC info",    "cat /sys/block/mmcblk0/device/name 2>/dev/null || echo N/A")
    shell_collect("eMMC size",    "cat /sys/block/mmcblk0/size 2>/dev/null | awk '{print $1*512/1024/1024/1024 \" GB\"}'")

    # CPU
    section("CPU")
    shell_collect("CPU info",     "cat /proc/cpuinfo | grep 'Hardware' | head -1")
    shell_collect("CPU cores",    "nproc")
    shell_collect("CPU governor", "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null")
    shell_collect("CPU freq max", "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null")

    # Root & Security
    section("Root & Security")
    shell_collect("Root (uid=0)",   "su -c id 2>/dev/null || echo NOT_ROOTED")
    shell_collect("SELinux state",  "getenforce 2>/dev/null")
    shell_collect("Bootloader lock","getprop ro.boot.flash.locked 2>/dev/null || echo unknown")
    shell_collect("dm-verity",      "getprop ro.boot.veritymode 2>/dev/null")

    # Running services
    section("Key Services")
    _, svc_out, _ = run_adb(["shell", "service list 2>/dev/null | head -30"], serial=target, check=False)
    key_svcs = ["SurfaceFlinger","Vibrator","Sensors","InputMethod","AudioFlinger","CameraService"]
    for svc in key_svcs:
        found = svc in svc_out
        console.print(f"  [{'green' if found else 'red'}]{'✓' if found else '✗'}[/{'green' if found else 'red'}] {svc}")
        report.append(f"Service {svc}: {'running' if found else 'NOT FOUND'}")

    # HALs
    section("Hardware Abstraction Layers")
    _, hal_out, _ = run_adb(
        ["shell", "ls /vendor/lib*/hw/*.so 2>/dev/null | xargs -I{} basename {}"],
        serial=target, check=False
    )
    hals = [h.strip() for h in hal_out.splitlines() if h.strip()]
    for hal in hals[:20]:
        console.print(f"  [dim]✓ {hal}[/dim]")
    report.append(f"HALs found: {', '.join(hals)}")

    # Logcat errors
    section("Recent Errors")
    _, log_out, _ = run_adb(
        ["shell", "logcat -d -s AndroidRuntime:E System.err:E -T 100"],
        serial=target, check=False
    )
    errors = [l for l in log_out.splitlines() if " E " in l or "FATAL" in l][:10]
    for err in errors:
        console.print(f"  [red]{err[:100]}[/red]")
    report.append("Recent errors:\n" + "\n".join(errors))

    # Crashes
    section("Recent Tombstones / Crashes")
    _, tomb_out, _ = run_adb(
        ["shell", "ls /data/tombstones/ 2>/dev/null || echo none"],
        serial=target, check=False
    )
    console.print(f"  Tombstones: {tomb_out.strip()}")

    # Save report
    out_path = Path(out) if out else (OUTPUT_DIR / f"diag_{target}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(report))
    console.print(f"\n[green]✓ Report saved: {out_path}[/green]")


@diag.command("logcat")
@click.option("--serial",  "-s", default=None)
@click.option("--level",   "-l",
              type=click.Choice(["V","D","I","W","E","F"]), default="W")
@click.option("--tag",     "-t", default=None, help="Filter by tag")
@click.option("--crash",   "-c", is_flag=True, help="Show only crashes/fatal errors")
@click.option("--out",     "-o", default=None, help="Save to file")
@click.option("--lines",   "-n", default=None, type=int, help="Last N lines (dump mode)")
def diag_logcat(serial, level, tag, crash, out, lines):
    """Filtered logcat viewer with crash detection."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    cmd = ["adb", "-s", target, "logcat", "-v", "time"]
    if lines:
        cmd += ["-d", "-T", str(lines)]
    if crash:
        cmd += ["-s", "AndroidRuntime:E", "CRASH:*", "libc:F"]
    elif tag:
        cmd += ["-s", f"{tag}:{level}"]
    else:
        cmd += [f"*:{level}"]

    console.print(f"[cyan]Logcat ({target}) level={level}{' crash-only' if crash else ''} ...[/cyan]\n")

    if out:
        with open(out, "w") as f:
            subprocess.run(cmd, stdout=f, text=True)
        console.print(f"[green]✓ Saved: {out}[/green]")
    else:
        subprocess.run(cmd)


@diag.command("bugreport")
@click.option("--serial", "-s", default=None)
@click.option("--out",    "-o", default=None)
def diag_bugreport(serial, out):
    """Capture a full Android bug report (adb bugreport)."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    out_path = Path(out) if out else (OUTPUT_DIR / f"bugreport_{target}.zip")
    console.print(f"[cyan]Capturing bug report from {target}...[/cyan]")
    console.print(f"[dim]This may take 2-3 minutes.[/dim]")

    subprocess.run(["adb", "-s", target, "bugreport", str(out_path)])
    if out_path.exists():
        console.print(f"[green]✓ Bug report: {out_path}[/green]")
    else:
        console.print("[red]✗ Bug report failed.[/red]")


@diag.command("partitions")
@click.option("--serial", "-s", default=None)
def diag_partitions(serial):
    """Show full partition layout with sizes from device."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    _, out, _ = run_adb(
        ["shell", "su -c 'cat /proc/partitions' 2>/dev/null || cat /proc/partitions"],
        serial=target, check=False
    )
    console.print(f"\n[bold cyan]Partition Table — {target}[/bold cyan]\n")

    from rich.table import Table
    from rich import box as rbox
    t = Table(box=rbox.SIMPLE, border_style="cyan")
    t.add_column("Major", style="dim")
    t.add_column("Minor", style="dim")
    t.add_column("Blocks", style="green")
    t.add_column("Name", style="cyan")
    t.add_column("Size", style="yellow")

    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0].isdigit():
            major, minor, blocks, name = parts
            try:
                size_mb = int(blocks) // 1024
                size_str = f"{size_mb} MB" if size_mb < 1024 else f"{size_mb//1024:.1f} GB"
            except Exception:
                size_str = "?"
            t.add_row(major, minor, blocks, name, size_str)

    console.print(t)

    # Also show by-name symlinks
    _, byname, _ = run_adb(
        ["shell", "ls -la /dev/block/by-name/ 2>/dev/null"],
        serial=target, check=False
    )
    if byname.strip():
        console.print(f"\n[bold]/dev/block/by-name/[/bold]\n")
        for line in byname.splitlines():
            if "->" in line:
                parts = line.split("->")
                name = parts[0].strip().split()[-1]
                target_node = parts[1].strip()
                console.print(f"  [green]{name:20s}[/green] → {target_node}")
