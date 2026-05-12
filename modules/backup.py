"""
backup.py — Full device backup and restore
Handles: ADB backup, partition image backup, app+data backup, restore
"""
import click
import shutil
import json
from pathlib import Path
from datetime import datetime
from modules import (
    run, run_adb, run_fastboot, adb_devices, get_device_props,
    detect_chipset_from_props, PARTITION_MAPS, OUTPUT_DIR, WORKSPACE,
    sha256_file, file_size_mb, console
)


def backup_dir(serial: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return OUTPUT_DIR / "backups" / f"{serial}_{stamp}"


# ── CLI ───────────────────────────────────────────────────────────────────────

@click.group()
def backup():
    """Full device backup and restore — partitions, apps, and data."""
    pass


@backup.command("full")
@click.option("--serial",  "-s", default=None)
@click.option("--out",     "-o", default=None, help="Backup output directory")
@click.option("--no-data", is_flag=True, help="Skip userdata partition (faster)")
def backup_full(serial, out, no_data):
    """
    Full device backup: all partition images + ADB app backup.

    Creates a timestamped backup directory containing:
      partitions/   — All partition .img files
      apps/         — ADB backup of all user apps + data
      manifest.json — Backup index with checksums
    """
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    props  = get_device_props(target)
    vendor, chipset = detect_chipset_from_props(props)
    parts  = PARTITION_MAPS.get(vendor, PARTITION_MAPS["mtk"])
    if no_data and "userdata" in parts:
        parts = [p for p in parts if p != "userdata"]

    bk_dir   = Path(out) if out else backup_dir(target)
    part_dir = bk_dir / "partitions"
    part_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold cyan]Full Device Backup[/bold cyan]")
    console.print(f"  Device  : {target}  ({vendor.upper()} / {chipset})")
    console.print(f"  Output  : {bk_dir}")
    console.print(f"  Parts   : {len(parts)}\n")

    # Partition images
    from modules.partition import dump_partition_adb
    results = []
    for part in parts:
        out_path = part_dir / f"{part}.img"
        console.print(f"  [cyan]Dumping {part}...[/cyan]", end=" ")
        ok = dump_partition_adb(part, out_path, serial=target)
        if ok and out_path.exists():
            console.print(f"[green]✓[/green] {file_size_mb(out_path):.1f} MB")
            results.append({"partition": part, "file": out_path.name,
                             "size": out_path.stat().st_size,
                             "sha256": sha256_file(out_path)})
        else:
            console.print(f"[red]✗ FAILED[/red]")
            results.append({"partition": part, "file": None, "error": "dump failed"})

    # ADB app backup
    apps_bk = bk_dir / "apps.ab"
    console.print(f"\n[cyan]→ ADB app backup...[/cyan]")
    rc, _, _ = run(
        ["adb", "-s", target, "backup", "-apk", "-shared", "-all",
         "-f", str(apps_bk)],
        capture=False, check=False, timeout=600
    )
    app_size = file_size_mb(apps_bk) if apps_bk.exists() else 0
    console.print(f"  [{'green' if apps_bk.exists() else 'red'}]"
                  f"{'✓' if apps_bk.exists() else '✗'} App backup: {app_size:.1f} MB[/]")

    # Device info snapshot
    info_path = bk_dir / "device_info.json"
    with open(info_path, "w") as f:
        json.dump({
            "serial":    target,
            "vendor":    vendor,
            "chipset":   chipset,
            "timestamp": datetime.now().isoformat(),
            "model":     props.get("ro.product.model","?"),
            "android":   props.get("ro.build.version.release","?"),
            "build":     props.get("ro.build.fingerprint","?"),
        }, f, indent=2)

    # Manifest
    manifest = {
        "watchrom_backup": "1.0",
        "created": datetime.now().isoformat(),
        "device": target, "vendor": vendor, "chipset": chipset,
        "partitions": results,
        "apps_backup": str(apps_bk) if apps_bk.exists() else None,
    }
    with open(bk_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    ok_count = sum(1 for r in results if r.get("sha256"))
    console.print(f"\n[bold green]✓ Backup complete → {bk_dir}[/bold green]")
    console.print(f"  Partitions: {ok_count}/{len(parts)}")
    console.print(f"  Apps      : {'✓' if apps_bk.exists() else '✗'}")
    console.print(f"\n  Restore: [bold]watchrom backup restore {bk_dir}[/bold]")


@backup.command("restore")
@click.argument("backup_dir_path")
@click.option("--serial",      "-s", default=None)
@click.option("--partitions",  "-p", multiple=True,
              help="Only restore specific partitions (default: all)")
@click.option("--skip-data",   is_flag=True, help="Skip userdata restore")
@click.option("--dry-run",     is_flag=True, help="Show what would be flashed without doing it")
def backup_restore(backup_dir_path, serial, partitions, skip_data, dry_run):
    """
    Restore a device from a WatchROM backup directory.

    Flashes all backed-up partition images via fastboot.
    """
    bk_dir = Path(backup_dir_path)
    manifest_path = bk_dir / "manifest.json"
    if not manifest_path.exists():
        console.print(f"[red]✗ No manifest.json — not a valid WatchROM backup.[/red]")
        return

    with open(manifest_path) as f:
        manifest = json.load(f)

    console.print(f"\n[bold cyan]Backup Restore[/bold cyan]")
    console.print(f"  Backup  : {bk_dir.name}")
    console.print(f"  Device  : {manifest.get('device','?')}")
    console.print(f"  Created : {manifest.get('created','?')}\n")

    part_dir = bk_dir / "partitions"
    to_restore = manifest.get("partitions", [])

    if partitions:
        to_restore = [r for r in to_restore if r["partition"] in partitions]
    if skip_data:
        to_restore = [r for r in to_restore if r["partition"] != "userdata"]

    console.print(f"  Will restore {len(to_restore)} partition(s):\n")
    for r in to_restore:
        img = part_dir / r["file"] if r.get("file") else None
        exists = img and img.exists()
        size = file_size_mb(img) if exists else 0
        console.print(f"    [{'cyan' if exists else 'red'}]{r['partition']:20s}[/{'cyan' if exists else 'red'}]  "
                      f"{'%.1f MB' % size if exists else 'MISSING'}")

    if dry_run:
        console.print("\n[yellow]Dry run — no changes made.[/yellow]")
        return

    if not click.confirm("\n⚠ This will overwrite device partitions. Continue?", default=False):
        return

    # Reboot to fastboot
    target = serial
    if not target:
        devs = adb_devices()
        online = [s for s, st in devs if st == "device"]
        if online:
            target = online[0]
            run_adb(["reboot", "bootloader"], serial=target, check=False)
            import time; time.sleep(6)

    from modules import fastboot_devices
    fb = fastboot_devices()
    fb_serial = target if target in fb else (fb[0] if fb else None)
    if not fb_serial:
        console.print("[red]✗ No fastboot device.[/red]")
        return

    for r in to_restore:
        img = part_dir / r["file"] if r.get("file") else None
        if not img or not img.exists():
            console.print(f"[yellow]! Skipping {r['partition']} — image missing[/yellow]")
            continue
        console.print(f"[cyan]Flashing {r['partition']}...[/cyan]", end=" ")
        rc, _, err = run_fastboot(
            ["flash", r["partition"], str(img)],
            serial=fb_serial, check=False, timeout=300
        )
        if rc == 0:
            console.print(f"[green]✓[/green]")
        else:
            console.print(f"[red]✗ {err[:60]}[/red]")

    run_fastboot(["reboot"], serial=fb_serial, check=False)
    console.print(f"\n[green]✓ Restore complete. Device rebooting.[/green]")


@backup.command("apps")
@click.option("--serial",  "-s", default=None)
@click.option("--package", "-p", default=None,
              help="Backup specific package only")
@click.option("--out",     "-o", default=None)
def backup_apps(serial, package, out):
    """Backup app APKs and data via ADB backup."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    out_path = Path(out) if out else (OUTPUT_DIR / "backups" / f"apps_{target}.ab")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["adb", "-s", target, "backup", "-apk", "-f", str(out_path)]
    if package:
        cmd.append(package)
        console.print(f"[cyan]Backing up {package}...[/cyan]")
    else:
        cmd += ["-all"]
        console.print(f"[cyan]Backing up all apps...[/cyan]")

    console.print("[dim]Confirm backup on device screen if prompted.[/dim]")
    subprocess.run(cmd) if (import_subprocess := __import__("subprocess")) else None
    import subprocess
    subprocess.run(cmd)

    if out_path.exists():
        console.print(f"[green]✓ Backup: {out_path} ({file_size_mb(out_path):.1f} MB)[/green]")
        console.print(f"  Restore: adb restore {out_path}")


@backup.command("list")
def backup_list():
    """List all available WatchROM backups."""
    bk_root = OUTPUT_DIR / "backups"
    if not bk_root.exists():
        console.print("[dim]No backups found.[/dim]")
        return

    from rich.table import Table
    from rich import box as rbox
    t = Table(box=rbox.ROUNDED, border_style="cyan")
    t.add_column("Backup",   style="cyan")
    t.add_column("Device",   style="green")
    t.add_column("Created",  style="yellow")
    t.add_column("Parts",    style="white")
    t.add_column("Size",     style="dim")

    for d in sorted(bk_root.iterdir()):
        mf = d / "manifest.json"
        if not mf.exists():
            continue
        try:
            with open(mf) as f:
                m = json.load(f)
            parts = len([p for p in m.get("partitions",[]) if p.get("sha256")])
            total = sum(
                (d/"partitions"/p["file"]).stat().st_size
                for p in m.get("partitions",[])
                if p.get("file") and (d/"partitions"/p["file"]).exists()
            ) / (1024*1024)
            t.add_row(
                d.name,
                m.get("device","?"),
                m.get("created","?")[:19],
                str(parts),
                f"{total:.0f} MB"
            )
        except Exception:
            continue

    console.print(t)
