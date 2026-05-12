"""
rk_aw_rtk.py — Rockchip, Allwinner, Realtek chipset CLI commands
Full MaskROM / FEL / Rescue mode support, chip identification,
partition management, and flashing tool guidance
"""
import click
import shutil
import subprocess
from pathlib import Path
from modules import (
    run, run_adb, adb_devices, get_device_props,
    OUTPUT_DIR, WORKSPACE, console, tool_available, file_size_mb, sha256_file
)
from modules.chipsets import (
    ROCKCHIP_CHIPS, ROCKCHIP_PARTITIONS, ROCKCHIP_SIGNATURES,
    ALLWINNER_CHIPS,  ALLWINNER_PARTITIONS,
    REALTEK_CHIPS,    REALTEK_PARTITIONS,
    identify_rockchip_chip, identify_allwinner_chip, identify_realtek_chip,
    identify_chip_universal, get_partition_list, get_flash_tool_info,
)

REPOS_DIR = Path(__file__).resolve().parent.parent.parent / "watchrom_repos"


# ═══════════════════════════════════════════════════════════════════════════════
# ROCKCHIP
# ═══════════════════════════════════════════════════════════════════════════════

@click.group()
def rockchip():
    """Rockchip chipset commands — PX30, RK3288 through RK3588S."""
    pass


@rockchip.command("list")
@click.option("--type", "-t", "chip_type", default=None,
              help="Filter by type: tablet, tv_box, sbc, auto, gaming, iot")
def rk_list(chip_type):
    """List all supported Rockchip chipsets."""
    from rich.table import Table
    from rich import box as rbox
    t = Table(title="Supported Rockchip Chipsets",
              box=rbox.ROUNDED, border_style="cyan")
    t.add_column("Chip",     style="bold green", width=12)
    t.add_column("Name",     style="white",      width=24)
    t.add_column("Arch",     style="yellow",     width=7)
    t.add_column("Year",     style="dim",        width=6)
    t.add_column("Type",     style="cyan",       width=14)
    t.add_column("MaskROM",  style="magenta",    width=9)
    t.add_column("Notes",    style="dim",        width=30)
    for key, info in sorted(ROCKCHIP_CHIPS.items(), key=lambda x: x[1]["year"]):
        if chip_type and chip_type not in info.get("type",""):
            continue
        t.add_row(
            key, info["name"], info["arch"], str(info["year"]),
            info.get("type",""), 
            "[green]✓[/green]" if info.get("maskrom") else "[dim]—[/dim]",
            info.get("notes","")[:30],
        )
    console.print(t)


@rockchip.command("identify")
@click.option("--serial", "-s", default=None)
def rk_identify(serial):
    """Detect Rockchip chipset and show full hardware info."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]
    props = get_device_props(target)
    platform = props.get("ro.board.platform", props.get("ro.hardware",""))
    chip = identify_rockchip_chip(platform)

    console.print(f"\n[bold cyan]Rockchip Device Info — {target}[/bold cyan]\n")
    if chip:
        console.print(f"  [bold green]Detected:[/bold green] {chip.get('name','?')}")
        console.print(f"  Architecture  : {chip.get('arch','?')}")
        console.print(f"  Type          : {chip.get('type','?')}")
        console.print(f"  MaskROM       : {'[green]Yes — full dump possible[/green]' if chip.get('maskrom') else 'Unknown'}")
        console.print(f"  Notes         : {chip.get('notes','')}")
    else:
        console.print(f"  [yellow]! Could not auto-detect Rockchip chip[/yellow]")
        console.print(f"  Platform string: {platform}")

    # Key props
    rk_props = [
        "ro.board.platform","ro.hardware","ro.product.board",
        "ro.boot.hardware","ro.chip.id","hw.board.hardware",
    ]
    console.print()
    for k in rk_props:
        v = props.get(k,"")
        if v:
            console.print(f"  [cyan]{k}[/cyan] = {v}")

    _, cpu_out, _ = run_adb(["shell", "cat /proc/cpuinfo | head -20"],
                             serial=target, check=False)
    console.print(f"\n  [bold]CPU Info:[/bold]\n{cpu_out.strip()[:400]}")

    # Partition layout
    ab = props.get("ro.build.ab_update","false") == "true"
    parts = get_partition_list("rockchip", ab)
    console.print(f"\n  [bold]Partition layout ({('A/B' if ab else 'standard')}):[/bold]")
    console.print(f"  [dim]{' '.join(parts[:10])}...[/dim]")

    tool = get_flash_tool_info("rockchip")
    console.print(f"\n  [bold]Flash tool :[/bold] {tool['primary']}")
    console.print(f"  [bold]Mode       :[/bold] {tool['mode']}")
    console.print(f"  [bold]USB VID    :[/bold] {tool['usb_vid']}")


@rockchip.command("download")
@click.option("--serial", "-s", default=None)
def rk_download(serial):
    """
    Enter Rockchip MaskROM mode for flashing.

    Works with: ALL Rockchip chips (RK3126 through RK3588S, PX30, PX5, PX6)
    """
    console.print("\n[bold cyan]Rockchip MaskROM / Download Mode[/bold cyan]\n")

    console.print("[bold yellow]Method 1 — Recovery button + USB:[/bold yellow]")
    console.print("  1. Power off device completely")
    console.print("  2. Hold [Recovery] button (or Vol-)")
    console.print("  3. Connect USB cable to PC while holding")
    console.print("  4. Release after 3 seconds")
    console.print("  5. Device appears as 'Rockchip' in rkdeveloptool\n")

    console.print("[bold yellow]Method 2 — MaskROM test point (no OS needed):[/bold yellow]")
    console.print("  1. Locate MaskROM pads on PCB (usually near eMMC)")
    console.print("  2. Short the two MaskROM pads with tweezers/wire")
    console.print("  3. While shorted, connect USB to PC")
    console.print("  4. Release — device enters MaskROM mode")
    console.print("  Linux check: [dim]lsusb | grep 2207[/dim]\n")

    console.print("[bold yellow]Method 3 — ADB reboot (if OS is running):[/bold yellow]")
    console.print("  adb reboot loader\n")

    console.print("[bold yellow]Flashing Tools:[/bold yellow]")
    console.print("  Linux  : [bold]rkdeveloptool[/bold] or [bold]upgrade_tool[/bold]")
    console.print("  Windows: [bold]RKDevTool[/bold] (AndroidTool)")
    console.print("  Both   : [bold]rkflashtool[/bold] (open source)\n")

    console.print("[bold yellow]Common rkdeveloptool commands:[/bold yellow]")
    console.print("  rkdeveloptool ld                          # list devices")
    console.print("  rkdeveloptool db loader.bin               # download boot (init)")
    console.print("  rkdeveloptool wl 0 update.img             # flash full image")
    console.print("  rkdeveloptool ul loader.bin               # upload loader")
    console.print("  rkdeveloptool ppt                         # print partition table")
    console.print("  rkdeveloptool read 0 0x2000 dump.bin      # dump sectors\n")

    # Check rkdeveloptool
    if tool_available("rkdeveloptool"):
        console.print("[green]✓ rkdeveloptool is installed[/green]")
        rc, out, _ = run(["rkdeveloptool", "ld"], check=False)
        if out.strip():
            console.print(f"  Detected devices:\n{out}")
    else:
        console.print("[yellow]! rkdeveloptool not found[/yellow]")
        console.print("  Install: sudo apt install rkdeveloptool")
        console.print("  OR: git clone https://github.com/rockchip-linux/rkdeveloptool\n")

    # Check rkflashtool
    rk_repo = REPOS_DIR / "rkdeveloptool"
    if rk_repo.exists():
        console.print(f"[dim]  rkdeveloptool source: {rk_repo}[/dim]")

    # Try ADB reboot
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if online:
        target = serial or online[0]
        if click.confirm(f"\n  Reboot {target} to loader/MaskROM now?"):
            rc, _, _ = run_adb(["reboot", "loader"], serial=target, check=False)
            if rc != 0:
                run_adb(["reboot", "bootloader"], serial=target, check=False)
            console.print("[green]✓ Reboot command sent.[/green]")


@rockchip.command("dump")
@click.argument("partition")
@click.option("--out", "-o", default=None)
@click.option("--serial", "-s", default=None)
def rk_dump(partition, out, serial):
    """
    Dump a partition via rkdeveloptool (MaskROM mode) or ADB.
    """
    out_path = Path(out) if out else (OUTPUT_DIR / f"rk_{partition}.img")

    # Try ADB first
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if online:
        target = serial or online[0]
        from modules.partition import dump_partition_adb
        console.print(f"[cyan]→ Dumping {partition} via ADB...[/cyan]")
        if dump_partition_adb(partition, out_path, serial=target):
            console.print(f"[green]✓ {out_path}[/green]")
            return

    # Fallback to rkdeveloptool
    if tool_available("rkdeveloptool"):
        console.print(f"[cyan]→ Trying rkdeveloptool...[/cyan]")
        console.print("[dim]  Device must be in MaskROM mode.[/dim]")
        rc, ppt_out, _ = run(["rkdeveloptool", "ppt"], check=False)
        if rc == 0:
            console.print(f"[dim]{ppt_out[:300]}[/dim]")
    else:
        console.print("[red]✗ No dump method available. Connect device or install rkdeveloptool.[/red]")


@rockchip.command("flash")
@click.argument("image")
@click.option("--partition", "-p", default=None, help="Partition to flash (or full image)")
@click.option("--loader", "-l", default=None, help="Loader .bin for MaskROM init")
def rk_flash(image, partition, loader):
    """
    Flash image to Rockchip device via rkdeveloptool (MaskROM mode).
    """
    img = Path(image)
    if not img.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return

    console.print(f"\n[bold cyan]Rockchip Flash — {img.name}[/bold cyan]")
    console.print(f"  Size  : {file_size_mb(img):.1f} MB")
    console.print(f"  SHA256: {sha256_file(img)[:32]}…\n")

    if not tool_available("rkdeveloptool"):
        console.print("[red]✗ rkdeveloptool not found.[/red]")
        console.print("  Install: sudo apt install rkdeveloptool")
        console.print("  Fallback: use RKDevTool on Windows with update.img\n")
        console.print("[bold]Manual steps:[/bold]")
        console.print(f"  1. Enter MaskROM mode")
        console.print(f"  2. rkdeveloptool db <loader.bin>")
        if partition:
            console.print(f"  3. rkdeveloptool wlx {partition} {img}")
        else:
            console.print(f"  3. rkdeveloptool wl 0 {img}")
        return

    if not click.confirm("  Device must be in MaskROM mode. Continue?", default=False):
        return

    if loader:
        console.print(f"[cyan]→ Initializing with loader...[/cyan]")
        run(["rkdeveloptool", "db", loader], check=False)

    if partition:
        rc, _, err = run(["rkdeveloptool", "wlx", partition, str(img)], check=False)
    else:
        rc, _, err = run(["rkdeveloptool", "wl", "0", str(img)], check=False)

    if rc == 0:
        console.print(f"[green]✓ Flash complete.[/green]")
        run(["rkdeveloptool", "rd"], check=False)  # reboot device
    else:
        console.print(f"[red]✗ Flash failed: {err}[/red]")


@rockchip.command("partition-table")
@click.option("--chip", "-c", default=None, help="Chip model (e.g. RK3568)")
@click.option("--ab",   is_flag=True, help="A/B partition layout")
def rk_partition_table(chip, ab):
    """Show Rockchip partition layout for a chip."""
    layout = "ab" if ab else "gpt"
    parts  = ROCKCHIP_PARTITIONS[layout]
    console.print(f"\n[bold cyan]Rockchip Partition Layout ({layout.upper()})[/bold cyan]\n")
    for i, p in enumerate(parts):
        console.print(f"  [green]{i+1:2d}.[/green] [cyan]{p}[/cyan]")


# ═══════════════════════════════════════════════════════════════════════════════
# ALLWINNER
# ═══════════════════════════════════════════════════════════════════════════════

@click.group()
def allwinner():
    """Allwinner chipset commands — A10/A20/H3/H6/H616/A64/R818 and more."""
    pass


@allwinner.command("list")
@click.option("--type", "-t", "chip_type", default=None,
              help="Filter: tablet, tv_box, sbc, auto, iot, watch")
def aw_list(chip_type):
    """List all supported Allwinner chipsets."""
    from rich.table import Table
    from rich import box as rbox
    t = Table(title="Supported Allwinner Chipsets",
              box=rbox.ROUNDED, border_style="yellow")
    t.add_column("Chip",    style="bold green", width=10)
    t.add_column("Name",    style="white",      width=22)
    t.add_column("Platform",style="dim",        width=10)
    t.add_column("Arch",    style="yellow",     width=7)
    t.add_column("Year",    style="dim",        width=6)
    t.add_column("Type",    style="cyan",       width=14)
    t.add_column("FEL",     style="magenta",    width=5)
    for key, info in sorted(ALLWINNER_CHIPS.items(), key=lambda x: x[1]["year"]):
        if chip_type and chip_type not in info.get("type",""):
            continue
        t.add_row(
            key, info["name"], info["platform"], info["arch"],
            str(info["year"]), info.get("type",""),
            "[green]✓[/green]" if info.get("fel") else "[dim]—[/dim]",
        )
    console.print(t)


@allwinner.command("identify")
@click.option("--serial", "-s", default=None)
def aw_identify(serial):
    """Detect Allwinner chipset and show hardware info."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]
    props = get_device_props(target)
    platform = props.get("ro.board.platform", props.get("ro.hardware",""))
    chip = identify_allwinner_chip(platform)

    console.print(f"\n[bold cyan]Allwinner Device Info — {target}[/bold cyan]\n")
    if chip:
        console.print(f"  [bold green]Detected:[/bold green] {chip.get('name','?')}")
        console.print(f"  Platform      : {chip.get('platform','?')}")
        console.print(f"  Architecture  : {chip.get('arch','?')}")
        console.print(f"  Type          : {chip.get('type','?')}")
        console.print(f"  FEL mode      : {'[green]Yes[/green]' if chip.get('fel') else 'Unknown'}")
        console.print(f"  Notes         : {chip.get('notes','')}")
    else:
        console.print(f"  [yellow]! Could not auto-detect Allwinner chip[/yellow]")
        console.print(f"  Platform: {platform}")

    aw_props = [
        "ro.board.platform","ro.hardware","ro.product.board",
        "ro.boot.hardware","ro.arch",
    ]
    console.print()
    for k in aw_props:
        v = props.get(k,"")
        if v:
            console.print(f"  [cyan]{k}[/cyan] = {v}")

    _, cpu_out, _ = run_adb(["shell", "cat /proc/cpuinfo | head -15"],
                             serial=target, check=False)
    console.print(f"\n  [bold]CPU Info:[/bold]\n{cpu_out.strip()[:300]}")

    tool = get_flash_tool_info("allwinner")
    console.print(f"\n  [bold]Flash tool:[/bold] {tool['primary']}")
    console.print(f"  [bold]Mode       :[/bold] {tool['mode']}")
    console.print(f"  [bold]USB VID    :[/bold] {tool['usb_vid']}")


@allwinner.command("download")
@click.option("--serial", "-s", default=None)
def aw_download(serial):
    """
    Enter Allwinner FEL mode for flashing/dumping.

    Works with: A10, A13, A20, A23, A33, A64, H3, H5, H6, H616, H618,
                A100, A133, R818, T507, and all other Allwinner SoCs.
    """
    console.print("\n[bold cyan]Allwinner FEL Mode[/bold cyan]\n")
    console.print("[bold yellow]What is FEL?[/bold yellow]")
    console.print("  FEL (Flashing/Emergency Load) is Allwinner's built-in")
    console.print("  USB boot ROM mode — works on every Allwinner chip.")
    console.print("  USB VID: 0x1F3A  PID: 0xEFE8\n")

    console.print("[bold yellow]Method 1 — FEL button (many dev boards/tablets):[/bold yellow]")
    console.print("  1. Hold the [FEL] button on the board")
    console.print("  2. Connect USB OTG port to PC")
    console.print("  3. Release button — device is now in FEL\n")

    console.print("[bold yellow]Method 2 — No FEL button (tablets/TV boxes):[/bold yellow]")
    console.print("  1. Short NAND/eMMC data pin to GND (prevents normal boot)")
    console.print("  2. OR: remove SD card and eMMC has no boot code → auto-FEL")
    console.print("  3. Hold Vol- or Recovery during power-on\n")

    console.print("[bold yellow]Method 3 — SD card trick:[/bold yellow]")
    console.print("  1. Write a FEL-mode SD image:")
    console.print("     dd if=/dev/zero bs=1M count=1 | dd of=fel.img")
    console.print("     (blank SD with no valid boot code → device falls to FEL)")
    console.print("  2. Boot from that SD card\n")

    console.print("[bold yellow]Method 4 — ADB (if device is running):[/bold yellow]")
    console.print("  adb reboot efex\n")

    console.print("[bold yellow]sunxi-fel commands (Linux):[/bold yellow]")
    console.print("  sunxi-fel version                   # detect device")
    console.print("  sunxi-fel sid                       # read SoC ID")
    console.print("  sunxi-fel spl u-boot-sunxi-with-spl.bin  # boot SPL+u-boot")
    console.print("  sunxi-fel -p write 0x4a000000 image.img  # upload image")
    console.print("  sunxi-fel read  0x4a000000 0x400000 dump.bin  # dump\n")

    console.print("[bold yellow]PhoenixSuit / LiveSuit (Windows):[/bold yellow]")
    console.print("  1. Install PhoenixSuit")
    console.print("  2. Load firmware .img file")
    console.print("  3. Connect device in FEL mode")
    console.print("  4. Click 'Download' or 'Upgrade'\n")

    # Check sunxi-fel
    if tool_available("sunxi-fel"):
        console.print("[green]✓ sunxi-fel is installed[/green]")
        rc, out, _ = run(["sunxi-fel", "version"], check=False)
        if out.strip():
            console.print(f"  {out.strip()}")
    else:
        console.print("[yellow]! sunxi-fel not found[/yellow]")
        console.print("  Install: sudo apt install sunxi-tools")
        console.print("  OR: https://github.com/linux-sunxi/sunxi-tools\n")

    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if online:
        target = serial or online[0]
        if click.confirm("\n  Try 'adb reboot efex' on connected device?"):
            run_adb(["reboot", "efex"], serial=target, check=False)
            console.print("[green]✓ Reboot command sent.[/green]")


@allwinner.command("dump-sid")
def aw_dump_sid():
    """Read Allwinner SoC SID (unique chip ID) via sunxi-fel."""
    if not tool_available("sunxi-fel"):
        console.print("[red]✗ sunxi-fel not found. Install: sudo apt install sunxi-tools[/red]")
        return
    console.print("[cyan]→ Reading SID (device must be in FEL mode)...[/cyan]")
    rc, out, err = run(["sunxi-fel", "sid"], check=False)
    if rc == 0:
        console.print(f"[green]SID:[/green] {out.strip()}")
    else:
        console.print(f"[red]✗ {err[:200]}[/red]")


@allwinner.command("flash")
@click.argument("image")
@click.option("--method", "-m",
              type=click.Choice(["sunxi-fel","phoenixsuit","livesuit","dd"]),
              default="sunxi-fel")
@click.option("--address", "-a", default="0x4a000000", help="Memory address for FEL upload")
def aw_flash(image, method, address):
    """Flash an image to Allwinner device."""
    img = Path(image)
    if not img.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return

    console.print(f"\n[bold cyan]Allwinner Flash — {img.name}[/bold cyan]")
    console.print(f"  Size  : {file_size_mb(img):.1f} MB  |  Method: {method}\n")

    if method == "sunxi-fel":
        if not tool_available("sunxi-fel"):
            console.print("[red]✗ sunxi-fel not found.[/red]")
            return
        console.print("[cyan]→ Uploading via sunxi-fel FEL mode...[/cyan]")
        rc, _, err = run(["sunxi-fel", "-p", "write", address, str(img)], check=False, timeout=300)
        if rc == 0:
            console.print("[green]✓ Upload complete.[/green]")
        else:
            console.print(f"[red]✗ {err}[/red]")
    else:
        console.print(f"\n[bold]{method} instructions:[/bold]")
        console.print(f"  1. Open {method}")
        console.print(f"  2. Load firmware: {img}")
        console.print(f"  3. Connect device in FEL mode")
        console.print(f"  4. Click Upgrade/Flash")


@allwinner.command("partition-table")
@click.option("--storage", "-s",
              type=click.Choice(["emmc","nand","ab"]), default="emmc")
def aw_partition_table(storage):
    """Show Allwinner partition layout."""
    parts = ALLWINNER_PARTITIONS[storage]
    console.print(f"\n[bold cyan]Allwinner Partition Layout ({storage.upper()})[/bold cyan]\n")
    for i, p in enumerate(parts):
        console.print(f"  [green]{i+1:2d}.[/green] [cyan]{p}[/cyan]")


# ═══════════════════════════════════════════════════════════════════════════════
# REALTEK
# ═══════════════════════════════════════════════════════════════════════════════

@click.group()
def realtek():
    """Realtek chipset commands — RTD1195 through RTD1619B media/TV SoCs."""
    pass


@realtek.command("list")
def rtk_list():
    """List all supported Realtek chipsets."""
    from rich.table import Table
    from rich import box as rbox
    t = Table(title="Supported Realtek Chipsets",
              box=rbox.ROUNDED, border_style="red")
    t.add_column("Chip",    style="bold green", width=12)
    t.add_column("Name",    style="white",      width=24)
    t.add_column("Platform",style="dim",        width=10)
    t.add_column("Arch",    style="yellow",     width=7)
    t.add_column("Year",    style="dim",        width=6)
    t.add_column("Type",    style="cyan",       width=10)
    t.add_column("Notes",   style="dim",        width=30)
    for key, info in sorted(REALTEK_CHIPS.items(), key=lambda x: x[1]["year"]):
        t.add_row(
            key, info["name"], info["platform"], info["arch"],
            str(info["year"]), info.get("type",""),
            info.get("notes","")[:30],
        )
    console.print(t)


@realtek.command("identify")
@click.option("--serial", "-s", default=None)
def rtk_identify(serial):
    """Detect Realtek chipset and show hardware info."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]
    props = get_device_props(target)
    platform = props.get("ro.board.platform", props.get("ro.hardware",""))
    chip = identify_realtek_chip(platform)

    console.print(f"\n[bold cyan]Realtek Device Info — {target}[/bold cyan]\n")
    if chip:
        console.print(f"  [bold green]Detected:[/bold green] {chip.get('name','?')}")
        console.print(f"  Architecture : {chip.get('arch','?')}")
        console.print(f"  Type         : {chip.get('type','?')}")
        console.print(f"  Notes        : {chip.get('notes','')}")
    else:
        console.print(f"  [yellow]! Could not auto-detect Realtek chip[/yellow]")

    rtk_props = [
        "ro.board.platform","ro.hardware","ro.product.board",
        "ro.chip.model","ro.build.description",
    ]
    console.print()
    for k in rtk_props:
        v = props.get(k,"")
        if v:
            console.print(f"  [cyan]{k}[/cyan] = {v}")

    tool = get_flash_tool_info("realtek")
    console.print(f"\n  [bold]Flash tool:[/bold] {tool['primary']}")
    console.print(f"  [bold]Mode       :[/bold] {tool['mode']}")


@realtek.command("download")
@click.option("--serial", "-s", default=None)
def rtk_download(serial):
    """
    Enter Realtek Rescue mode for flashing.

    Works with: RTD1195, RTD1295, RTD1296, RTD1312, RTD1319,
                RTD1395, RTD1619, RTD1619B
    """
    console.print("\n[bold cyan]Realtek Rescue Mode[/bold cyan]\n")
    console.print("[bold yellow]What is Rescue mode?[/bold yellow]")
    console.print("  Realtek devices have a built-in 'Rescue' ROM that allows")
    console.print("  full reflashing via USB or Ethernet when triggered.\n")

    console.print("[bold yellow]Method 1 — Rescue button:[/bold yellow]")
    console.print("  1. Locate the 'Rescue' button on the device (often recessed)")
    console.print("  2. Hold Rescue button while powering on")
    console.print("  3. Device enters rescue mode — LED may blink or change color\n")

    console.print("[bold yellow]Method 2 — USB OTG rescue:[/bold yellow]")
    console.print("  1. Connect device to PC via USB OTG while holding rescue")
    console.print("  2. Device appears as 'Realtek Semiconductor' USB device")
    console.print("  3. Use RTD1xxx USB flashing tool to write rescue.img\n")

    console.print("[bold yellow]Method 3 — Ethernet rescue (RTD1295/1619):[/bold yellow]")
    console.print("  1. Connect Ethernet cable to device")
    console.print("  2. Configure TFTP server on PC")
    console.print("  3. Hold rescue button, power on — device fetches from TFTP")
    console.print("  4. TFTP server: sudo apt install tftpd-hpa\n")

    console.print("[bold yellow]Flashing with rtd-flash tool:[/bold yellow]")
    console.print("  git clone https://github.com/jrior001/rtd-flash")
    console.print("  python3 rtd-flash.py install.img\n")

    console.print("[bold yellow]USB ID in rescue mode:[/bold yellow]")
    console.print("  VID: 0x0BDA  PID: varies by model")
    console.print("  Linux check: [dim]lsusb | grep 0bda[/dim]\n")

    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if online:
        target = serial or online[0]
        if click.confirm("\n  Reboot device for rescue access?"):
            run_adb(["reboot", "recovery"], serial=target, check=False)
            console.print("[green]✓ Reboot command sent — hold Rescue button immediately![/green]")


@realtek.command("partition-table")
@click.option("--type", "-t",
              type=click.Choice(["standard","android_tv"]), default="android_tv")
def rtk_partition_table(type):
    """Show Realtek partition layout."""
    parts = REALTEK_PARTITIONS[type]
    console.print(f"\n[bold cyan]Realtek Partition Layout ({type})[/bold cyan]\n")
    for i, p in enumerate(parts):
        console.print(f"  [green]{i+1:2d}.[/green] [cyan]{p}[/cyan]")


@realtek.command("extract-rescue")
@click.argument("rescue_img")
@click.option("--out", "-o", default=None)
def rtk_extract_rescue(rescue_img, out):
    """
    Extract a Realtek rescue/install image to inspect its contents.
    These images are often squashfs or ext4 inside a custom wrapper.
    """
    img = Path(rescue_img)
    if not img.exists():
        console.print(f"[red]✗ Not found: {rescue_img}[/red]")
        return

    out_dir = Path(out) if out else (OUTPUT_DIR / "rtk_rescue" / img.stem)
    out_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold cyan]Realtek Rescue Image Extractor[/bold cyan]")
    console.print(f"  Image : {img.name} ({file_size_mb(img):.1f} MB)")

    # Detect format
    with open(img, "rb") as f:
        magic = f.read(8)

    import struct
    console.print(f"  Magic : {magic.hex()}")

    # Try unsquashfs
    if tool_available("unsquashfs"):
        console.print("[cyan]→ Trying unsquashfs...[/cyan]")
        rc, _, err = run(["unsquashfs", "-d", str(out_dir), str(img)], check=False, timeout=300)
        if rc == 0:
            count = sum(1 for _ in out_dir.rglob("*"))
            console.print(f"[green]✓ Extracted {count} items → {out_dir}[/green]")
            return

    # Try as raw ext4
    if tool_available("debugfs"):
        console.print("[cyan]→ Trying ext4 extract...[/cyan]")
        rc, out_text, _ = run(["debugfs", "-R", f"rdump / {out_dir}", str(img)], check=False)
        if rc == 0:
            console.print(f"[green]✓ Extracted → {out_dir}[/green]")
            return

    console.print(f"[yellow]! Could not auto-extract. Image saved for manual inspection.[/yellow]")
    console.print(f"  Try: binwalk -e {img}")
    console.print(f"  Or:  7z x {img} -o{out_dir}")
