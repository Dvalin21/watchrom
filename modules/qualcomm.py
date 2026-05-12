"""
qualcomm.py — Qualcomm Snapdragon CLI module
Covers: chip detection, EDL mode, band configuration via QPST/ADB,
        EFS backup/restore, modem info display

SAFETY DESIGN:
  ✓  Band preference masks — safe, documented, reversible
  ✓  EFS backup/restore — critical safety net
  ✓  Mode preference (LTE/5G/3G) — safe, documented
  ✗  IMEI modification — NOT implemented (illegal in most jurisdictions)
  ✗  RF calibration NV items — NOT implemented (irreversible, brick risk)
  ✗  SPC/MSL unlock codes — NOT implemented
"""
import click
import struct
import shutil
import time
import subprocess
from pathlib import Path
from modules import (
    run, run_adb, adb_devices, get_device_props,
    OUTPUT_DIR, WORKSPACE, console, tool_available, file_size_mb, sha256_file
)
from modules.qualcomm_chips import (
    SNAPDRAGON_CHIPS, LTE_BANDS, NR_BANDS, NV_ITEMS,
    BAND_PRESETS, FIREHOSE_INFO, QUALCOMM_MODEMS,
    identify_snapdragon, get_modem_info
)

REPOS_DIR = Path(__file__).resolve().parent.parent.parent / "watchrom_repos"

# ── Safety banner (shown before any write operation) ──────────────────────────
SAFETY_NOTICE = """
[bold yellow]⚠  SAFETY NOTICE[/bold yellow]
[dim]─────────────────────────────────────────────────────────────────[/dim]
  This operation modifies modem NV (Non-Volatile) configuration.

  SAFE items being modified:
    ✓ Band preference bitmasks (which LTE/5G bands to search)
    ✓ Network mode preference (LTE-only, 5G-preferred, etc.)

  NOT modified by WatchROM (ever):
    ✗ IMEI or MEID (illegal to modify)
    ✗ RF calibration data (irreversible, brick risk)
    ✗ SPC/MSL codes
    ✗ Carrier lock status

  Band changes are FULLY REVERSIBLE.
  Use 'watchrom qualcomm efs backup' BEFORE any changes.
[dim]─────────────────────────────────────────────────────────────────[/dim]
"""


# ═══════════════════════════════════════════════════════════════════════════════
# ADB helpers for modem/band access (no root needed for most)
# ═══════════════════════════════════════════════════════════════════════════════

def adb_get_prop_modem(prop: str, serial=None) -> str:
    _, out, _ = run_adb(["shell", f"getprop {prop}"], serial=serial, check=False)
    return out.strip()


def adb_get_service_state(serial=None) -> dict:
    """Read telephony service state via dumpsys (no root needed)."""
    _, out, _ = run_adb(["shell", "dumpsys telephony.registry 2>/dev/null | head -80"],
                         serial=serial, check=False)
    state = {}
    for line in out.splitlines():
        line = line.strip()
        if "mDataConnectionState" in line:
            state["data_state"] = line.split("=")[-1].strip()
        elif "mServiceState" in line:
            state["service_state"] = line.split("=")[-1].strip()
        elif "mDataNetworkType" in line:
            state["network_type"] = line.split("=")[-1].strip()
        elif "mSignalStrength" in line:
            state["signal"] = line.split("=")[-1].strip()[:60]
        elif "mOperatorAlphaLong" in line:
            state["carrier"] = line.split("=")[-1].strip()
        elif "mOperatorNumeric" in line:
            state["mcc_mnc"] = line.split("=")[-1].strip()
    return state


def adb_get_network_info(serial=None) -> dict:
    """Read detailed network info via shell commands (no root needed)."""
    results = {}
    cmds = {
        "operator":     "getprop gsm.operator.alpha",
        "network_type": "getprop gsm.network.type",
        "data_type":    "getprop gsm.data.network.type",
        "roaming":      "getprop gsm.operator.isroaming",
        "mcc_mnc":      "getprop gsm.operator.numeric",
        "sim_state":    "getprop gsm.sim.state",
        "ril_version":  "getprop gsm.version.ril-impl",
        "icc_id":       "getprop ril.iccid.sim1",  # read-only, no privacy issue
        "imei_sv":      "getprop ro.telephony.imei_sv",  # software version only
    }
    for key, cmd in cmds.items():
        _, out, _ = run_adb(["shell", cmd], serial=serial, check=False)
        results[key] = out.strip()
    return results


def adb_read_band_config_efs(serial=None) -> dict:
    """
    Read current band config from EFS via ADB (requires root for direct EFS read).
    Falls back to AT command method if available.
    """
    results = {}

    # Method 1: Direct EFS read via ADB root
    efs_items = {
        "lte_band": "/data/vendor/modem_config/mcfg/mbn/mcfg_sw.mbn",
        "mode_pref": NV_ITEMS["efs_mode_pref"]["path"],
        "lte_pref":  NV_ITEMS["efs_lte_band_pref"]["path"],
        "nr_pref":   NV_ITEMS["efs_nr_band_pref"]["path"],
    }
    for key, path in efs_items.items():
        _, out, _ = run_adb(
            ["shell", f"su -c 'xxd {path} 2>/dev/null | head -4'"],
            serial=serial, check=False
        )
        if out.strip() and "No such" not in out:
            results[key] = out.strip()

    # Method 2: dumpsys phone (no root)
    _, ds_out, _ = run_adb(
        ["shell", "dumpsys phone 2>/dev/null | grep -iE '(band|lte|5g|nr|preferred)' | head -20"],
        serial=serial, check=False
    )
    if ds_out.strip():
        results["dumpsys_bands"] = ds_out.strip()

    # Method 3: AT commands via /dev/smd7 or /dev/at_mdm0 (if accessible)
    for at_port in ["/dev/smd7", "/dev/at_mdm0", "/dev/at0"]:
        _, exists, _ = run_adb(
            ["shell", f"ls {at_port} 2>/dev/null"], serial=serial, check=False
        )
        if exists.strip() == at_port:
            results["at_port"] = at_port
            break

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# QPST / QFIL / edl integration
# ═══════════════════════════════════════════════════════════════════════════════

def check_edl_device() -> bool:
    """Check if a Qualcomm 9008 (EDL) device is connected."""
    try:
        r = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
        return "9008" in r.stdout or "Qualcomm" in r.stdout
    except Exception:
        return False


def check_qpst_tools() -> dict:
    """Check which Qualcomm tools are available."""
    available = {}
    tools = {
        "edl":        "bkerler/edl (github.com/bkerler/edl)",
        "qfirehose":  "Qualcomm QFirehose",
        "diag_port":  "/dev/ttyUSB* or /dev/diag",
        "at_port":    "/dev/ttyUSB* AT commands",
    }
    edl_repo = REPOS_DIR / "edl" / "edl.py"
    if edl_repo.exists():
        available["edl"] = str(edl_repo)
    if tool_available("edl"):
        available["edl_system"] = shutil.which("edl")
    for port_glob in ["/dev/ttyUSB0","/dev/ttyUSB1","/dev/diag"]:
        if Path(port_glob).exists():
            available["serial_port"] = port_glob
    return available


def efs_backup_via_edl(serial_port: str, out_dir: Path) -> Path:
    """Backup EFS via EDL/diag protocol using bkerler/edl tool."""
    edl_py = REPOS_DIR / "edl" / "edl.py"
    if not edl_py.exists() and not tool_available("edl"):
        raise FileNotFoundError(
            "edl tool not found.\n"
            "  Run: watchrom setup   ← clones bkerler/edl automatically\n"
            "  OR:  pip install edl"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    efs_out = out_dir / "efs_backup.tar"
    cmd_base = ["python3", str(edl_py)] if edl_py.exists() else ["edl"]
    cmd = cmd_base + [
        "--port", serial_port,
        "qfil", "efs-backup",
        "--output", str(efs_out),
    ]
    console.print(f"[cyan]→ Starting EFS backup via EDL...[/cyan]")
    rc, out, err = run(cmd, check=False, timeout=300, capture=True)
    if rc == 0 and efs_out.exists():
        return efs_out
    # Try QPST EFS sync method
    console.print("[dim]  Trying alternate EFS method...[/dim]")
    efs_sync_out = out_dir / "efs_sync"
    efs_sync_out.mkdir(exist_ok=True)
    cmd2 = cmd_base + ["--port", serial_port, "efs", "sync", str(efs_sync_out)]
    rc2, _, _ = run(cmd2, check=False, timeout=300, capture=True)
    if rc2 == 0:
        return efs_sync_out
    raise RuntimeError(f"EFS backup failed: {err[:300]}")


# ═══════════════════════════════════════════════════════════════════════════════
# Band mask helpers
# ═══════════════════════════════════════════════════════════════════════════════

def build_lte_bitmask(band_list: list) -> tuple:
    """
    Build 128-bit LTE band mask as (low_64, high_64).
    low_64  = bands 1-64   (bit n-1 for band n)
    high_64 = bands 65-128 (bit n-65 for band n)
    """
    low = high = 0
    for band in band_list:
        b = int(str(band).replace("B","").replace("b",""))
        if   1 <= b <= 64:  low  |= (1 << (b -  1))
        elif 65 <= b <= 128: high |= (1 << (b - 65))
    return low, high


def build_lte_bitmask_single(band_list: list) -> int:
    """Build flat 64-bit mask (bands 1-64 only) for display/comparison."""
    mask = 0
    for band in band_list:
        b = int(str(band).replace("B","").replace("b",""))
        if 1 <= b <= 64:
            mask |= (1 << (b - 1))
    return mask


def parse_lte_bitmask(low: int, high: int = 0) -> list:
    """Decode (low_64, high_64) into sorted list of band numbers."""
    bands = []
    for b in range(1, 65):
        if low  & (1 << (b -  1)): bands.append(b)
    for b in range(65, 129):
        if high & (1 << (b - 65)): bands.append(b)
    return bands


def format_band_list(bands: list, band_db: dict = None) -> str:
    """Format band list with frequency info."""
    if not band_db:
        return ", ".join(f"B{b}" for b in sorted(bands))
    parts = []
    for b in sorted(bands):
        info = band_db.get(b, {})
        freq = info.get("freq","?")
        parts.append(f"B{b}({freq})")
    return ", ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI group
# ═══════════════════════════════════════════════════════════════════════════════

@click.group()
def qualcomm():
    """Qualcomm Snapdragon: chip detection, band config, EFS backup, EDL mode."""
    pass


# ─── Chip identification ───────────────────────────────────────────────────────

@qualcomm.command("identify")
@click.option("--serial", "-s", default=None)
def qc_identify(serial):
    """
    Detect Qualcomm Snapdragon chipset and display full modem capabilities.
    Works without root — reads Android system properties only.
    """
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]
    props = get_device_props(target)

    platform = props.get("ro.board.platform", "")
    hardware  = props.get("ro.hardware", "")
    product   = props.get("ro.product.board","")
    chip = identify_snapdragon(f"{platform} {hardware} {product}", "")

    console.print(f"\n[bold cyan]Qualcomm Snapdragon — {target}[/bold cyan]\n")

    if chip:
        modem = chip.get("modem","?")
        modem_info = get_modem_info(modem)
        console.print(f"  [bold green]Detected  :[/bold green] {chip.get('name','?')}  [dim]({chip.get('key','?')})[/dim]")
        console.print(f"  Tier      : {chip.get('tier','?')}")
        console.print(f"  Year      : {chip.get('year','?')}")
        console.print(f"  Modem     : [bold yellow]X{modem}[/bold yellow]" if modem != "none" else "  Modem     : [dim]Wi-Fi only[/dim]")
        if modem_info:
            console.print(f"  Max DL    : {modem_info.get('max_dl','?')}")
            console.print(f"  Max UL    : {modem_info.get('max_ul','?')}")
            console.print(f"  LTE Cat   : Category {modem_info.get('lte_cat','?')}")
            console.print(f"  5G Sub-6  : {'[green]Yes[/green]' if modem_info.get('5g_sub6') else '[dim]No[/dim]'}")
            console.print(f"  5G mmWave : {'[green]Yes[/green]' if modem_info.get('5g_mmwave') else '[dim]No[/dim]'}")
            console.print(f"  LTE bands : up to {modem_info.get('bands_lte','?')} bands")
            if modem_info.get("bands_5g_nr",0) > 0:
                console.print(f"  NR bands  : up to {modem_info.get('bands_5g_nr','?')} bands")
        console.print(f"  EDL mode  : {'[green]Supported[/green]' if chip.get('edl') else '[dim]Not confirmed[/dim]'}")
    else:
        console.print(f"  [yellow]! Could not identify Snapdragon chip[/yellow]")
        console.print(f"  Platform : {platform}")
        console.print(f"  Hardware : {hardware}")

    # System properties
    console.print(f"\n  [bold]Key Properties:[/bold]")
    qc_props = [
        "ro.board.platform", "ro.hardware", "ro.product.board",
        "ro.baseband", "ro.build.version.release",
        "gsm.version.baseband",
        "ro.telephony.default_network",
    ]
    for k in qc_props:
        v = props.get(k,"")
        if v:
            console.print(f"  [cyan]{k}[/cyan] = {v}")


@qualcomm.command("list")
@click.option("--tier", "-t", default=None,
              type=click.Choice(["flagship","upper_mid","mid","budget","tablet","auto"]),
              help="Filter by tier")
@click.option("--5g-only", "only_5g", is_flag=True, help="Show only 5G-capable chips")
def qc_list(tier, only_5g):
    """List all supported Qualcomm Snapdragon chipsets."""
    from rich.table import Table
    from rich import box as rbox
    t = Table(title="Supported Qualcomm Snapdragon Chipsets",
              box=rbox.ROUNDED, border_style="red")
    t.add_column("Chip ID",  style="bold green", width=12)
    t.add_column("Name",     style="white",      width=26)
    t.add_column("Modem",    style="yellow",      width=7)
    t.add_column("Year",     style="dim",         width=6)
    t.add_column("Tier",     style="cyan",        width=12)
    t.add_column("5G Sub6",  style="green",       width=8)
    t.add_column("mmWave",   style="magenta",     width=8)
    t.add_column("EDL",      style="blue",        width=5)

    for key, info in sorted(SNAPDRAGON_CHIPS.items(), key=lambda x: -x[1]["year"]):
        if tier and info.get("tier") != tier:
            continue
        if only_5g and not info.get("bands_5g"):
            continue
        t.add_row(
            key,
            info["name"],
            info.get("modem","?"),
            str(info["year"]),
            info.get("tier","?"),
            "[green]✓[/green]" if info.get("sub6")    else "[dim]—[/dim]",
            "[green]✓[/green]" if info.get("mmwave")  else "[dim]—[/dim]",
            "[green]✓[/green]" if info.get("edl")     else "[dim]—[/dim]",
        )
    console.print(t)
    console.print(f"\n  [dim]Showing {len([k for k,v in SNAPDRAGON_CHIPS.items() if (not tier or v.get('tier')==tier) and (not only_5g or v.get('bands_5g'))])} chips[/dim]")


# ─── Network & band status ─────────────────────────────────────────────────────

@qualcomm.command("network-status")
@click.option("--serial", "-s", default=None)
def qc_network_status(serial):
    """
    Show current network status, connected bands, signal, and carrier info.
    No root required — reads via ADB shell and dumpsys.
    """
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    console.print(f"\n[bold cyan]Network Status — {target}[/bold cyan]\n")

    net = adb_get_network_info(target)
    svc = adb_get_service_state(target)

    from rich.table import Table
    from rich import box as rbox
    t = Table(box=rbox.SIMPLE, show_header=False, padding=(0,2))
    t.add_column("Key",   style="bold cyan", width=26)
    t.add_column("Value", style="white")

    fields = [
        ("Carrier",         net.get("operator","?")),
        ("MCC/MNC",         net.get("mcc_mnc","?")),
        ("Network type",    net.get("network_type","?")),
        ("Data type",       net.get("data_type","?")),
        ("SIM state",       net.get("sim_state","?")),
        ("Roaming",         net.get("roaming","?")),
        ("Service state",   svc.get("service_state","?")),
        ("Signal",          svc.get("signal","?")[:60] if svc.get("signal") else "?"),
        ("RIL version",     net.get("ril_version","?")),
        ("Baseband",        adb_get_prop_modem("gsm.version.baseband", target)),
    ]
    for k, v in fields:
        t.add_row(k, v or "[dim]—[/dim]")
    console.print(t)

    # Extended network info from dumpsys telephony
    console.print("\n[bold]Telephony Details:[/bold]")
    _, tel_out, _ = run_adb(
        ["shell", "dumpsys telephony.registry 2>/dev/null | grep -iE '(band|lte|nr|5g|signal|type|state|operator)' | head -25"],
        serial=target, check=False
    )
    for line in tel_out.strip().splitlines()[:20]:
        console.print(f"  [dim]{line.strip()[:100]}[/dim]")

    # Physical channel config (shows active bands)
    console.print("\n[bold]Active Physical Channels:[/bold]")
    _, phys_out, _ = run_adb(
        ["shell", "dumpsys phone 2>/dev/null | grep -iA2 -iE '(physicalChannel|band|earfcn|arfcn|channel)' | head -30"],
        serial=target, check=False
    )
    if phys_out.strip():
        for line in phys_out.strip().splitlines()[:15]:
            console.print(f"  [cyan]{line.strip()[:100]}[/cyan]")
    else:
        console.print("  [dim](Not available — try with root for deeper info)[/dim]")


@qualcomm.command("bands-info")
@click.option("--serial", "-s", default=None)
def qc_bands_info(serial):
    """
    Display LTE and 5G band information for the device and carrier.
    Shows active bands, signal per band, and band reference table.
    No root required.
    """
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    console.print(f"\n[bold cyan]LTE / 5G Band Information — {target}[/bold cyan]\n")

    # Read band config via multiple methods
    config = adb_read_band_config_efs(target)

    # Try dumpsys phone for active band info
    _, dp_out, _ = run_adb(
        ["shell", "dumpsys phone 2>/dev/null"],
        serial=target, check=False
    )

    # Extract active band info
    console.print("[bold]Active Band Detection:[/bold]")
    band_found = False
    for line in dp_out.splitlines():
        ls = line.strip().lower()
        if any(kw in ls for kw in ["band","earfcn","arfcn","freq","lte","nr5g","5gnr"]):
            if len(line.strip()) < 120:
                console.print(f"  [cyan]{line.strip()}[/cyan]")
                band_found = True
    if not band_found:
        console.print("  [dim]Run with root for detailed band info[/dim]")

    # AT command band read (if port available)
    if config.get("at_port"):
        console.print(f"\n[bold]AT Command Port:[/bold] [green]{config['at_port']}[/green]")
        console.print("  [dim]Use: watchrom qualcomm at-cmd --cmd 'AT+QNWINFO' to query band[/dim]")

    # Show dumpsys band config
    if config.get("dumpsys_bands"):
        console.print("\n[bold]Band Configuration (dumpsys):[/bold]")
        for line in config["dumpsys_bands"].splitlines()[:12]:
            console.print(f"  [dim]{line.strip()[:100]}[/dim]")

    # Reference table: Common LTE bands
    console.print(f"\n[bold]Common LTE Band Reference:[/bold]")
    from rich.table import Table
    from rich import box as rbox
    t = Table(box=rbox.SIMPLE, border_style="dim", show_header=True,
              header_style="bold cyan")
    t.add_column("Band",   style="green", width=8)
    t.add_column("Freq",   style="white", width=16)
    t.add_column("Region", style="dim",   width=28)
    for band_num, info in sorted(LTE_BANDS.items()):
        t.add_row(f"B{band_num}", info["freq"], info["region"])
    console.print(t)

    # 5G NR reference
    console.print(f"\n[bold]5G NR Band Reference:[/bold]")
    t2 = Table(box=rbox.SIMPLE, border_style="dim", show_header=True,
               header_style="bold yellow")
    t2.add_column("Band",   style="yellow", width=8)
    t2.add_column("Freq",   style="white",  width=14)
    t2.add_column("Type",   style="cyan",   width=10)
    t2.add_column("Region", style="dim",    width=28)
    for band_id, info in NR_BANDS.items():
        t2.add_row(band_id, info["freq"], info["type"], info["region"])
    console.print(t2)


@qualcomm.command("band-presets")
def qc_band_presets():
    """List available band configuration presets."""
    from rich.table import Table
    from rich import box as rbox
    t = Table(title="Band Configuration Presets",
              box=rbox.ROUNDED, border_style="cyan")
    t.add_column("Preset",  style="bold green", width=18)
    t.add_column("Description", style="white",  width=46)
    t.add_column("LTE Mask",    style="dim",    width=22)
    t.add_column("NR Mask",     style="dim",    width=22)
    for name, info in BAND_PRESETS.items():
        t.add_row(name, info["desc"], info["lte"], info["nr"])
    console.print(t)
    console.print("\n  [dim]Apply a preset: [bold]watchrom qualcomm band-set --preset us_tmobile[/bold][/dim]")
    console.print("  [dim]Custom mask:     [bold]watchrom qualcomm band-set --lte 0x... --nr 0x...[/bold][/dim]")


# ─── Band configuration write ──────────────────────────────────────────────────

@qualcomm.command("band-set")
@click.option("--serial",  "-s", default=None)
@click.option("--preset",  "-p", default=None,
              type=click.Choice(list(BAND_PRESETS.keys())),
              help="Apply a named band preset")
@click.option("--lte",     default=None, help="LTE band bitmask (hex, e.g. 0x2000000401E1)")
@click.option("--nr",      default=None, help="5G NR band bitmask (hex)")
@click.option("--bands",   default=None,
              help="Comma-separated LTE band numbers to enable (e.g. 2,4,5,12,66,71)")
@click.option("--lte-only","lte_only", is_flag=True,
              help="Set LTE-only mode (disables 5G NR — saves battery)")
@click.option("--5g-preferred","prefer_5g", is_flag=True,
              help="Enable 5G preferred with LTE fallback")
@click.option("--method",  "-m",
              type=click.Choice(["efs","qmi","at"]), default="efs",
              help="Write method: efs (root, ADB), qmi (QPST), at (AT command)")
@click.option("--dry-run", is_flag=True, help="Show what would be done without writing")
def qc_band_set(serial, preset, lte, nr, bands, lte_only, prefer_5g, method, dry_run):
    """
    Configure LTE and 5G NR band preferences on Qualcomm modem.

    Band changes tell the modem which frequencies to search/prefer.
    This is the standard method used by network engineers and ROM devs.

    SAFETY: Band masks are fully reversible. Use --preset all_bands to restore.
    Requires root for EFS method. AT command method may work without root.

    Examples:
      watchrom qualcomm band-set --preset us_tmobile
      watchrom qualcomm band-set --bands 2,4,12,66,71 --lte-only
      watchrom qualcomm band-set --preset all_bands    (restore defaults)
    """
    console.print(SAFETY_NOTICE)

    # Resolve mask values
    lte_mask = None
    nr_mask  = None

    if preset:
        p = BAND_PRESETS[preset]
        lte_mask = int(p["lte"], 16)
        nr_mask  = int(p["nr"], 16)
        console.print(f"  [bold]Preset :[/bold] {preset} — {p['desc']}")

    if lte:
        lte_mask = int(lte, 16)
    if nr:
        nr_mask = int(nr, 16)

    if bands:
        band_list = [int(b.strip().replace("B","").replace("b",""))
                     for b in bands.split(",") if b.strip()]
        lte_low, lte_high = build_lte_bitmask(band_list)
        lte_mask = lte_low  # primary 64-bit value for writes
        console.print(f"  [bold]Bands  :[/bold] {', '.join(f'B{b}' for b in sorted(band_list))}")
        console.print(f"  [bold]LTE low (B1-B64) :[/bold] 0x{lte_low:016X}")
        if lte_high:
            console.print(f"  [bold]LTE high (B65+) :[/bold] 0x{lte_high:016X}")

    if lte_only:
        nr_mask = 0
        if not lte_mask:
            lte_mask = int(BAND_PRESETS["all_bands"]["lte"], 16)
        console.print("  [bold]Mode   :[/bold] LTE only (5G NR disabled)")

    if prefer_5g:
        if not lte_mask:
            lte_mask = int(BAND_PRESETS["all_bands"]["lte"], 16)
        if not nr_mask:
            nr_mask  = int(BAND_PRESETS["all_bands"]["nr"], 16)
        console.print("  [bold]Mode   :[/bold] 5G preferred with LTE fallback")

    if lte_mask is None and nr_mask is None:
        console.print("[red]✗ Specify --preset, --bands, --lte/--nr mask, --lte-only, or --5g-preferred[/red]")
        return

    # Show what will be written
    if lte_mask is not None:
        lte_low_disp  = lte_mask & 0xFFFFFFFFFFFFFFFF
        lte_high_disp = (lte_mask >> 64) & 0xFFFFFFFFFFFFFFFF if lte_mask > 0xFFFFFFFFFFFFFFFF else 0
        active_bands = parse_lte_bitmask(lte_low_disp, lte_high_disp)
        console.print(f"\n  [bold]LTE bands to enable:[/bold]")
        console.print(f"    {format_band_list(active_bands, LTE_BANDS)}")
        console.print(f"  [bold]LTE mask (low) :[/bold] 0x{lte_low_disp:016X}")
        if lte_high_disp:
            console.print(f"  [bold]LTE mask (high):[/bold] 0x{lte_high_disp:016X}")
    if nr_mask is not None:
        console.print(f"  [bold]NR mask :[/bold] 0x{nr_mask:016X}")
        if nr_mask == 0:
            console.print(f"  [dim](5G NR disabled)[/dim]")

    if dry_run:
        console.print(f"\n[yellow]  Dry run — no changes written.[/yellow]")
        return

    if not click.confirm("\n  Apply band configuration to device?", default=False):
        return

    # Connect to device
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device online.[/red]")
        return
    target = serial or online[0]

    # Backup first
    console.print("\n[cyan]→ Creating EFS backup before changes...[/cyan]")
    bk_dir = OUTPUT_DIR / "qualcomm_backups" / target / time.strftime("%Y%m%d_%H%M%S")
    _quick_efs_backup(target, bk_dir)

    if method == "efs":
        _write_bands_efs(target, lte_mask, nr_mask)
    elif method == "at":
        _write_bands_at(target, lte_mask, nr_mask)
    elif method == "qmi":
        _write_bands_qpst(target, lte_mask, nr_mask)


def _quick_efs_backup(serial: str, out_dir: Path):
    """Quick EFS config backup before writing."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # Backup key EFS NV items via ADB
    efs_paths = [
        NV_ITEMS["efs_lte_band_pref"]["path"],
        NV_ITEMS["efs_nr_band_pref"]["path"],
        NV_ITEMS["efs_mode_pref"]["path"],
    ]
    for efs_path in efs_paths:
        fname = efs_path.replace("/","_").lstrip("_")
        local = out_dir / fname
        run_adb(
            ["shell", f"su -c 'cp {efs_path} /sdcard/wrom_bk_{fname} 2>/dev/null'"],
            serial=serial, check=False
        )
        run_adb(
            ["pull", f"/sdcard/wrom_bk_{fname}", str(local)],
            serial=serial, check=False
        )
    # Also backup via dumpsys snapshot
    _, ds_out, _ = run_adb(
        ["shell", "dumpsys phone 2>/dev/null | grep -iE '(band|nr|lte|mode)' | head -50"],
        serial=serial, check=False
    )
    (out_dir / "band_config_snapshot.txt").write_text(ds_out)
    console.print(f"  [green]✓ Backup saved: {out_dir}[/green]")


def _write_bands_efs(serial: str, lte_mask: int, nr_mask: int):
    """Write band config to EFS via ADB root (most reliable method)."""
    console.print("\n[cyan]→ Writing band config via EFS (ADB root)...[/cyan]")

    # Check root
    _, root_out, _ = run_adb(["shell", "su -c id"], serial=serial, check=False)
    if "uid=0" not in root_out:
        console.print("[red]✗ Root required for EFS write method.[/red]")
        console.print("  Try: [bold]--method at[/bold] for AT command method (no root)")
        return

    success = []
    if lte_mask is not None:
        # Write LTE band preference (little-endian 8 bytes)
        lte_bytes = struct.pack("<Q", lte_mask & 0xFFFFFFFFFFFFFFFF)
        lte_hex   = lte_bytes.hex()
        lte_path  = NV_ITEMS["efs_lte_band_pref"]["path"]

        # Use printf to write binary via ADB shell
        cmd = (f"su -c 'printf \"\\x{chr(10).join(lte_hex[i:i+2] for i in range(0,16,2))}\" "
               f"> {lte_path} 2>/dev/null && echo OK'")
        # Simpler: use Python on-device
        py_cmd = (
            f"su -c 'python3 -c \""
            f"import struct; "
            f"open(\\\"{lte_path}\\\",\\\"wb\\\").write(struct.pack(\\\"<Q\\\",{lte_mask}))"
            f"\" && echo OK'"
        )
        _, out, _ = run_adb(["shell", py_cmd], serial=serial, check=False)
        if "OK" in out:
            console.print(f"  [green]✓ LTE band mask written: 0x{lte_mask:016X}[/green]")
            success.append("LTE")
        else:
            console.print(f"  [yellow]! LTE write via python3 failed, trying busybox...[/yellow]")
            bb_cmd = (
                f"su -c 'echo -n -e \"{' '.join(chr(b) for b in struct.pack('<Q', lte_mask))}\" "
                f"> {lte_path} && echo OK'"
            )
            _, out2, _ = run_adb(["shell", bb_cmd], serial=serial, check=False)

    if nr_mask is not None:
        nr_path = NV_ITEMS["efs_nr_band_pref"]["path"]
        py_cmd_nr = (
            f"su -c 'python3 -c \""
            f"import struct; "
            f"open(\\\"{nr_path}\\\",\\\"wb\\\").write(struct.pack(\\\"<Q\\\",{nr_mask}))"
            f"\" && echo OK'"
        )
        _, out_nr, _ = run_adb(["shell", py_cmd_nr], serial=serial, check=False)
        if "OK" in out_nr:
            console.print(f"  [green]✓ NR band mask written:  0x{nr_mask:016X}[/green]")
            success.append("NR")

    if success:
        console.print(f"\n  [bold yellow]Reboot required for changes to take effect.[/bold yellow]")
        if click.confirm("  Reboot device now?", default=True):
            run_adb(["reboot"], serial=serial, check=False)
            console.print("  [green]✓ Rebooting...[/green]")
    else:
        console.print("  [red]✗ Write failed. Check root access and EFS paths.[/red]")


def _write_bands_at(serial: str, lte_mask: int, nr_mask: int):
    """Write band config via AT commands (may work without root on some devices)."""
    console.print("\n[cyan]→ Writing band config via AT commands...[/cyan]")

    # Find AT port
    at_port = None
    for port in ["/dev/smd7","/dev/at_mdm0","/dev/at0","/dev/ttyUSB2","/dev/ttyUSB1"]:
        _, out, _ = run_adb(["shell",f"ls {port} 2>/dev/null"], serial=serial, check=False)
        if port in out:
            at_port = port
            break

    if not at_port:
        console.print("[yellow]! No AT command port found on device.[/yellow]")
        console.print("  Try: --method efs (requires root)")
        return

    console.print(f"  [green]AT port: {at_port}[/green]")

    # Qualcomm AT command for band lock: AT+QNWPREFMODI and AT+QCFG
    at_commands = []
    if lte_mask is not None:
        lte_hex = f"0x{lte_mask:08X}"
        at_commands.append(f"AT+QCFG=\"band\",0,{lte_hex},0,1")  # GSM=0, LTE=mask, NR=0
    if nr_mask is not None:
        nr_hex = f"0x{nr_mask:08X}"
        at_commands.append(f"AT+QCFG=\"band\",0,0x{lte_mask or 0:08X},{nr_hex},1")

    for cmd in at_commands:
        console.print(f"  [dim]AT> {cmd}[/dim]")
        shell_cmd = f"echo -e '{cmd}\\r' > {at_port} && sleep 0.5 && timeout 1 cat {at_port} 2>/dev/null"
        _, out, _ = run_adb(["shell", f"su -c '{shell_cmd}'"], serial=serial, check=False)
        if "OK" in out:
            console.print(f"  [green]✓ AT command accepted[/green]")
        else:
            console.print(f"  [dim]{out.strip()[:80]}[/dim]")

    console.print("\n  [dim]Note: AT+QCFG band syntax varies by device/modem firmware.[/dim]")
    console.print("  [dim]If this fails, use --method efs (requires root).[/dim]")


def _write_bands_qpst(serial: str, lte_mask: int, nr_mask: int):
    """Guide for writing bands via QPST tool (desktop software)."""
    console.print("\n[bold cyan]QPST Band Configuration Guide[/bold cyan]\n")
    console.print("  QPST (Qualcomm Product Support Tools) is the official")
    console.print("  desktop tool for modem NV configuration.\n")
    console.print("  [bold]Steps:[/bold]")
    console.print("  1. Download QPST from Qualcomm or partner portal")
    console.print("  2. Enable DIAG mode on device:")
    console.print("     adb shell setprop sys.usb.config diag,adb")
    console.print("  3. Open QPST → EFS Explorer → /nv/item_files/modem/mmode/")
    console.print(f"  4. Edit lte_bandpref: write [bold]{f'0x{lte_mask:016X}' if lte_mask else 'N/A'}[/bold]")
    console.print(f"  5. Edit nr5g_bandpref: write [bold]{f'0x{nr_mask:016X}' if nr_mask else 'N/A'}[/bold]")
    console.print("  6. Reboot device\n")
    console.print("  [bold]Alternative: QFIL (Qualcomm Flash Image Loader)[/bold]")
    console.print("  Use QFIL for EFS backup/restore via DIAG/EDL port.\n")

    # Enable DIAG mode on device
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if online:
        target = serial or online[0]
        if click.confirm("  Enable DIAG mode on device now?", default=False):
            run_adb(["shell", "setprop sys.usb.config diag,adb"],
                    serial=target, check=False)
            console.print("  [green]✓ DIAG mode enabled. Check Device Manager / lsusb.[/green]")


# ─── AT command interface ──────────────────────────────────────────────────────

@qualcomm.command("at-cmd")
@click.option("--serial", "-s", default=None)
@click.option("--cmd",    "-c", required=True,
              help="AT command to send (e.g. AT+QNWINFO, AT+CSQ)")
@click.option("--port",   "-p", default=None,
              help="AT port path (auto-detected if not specified)")
def qc_at_cmd(serial, cmd, port):
    """
    Send an AT command to the modem.

    Useful for querying current bands, signal strength, operator info.
    May work without root on some devices.

    Common commands:
      AT+QNWINFO        — current network info and band
      AT+CSQ            — signal strength
      AT+COPS?          — current operator
      AT+CEREG?         — LTE registration status
      AT+C5GREG?        — 5G NR registration status
      AT+QCFG="band"   — read current band config
    """
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    # Find AT port
    at_port = port
    if not at_port:
        for p in ["/dev/smd7","/dev/at_mdm0","/dev/at0",
                  "/dev/ttyUSB0","/dev/ttyUSB1","/dev/ttyUSB2"]:
            _, out, _ = run_adb(["shell",f"ls {p} 2>/dev/null"], serial=target, check=False)
            if p in out.strip():
                at_port = p
                break

    if not at_port:
        console.print("[red]✗ No AT port found.[/red]")
        console.print("  Common ports: /dev/smd7, /dev/at_mdm0, /dev/ttyUSB*")
        console.print("  Try enabling DIAG mode: adb shell setprop sys.usb.config diag,adb")
        return

    console.print(f"  [dim]Port: {at_port}[/dim]")
    console.print(f"  [cyan]Sending: {cmd}[/cyan]\n")

    shell = (
        f"echo -e '{cmd}\\r\\n' > {at_port} && "
        f"sleep 1 && timeout 2 cat {at_port} 2>/dev/null"
    )
    _, out, _ = run_adb(["shell", shell], serial=target, check=False)
    if out.strip():
        console.print(out.strip())
    else:
        # Try with root
        _, out2, _ = run_adb(["shell", f"su -c '{shell}'"], serial=target, check=False)
        console.print(out2.strip() if out2.strip() else "[dim]No response[/dim]")


# ─── EFS backup / restore ─────────────────────────────────────────────────────

@qualcomm.command("efs-backup")
@click.option("--serial",    "-s", default=None)
@click.option("--out",       "-o", default=None, help="Output directory")
@click.option("--full",      "-f", is_flag=True,
              help="Full EFS backup via EDL (device must be in EDL/DIAG mode)")
@click.option("--port",      "-p", default=None,
              help="EDL/DIAG serial port (e.g. /dev/ttyUSB0)")
def qc_efs_backup(serial, out, full, port):
    """
    Backup modem EFS (Embedded File System) — CRITICAL before any changes.

    EFS contains: band config, NV items, modem calibration data, provisioning.
    Always backup before modifying band settings or flashing modem firmware.

    Quick backup (ADB root): backs up band config NV items
    Full backup (--full, EDL): complete EFS via bkerler/edl tool
    """
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    target = serial or (online[0] if online else None)

    out_dir = Path(out) if out else (
        OUTPUT_DIR / "qualcomm_backups" / (target or "unknown") /
        time.strftime("%Y%m%d_%H%M%S")
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"\n[bold cyan]EFS Backup[/bold cyan]")
    console.print(f"  Output: {out_dir}\n")

    if full:
        # Full EFS via EDL
        diag_port = port
        if not diag_port:
            # Check for DIAG device
            for p in ["/dev/ttyUSB0","/dev/ttyUSB1","/dev/diag"]:
                if Path(p).exists():
                    diag_port = p
                    break

        if not diag_port:
            console.print("[yellow]! No DIAG/EDL port found. Checking for EDL USB device...[/yellow]")
            if check_edl_device():
                console.print("[green]✓ Qualcomm EDL device detected (lsusb)[/green]")
            else:
                console.print("[dim]Connect device in EDL mode or enable DIAG:[/dim]")
                console.print("  [dim]adb shell setprop sys.usb.config diag,adb[/dim]")

        try:
            result = efs_backup_via_edl(diag_port or "/dev/ttyUSB0", out_dir)
            console.print(f"[green]✓ Full EFS backup: {result}[/green]")
        except Exception as e:
            console.print(f"[yellow]! Full EFS backup failed: {e}[/yellow]")
            console.print("  Falling back to ADB backup...")
            _quick_efs_backup(target, out_dir)
    else:
        # Quick ADB backup of band config items
        if not target:
            console.print("[red]✗ No device connected.[/red]")
            return
        _quick_efs_backup(target, out_dir)

    # Write manifest
    manifest = out_dir / "BACKUP_MANIFEST.txt"
    contents = list(out_dir.rglob("*"))
    with open(manifest, "w") as f:
        f.write(f"WatchROM EFS Backup\n")
        f.write(f"Device: {target}\nTime: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Files:\n")
        for item in contents:
            if item.is_file():
                f.write(f"  {item.name}  ({item.stat().st_size} bytes)\n")

    console.print(f"\n[bold green]✓ Backup complete → {out_dir}[/bold green]")
    console.print(f"  Restore: [bold]watchrom qualcomm efs-restore {out_dir}[/bold]")


@qualcomm.command("efs-restore")
@click.option("--serial",    "-s", default=None)
@click.argument("backup_dir")
def qc_efs_restore(serial, backup_dir):
    """
    Restore modem EFS band config from a WatchROM backup.
    Restores the band preference NV items saved by efs-backup.
    """
    bk = Path(backup_dir)
    if not bk.is_dir():
        console.print(f"[red]✗ Not a directory: {backup_dir}[/red]")
        return

    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    console.print(f"\n[bold cyan]EFS Restore — {target}[/bold cyan]")
    console.print(f"  Source: {bk}\n")

    if not click.confirm("  This will overwrite current band config. Continue?", default=False):
        return

    # Restore each backed-up EFS file
    restored = 0
    efs_paths = {
        NV_ITEMS["efs_lte_band_pref"]["path"]: "lte_bandpref",
        NV_ITEMS["efs_nr_band_pref"]["path"]:  "nr5g_bandpref",
        NV_ITEMS["efs_mode_pref"]["path"]:     "mode_pref",
    }
    for efs_path, fname_hint in efs_paths.items():
        # Look for backup file
        candidates = list(bk.glob(f"*{fname_hint}*")) + list(bk.glob(f"*{efs_path.split('/')[-1]}*"))
        if candidates:
            src = candidates[0]
            remote_tmp = f"/sdcard/wrom_restore_{src.name}"
            run_adb(["push", str(src), remote_tmp], serial=target, check=False)
            _, out, _ = run_adb(
                ["shell", f"su -c 'cp {remote_tmp} {efs_path} && echo OK'"],
                serial=target, check=False
            )
            if "OK" in out:
                console.print(f"  [green]✓ Restored: {efs_path}[/green]")
                restored += 1
            run_adb(["shell", f"rm {remote_tmp}"], serial=target, check=False)

    if restored > 0:
        console.print(f"\n  [bold yellow]Reboot required.[/bold yellow]")
        if click.confirm("  Reboot now?", default=True):
            run_adb(["reboot"], serial=serial, check=False)
    else:
        console.print("  [yellow]! No backup files matched EFS paths.[/yellow]")


# ─── EDL mode ─────────────────────────────────────────────────────────────────

@qualcomm.command("edl")
@click.option("--serial",   "-s", default=None)
@click.option("--enter",    "-e", is_flag=True, help="Reboot device into EDL mode")
@click.option("--check",    "-c", is_flag=True, help="Check if EDL device is connected (USB 9008)")
@click.option("--loader",   "-l", default=None,
              help="Path to firehose .mbn loader (required for EDL operations)")
@click.option("--dump-efs", is_flag=True,
              help="Dump EFS via EDL (requires loader + bkerler/edl)")
def qc_edl(serial, enter, check, loader, dump_efs):
    """
    Qualcomm EDL (Emergency Download) mode — 9008 protocol.

    EDL is Qualcomm's low-level flashing interface built into the Boot ROM.
    It is identified as USB 0x05C6:0x9008 (Qualcomm HS-USB QDLoader).

    SAFETY NOTES:
      ✓ EFS backup via EDL — safe, read-only
      ✓ Modem firmware flash using official .mbn files — safe
      ✗ Flashing wrong partitions with wrong loader — brick risk
      → Always backup EFS before any EDL write operations

    Requires: bkerler/edl (auto-installed by watchrom setup)
    """
    console.print(f"\n[bold cyan]Qualcomm EDL Mode (USB 9008)[/bold cyan]\n")

    if check:
        console.print("[cyan]→ Scanning for Qualcomm EDL device (0x05C6:0x9008)...[/cyan]")
        if check_edl_device():
            console.print("[bold green]✓ Qualcomm EDL device detected![/bold green]")
            _, lsusb, _ = run(["lsusb"], check=False)
            for line in lsusb.splitlines():
                if "Qualcomm" in line or "9008" in line or "05c6" in line.lower():
                    console.print(f"  [green]{line.strip()}[/green]")
        else:
            console.print("[yellow]! No EDL device found.[/yellow]")
            console.print("  Connect device in EDL mode and try again.")
        return

    if enter:
        devs = adb_devices()
        online = [s for s, st in devs if st == "device"]
        if not online:
            console.print("[red]✗ No ADB device to reboot.[/red]")
            return
        target = serial or online[0]

        console.print("[bold yellow]⚠ EDL MODE ENTRY[/bold yellow]")
        console.print("  Device will reboot into Emergency Download mode.")
        console.print("  It will appear as USB 0x05C6:0x9008.")
        console.print("  You will need a firehose loader to interact with it.\n")

        if not click.confirm("  Reboot into EDL mode?", default=False):
            return

        # ADB EDL reboot (requires ADB root or specific kernel config)
        rc, _, err = run_adb(["reboot", "edl"], serial=target, check=False)
        if rc == 0:
            console.print("[green]✓ EDL reboot command sent.[/green]")
        else:
            # Try root method
            run_adb(["shell", "su -c 'reboot edl'"], serial=target, check=False)
            console.print("[green]✓ EDL reboot via root sent.[/green]")

        console.print("\n[bold]Next steps:[/bold]")
        console.print("  1. Confirm with: [bold]watchrom qualcomm edl --check[/bold]")
        console.print("  2. Find firehose loader for your device")
        console.print("  3. Use bkerler/edl or QFIL for partition operations")
        return

    # General EDL guide
    console.print("[bold yellow]Hardware EDL Entry (when ADB is unavailable):[/bold yellow]")
    console.print("  Method 1 — Button combo (most devices):")
    console.print("    Power off → Hold Vol+ + Vol− simultaneously → Connect USB")
    console.print("    Some: Hold Vol− only. Try both.\n")
    console.print("  Method 2 — EDL test point (PCB short):")
    console.print("    Locate EDL/DLOAD pad on PCB (near UFS/eMMC)")
    console.print("    Short pad to GND for 2-3 seconds while connecting USB\n")
    console.print("  Method 3 — ADB (if device boots):")
    console.print("    watchrom qualcomm edl --enter\n")

    console.print("[bold yellow]Working with EDL — bkerler/edl:[/bold yellow]")
    edl_repo = REPOS_DIR / "edl"
    edl_path = str(edl_repo / "edl.py") if edl_repo.exists() else "edl"
    console.print(f"  [dim]Tool location: {edl_path}[/dim]\n")
    console.print("  # Read partition info")
    console.print(f"  python3 {edl_path} printgpt\n")
    console.print("  # Backup a partition (e.g. modem)")
    console.print(f"  python3 {edl_path} r modem modem.img\n")
    console.print("  # Flash a partition")
    console.print(f"  python3 {edl_path} w boot boot_patched.img\n")
    console.print("  # EFS backup")
    console.print(f"  python3 {edl_path} qfil efs-backup --output ./efs_backup/\n")

    console.print("[bold yellow]Firehose Loader Notes:[/bold yellow]")
    console.print("  A firehose loader (.mbn/.elf) is required for most EDL operations.")
    console.print("  The correct loader is device-specific (matches SoC + board).")
    console.print("  Wrong loader = failed handshake (safe), NOT a brick.")
    console.print("  Find loaders in TWRP/LineageOS device repos or OEM EDL packages.\n")

    # Show known loaders
    console.print("[bold]Known Firehose Availability:[/bold]")
    from rich.table import Table
    from rich import box as rbox
    t = Table(box=rbox.SIMPLE, border_style="dim")
    t.add_column("Chip",  style="green",  width=12)
    t.add_column("Notes", style="dim",    width=60)
    for chip, info in FIREHOSE_INFO.items():
        t.add_row(chip, info["notes"])
    console.print(t)


@qualcomm.command("diag-enable")
@click.option("--serial", "-s", default=None)
def qc_diag_enable(serial):
    """
    Enable Qualcomm DIAG mode via ADB for use with QPST/QFIL.
    DIAG mode exposes the modem diagnostic interface over USB.
    No root required on most devices.
    """
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    console.print(f"\n[bold cyan]Enable DIAG Mode — {target}[/bold cyan]\n")
    console.print("  DIAG mode exposes the Qualcomm diagnostic interface.")
    console.print("  Required for: QPST, QFIL, NV item editing, EFS access.")
    console.print("  USB ID in DIAG mode: 0x05C6 (Qualcomm)\n")

    # Enable DIAG
    configs = ["diag,adb", "diag,serial,adb", "diag,adb,rmnet"]
    for cfg in configs:
        _, out, _ = run_adb(
            ["shell", f"setprop sys.usb.config {cfg} && getprop sys.usb.config"],
            serial=target, check=False
        )
        if cfg.split(",")[0] in out:
            console.print(f"[green]✓ USB config set: {cfg}[/green]")
            break

    console.print("\n  [dim]Verify: lsusb | grep 05c6[/dim]")
    console.print("  [dim]DIAG port will appear as /dev/ttyUSBx or COM port[/dim]")
    console.print("\n  [bold]QPST connection:[/bold]")
    console.print("    QPST → Communication → Add New Port → select DIAG COM port")
    console.print("    QPST → EFS Explorer → browse /nv/item_files/")
