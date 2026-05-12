"""
rom.py — ROM building, repacking, GSI flash, and firmware packaging
Supports MTK PAC and Unisoc PAC repacking, and Treble GSI deployment
"""
import click
import shutil
import json
from pathlib import Path
from datetime import datetime
from modules import (
    run, run_adb, run_fastboot, adb_devices, get_device_props,
    detect_chipset_from_props, OUTPUT_DIR, WORKSPACE, KEYS_DIR,
    sha256_file, file_size_mb, console, tool_available
)


# ─── ROM manifest ─────────────────────────────────────────────────────────────

def write_rom_manifest(rom_dir: Path, meta: dict):
    manifest = {
        "watchrom_version": "1.0",
        "created": datetime.now().isoformat(),
        "partitions": {},
        **meta,
    }
    for img in rom_dir.glob("*.img"):
        manifest["partitions"][img.stem] = {
            "file":   img.name,
            "size":   img.stat().st_size,
            "sha256": sha256_file(img),
        }
    out = rom_dir / "rom_manifest.json"
    with open(out, "w") as f:
        json.dump(manifest, f, indent=2)
    return out


# ─── MTK scatter file ─────────────────────────────────────────────────────────

MTK_SCATTER_TEMPLATE = """\
############################################################################################################
#
#  General Setting
#
############################################################################################################
- general: {{
   platform: {platform}
   project: {project}
   storage: EMMC
   boot_channel: MSDC_0
   block_size: 0x20000
}}

"""

MTK_PARTITION_ENTRY = """\
- partition_index: SYS{index}
  partition_name: {name}
  file_name: {filename}
  is_download: true
  type: EXT4_IMG
  linear_start_addr: 0x{offset:x}
  physical_start_addr: 0x{offset:x}
  partition_size: 0x{size:x}
  region: EMMC_USER
  storage: HW_STORAGE_EMMC
  boundary_check: true
  is_reserved: false
  operation_type: UPDATE
  is_upgradable: true
  empty_boot_needed: false
  reserve: 0x00

"""

def generate_mtk_scatter(rom_dir: Path, platform="MT6761", project="watchrom"):
    """Generate an SP Flash Tool scatter file for an MTK ROM directory."""
    parts = sorted(rom_dir.glob("*.img"))
    scatter_lines = [MTK_SCATTER_TEMPLATE.format(platform=platform, project=project)]

    offset = 0x00200000  # Start after preloader gap
    for i, img in enumerate(parts):
        size = img.stat().st_size
        entry = MTK_PARTITION_ENTRY.format(
            index=i+1,
            name=img.stem,
            filename=img.name,
            offset=offset,
            size=size,
        )
        scatter_lines.append(entry)
        offset += (size + 0x1FFFFF) & ~0x1FFFFF  # Align to 2MB

    scatter_path = rom_dir / "MT_scatter.txt"
    with open(scatter_path, "w") as f:
        f.writelines(scatter_lines)
    return scatter_path


# ─── Unisoc PAC packer ────────────────────────────────────────────────────────

def generate_unisoc_xml(rom_dir: Path, chipset="SC9863A"):
    """Generate Unisoc flash XML for UpgradeDownload tool."""
    parts = list(rom_dir.glob("*.img"))
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<Partitions chipset="{chipset}" version="1.0">',
    ]
    for img in parts:
        lines.append(f'  <Partition id="{img.stem}" filename="{img.name}" '
                     f'size="{img.stat().st_size}" sha256="{sha256_file(img)}"/>')
    lines.append('</Partitions>')
    xml_path = rom_dir / "flashconfig.xml"
    with open(xml_path, "w") as f:
        f.write("\n".join(lines))
    return xml_path


# ─── CLI ──────────────────────────────────────────────────────────────────────

@click.group()
def rom():
    """ROM building, repacking, GSI deployment, and full firmware flash."""
    pass


@rom.command("build")
@click.option("--parts-dir", "-p", required=True,
              help="Directory containing partition .img files")
@click.option("--vendor", "-v",
              type=click.Choice(["mtk","unisoc","auto"]), default="auto")
@click.option("--chipset", "-c", default=None,
              help="Chipset name (e.g. MT6761, SC9863A)")
@click.option("--out",    "-o", default=None,
              help="Output directory for ROM package")
@click.option("--serial", "-s", default=None,
              help="Auto-detect chipset from connected device")
def rom_build(parts_dir, vendor, chipset, out, serial):
    """
    Repack partition images into a flashable ROM package.

    Generates:
      - MT_scatter.txt     (MTK / SP Flash Tool)
      - flashconfig.xml    (Unisoc / UpgradeDownload)
      - rom_manifest.json  (WatchROM index)
    """
    parts_path = Path(parts_dir)
    if not parts_path.is_dir():
        console.print(f"[red]✗ Not a directory: {parts_dir}[/red]")
        return

    imgs = list(parts_path.glob("*.img"))
    if not imgs:
        console.print(f"[red]✗ No .img files found in {parts_dir}[/red]")
        return

    console.print(f"\n[bold cyan]ROM Builder[/bold cyan]")
    console.print(f"  Parts dir : {parts_path}")
    console.print(f"  Images    : {len(imgs)}")

    # Auto-detect vendor from connected device if needed
    detected_vendor = vendor
    detected_chip   = chipset
    if (vendor == "auto" or not chipset) and serial:
        props = get_device_props(serial)
        detected_vendor, detected_chip = detect_chipset_from_props(props)
        console.print(f"  [dim]Auto-detected: {detected_vendor.upper()} / {detected_chip}[/dim]")

    out_path = Path(out) if out else (OUTPUT_DIR / "rom_package")
    out_path.mkdir(parents=True, exist_ok=True)

    # Copy all images to output
    for img in imgs:
        dst = out_path / img.name
        if not dst.exists() or sha256_file(img) != sha256_file(dst):
            shutil.copy(img, dst)

    # Generate scatter / flash config
    if detected_vendor in ("mtk", "auto"):
        scatter = generate_mtk_scatter(out_path,
                                        platform=detected_chip or "MT6761",
                                        project="watchrom")
        console.print(f"[green]✓ MTK scatter: {scatter}[/green]")

    if detected_vendor in ("unisoc", "auto"):
        xml = generate_unisoc_xml(out_path, chipset=detected_chip or "SC9863A")
        console.print(f"[green]✓ Unisoc XML: {xml}[/green]")

    manifest = write_rom_manifest(out_path, {
        "vendor": detected_vendor,
        "chipset": detected_chip or "unknown",
        "partition_count": len(imgs),
    })
    console.print(f"[green]✓ Manifest: {manifest}[/green]")

    total_mb = sum(f.stat().st_size for f in out_path.glob("*.img")) / (1024*1024)
    console.print(f"\n[bold]ROM Package:[/bold] {out_path}")
    console.print(f"  {len(imgs)} images | {total_mb:.0f} MB total")
    console.print(f"\n[dim]Flash with:[/dim]")
    console.print(f"  [cyan]MTK    → SP Flash Tool → Load MT_scatter.txt → Download[/cyan]")
    console.print(f"  [cyan]Unisoc → UpgradeDownload → Load flashconfig.xml → Start[/cyan]")


@rom.command("gsi")
@click.argument("gsi_image")
@click.option("--serial", "-s", default=None)
@click.option("--wipe-data", "-w", is_flag=True,
              help="Wipe userdata after GSI flash (required for clean boot)")
def rom_gsi(gsi_image, serial, wipe_data):
    """
    Flash a Generic System Image (GSI) to the system partition.

    Requires Project Treble-enabled device. The vendor partition
    is preserved; only system is replaced.
    """
    gsi_path = Path(gsi_image)
    if not gsi_path.exists():
        console.print(f"[red]✗ GSI image not found: {gsi_image}[/red]")
        return

    console.print(f"\n[bold cyan]GSI Flash — Project Treble[/bold cyan]")
    console.print(f"  GSI  : {gsi_path.name} ({file_size_mb(gsi_path):.0f} MB)")

    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    target = serial or (online[0] if online else None)

    if target:
        props = get_device_props(target)
        treble = props.get("ro.treble.enabled", "false")
        if treble != "true":
            console.print("[yellow]⚠ ro.treble.enabled=false — this device may not support GSI.[/yellow]")
        abi = props.get("ro.product.cpu.abi", "?")
        console.print(f"  ABI  : {abi}")
        console.print(f"  Treble: {treble}")

    if not click.confirm("\n⚠ This replaces the system partition. Continue?", default=False):
        return

    # Reboot to fastboot
    if target:
        run_adb(["reboot", "bootloader"], serial=target, check=False)
        import time; time.sleep(6)

    from modules import fastboot_devices
    fb = fastboot_devices()
    fb_serial = serial or (fb[0] if fb else None)

    if not fb_serial:
        console.print("[red]✗ No fastboot device.[/red]")
        return

    # Disable verity for GSI
    console.print("[cyan]→ Disabling verity...[/cyan]")
    run_fastboot(["--disable-verity", "--disable-verification",
                  "flash", "vbmeta",
                  str(OUTPUT_DIR / "vbmeta_blank.img") if (OUTPUT_DIR/"vbmeta_blank.img").exists() else "vbmeta"],
                 serial=fb_serial, check=False)

    # Flash GSI
    console.print("[cyan]→ Flashing GSI to system partition...[/cyan]")
    rc, _, err = run_fastboot(
        ["flash", "system", str(gsi_path)],
        serial=fb_serial, check=False, timeout=600
    )
    if rc != 0:
        console.print(f"[yellow]Retry with --skip-secondary...[/yellow]")
        rc, _, err = run_fastboot(
            ["--skip-secondary", "flash", "system", str(gsi_path)],
            serial=fb_serial, check=False, timeout=600
        )

    if rc == 0:
        console.print("[green]✓ GSI flashed.[/green]")
    else:
        console.print(f"[red]✗ GSI flash failed: {err}[/red]")
        return

    if wipe_data:
        console.print("[cyan]→ Wiping userdata...[/cyan]")
        run_fastboot(["erase", "userdata"], serial=fb_serial, check=False)
        run_fastboot(["erase", "cache"],    serial=fb_serial, check=False)

    run_fastboot(["reboot"], serial=fb_serial, check=False)
    console.print("[green]✓ Device rebooting...[/green]")


@rom.command("flash")
@click.argument("rom_dir")
@click.option("--serial", "-s", default=None)
@click.option("--vendor", "-v", type=click.Choice(["mtk","unisoc"]), required=True)
def rom_flash(rom_dir, serial, vendor):
    """Print flash instructions for the ROM package (vendor tool required)."""
    rd = Path(rom_dir)
    console.print(f"\n[bold cyan]ROM Flash Instructions — {vendor.upper()}[/bold cyan]\n")

    if vendor == "mtk":
        scatter = rd / "MT_scatter.txt"
        console.print("[bold yellow]MTK — SP Flash Tool[/bold yellow]")
        console.print(f"  1. Open SP Flash Tool (spflashtools.com)")
        console.print(f"  2. [Download] tab → [Choose] → select: [cyan]{scatter}[/cyan]")
        console.print(f"  3. Select partitions to flash (or Download All)")
        console.print(f"  4. Power off device, click [Download], connect USB")
        console.print(f"  5. SP Flash Tool auto-detects MTK preloader and begins flash")
        console.print(f"\n  [dim]BROM mode: hold Vol- while connecting USB for forced download mode[/dim]")
    else:
        xml = rd / "flashconfig.xml"
        console.print("[bold yellow]Unisoc — UpgradeDownload / SPD Research Tool[/bold yellow]")
        console.print(f"  1. Open Unisoc UpgradeDownload tool")
        console.print(f"  2. Load config: [cyan]{xml}[/cyan]")
        console.print(f"  3. Set firmware directory to: [cyan]{rd}[/cyan]")
        console.print(f"  4. Power off device, hold Vol- + connect USB")
        console.print(f"  5. Tool detects FDL and begins flash sequence")
        console.print(f"\n  [dim]Alternative: SPD Research Tool with PAC file for full image flash[/dim]")
