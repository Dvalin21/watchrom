"""
chipset.py — MTK and Unisoc chipset-specific CLI commands
Full support for all known MTK (MT6739-MT6983) and Unisoc (SC9832E-T820) chips
"""
import click
import subprocess
from pathlib import Path
from modules import run, run_adb, adb_devices, console, tool_available, OUTPUT_DIR
from modules.chipsets import (
    MTK_CHIPS, UNISOC_CHIPS, identify_mtk_chip, identify_unisoc_chip,
    get_partition_list, get_flash_tool_info, all_watch_chips, MTK_PARTITIONS, UNISOC_PARTITIONS
)


# ─────────────────────────────────────────────────────────────────────────────
# MTK
# ─────────────────────────────────────────────────────────────────────────────

@click.group()
def mtk():
    """MediaTek (MTK) chipset-specific commands — MT6739 through MT6983."""
    pass


@mtk.command("list")
@click.option("--watch-only", "-w", is_flag=True, help="Show only watch-class chips")
def mtk_list(watch_only):
    """List all supported MTK chipsets."""
    from rich.table import Table
    from rich import box as rbox
    t = Table(title="Supported MediaTek Chipsets", box=rbox.ROUNDED, border_style="cyan")
    t.add_column("Chip",    style="bold green", width=12)
    t.add_column("Name",    style="white",      width=28)
    t.add_column("Arch",    style="yellow",     width=8)
    t.add_column("Year",    style="dim",        width=6)
    t.add_column("Watch",   style="cyan",       width=7)
    t.add_column("BROM",    style="magenta",    width=6)
    for key, info in sorted(MTK_CHIPS.items()):
        if watch_only and not info["watch"]:
            continue
        t.add_row(
            key, info["name"], info["arch"], str(info["year"]),
            "[green]✓[/green]" if info["watch"] else "[dim]—[/dim]",
            "[green]✓[/green]" if info["brom"]  else "[dim]—[/dim]",
        )
    console.print(t)


@mtk.command("download")
@click.option("--serial", "-s", default=None)
def mtk_download(serial):
    """
    Enter MTK BROM / Preloader download mode.

    Works with: MT6739, MT6761, MT6762, MT6765, MT6768, MT6771,
                MT6785, MT6789, MT6833, MT6853, MT6873, MT6877,
                MT6893, MT6895, MT6983 and all watch variants.
    """
    console.print("\n[bold cyan]MTK Download Mode Entry[/bold cyan]\n")

    console.print("[bold yellow]Method 1 — ADB reboot (if device is on):[/bold yellow]")
    console.print("  watchrom device reboot bootloader\n")

    console.print("[bold yellow]Method 2 — Hardware BROM (most reliable):[/bold yellow]")
    console.print("  1. Fully power off the device")
    console.print("  2. Hold [Vol−] button")
    console.print("  3. While holding, connect USB cable to PC")
    console.print("  4. Release when SP Flash Tool shows a COM port\n")

    console.print("[bold yellow]Method 3 — MTK Client (advanced, no Vol button needed):[/bold yellow]")
    repos = Path(__file__).resolve().parent.parent.parent / "watchrom_repos" / "mtkclient"
    if repos.exists():
        console.print(f"  cd {repos}")
        console.print(f"  python3 mtk.py payload    ← exploit BROM, gain full access")
        console.print(f"  python3 mtk.py r boot boot.img  ← dump boot partition")
        console.print(f"  python3 mtk.py w boot boot_patched.img  ← flash partition\n")
    else:
        console.print("  Install: watchrom setup  ← clones mtkclient automatically\n")

    console.print("[bold yellow]SP Flash Tool Workflow:[/bold yellow]")
    console.print("  1. Download SP Flash Tool from spflashtools.com")
    console.print("  2. [Download] tab → [Choose] → select MT_scatter.txt")
    console.print("  3. Click [Download] → connect device in BROM mode")
    console.print("  4. Green progress bar = success\n")

    console.print("[bold yellow]USB Identification:[/bold yellow]")
    console.print("  BROM mode: VID=0x0E8D PID=0x0003 (MTK USB VCOM)")
    console.print("  Preloader: VID=0x0E8D PID=0x2000\n")
    console.print("  Linux check: [dim]lsusb | grep 0e8d[/dim]\n")

    # Try ADB if device connected
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if online:
        target = serial or online[0]
        if click.confirm(f"  Reboot {target} to bootloader now?"):
            run_adb(["reboot", "bootloader"], serial=target, check=False)
            console.print("[green]✓ Reboot command sent.[/green]")


@mtk.command("identify")
@click.option("--serial", "-s", default=None)
def mtk_identify(serial):
    """Show detailed MTK-specific device information."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    from modules import get_device_props
    props = get_device_props(target)

    platform = props.get("ro.board.platform", props.get("ro.hardware", ""))
    chip_info = identify_mtk_chip(platform)

    console.print(f"\n[bold cyan]MTK Device Info — {target}[/bold cyan]\n")

    if chip_info:
        console.print(f"  [bold green]Detected:[/bold green] {chip_info.get('name','?')}")
        console.print(f"  Architecture : {chip_info.get('arch','?')}")
        console.print(f"  Watch class  : {'Yes' if chip_info.get('watch') else 'No'}")
        console.print(f"  BROM support : {'Yes' if chip_info.get('brom') else 'No'}")
        console.print()

    mtk_prop_keys = [
        "ro.board.platform", "ro.mediatek.platform", "ro.mediatek.chip_ver",
        "ro.mediatek.version.release", "ro.boot.hardware",
        "persist.vendor.mtk.platform", "ro.mtk_wl_opt",
        "ro.vendor.mediatek.platform",
    ]
    for k in mtk_prop_keys:
        v = props.get(k, "")
        if v:
            console.print(f"  [cyan]{k}[/cyan] = {v}")

    _, cpu_out, _ = run_adb(["shell", "cat /proc/cpuinfo | grep -E '(Hardware|processor)' | head -5"],
                             serial=target, check=False)
    console.print(f"\n  [bold]CPU Info:[/bold]\n{cpu_out.strip()}")

    # Partition layout suggestion
    ab = props.get("ro.build.ab_update", "false") == "true"
    parts = MTK_PARTITIONS["ab" if ab else "standard"]
    console.print(f"\n  [bold]Expected partitions ({('A/B' if ab else 'A-only')}):[/bold]")
    console.print(f"  [dim]{' '.join(parts[:12])}...[/dim]")

    # Flash tool info
    tool = get_flash_tool_info("mtk")
    console.print(f"\n  [bold]Flash tool:[/bold] {tool['primary']}")
    console.print(f"  [bold]Format    :[/bold] {tool['format']}")
    console.print(f"  [bold]Mode      :[/bold] {tool['mode']}")


@mtk.command("dump-brom")
@click.option("--out", "-o", default=None, help="Output BROM dump path")
def mtk_dump_brom(out):
    """
    Dump MTK Boot ROM using mtkclient (requires mtkclient installed).
    Device must be in BROM mode (powered off + Vol- + USB).
    """
    repos = Path(__file__).resolve().parent.parent.parent / "watchrom_repos" / "mtkclient"
    if not repos.exists() and not tool_available("mtk"):
        console.print("[red]✗ mtkclient not found.[/red]")
        console.print("  Run: [bold]python3 setup.py[/bold] to clone and install it.")
        return

    out_path = Path(out) if out else (OUTPUT_DIR / "brom_dump.bin")
    console.print("[cyan]→ Attempting BROM dump via mtkclient...[/cyan]")
    console.print("[dim]Connect device in BROM mode first (power off + hold Vol- + USB)[/dim]\n")

    mtk_bin = str(repos / "mtk.py") if repos.exists() else "mtk"
    cmd_base = ["python3", mtk_bin] if mtk_bin.endswith(".py") else [mtk_bin]

    rc, out_text, err = run(
        cmd_base + ["dumpbrom", "--filename", str(out_path)],
        check=False, timeout=120, capture=True
    )
    if rc == 0 and out_path.exists():
        from modules import file_size_mb, sha256_file
        console.print(f"[green]✓ BROM dump: {out_path} ({file_size_mb(out_path):.1f} MB)[/green]")
        console.print(f"  SHA256: {sha256_file(out_path)[:32]}…")
    else:
        console.print(f"[yellow]! mtkclient output:[/yellow]\n{out_text[:300]}{err[:200]}")


# ─────────────────────────────────────────────────────────────────────────────
# Unisoc / Spreadtrum
# ─────────────────────────────────────────────────────────────────────────────

@click.group()
def unisoc():
    """Unisoc / Spreadtrum chipset commands — SC9832E through T820."""
    pass


@unisoc.command("list")
@click.option("--watch-only", "-w", is_flag=True, help="Show only watch-class chips")
def unisoc_list(watch_only):
    """List all supported Unisoc chipsets."""
    from rich.table import Table
    from rich import box as rbox
    t = Table(title="Supported Unisoc / Spreadtrum Chipsets", box=rbox.ROUNDED, border_style="yellow")
    t.add_column("Chip",       style="bold green", width=12)
    t.add_column("Name",       style="white",      width=24)
    t.add_column("Arch",       style="yellow",     width=8)
    t.add_column("Year",       style="dim",        width=6)
    t.add_column("Watch",      style="cyan",       width=7)
    t.add_column("FDL",        style="magenta",    width=5)
    t.add_column("Weak AVB",   style="red",        width=10)
    for key, info in sorted(UNISOC_CHIPS.items()):
        if watch_only and not info.get("watch"):
            continue
        t.add_row(
            key, info["name"], info["arch"], str(info["year"]),
            "[green]✓[/green]" if info.get("watch")     else "[dim]—[/dim]",
            "[green]✓[/green]" if info.get("fdl")       else "[dim]—[/dim]",
            "[red]✓[/red]"    if info.get("avb_weak")  else "[dim]—[/dim]",
        )
    console.print(t)
    console.print("[dim]Weak AVB = AVB verification bypass possible without unlock[/dim]")


@unisoc.command("download")
@click.option("--serial", "-s", default=None)
def unisoc_download(serial):
    """
    Enter Unisoc FDL (Flash Download Loader) mode.

    Works with: SC9832E, SC9863A, SC9863, SL8541E, SC8541E,
                UIS8581A, UIS8520E, T606, T612, T618, T760, T820
    """
    console.print("\n[bold cyan]Unisoc / Spreadtrum Download Mode[/bold cyan]\n")

    console.print("[bold yellow]Method 1 — ADB (if device is on):[/bold yellow]")
    console.print("  adb reboot download   [dim](or)[/dim]   adb reboot bootloader\n")

    console.print("[bold yellow]Method 2 — Hardware FDL (power-off method):[/bold yellow]")
    console.print("  1. Fully power off device")
    console.print("  2. Hold [Vol−] (some models: hold power briefly then Vol−)")
    console.print("  3. Connect USB — release when tool shows port detected\n")

    console.print("[bold yellow]Method 3 — FDL Test Point (no button):[/bold yellow]")
    console.print("  1. Disassemble watch, find FDL/BOOT test point on PCB")
    console.print("  2. Short the test point to GND for ~1 sec while connecting USB")
    console.print("  3. Device appears as 'Spreadtrum' composite USB device\n")

    console.print("[bold yellow]USB Identification:[/bold yellow]")
    console.print("  VID: 0x1782  PID: 0x4D00  (Spreadtrum FDL)")
    console.print("  VID: 0x1782  PID: 0x5D0E  (Spreadtrum Download)")
    console.print("  Linux check: [dim]lsusb | grep -i spreadtrum[/dim]\n")

    console.print("[bold yellow]UpgradeDownload Tool Workflow:[/bold yellow]")
    console.print("  1. Open Unisoc UpgradeDownload or SPD Research Tool")
    console.print("  2. [Load Packet] → select .pac file")
    console.print("     OR [Configure] → load flashconfig.xml from WatchROM output")
    console.print("  3. Click [Start Downloading]")
    console.print("  4. Connect device in FDL mode")
    console.print("  5. Wait for 'PASSED' confirmation\n")

    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if online:
        target = serial or online[0]
        if click.confirm(f"  Reboot {target} to download mode now?"):
            rc, _, _ = run_adb(["reboot", "download"], serial=target, check=False)
            if rc != 0:
                run_adb(["reboot", "bootloader"], serial=target, check=False)
            console.print("[green]✓ Reboot command sent.[/green]")


@unisoc.command("identify")
@click.option("--serial", "-s", default=None)
def unisoc_identify(serial):
    """Show Unisoc-specific device information and capabilities."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    from modules import get_device_props
    props = get_device_props(target)
    platform = props.get("ro.board.platform", props.get("ro.hardware", ""))
    chip_info = identify_unisoc_chip(platform)

    console.print(f"\n[bold cyan]Unisoc Device Info — {target}[/bold cyan]\n")

    if chip_info:
        console.print(f"  [bold yellow]Detected:[/bold yellow] {chip_info.get('name','?')}")
        console.print(f"  Architecture : {chip_info.get('arch','?')}")
        console.print(f"  Watch class  : {'Yes' if chip_info.get('watch') else 'No'}")
        console.print(f"  FDL support  : {'Yes' if chip_info.get('fdl') else 'No'}")
        avb_weak = chip_info.get("avb_weak", False)
        console.print(f"  AVB strength : {'[red]WEAK (bypass possible)[/red]' if avb_weak else '[green]Standard[/green]'}")
        console.print()

    unisoc_props = [
        "ro.board.platform", "ro.hardware", "ro.product.board",
        "ro.boot.hardware", "persist.vendor.sprd.modemreset",
        "ro.vendor.modem.product.model", "ro.sprd.hardware",
        "ro.build.version.incremental",
    ]
    for k in unisoc_props:
        v = props.get(k, "")
        if v:
            console.print(f"  [cyan]{k}[/cyan] = {v}")

    _, cpu_out, _ = run_adb(
        ["shell", "cat /proc/cpuinfo | grep -E '(Hardware|processor)' | head -5"],
        serial=target, check=False
    )
    console.print(f"\n  [bold]CPU Info:[/bold]\n{cpu_out.strip()}")

    # Unisoc paths check
    sprd_paths = [
        "/dev/sprd_fm", "/dev/sprd_io", "/proc/sprd_iq",
        "/vendor/lib/libsprd", "/sys/kernel/debug/sprd",
    ]
    console.print("\n  [bold]Unisoc-specific paths:[/bold]")
    for path in sprd_paths:
        _, out, _ = run_adb(["shell", f"ls {path} 2>/dev/null && echo FOUND || echo MISSING"],
                             serial=target, check=False)
        found = "FOUND" in out
        console.print(f"    [{'green' if found else 'dim'}]{'✓' if found else '—'}[/{'green' if found else 'dim'}] {path}")

    # Partition layout
    ab = props.get("ro.build.ab_update", "false") == "true"
    parts = UNISOC_PARTITIONS["ab" if ab else "standard"]
    console.print(f"\n  [bold]Expected partitions ({('A/B' if ab else 'A-only')}):[/bold]")
    console.print(f"  [dim]{' '.join(parts[:12])}...[/dim]")

    tool = get_flash_tool_info("unisoc")
    console.print(f"\n  [bold]Flash tool:[/bold] {tool['primary']}")
    console.print(f"  [bold]Format    :[/bold] {tool['format']}")
    console.print(f"  [bold]Mode      :[/bold] {tool['mode']}")


@unisoc.command("pac-info")
@click.argument("pac_file")
def unisoc_pac_info(pac_file):
    """Show information about a Unisoc PAC firmware file."""
    pac = Path(pac_file)
    if not pac.exists():
        console.print(f"[red]✗ Not found: {pac_file}[/red]")
        return

    from modules import file_size_mb, sha256_file
    console.print(f"\n[bold cyan]Unisoc PAC File: {pac.name}[/bold cyan]\n")
    console.print(f"  Size  : {file_size_mb(pac):.1f} MB")
    console.print(f"  SHA256: {sha256_file(pac)[:32]}…")

    # PAC header starts with magic and XML header
    with open(pac, "rb") as f:
        header = f.read(4096)

    # Try to extract XML header (Unisoc PAC has XML at start)
    try:
        xml_start = header.find(b"<?xml")
        xml_end   = header.find(b"</Partitions>")
        if xml_start >= 0 and xml_end > xml_start:
            xml_data = header[xml_start:xml_end+13].decode("utf-8", errors="replace")
            console.print(f"\n  [bold]PAC Partition Table:[/bold]")
            import re
            parts = re.findall(r'id="([^"]+)"', xml_data)
            for p in parts:
                console.print(f"    [cyan]{p}[/cyan]")
        else:
            console.print("  [dim]XML header not found at start — may be encrypted or different format[/dim]")
    except Exception as e:
        console.print(f"  [yellow]Parse error: {e}[/yellow]")

    # Check for unisoc-tools
    repos = Path(__file__).resolve().parent.parent.parent / "watchrom_repos" / "unisoc-tools"
    if repos.exists():
        console.print(f"\n  [dim]unisoc-tools available at {repos}[/dim]")
        console.print(f"  [dim]Extract: python3 {repos}/pac_extract.py {pac} --output ./pac_extracted/[/dim]")


# ─────────────────────────────────────────────────────────────────────────────
# Shared watch chip info command
# ─────────────────────────────────────────────────────────────────────────────

@click.group()
def chips():
    """All supported MTK + Unisoc chipset information."""
    pass


@chips.command("list-all")
def chips_list_all():
    """List every supported watch-class chip (MTK + Unisoc)."""
    watch_chips = all_watch_chips()
    from rich.table import Table
    from rich import box as rbox
    t = Table(title="All Supported Watch Chipsets", box=rbox.ROUNDED, border_style="cyan")
    t.add_column("Chip",    style="bold green", width=12)
    t.add_column("Vendor",  style="yellow",     width=8)
    t.add_column("Name",    style="white",      width=26)
    t.add_column("Arch",    style="cyan",       width=7)
    t.add_column("Year",    style="dim",        width=6)
    for c in watch_chips:
        t.add_row(c["key"], c["vendor"].upper(), c["name"], c["arch"], str(c.get("year","?")))
    console.print(t)
    console.print(f"\n  [dim]Total: {len(watch_chips)} watch-class chipsets supported[/dim]")
