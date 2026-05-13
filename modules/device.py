"""
device.py — Device detection, info display, and chipset identification
"""
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from modules import (
    adb_devices, fastboot_devices, get_device_props,
    detect_chipset_from_props, run_adb, run_fastboot,
    PARTITION_MAPS, console
)

@click.group()
def device():
    """Device detection and information commands."""
    pass


@device.command("info")
@click.option("--serial", "-s", default=None, help="ADB serial (for multi-device setups)")
def device_info(serial):
    """Detect connected device, chipset vendor, and partition layout."""

    # ── ADB devices ────────────────────────────────────────────────────────────
    adb_list = adb_devices()
    fb_list  = fastboot_devices()

    console.print(Panel("[bold cyan]WatchROM — Device Detection[/bold cyan]", expand=False))

    if not adb_list and not fb_list:
        console.print("[red]✗ No devices found via ADB or Fastboot.[/red]")
        console.print("[dim]  → Enable USB debugging, connect cable, and accept RSA prompt.[/dim]")
        return

    if adb_list:
        t = Table(title="ADB Devices", box=box.SIMPLE_HEAVY, border_style="cyan")
        t.add_column("Serial",  style="green")
        t.add_column("State",   style="yellow")
        for serial_id, state in adb_list:
            t.add_row(serial_id, state)
        console.print(t)

    if fb_list:
        t = Table(title="Fastboot Devices", box=box.SIMPLE_HEAVY, border_style="magenta")
        t.add_column("Serial", style="green")
        for serial_id in fb_list:
            t.add_row(serial_id)
        console.print(t)

    # ── Full device info via ADB ───────────────────────────────────────────────
    online = [s for s, st in adb_list if st == "device"]
    if not online:
        console.print("[yellow]Device not in ADB mode — limited info available.[/yellow]")
        return

    target = serial or online[0]
    console.print(f"\n[bold]Probing device:[/bold] [green]{target}[/green]\n")

    props = get_device_props(target)

    vendor, chipset = detect_chipset_from_props(props)
    partition_list  = PARTITION_MAPS.get(vendor, PARTITION_MAPS["unknown"])

    # Enrich chip info from full database
    try:
        from modules.chipsets import identify_chip_universal
        platform = props.get("ro.board.platform", props.get("ro.hardware",""))
        chip_info = identify_chip_universal(platform)
        if chip_info.get("vendor","unknown") != "unknown" and vendor == "unknown":
            vendor = chip_info["vendor"]
            chipset = chip_info["key"]
            partition_list = PARTITION_MAPS.get(vendor, PARTITION_MAPS["unknown"])
    except Exception:
        pass

    # ── Identity table ─────────────────────────────────────────────────────────
    id_table = Table(box=box.ROUNDED, border_style="cyan", show_header=False, padding=(0,1))
    id_table.add_column("Key",   style="bold magenta", width=30)
    id_table.add_column("Value", style="white")

    fields = [
        ("Brand",            props.get("ro.product.brand", "?")),
        ("Model",            props.get("ro.product.model", "?")),
        ("Device",           props.get("ro.product.device", "?")),
        ("Android Version",  props.get("ro.build.version.release", "?")),
        ("API Level",        props.get("ro.build.version.sdk", "?")),
        ("Security Patch",   props.get("ro.build.version.security_patch", "?")),
        ("Board Platform",   props.get("ro.board.platform", "?")),
        ("Hardware",         props.get("ro.hardware", "?")),
        ("Chipset (detected)", f"[bold yellow]{chipset}[/bold yellow] ([cyan]{vendor.upper()}[/cyan])"),
        ("Flash Mode",       {
            "mtk":       "[dim]SP Flash Tool / MTK Client (BROM)[/dim]",
            "unisoc":    "[dim]UpgradeDownload / SPD Tool (FDL)[/dim]",
            "rockchip":  "[dim]rkdeveloptool / RKDevTool (MaskROM)[/dim]",
            "allwinner": "[dim]sunxi-fel / PhoenixSuit (FEL)[/dim]",
            "realtek":   "[dim]Rescue Mode / rtd-flash (USB)[/dim]",
        }.get(vendor, "[dim]fastboot / ADB[/dim]")),
        ("Build Fingerprint", props.get("ro.build.fingerprint", "?")),
        ("ABI",              props.get("ro.product.cpu.abi", "?")),
        ("Treble Enabled",   props.get("ro.treble.enabled", "false")),
        ("Verified Boot",    props.get("ro.boot.verifiedbootstate", "?")),
        ("AVB Version",      props.get("ro.boot.avb_version", "?")),
        ("dm-verity",        props.get("ro.boot.veritymode", "?")),
        ("Encryption",       props.get("ro.crypto.state", "?")),
        ("Bootloader",       props.get("ro.bootloader", "?")),
        ("Serial Number",    props.get("ro.serialno", target)),
    ]
    for k, v in fields:
        id_table.add_row(k, v)

    console.print(id_table)

    # ── Partition probe ────────────────────────────────────────────────────────
    console.print(f"\n[bold cyan]Probing partitions for {vendor.upper()} device...[/bold cyan]\n")

    part_table = Table(box=box.SIMPLE, border_style="dim", show_header=True,
                       header_style="bold magenta")
    part_table.add_column("Partition",  style="green",  width=20)
    part_table.add_column("Device Node", style="cyan", width=30)
    part_table.add_column("Found", style="white", width=8)

    found_partitions = {}
    for part in partition_list:
        # Try /dev/block/by-name/ (most modern Android)
        _, out, _ = run_adb(
            ["shell", f"ls /dev/block/by-name/{part} 2>/dev/null || echo MISSING"],
            serial=target, check=False
        )
        out = out.strip()
        found = "MISSING" not in out
        node  = out if found else "—"
        found_partitions[part] = (found, node)
        status = "[green]✓[/green]" if found else "[red]✗[/red]"
        part_table.add_row(part, node, status)

    console.print(part_table)

    # ── Bootloader lock state ──────────────────────────────────────────────────
    # Note: We use ONLY "getvar unlocked" here. "getvar all" is known to HANG
    # indefinitely on Xiaomi, OnePlus, and Motorola devices. See XDA consensus.
    _, fb_out, _ = run_fastboot(["getvar", "unlocked"], serial=target, check=False)
    lock_state = "unknown"
    for line in fb_out.splitlines():
        if "unlocked" in line.lower():
            lock_state = "UNLOCKED" if "yes" in line.lower() else "LOCKED"
            break

    console.print(f"\n[bold]Bootloader:[/bold] [{'green' if lock_state == 'UNLOCKED' else 'red'}]{lock_state}[/{'green' if lock_state == 'UNLOCKED' else 'red'}]")

    # ── Root check ────────────────────────────────────────────────────────────
    _, root_out, _ = run_adb(["shell", "su -c id 2>/dev/null || echo NOROOT"],
                              serial=target, check=False)
    rooted = "uid=0" in root_out
    console.print(f"[bold]Root:[/bold] [{'green' if rooted else 'red'}]{'YES (uid=0)' if rooted else 'NOT ROOTED'}[/{'green' if rooted else 'red'}]")

    console.print(f"\n[dim]Vendor: {vendor.upper()} | Chip: {chipset} | Partitions detected: {sum(1 for f,_ in found_partitions.values() if f)}/{len(partition_list)}[/dim]")


@device.command("reboot")
@click.argument("mode", type=click.Choice(["system","recovery","bootloader","fastboot","edl"]))
@click.option("--serial", "-s", default=None)
def device_reboot(mode, serial):
    """Reboot device into a specific mode."""
    mode_map = {
        "system":     ["adb", "reboot"],
        "recovery":   ["adb", "reboot", "recovery"],
        "bootloader": ["adb", "reboot", "bootloader"],
        "fastboot":   ["adb", "reboot", "fastboot"],
        "edl":        ["adb", "reboot", "edl"],
    }
    cmd = mode_map[mode]
    if serial:
        cmd = cmd[:1] + ["-s", serial] + cmd[1:]

    console.print(f"[cyan]Rebooting to [bold]{mode}[/bold]...[/cyan]")
    from modules import run
    rc, _, _ = run(cmd, check=False)
    if rc == 0:
        console.print(f"[green]✓ Reboot command sent.[/green]")
    else:
        console.print(f"[red]✗ Reboot failed (device may have disconnected).[/red]")


@device.command("wait")
@click.option("--serial", "-s", default=None)
def device_wait(serial):
    """Wait for device to come online (ADB)."""
    console.print("[cyan]Waiting for device...[/cyan]")
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += ["wait-for-device"]
    from modules import run
    run(cmd, capture=False, check=False, timeout=120)
    console.print("[green]✓ Device online.[/green]")
