"""
root.py — Boot image patching for root access via Magisk
Handles: boot.img extraction, Magisk patch, re-flash
"""
import click
import shutil
import subprocess
from pathlib import Path
from modules import (
    run_adb, run_fastboot, adb_devices, get_device_props,
    detect_chipset_from_props, OUTPUT_DIR, WORKSPACE,
    sha256_file, file_size_mb, parse_android_image_header,
    console, require_tool, tool_available
)


# ─── Magisk Patching ──────────────────────────────────────────────────────────

MAGISK_PKG = "io.github.huskydg.magisk"          # Delta variant (watch-friendly)
MAGISK_PKG_OFFICIAL = "com.topjohnwu.magisk"

MAGISK_ENV = {
    "KEEPVERITY":    "false",   # Disable dm-verity
    "KEEPFORCEENCRYPT": "false", # Disable force-encrypt
    "PATCHVBMETAFLAG": "true",   # Patch vbmeta flags
    "RECOVERYMODE":  "false",
    "LEGACYSAR":     "false",
}


def find_magisk_on_device(serial=None) -> str:
    """Return Magisk app data path on device, or empty string."""
    for pkg in (MAGISK_PKG, MAGISK_PKG_OFFICIAL):
        _, out, _ = run_adb(
            ["shell", f"pm path {pkg} 2>/dev/null"],
            serial=serial, check=False
        )
        if "package:" in out:
            return out.strip().replace("package:", "")
    return ""


def pull_magisk_apk(serial=None, dest: Path = None) -> Path:
    """Pull Magisk APK from device to host."""
    apk_path = find_magisk_on_device(serial)
    if not apk_path:
        raise FileNotFoundError(
            "Magisk not installed on device.\n"
            "  1. Download Magisk.apk from https://github.com/topjohnwu/Magisk/releases\n"
            "  2. Install:  adb install Magisk.apk\n"
            "  3. Open Magisk on device once, then re-run this command."
        )
    dest = dest or (WORKSPACE / "magisk.apk")
    run_adb(["pull", apk_path, str(dest)], serial=serial)
    return dest


def magisk_patch_boot(boot_img: Path, serial=None, magisk_apk: Path = None) -> Path:
    """
    Patch boot.img using Magisk's built-in boot_patch.sh script.

    Strategy:
      1. Push boot.img to /data/local/tmp/ on device
      2. Invoke Magisk to patch it (uses device's own Magisk binary)
      3. Pull patched image back
    """
    console.print(f"\n[bold cyan]Magisk Boot Patcher[/bold cyan]")
    console.print(f"  Input : {boot_img} ({file_size_mb(boot_img):.1f} MB)")
    console.print(f"  SHA256: {sha256_file(boot_img)[:24]}…\n")

    remote_boot  = "/data/local/tmp/watchrom_boot.img"
    remote_patch = "/data/local/tmp/watchrom_boot_patched.img"

    # Push boot.img
    console.print("[cyan]→ Pushing boot.img to device...[/cyan]")
    run_adb(["push", str(boot_img), remote_boot], serial=serial, timeout=180)

    # Set environment flags and invoke Magisk patch
    env_str = " ".join(f"{k}={v}" for k, v in MAGISK_ENV.items())
    patch_cmd = (
        f"su -c '"
        f"{env_str} "
        f"BOOTIMAGE={remote_boot} "
        f"MAGISKTMP=$(magisk --path) "
        f"sh $(magisk --path)/.magisk/mirror/data/adb/magisk/boot_patch.sh {remote_boot}"
        f"'"
    )
    console.print("[cyan]→ Patching boot.img on device (requires Magisk installed)...[/cyan]")
    _, out, err = run_adb(["shell", patch_cmd], serial=serial, check=False, timeout=120)
    console.print(f"[dim]{out[:500]}[/dim]")

    # Magisk writes to /data/local/tmp/new-boot.img by default
    for candidate in ["/data/local/tmp/new-boot.img", remote_patch]:
        _, chk, _ = run_adb(["shell", f"ls {candidate} 2>/dev/null"], serial=serial, check=False)
        if candidate.split("/")[-1] in chk or chk.strip():
            patched_local = WORKSPACE / f"boot_magisk_patched.img"
            rc, _, _ = run_adb(["pull", candidate, str(patched_local)], serial=serial, check=False)
            if rc == 0 and patched_local.exists():
                console.print(f"[green]✓ Patched image: {patched_local} ({file_size_mb(patched_local):.1f} MB)[/green]")
                console.print(f"  SHA256: {sha256_file(patched_local)[:24]}…")
                run_adb(["shell", f"rm {remote_boot} {candidate} 2>/dev/null"], serial=serial, check=False)
                return patched_local

    # Cleanup
    run_adb(["shell", f"rm {remote_boot} 2>/dev/null"], serial=serial, check=False)
    raise RuntimeError("Patched boot image not found on device. Check Magisk installation.")


# ─── CLI ──────────────────────────────────────────────────────────────────────

@click.group()
def root():
    """Root device via boot.img patching (Magisk method)."""
    pass


@root.command("patch")
@click.option("--boot",   "-b", default=None, help="Local boot.img path (or dumps from device)")
@click.option("--serial", "-s", default=None)
@click.option("--flash",  "-f", "do_flash", is_flag=True,
              help="Auto-flash patched boot.img after patching")
@click.option("--out",    "-o", default=None, help="Save patched image to path")
def root_patch(boot, serial, do_flash, out):
    """
    Patch boot.img with Magisk for root access.

    Workflow:
      1. Dump stock boot.img from device (or use --boot <path>)
      2. Push to device, invoke Magisk boot_patch.sh
      3. Pull patched boot.img back
      4. Optionally flash via fastboot
    """
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device online.[/red]")
        return

    target = serial or online[0]
    props = get_device_props(target)
    vendor, chipset = detect_chipset_from_props(props)
    console.print(f"[bold]Device:[/bold] {target}  [dim]({vendor.upper()} / {chipset})[/dim]")

    # 1. Get boot.img
    if boot:
        boot_path = Path(boot)
        if not boot_path.exists():
            console.print(f"[red]✗ Boot image not found: {boot}[/red]")
            return
    else:
        console.print("[cyan]→ Dumping stock boot.img from device...[/cyan]")
        from modules.partition import dump_partition_adb
        boot_path = WORKSPACE / f"boot_stock_{target}.img"
        if not dump_partition_adb("boot", boot_path, serial=target):
            console.print("[red]✗ Could not dump boot.img. Use --boot <path> to provide it.[/red]")
            return

    hdr = parse_android_image_header(boot_path)
    console.print(f"  [dim]Boot image: {hdr['magic']} | v{hdr['version']} | {hdr['size']:.1f} MB[/dim]")

    # 2. Patch
    try:
        patched = magisk_patch_boot(boot_path, serial=target)
    except Exception as e:
        console.print(f"[red]✗ Patching failed: {e}[/red]")
        return

    # 3. Save
    if out:
        dst = Path(out)
        import shutil as sh
        sh.copy(patched, dst)
        console.print(f"[green]✓ Saved patched image: {dst}[/green]")
    else:
        out_path = OUTPUT_DIR / target / "boot_magisk_patched.img"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        import shutil as sh
        sh.copy(patched, out_path)
        console.print(f"[green]✓ Patched image: {out_path}[/green]")
        patched = out_path

    # 4. Flash
    if do_flash or click.confirm("\n[yellow]Flash patched boot.img to device now?[/yellow]", default=False):
        _flash_boot(patched, target, vendor)


def _flash_boot(patched_img: Path, serial: str, vendor: str):
    """Flash patched boot.img via fastboot or ADB dd."""
    console.print(f"\n[cyan]→ Rebooting to bootloader/fastboot...[/cyan]")
    run_adb(["reboot", "bootloader"], serial=serial, check=False)
    import time; time.sleep(5)

    from modules import fastboot_devices
    fb = fastboot_devices()
    if fb:
        fb_serial = serial if serial in fb else fb[0]
        console.print(f"[cyan]→ Flashing boot via fastboot...[/cyan]")
        rc, _, err = run_fastboot(["flash", "boot", str(patched_img)], serial=fb_serial, check=False)
        if rc == 0:
            console.print("[green]✓ Boot flashed successfully![/green]")
            run_fastboot(["reboot"], serial=fb_serial, check=False)
            console.print("[green]✓ Device rebooting...[/green]")
        else:
            console.print(f"[red]✗ Fastboot flash failed: {err}[/red]")
    else:
        console.print("[yellow]! Fastboot device not found. Use 'watchrom flash boot <patched.img>' manually.[/yellow]")


@root.command("check")
@click.option("--serial", "-s", default=None)
def root_check(serial):
    """Check if device is rooted."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device online.[/red]")
        return
    target = serial or online[0]

    checks = {
        "su binary":      "which su 2>/dev/null || echo MISSING",
        "uid=0 check":    "su -c id 2>/dev/null || echo FAILED",
        "Magisk (official)": f"pm path {MAGISK_PKG_OFFICIAL} 2>/dev/null || echo NOT_FOUND",
        "Magisk (delta)":    f"pm path {MAGISK_PKG} 2>/dev/null || echo NOT_FOUND",
        "magiskd running":   "pgrep -f magiskd 2>/dev/null || echo NOT_RUNNING",
        "/sbin/.magisk":     "ls /sbin/.magisk 2>/dev/null || echo MISSING",
    }
    console.print(f"\n[bold cyan]Root Check — {target}[/bold cyan]\n")
    rooted = False
    for name, cmd in checks.items():
        _, out, _ = run_adb(["shell", cmd], serial=target, check=False)
        out = out.strip()
        ok = "MISSING" not in out and "NOT_FOUND" not in out and "FAILED" not in out and out
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        console.print(f"  {status} {name:30s} {out[:60]}")
        if ok and "uid=0" in out:
            rooted = True

    console.print(f"\n[bold]Root Status:[/bold] [{'green]ROOTED' if rooted else 'red]NOT ROOTED'}[/{'green' if rooted else 'red'}]")
