"""
modem_bands.py — Universal LTE/5G Band Configuration
Supports: Qualcomm (NV/EFS), MTK (NVRAM/AT), Unisoc (NV/AT),
          Rockchip/Allwinner (modem-side AT commands)

Band configuration is the standard method for:
  - Carrier compatibility (traveling internationally)
  - Forcing specific bands for better signal
  - Disabling 5G to save battery
  - Enabling bands locked by carrier on unlocked devices

All changes are reversible. EFS/NVRAM backup is created automatically.
"""
import click
import time
import struct
from pathlib import Path
from modules import (
    run, run_adb, adb_devices, get_device_props,
    detect_chipset_from_props, OUTPUT_DIR, WORKSPACE, console
)
from modules.qualcomm_chips import (
    BAND_PRESETS, LTE_BANDS, NR_BANDS, VERIZON_BANDS,
    compute_lte_mask_hex, compute_nr_mask_hex, verify_carrier_masks
)

# ── MTK band config reference ──────────────────────────────────────────────────
# MTK Engineering Mode app provides a GUI, but we can also write via AT commands
# and NVRAM (on rooted devices)

MTK_BAND_NV_PATHS = {
    # NVRAM paths for MTK modem band configuration
    "lte_band":   "/data/nvram/md/NVRAM/CALIBRAT/File_Ef_Cali",
    "at_port_candidates": [
        "/dev/ttyC0",   # MTK CCCI AT
        "/dev/ttyMT0",  # MTK UART
        "/dev/ttyGS0",  # MTK USB serial
        "/dev/ttyS0",
        "/dev/smd0",
    ],
}

# MTK AT command band mask format (different from Qualcomm)
# MTK uses AT+ERAT for RAT control and AT+EPBSE for band selection
MTK_BAND_COMMANDS = {
    "query_rat":      "AT+ERAT?",         # Query current RAT mode
    "query_band":     "AT+EPBSE?",        # Query band config
    "set_lte_only":   'AT+ERAT=3,2',      # LTE only
    "set_auto":       'AT+ERAT=0,0',      # Auto (all RATs)
    "set_5g_pref":    'AT+ERAT=0,0,0,1',  # 5G preferred
    "set_nr_only":    'AT+ERAT=0,0,0,2',  # NR only
    # AT+EPBSE format: AT+EPBSE=<GSM_band>,<UMTS_band>,<LTE_band_low>,<LTE_band_high>
    # LTE bands as 64-bit hex split into two 32-bit words
}

# Unisoc / Spreadtrum band config
UNISOC_BAND_NV_PATHS = {
    "at_port_candidates": [
        "/dev/stty0",   # Unisoc CCCI
        "/dev/stty1",
        "/dev/slog0",
        "/dev/ttyS1",
        "/dev/ttyUSB0",
    ],
    "nv_dir": "/data/misc/wifi",  # Some Unisoc store NV here
}

UNISOC_BAND_COMMANDS = {
    "query_rat":   "AT+ERAT?",
    "query_band":  "AT+EPBSE?",
    "set_lte_only":'AT+ERAT=3,2',
    "set_auto":    'AT+ERAT=0,0',
}

# MediaTek Engineering Mode app package (provides GUI band selection)
MTK_ENG_MODE_PKG = "com.mediatek.engineermode"
MTK_ENG_MODE_PKG2 = "com.mtk.engineermode"


# ── Common carrier band profiles ──────────────────────────────────────────────

CARRIER_PROFILES = {
    # ── United States ─────────────────────────────────────────────────────
    "verizon": {
        "display":   "Verizon Wireless (US)",
        "lte_bands": [2, 4, 5, 13, 48, 66],
        "nr_sub6":   ["n5", "n48", "n66", "n77"],
        "nr_mmwave": ["n260", "n261"],
        "primary_lte": 13,
        "primary_nr":  "n77",
        "notes": [
            "B13 (700 MHz) is Verizon's primary band — always include",
            "n77 C-band (3.7 GHz) = Verizon 5G Ultra Wideband",
            "n260/n261 mmWave only works within ~100m of small cell",
            "B48/n48 = CBRS, used in enterprise/private networks",
            "For best coverage: enable B2+B4+B5+B13+B66",
            "For 5G priority: add n5+n77",
        ],
        "lte_hex_low":  "0x000080000000101A",
        "lte_hex_high": "0x0000000000000002",  # B66 in upper word
        "nr_hex":       "0x0000000000000118",
    },
    "tmobile": {
        "display":   "T-Mobile US",
        "lte_bands": [2, 4, 5, 12, 25, 26, 41, 66, 71],
        "nr_sub6":   ["n25", "n41", "n71"],
        "nr_mmwave": ["n260", "n261"],
        "primary_lte": 12,
        "primary_nr":  "n41",
        "notes": [
            "B71 (600 MHz) = T-Mobile Extended Range 5G — best rural coverage",
            "n41 (2.5 GHz) = T-Mobile Ultra Capacity 5G — fastest indoor",
            "n25 (1900 MHz) = supplemental 5G on PCS spectrum",
            "n260/n261 mmWave = T-Mobile 5G Ultra Capacity (dense urban)",
            "B12 is nationwide coverage, B41 is capacity in cities",
            "B25/B26 = Sprint legacy bands (still active after merger)",
        ],
        "lte_hex_low":  "0x000001000300081A",
        "lte_hex_high": "0x0000000000000042",
        "nr_hex":       "0xC000000000420800",
    },
    "att": {
        "display":   "AT&T (US)",
        "lte_bands": [2, 4, 5, 7, 14, 17, 29, 30, 66],
        "nr_sub6":   ["n77", "n78"],
        "nr_mmwave": [],
        "primary_lte": 17,
        "primary_nr":  "n77",
        "notes": [
            "B14 = FirstNet priority band for first responders",
            "B17 is AT&T's primary 700 MHz coverage band",
            "B29 is downlink-only supplemental (SDL)",
            "n77 C-band = AT&T 5G+ (fast mid-band)",
        ],
        "lte_hex_low":  "0x000000003001205A",
        "lte_hex_high": "0x0000000000000002",
        "nr_hex":       "0x0000000000000018",
    },
    "firstnet": {
        "display":   "FirstNet (AT&T) — First Responder Network",
        "lte_bands": [2, 4, 14, 17, 29, 30],
        "nr_sub6":   ["n77"],
        "nr_mmwave": [],
        "primary_lte": 14,
        "primary_nr":  "n77",
        "notes": [
            "B14 is dedicated FirstNet spectrum (highest priority)",
            "Required for first responder devices",
        ],
        "lte_hex_low":  "0x000000003001200A",
        "lte_hex_high": "0x0000000000000000",
        "nr_hex":       "0x0000000000000008",
    },
    "dish_boost": {
        "display":   "Dish/Boost Mobile (US)",
        "lte_bands": [2, 26, 41, 66],
        "nr_sub6":   ["n66", "n70"],
        "nr_mmwave": [],
        "primary_lte": 41,
        "primary_nr":  "n70",
        "notes": [
            "Dish uses AWS spectrum (B66/n66) as primary",
            "n70 = 1700/2100 MHz AWS-4",
        ],
        "lte_hex_low":  "0x0000010002000002",
        "lte_hex_high": "0x0000000000000002",
        "nr_hex":       "0x0000000000002080",
    },
    "cbrs": {
        "display":   "CBRS Private Network (US — 3.5 GHz)",
        "lte_bands": [48],
        "nr_sub6":   ["n48"],
        "nr_mmwave": [],
        "primary_lte": 48,
        "primary_nr":  "n48",
        "notes": [
            "B48/n48 = 3.5 GHz Citizens Broadband Radio Service",
            "Used for private enterprise LTE/5G deployments",
            "Available on Verizon, some MVNO, and private networks",
        ],
        "lte_hex_low":  "0x0000800000000000",
        "lte_hex_high": "0x0000000000000000",
        "nr_hex":       "0x0000000000008000",
    },
    # ── International ───────────────────────────────────────────────────────
    "uk_vodafone": {
        "display":   "Vodafone UK",
        "lte_bands": [1, 2, 3, 7, 8, 20, 28],
        "nr_sub6":   ["n1","n3","n28","n78"],
        "nr_mmwave": [],
        "primary_lte": 3,
        "primary_nr":  "n78",
        "notes": ["B20 (800MHz) = UK primary coverage","n78 = UK 5G main"],
        "lte_hex_low":  "0x00000000080800C7",
        "lte_hex_high": "0x0000000000000000",
        "nr_hex":       "0x0000000000004009",
    },
    "uk_ee": {
        "display":   "EE UK",
        "lte_bands": [1, 3, 7, 8, 20, 28, 32],
        "nr_sub6":   ["n1","n3","n78"],
        "nr_mmwave": [],
        "primary_lte": 3,
        "primary_nr":  "n78",
        "notes": ["EE B3+B7+B20 = standard UK coverage","n78 = EE 5G"],
        "lte_hex_low":  "0x00000000880800C5",
        "lte_hex_high": "0x0000000000000000",
        "nr_hex":       "0x0000000000004009",
    },
    "eu_generic": {
        "display":   "Europe (generic — all major carriers)",
        "lte_bands": [1, 3, 5, 7, 8, 20, 28, 38],
        "nr_sub6":   ["n1","n3","n7","n28","n78"],
        "nr_mmwave": [],
        "primary_lte": 3,
        "primary_nr":  "n78",
        "notes": ["Works across DE/FR/IT/ES/NL and most EU carriers"],
        "lte_hex_low":  "0x00000020080800D5",
        "lte_hex_high": "0x0000000000000000",
        "nr_hex":       "0x0000000000006009",
    },
    "canada_rogers": {
        "display":   "Rogers/Fido/Shaw (Canada)",
        "lte_bands": [2, 4, 5, 7, 12, 17, 66],
        "nr_sub6":   ["n66","n77"],
        "nr_mmwave": [],
        "primary_lte": 4,
        "primary_nr":  "n77",
        "notes": ["B4/B66 AWS = Rogers primary","n77 C-band = Rogers 5G+"],
        "lte_hex_low":  "0x000000000001085A",
        "lte_hex_high": "0x0000000000000002",
        "nr_hex":       "0x0000000000002008",
    },
    "australia_telstra": {
        "display":   "Telstra (Australia)",
        "lte_bands": [1, 3, 5, 7, 28, 40],
        "nr_sub6":   ["n28","n78"],
        "nr_mmwave": [],
        "primary_lte": 28,
        "primary_nr":  "n78",
        "notes": ["B28 (700MHz) = Telstra coverage band","n78 3.5GHz = 5G"],
        "lte_hex_low":  "0x0000008008000055",
        "lte_hex_high": "0x0000000000000000",
        "nr_hex":       "0x0000000000004010",
    },
    "japan_docomo": {
        "display":   "NTT Docomo (Japan)",
        "lte_bands": [1, 3, 19, 21, 28, 42],
        "nr_sub6":   ["n77","n78","n79"],
        "nr_mmwave": ["n257"],
        "primary_lte": 1,
        "primary_nr":  "n78",
        "notes": [
            "B19 (850MHz) = Docomo primary coverage",
            "B21 (1500MHz) = Docomo supplementary",
            "n257 mmWave = Docomo 5G in dense urban areas",
        ],
        "lte_hex_low":  "0x0000020008140005",
        "lte_hex_high": "0x0000000000000000",
        "nr_hex":       "0x0000000000078000",
    },
    "korea_skt": {
        "display":   "SK Telecom (South Korea)",
        "lte_bands": [1, 3, 5, 7, 8, 42],
        "nr_sub6":   ["n78"],
        "nr_mmwave": ["n257","n258"],
        "primary_lte": 1,
        "primary_nr":  "n78",
        "notes": ["Korea 5G leaders","n257/n258 mmWave = 28GHz/26GHz 5G"],
        "lte_hex_low":  "0x00000200000000D5",
        "lte_hex_high": "0x0000000000000000",
        "nr_hex":       "0x0000000000024000",
    },
    "india_jio": {
        "display":   "Reliance Jio (India)",
        "lte_bands": [3, 5, 40],
        "nr_sub6":   ["n28","n77","n78"],
        "nr_mmwave": [],
        "primary_lte": 3,
        "primary_nr":  "n78",
        "notes": [
            "B40 (2300MHz TDD) = Jio primary LTE",
            "B3+B5 = coverage supplement",
            "n78 3.5GHz = Jio 5G True 5G",
        ],
        "lte_hex_low":  "0x0000008000000014",
        "lte_hex_high": "0x0000000000000000",
        "nr_hex":       "0x0000000000006010",
    },
    "china_telecom": {
        "display":   "China Telecom",
        "lte_bands": [1, 3, 5, 18, 40, 41],
        "nr_sub6":   ["n41","n78","n79"],
        "nr_mmwave": [],
        "primary_lte": 3,
        "primary_nr":  "n41",
        "notes": ["CT uses SA 5G network","n41 2.5GHz = primary 5G"],
        "lte_hex_low":  "0x0000018000020015",
        "lte_hex_high": "0x0000000000000000",
        "nr_hex":       "0x0000000000068002",
    },
    "global_roaming": {
        "display":   "Global Roaming (all bands)",
        "lte_bands": list(range(1, 69)),
        "nr_sub6":   list(NR_BANDS.keys()),
        "nr_mmwave": [],
        "primary_lte": 1,
        "primary_nr":  "n78",
        "notes": [
            "All bands enabled — maximum compatibility worldwide",
            "Device will search more bands (slightly more battery use)",
            "Recommended for international travel",
        ],
        "lte_hex_low":  "0xFFFFFFFFFFFFFFFF",
        "lte_hex_high": "0x000000000000000F",
        "nr_hex":       "0x7FFFFFFFFFFFFFFF",
    },
}


# ── Per-vendor AT command interface ───────────────────────────────────────────

def find_at_port(serial: str, vendor: str) -> str:
    """Find the AT command port for a device based on vendor."""
    candidates = {
        "qualcomm": ["/dev/smd7","/dev/at_mdm0","/dev/at0",
                     "/dev/ttyUSB1","/dev/ttyUSB2"],
        "mtk":      ["/dev/ttyC0","/dev/ttyMT0","/dev/ttyGS0",
                     "/dev/ttyS0","/dev/ccci_aud_md1"],
        "unisoc":   ["/dev/stty0","/dev/stty1","/dev/ttyS1",
                     "/dev/sprd_bsp_atcmd","/dev/ttyUSB0"],
        "rockchip": ["/dev/ttyS1","/dev/ttyUSB0","/dev/ttyACM0"],
        "allwinner":[ "/dev/ttyS1","/dev/ttyS2","/dev/ttyUSB0"],
    }.get(vendor, ["/dev/ttyUSB0","/dev/ttyUSB1","/dev/ttyS1"])

    for port in candidates:
        _, out, _ = run_adb(["shell", f"ls {port} 2>/dev/null"],
                             serial=serial, check=False)
        if port in out.strip():
            return port
    return ""


def send_at(serial: str, port: str, cmd: str, timeout: int = 2) -> str:
    """Send AT command and return response."""
    shell = (f"echo -e '{cmd}\\r\\n' > {port} && "
             f"sleep {timeout} && timeout {timeout} cat {port} 2>/dev/null")
    # Try without root first
    _, out, _ = run_adb(["shell", shell], serial=serial, check=False)
    if out.strip():
        return out.strip()
    # Try with root
    _, out2, _ = run_adb(["shell", f"su -c '{shell}'"], serial=serial, check=False)
    return out2.strip()


def get_current_bands_at(serial: str, vendor: str) -> dict:
    """Query current band config via AT commands."""
    port = find_at_port(serial, vendor)
    if not port:
        return {}
    results = {"at_port": port}

    if vendor == "qualcomm":
        results["band_query"] = send_at(serial, port, 'AT+QCFG="band"')
        results["network_info"] = send_at(serial, port, "AT+QNWINFO")
        results["reg_status"] = send_at(serial, port, "AT+CEREG?")
    elif vendor in ("mtk", "unisoc"):
        results["rat_query"]  = send_at(serial, port, "AT+ERAT?")
        results["band_query"] = send_at(serial, port, "AT+EPBSE?")
        results["network_info"] = send_at(serial, port, "AT+COPS?")
    else:
        results["info"] = send_at(serial, port, "ATI")
        results["rat"]  = send_at(serial, port, "AT+ERAT?")

    return results


# ── MTK-specific band write ───────────────────────────────────────────────────

def mtk_set_bands_at(serial: str, lte_low: int, lte_high: int,
                      nr_mask: int, mode: str = "auto") -> bool:
    """
    Set LTE/5G band config on MTK devices via AT commands.
    AT+EPBSE sets band config: AT+EPBSE=<GSM>,<WCDMA>,<LTE_low>,<LTE_high>
    AT+ERAT sets RAT preference.
    """
    port = find_at_port(serial, "mtk")
    if not port:
        console.print("[yellow]! No MTK AT port found.[/yellow]")
        return False

    console.print(f"  [cyan]Using AT port: {port}[/cyan]")

    # RAT mode
    rat_cmd = {
        "auto":     "AT+ERAT=0,0",
        "lte_only": "AT+ERAT=3,2",
        "5g_pref":  "AT+ERAT=0,0,0,1",
        "lte_5g":   "AT+ERAT=0,0,0,0",
    }.get(mode, "AT+ERAT=0,0")

    console.print(f"  [dim]Sending: {rat_cmd}[/dim]")
    resp = send_at(serial, port, rat_cmd)
    rat_ok = "OK" in resp
    console.print(f"  [{'green' if rat_ok else 'yellow'}]RAT: {'OK' if rat_ok else resp[:40]}[/{'green' if rat_ok else 'yellow'}]")

    # Band mask (MTK EPBSE format)
    # AT+EPBSE=<GSM_band_mask>,<WCDMA_band_mask>,<LTE_low_32bit>,<LTE_high_32bit>
    lte_low32  = lte_low  & 0xFFFFFFFF
    lte_high32 = (lte_low >> 32) | ((lte_high & 0xFFFFFFFF) << 32)

    epbse_cmd = f"AT+EPBSE=0xFFFFFFFF,0xFFFFFFFF,0x{lte_low32:08X},0x{lte_high32:08X}"
    console.print(f"  [dim]Sending: {epbse_cmd}[/dim]")
    resp2 = send_at(serial, port, epbse_cmd)
    band_ok = "OK" in resp2
    console.print(f"  [{'green' if band_ok else 'yellow'}]Band: {'OK' if band_ok else resp2[:40]}[/{'green' if band_ok else 'yellow'}]")

    return rat_ok or band_ok


def mtk_set_bands_nvram(serial: str, profile: dict) -> bool:
    """
    Set bands via MTK Engineering Mode (requires app installed).
    Falls back to direct NVRAM write if root available.
    """
    # Check for MTK Engineering Mode app
    for pkg in [MTK_ENG_MODE_PKG, MTK_ENG_MODE_PKG2]:
        _, out, _ = run_adb(["shell", f"pm path {pkg} 2>/dev/null"],
                             serial=serial, check=False)
        if "package:" in out:
            console.print(f"  [green]✓ MTK Engineering Mode found: {pkg}[/green]")
            console.print(f"  [dim]For GUI band selection:[/dim]")
            console.print(f"  [dim]  Open EngineerMode → Telephony → Band Select[/dim]")
            return True

    console.print("  [yellow]! MTK Engineering Mode not installed.[/yellow]")
    console.print("  [dim]  Install MTK EngineerMode APK for GUI band selection.[/dim]")
    return False


# ── Unisoc-specific band write ────────────────────────────────────────────────

def unisoc_set_bands_at(serial: str, lte_low: int, mode: str = "auto") -> bool:
    """Set band config on Unisoc devices via AT commands."""
    port = find_at_port(serial, "unisoc")
    if not port:
        console.print("[yellow]! No Unisoc AT port found.[/yellow]")
        return False

    console.print(f"  [cyan]Using AT port: {port}[/cyan]")

    rat_cmd = {
        "auto":     "AT+ERAT=0,0",
        "lte_only": "AT+ERAT=3,2",
        "5g_pref":  "AT+ERAT=0,0,0,1",
    }.get(mode, "AT+ERAT=0,0")

    resp = send_at(serial, port, rat_cmd)
    ok = "OK" in resp
    console.print(f"  [{'green' if ok else 'yellow'}]RAT: {'OK' if ok else resp[:40]}[/{'green' if ok else 'yellow'}]")

    # Unisoc EPBSE (same format as MTK in most firmwares)
    lte_low32 = lte_low & 0xFFFFFFFF
    lte_hi32  = (lte_low >> 32) & 0xFFFFFFFF
    epbse = f"AT+EPBSE=0xFFFFFFFF,0xFFFFFFFF,0x{lte_low32:08X},0x{lte_hi32:08X}"
    resp2 = send_at(serial, port, epbse)
    ok2 = "OK" in resp2
    console.print(f"  [{'green' if ok2 else 'yellow'}]Band: {'OK' if ok2 else resp2[:40]}[/{'green' if ok2 else 'yellow'}]")

    return ok or ok2


# ── Generic AT band config (for Rockchip/Allwinner with external modem) ──────

def generic_set_bands_at(serial: str, vendor: str,
                          lte_bands: list, mode: str = "auto") -> bool:
    """
    Generic AT command band config for devices with standalone modems
    (common on Rockchip/Allwinner tablets with separate LTE modem chip).
    """
    port = find_at_port(serial, vendor)
    if not port:
        # These devices often expose modem via USB serial
        console.print("[yellow]! No modem AT port found via ADB.[/yellow]")
        console.print("  [dim]Try: ls /dev/ttyUSB* or lsusb for modem detection[/dim]")
        return False

    console.print(f"  [cyan]AT port: {port}[/cyan]")

    # Try generic AT commands
    ati = send_at(serial, port, "ATI")
    if ati:
        console.print(f"  [dim]Modem ID: {ati[:80]}[/dim]")

    # Generic AT+COPS for network query
    cops = send_at(serial, port, "AT+COPS?")
    if cops:
        console.print(f"  [dim]Network: {cops[:60]}[/dim]")

    # Try EPBSE (works on many modem firmwares regardless of AP chip)
    lte_mask = 0
    for b in lte_bands:
        if 1 <= b <= 64:
            lte_mask |= (1 << (b-1))
    lte_low32 = lte_mask & 0xFFFFFFFF
    lte_hi32  = (lte_mask >> 32) & 0xFFFFFFFF

    epbse = f"AT+EPBSE=0xFFFFFFFF,0xFFFFFFFF,0x{lte_low32:08X},0x{lte_hi32:08X}"
    resp = send_at(serial, port, epbse)
    return "OK" in resp


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

@click.group()
def bands():
    """Universal LTE/5G band configuration — works on all chipset vendors."""
    pass


@bands.command("carriers")
@click.option("--country", "-c", default=None,
              help="Filter by country code: us, uk, eu, au, jp, kr, in, cn, ca")
def bands_carriers(country):
    """
    List all supported carrier band profiles with full LTE and 5G band details.
    """
    from rich.table import Table
    from rich import box as rbox

    console.print(f"\n[bold cyan]Carrier Band Profiles[/bold cyan]\n")

    country_filter = {
        "us": ["verizon","tmobile","att","firstnet","dish_boost","cbrs"],
        "uk": ["uk_vodafone","uk_ee"],
        "eu": ["eu_generic"],
        "au": ["australia_telstra"],
        "jp": ["japan_docomo"],
        "kr": ["korea_skt"],
        "in": ["india_jio"],
        "cn": ["china_telecom"],
        "ca": ["canada_rogers"],
    }

    show_keys = country_filter.get(country, list(CARRIER_PROFILES.keys())) if country else list(CARRIER_PROFILES.keys())

    for key in show_keys:
        if key not in CARRIER_PROFILES:
            continue
        p = CARRIER_PROFILES[key]
        console.print(f"[bold yellow]── {p['display']}[/bold yellow]")

        t = Table(box=rbox.SIMPLE, show_header=False, padding=(0,2), border_style="dim")
        t.add_column("Key",   style="dim cyan",  width=18)
        t.add_column("Value", style="white",      width=62)

        lte_str = ", ".join(f"B{b}" for b in p["lte_bands"])
        nr_str  = ", ".join(p["nr_sub6"])
        mm_str  = ", ".join(p.get("nr_mmwave",[]))

        t.add_row("LTE bands", lte_str)
        t.add_row("5G Sub-6",  nr_str  if nr_str  else "—")
        t.add_row("5G mmWave", mm_str  if mm_str  else "—")
        t.add_row("Primary LTE", f"B{p['primary_lte']}")
        t.add_row("Primary 5G",  p["primary_nr"])
        t.add_row("LTE hex (low)",  p["lte_hex_low"])
        if p.get("lte_hex_high","0x0000000000000000") != "0x0000000000000000":
            t.add_row("LTE hex (high)", p["lte_hex_high"])
        t.add_row("NR hex",    p["nr_hex"])
        for note in p.get("notes",[]):
            t.add_row("",f"[dim]• {note}[/dim]")

        console.print(t)
        console.print()

    console.print(f"[dim]Apply:  watchrom bands apply --carrier verizon[/dim]")
    console.print(f"[dim]Status: watchrom bands status[/dim]\n")


@bands.command("verizon")
@click.option("--serial",  "-s", default=None)
@click.option("--tier",    "-t",
              type=click.Choice(["full","lte-only","5g","cbrs"]),
              default="full",
              help="full=all Verizon bands, lte-only=no 5G, 5g=5G priority, cbrs=CBRS only")
@click.option("--dry-run", is_flag=True)
def bands_verizon(serial, tier, dry_run):
    """
    Configure all Verizon LTE and 5G bands with full carrier detail.

    Verizon Band Reference:
      LTE  : B2 (1900) · B4 (AWS) · B5 (850) · B13 (700★) · B48 (CBRS) · B66 (AWS-3)
      5G   : n5 (850) · n48 (CBRS) · n66 (AWS-3) · n77 (C-band★) · n260/n261 (mmWave)

    ★ = primary band (always include for Verizon compatibility)
    """
    console.print(f"\n[bold red]Verizon Band Configuration[/bold red]\n")

    from rich.table import Table
    from rich import box as rbox

    # Show Verizon band reference
    console.print("[bold yellow]Verizon LTE Bands:[/bold yellow]")
    t1 = Table(box=rbox.SIMPLE, show_header=True, header_style="bold cyan")
    t1.add_column("Band",   style="green",  width=6)
    t1.add_column("Freq",   style="white",  width=18)
    t1.add_column("Type",   style="yellow", width=12)
    t1.add_column("Notes",  style="dim",    width=36)
    for b_num, info in VERIZON_BANDS["lte"].items():
        t1.add_row(info["name"], info["freq"], info["type"], info["notes"])
    console.print(t1)

    console.print("\n[bold yellow]Verizon 5G Sub-6 GHz:[/bold yellow]")
    t2 = Table(box=rbox.SIMPLE, show_header=True, header_style="bold cyan")
    t2.add_column("Band",   style="green",  width=8)
    t2.add_column("Freq",   style="white",  width=14)
    t2.add_column("Type",   style="yellow", width=14)
    t2.add_column("Notes",  style="dim",    width=36)
    for b_id, info in VERIZON_BANDS["nr_sub6"].items():
        t2.add_row(b_id, info["freq"], info["type"], info["notes"])
    console.print(t2)

    console.print("\n[bold yellow]Verizon 5G mmWave (Ultra Wideband — dense urban only):[/bold yellow]")
    t3 = Table(box=rbox.SIMPLE, show_header=True, header_style="bold cyan")
    t3.add_column("Band",  style="green", width=8)
    t3.add_column("Freq",  style="white", width=10)
    t3.add_column("Notes", style="dim",   width=50)
    for b_id, info in VERIZON_BANDS["nr_mmwave"].items():
        t3.add_row(b_id, info["freq"], info["notes"])
    console.print(t3)

    for note in VERIZON_BANDS["notes"]:
        console.print(f"  [dim]• {note}[/dim]")

    # Tier-specific config
    tier_config = {
        "full":     CARRIER_PROFILES["verizon"],
        "lte-only": {**CARRIER_PROFILES["verizon"],
                     "nr_sub6":[], "nr_mmwave":[],
                     "nr_hex":"0x0000000000000000",
                     "display":"Verizon LTE only"},
        "5g":       CARRIER_PROFILES["verizon"],
        "cbrs":     CARRIER_PROFILES["cbrs"],
    }[tier]

    console.print(f"\n[bold]Selected tier:[/bold] [cyan]{tier}[/cyan] — {tier_config['display']}")

    if dry_run:
        console.print(f"\n[yellow]  Dry run — no changes written.[/yellow]")
        return

    # Connect to device
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    # Detect vendor and route to correct write method
    _apply_carrier_profile(target, tier_config)


@bands.command("apply")
@click.option("--carrier", "-c", required=True,
              type=click.Choice(list(CARRIER_PROFILES.keys())),
              help="Carrier profile to apply")
@click.option("--serial",  "-s", default=None)
@click.option("--dry-run", is_flag=True)
@click.option("--method",  "-m",
              type=click.Choice(["auto","at","efs","nvram"]),
              default="auto",
              help="Write method (auto=detect best)")
@click.option("--derive-masks", is_flag=True,
              help="Auto-derive hex masks from band lists instead of using stored values")
def bands_apply(carrier, serial, dry_run, method, derive_masks):
    """
    Apply a carrier's full LTE + 5G band profile to the device.

    Works on: Qualcomm, MTK, Unisoc, and external modem devices.
    Automatically detects chipset and uses the appropriate write method.

    Example:
      watchrom bands apply --carrier verizon
      watchrom bands apply --carrier tmobile --derive-masks
    """
    profile = dict(CARRIER_PROFILES[carrier])

    # Derive hex masks from band lists if requested
    if derive_masks and profile.get("lte_bands"):
        low, high = compute_lte_mask_hex(profile["lte_bands"])
        profile["lte_hex_low"] = low
        profile["lte_hex_high"] = high
        console.print(f"  [dim]Derived LTE masks: {low}, high={high}[/dim]")
        nr_all = profile.get("nr_sub6", []) + profile.get("nr_mmwave", [])
        if nr_all:
            profile["nr_hex"] = compute_nr_mask_hex(nr_all)
            console.print(f"  [dim]Derived NR mask: {profile['nr_hex']}[/dim]")

    console.print(f"\n[bold cyan]Band Apply — {profile['display']}[/bold cyan]\n")
    console.print(f"  LTE: {', '.join(f'B{b}' for b in profile['lte_bands'])}")
    console.print(f"  5G:  {', '.join(profile['nr_sub6'])}")
    if profile.get("nr_mmwave"):
        console.print(f"  mmW: {', '.join(profile['nr_mmwave'])}")

    if dry_run:
        console.print(f"\n[yellow]  Dry run — showing config only.[/yellow]")
        _show_band_hex(profile)
        return

    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    _apply_carrier_profile(target, profile, method=method)


def _show_band_hex(profile: dict):
    """Display hex masks for a carrier profile."""
    console.print(f"\n  [bold]Configuration hexadecimal masks:[/bold]")
    console.print(f"  LTE low  : [cyan]{profile['lte_hex_low']}[/cyan]")
    if profile.get("lte_hex_high","0x0000000000000000") != "0x0000000000000000":
        console.print(f"  LTE high : [cyan]{profile['lte_hex_high']}[/cyan]")
    console.print(f"  NR mask  : [cyan]{profile['nr_hex']}[/cyan]")


def _apply_carrier_profile(serial: str, profile: dict, method: str = "auto"):
    """Detect chipset and apply band profile using the right method."""
    props  = get_device_props(serial)
    vendor, chipset = detect_chipset_from_props(props)

    console.print(f"\n  [bold]Device :[/bold] {serial}")
    console.print(f"  [bold]Chipset:[/bold] {chipset} ({vendor.upper()})")

    # Backup before writing
    bk_dir = OUTPUT_DIR / "band_backups" / serial / time.strftime("%Y%m%d_%H%M%S")
    bk_dir.mkdir(parents=True, exist_ok=True)
    _backup_band_config(serial, vendor, bk_dir)

    lte_low  = int(profile["lte_hex_low"],  16)
    lte_high = int(profile.get("lte_hex_high","0x0"), 16)
    nr_mask  = int(profile["nr_hex"],        16)
    lte_bands = profile.get("lte_bands", [])

    console.print(f"\n[cyan]→ Applying band config...[/cyan]\n")

    success = False

    if vendor == "qualcomm" or method == "efs":
        from modules.qualcomm import _write_bands_efs
        _write_bands_efs(serial, lte_low | (lte_high << 64), nr_mask)
        success = True

    elif vendor == "mtk" or method in ("at","nvram"):
        # Try AT first
        success = mtk_set_bands_at(serial, lte_low, lte_high, nr_mask)
        if not success:
            success = mtk_set_bands_nvram(serial, profile)

    elif vendor == "unisoc" or method == "at":
        success = unisoc_set_bands_at(serial, lte_low)

    else:
        # Generic AT (Rockchip/Allwinner tablets with external modem)
        success = generic_set_bands_at(serial, vendor, lte_bands)

    if success:
        console.print(f"\n[bold green]✓ Band config applied.[/bold green]")
        console.print(f"  Backup saved: {bk_dir}")
        console.print(f"  [bold yellow]Reboot device for changes to take effect.[/bold yellow]")
        if click.confirm("  Reboot now?", default=True):
            run_adb(["reboot"], serial=serial, check=False)
    else:
        console.print(f"\n[yellow]! Write via AT commands did not confirm OK.")
        console.print(f"  This is not necessarily a failure — some modems don't echo OK.")
        console.print(f"  Reboot and check signal to verify.[/yellow]")
        console.print(f"\n  [dim]Manual alternative: use MTK Engineering Mode app or QPST[/dim]")


def _backup_band_config(serial: str, vendor: str, bk_dir: Path):
    """Snapshot current band/network state before writing."""
    # dumpsys snapshot
    _, ds, _ = run_adb(["shell",
        "dumpsys phone 2>/dev/null | grep -iE '(band|lte|nr|5g|rat|mode|erat|epbse)' | head -40"],
        serial=serial, check=False)
    (bk_dir / "network_snapshot.txt").write_text(ds)

    # AT port query
    port = find_at_port(serial, vendor)
    if port:
        for cmd in ["AT+ERAT?","AT+EPBSE?","AT+QCFG=\"band\"","AT+QNWINFO","AT+COPS?"]:
            resp = send_at(serial, port, cmd, timeout=1)
            if resp:
                with open(bk_dir / "at_snapshot.txt","a") as f:
                    f.write(f"\n>> {cmd}\n{resp}\n")

    console.print(f"  [green]✓ Pre-change backup: {bk_dir}[/green]")


@bands.command("status")
@click.option("--serial", "-s", default=None)
def bands_status(serial):
    """
    Show current band configuration and network status.
    Works on all vendors without root.
    """
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    props  = get_device_props(target)
    vendor, chipset = detect_chipset_from_props(props)

    console.print(f"\n[bold cyan]Band & Network Status — {target}[/bold cyan]")
    console.print(f"  Chipset: [yellow]{chipset}[/yellow] ({vendor.upper()})\n")

    # Network props
    net_props = [
        ("Carrier",      "gsm.operator.alpha"),
        ("MCC/MNC",      "gsm.operator.numeric"),
        ("Network type", "gsm.network.type"),
        ("Data type",    "gsm.data.network.type"),
        ("Roaming",      "gsm.operator.isroaming"),
        ("SIM state",    "gsm.sim.state"),
        ("Baseband",     "gsm.version.baseband"),
    ]
    for label, prop in net_props:
        val = props.get(prop,"")
        if val:
            console.print(f"  [cyan]{label:16s}[/cyan] {val}")

    # AT command query
    port = find_at_port(target, vendor)
    if port:
        console.print(f"\n  [bold]AT Commands (port: {port}):[/bold]")
        at_queries = {
            "qualcomm": [("Network info","AT+QNWINFO"),
                         ("Band config",'AT+QCFG="band"'),
                         ("LTE reg","AT+CEREG?"),
                         ("5G reg","AT+C5GREG?")],
            "mtk":      [("RAT mode","AT+ERAT?"),
                         ("Band","AT+EPBSE?"),
                         ("Operator","AT+COPS?")],
            "unisoc":   [("RAT mode","AT+ERAT?"),
                         ("Band","AT+EPBSE?"),
                         ("Operator","AT+COPS?")],
        }.get(vendor, [("Info","ATI"),("Operator","AT+COPS?"),("Signal","AT+CSQ")])

        for label, cmd in at_queries:
            resp = send_at(target, port, cmd, timeout=2)
            if resp and resp.strip():
                console.print(f"  [dim]{label}: {resp.strip()[:80]}[/dim]")
    else:
        console.print(f"\n  [dim](No AT port found — connect device and try again)[/dim]")

    # dumpsys active channel info
    _, phys, _ = run_adb(
        ["shell", "dumpsys phone 2>/dev/null | grep -iE '(physicalChannel|earfcn|arfcn)' | head -10"],
        serial=target, check=False)
    if phys.strip():
        console.print(f"\n  [bold]Active Channels:[/bold]")
        for line in phys.strip().splitlines()[:8]:
            console.print(f"  [cyan]{line.strip()[:100]}[/cyan]")


@bands.command("restore")
@click.argument("backup_dir")
@click.option("--serial", "-s", default=None)
def bands_restore(backup_dir, serial):
    """Restore band config from a WatchROM band backup snapshot."""
    bk = Path(backup_dir)
    if not bk.is_dir():
        console.print(f"[red]✗ Not a directory: {backup_dir}[/red]")
        return

    console.print(f"\n[bold cyan]Band Config Restore[/bold cyan]")
    console.print(f"  From: {bk}\n")

    # Show what's in the backup
    snap = bk / "network_snapshot.txt"
    at_snap = bk / "at_snapshot.txt"
    if snap.exists():
        console.print("[bold]Backed-up network state:[/bold]")
        console.print(f"[dim]{snap.read_text()[:400]}[/dim]")
    if at_snap.exists():
        console.print("\n[bold]Backed-up AT commands:[/bold]")
        console.print(f"[dim]{at_snap.read_text()[:400]}[/dim]")

    console.print("\n[yellow]To restore, apply 'all_bands' preset to re-enable all bands:[/yellow]")
    console.print("  [bold]watchrom bands apply --carrier global_roaming[/bold]")
    console.print("  [bold]watchrom qualcomm band-set --preset all_bands[/bold] (Qualcomm)")


@bands.command("verify-masks")
def bands_verify_masks():
    """Verify all carrier profile masks match computed values from band lists.

    Flags profiles where the stored hex mask doesn't match the
    mathematically computed mask from the band number list.
    Use --derive-masks with 'bands apply' to auto-correct at write time.
    """
    console.print(f"\n[bold cyan]Verify Band Masks[/bold cyan]\n")

    mismatches = verify_carrier_masks(CARRIER_PROFILES)
    if not mismatches:
        console.print("[green]✓ All LTE hex masks match their band lists![/green]")
        return

    console.print(f"[yellow]⚠ {len(mismatches)} profiles with mismatched masks:[/yellow]\n")
    for name, field, expected, actual, bands in mismatches[:20]:
        console.print(f"  [bold]{name}[/bold] ({field})")
        console.print(f"    Expected: {expected}")
        console.print(f"    Actual:   {actual}")
        console.print(f"    Bands:    {bands}")
        console.print()
    if len(mismatches) > 20:
        console.print(f"  ... and {len(mismatches) - 20} more\n")
    console.print("[dim]Fix: use --derive-masks with 'bands apply' to auto-derive[/dim]")


@bands.command("mtk-engmode")
@click.option("--serial", "-s", default=None)
def bands_mtk_engmode(serial):
    """
    Open MTK Engineering Mode for GUI-based band selection.
    Launches the hidden engineering app on MTK devices.
    No root required — uses ADB intent.
    """
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    console.print(f"\n[bold cyan]MTK Engineering Mode — {target}[/bold cyan]\n")

    # Try multiple intents for different MTK firmware variants
    intents = [
        "am start -n com.mediatek.engineermode/.EngineerMode",
        "am start -n com.mediatek.engineermode/.EngineerModeMain",
        "am start -a android.intent.action.MAIN -n com.mediatek.engineermode/.EngineerMode",
        "am start -n com.mtk.engineermode/.EngineerMode",
        # Phone code method
        "am start -a android.intent.action.DIAL -d tel:%23*%234636%23",
    ]

    launched = False
    for intent in intents:
        _, out, err = run_adb(["shell", intent], serial=target, check=False)
        if "Error" not in out and "error" not in err.lower():
            console.print(f"[green]✓ Launched: {intent.split('/')[-1]}[/green]")
            launched = True
            break

    if not launched:
        console.print("[yellow]! Could not launch MTK Engineering Mode automatically.[/yellow]")

    console.print("\n[bold]Inside MTK Engineering Mode — Band Selection:[/bold]")
    console.print("  Telephony → [Select Band] or [BandSelect]")
    console.print("  Check boxes for the bands you want to enable")
    console.print("  Scroll to bottom → [Set] to apply\n")

    console.print("[bold]Alternative — Dial Code:[/bold]")
    console.print("  Dial: [bold]*#*#4636#*#*[/bold] → Phone Information → Set Preferred Network")
    console.print("  Some MTK devices: [bold]*#*#3646633#*#*[/bold] → Telephony\n")

    console.print("[bold]Band Select screen explained:[/bold]")
    for b_num, info in sorted(LTE_BANDS.items()):
        console.print(f"  B{b_num:3d}  {info['freq']:16s}  {info['region']}")
