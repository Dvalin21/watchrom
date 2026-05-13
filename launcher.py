#!/usr/bin/env python3
# WatchROM Launcher — ensure PYTHONPATH includes toolkit root
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""
WatchROM — Interactive Terminal Launcher
Full TUI menu system for users without developer experience
Auto-runs: scan → backup → interactive menu
"""
import os
import sys
import subprocess
import time
import json
from pathlib import Path

# ── Ensure toolkit is on path ─────────────────────────────────────────────────
TOOLKIT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLKIT_DIR))

try:
    from rich.console import Console
    from rich.panel   import Panel
    from rich.table   import Table
    from rich.prompt  import Prompt, Confirm
    from rich.text    import Text
    from rich.live    import Live
    from rich.align   import Align
    from rich         import box
    from rich.columns import Columns
    from rich.rule    import Rule
except ImportError:
    # Install to user site-packages — avoids breaking system packages
    subprocess.run([sys.executable, "-m", "pip", "install",
                    "--user", "rich", "-q"])
    from rich.console import Console
    from rich.panel   import Panel
    from rich.table   import Table
    from rich.prompt  import Prompt, Confirm
    from rich.text    import Text
    from rich         import box
    from rich.rule    import Rule

console = Console()

BANNER = """[bold cyan]
 ██╗    ██╗ █████╗ ████████╗ ██████╗██╗  ██╗██████╗  ██████╗ ███╗   ███╗
 ██║    ██║██╔══██╗╚══██╔══╝██╔════╝██║  ██║██╔══██╗██╔═══██╗████╗ ████║
 ██║ █╗ ██║███████║   ██║   ██║     ███████║██████╔╝██║   ██║██╔████╔██║
 ██║███╗██║██╔══██║   ██║   ██║     ██╔══██║██╔══██╗██║   ██║██║╚██╔╝██║
 ╚███╔███╔╝██║  ██║   ██║   ╚██████╗██║  ██║██║  ██║╚██████╔╝██║ ╚═╝ ██║
  ╚══╝╚══╝ ╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝
[/bold cyan]"""

SESSION_FILE = TOOLKIT_DIR / ".session.json"


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def run_cmd(args: list, interactive=False) -> tuple:
    """Run a watchrom sub-command."""
    cmd = [sys.executable, str(TOOLKIT_DIR / "main.py")] + args
    if interactive:
        subprocess.run(cmd)
        return 0, ""
    try:
        r = subprocess.run(cmd, capture_output=False, text=True, timeout=600)
        return r.returncode, ""
    except subprocess.TimeoutExpired:
        return 1, "timeout"


def run_cmd_captured(args: list) -> tuple:
    cmd = [sys.executable, str(TOOLKIT_DIR / "main.py")] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return 1, "", str(e)


def adb_devices():
    try:
        r = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10)
        devices = []
        for line in r.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) == 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices
    except Exception:
        return []


def fastboot_devices():
    try:
        r = subprocess.run(["fastboot", "devices"], capture_output=True, text=True, timeout=5)
        return [l.split()[0] for l in r.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def get_device_info(serial=None):
    """Quick device info pull."""
    try:
        cmd = ["adb"]
        if serial:
            cmd += ["-s", serial]
        r = subprocess.run(
            cmd + ["shell", "getprop ro.product.model; getprop ro.product.device; "
                            "getprop ro.board.platform; getprop ro.build.version.release; "
                            "getprop ro.build.version.security_patch"],
            capture_output=True, text=True, timeout=10
        )
        lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
        return {
            "model":    lines[0] if len(lines) > 0 else "?",
            "device":   lines[1] if len(lines) > 1 else "?",
            "platform": lines[2] if len(lines) > 2 else "?",
            "android":  lines[3] if len(lines) > 3 else "?",
            "patch":    lines[4] if len(lines) > 4 else "?",
        }
    except Exception:
        return {}


def load_session():
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except Exception:
            pass
    return {}


def save_session(data: dict):
    SESSION_FILE.write_text(json.dumps(data, indent=2))


def header(session: dict):
    """Print the top status bar."""
    console.print(BANNER)

    devs = adb_devices()
    fbs  = fastboot_devices()

    if devs:
        info = get_device_info(devs[0])
        device_str = (f"[green]● {info.get('model','?')}[/green]  "
                      f"[dim]{info.get('device','?')} | "
                      f"Android {info.get('android','?')} | "
                      f"{info.get('platform','?')}[/dim]")
    elif fbs:
        device_str = f"[yellow]● Fastboot: {fbs[0]}[/yellow]"
    else:
        device_str = "[red]○ No device connected[/red]"

    backed_up = session.get("last_backup", None)
    backup_str = (f"[green]✓ {backed_up}[/green]" if backed_up
                  else "[yellow]! No backup yet[/yellow]")

    status_table = Table(box=box.SIMPLE, show_header=False,
                          padding=(0,2), expand=True)
    status_table.add_column(style="dim")
    status_table.add_column()
    status_table.add_row("Device  :", device_str)
    status_table.add_row("Backup  :", backup_str)
    status_table.add_row("Session :", f"[dim]{SESSION_FILE.parent}[/dim]")
    console.print(Panel(status_table, border_style="cyan", padding=(0,1)))


# ══════════════════════════════════════════════════════════════════════════════
# First-Run: Scan + Backup
# ══════════════════════════════════════════════════════════════════════════════

def first_run_scan(session: dict) -> dict:
    """Auto-scan device and offer backup on first run."""
    console.print(Rule("[bold yellow]★ First Run — Device Scan[/bold yellow]"))
    console.print()

    devs = adb_devices()
    if not devs:
        console.print(Panel(
            "[yellow]No device detected.[/yellow]\n\n"
            "Please connect your watch via USB and enable:\n"
            "  Settings → About → Tap Build Number 7×\n"
            "  Settings → Developer Options → USB Debugging ON\n\n"
            "Then press [bold]Enter[/bold] to retry.",
            title="Connect Your Device",
            border_style="yellow"
        ))
        input()
        devs = adb_devices()
        if not devs:
            console.print("[red]Still no device. Continuing without scan.[/red]")
            return session

    serial = devs[0]
    console.print(f"[green]✓ Device found:[/green] [bold]{serial}[/bold]\n")

    # Run device info
    console.print("[cyan]→ Scanning device...[/cyan]")
    run_cmd(["device", "info", "-s", serial], interactive=True)

    console.print()
    console.print(Panel(
        "[bold yellow]⚠ IMPORTANT — Create a Backup Before Modifying Anything[/bold yellow]\n\n"
        "WatchROM will now back up ALL partitions from your device.\n"
        "This lets you restore to factory state if anything goes wrong.\n\n"
        "[dim]This may take 5–20 minutes depending on device storage.[/dim]",
        border_style="yellow",
        padding=(1,2)
    ))

    if Confirm.ask("\n  [bold]Create a full backup now?[/bold]", default=True):
        console.print("\n[cyan]→ Starting full backup (please wait)...[/cyan]\n")
        rc, _ = run_cmd(["backup", "full", "-s", serial], interactive=True)
        if rc == 0:
            session["last_backup"] = time.strftime("%Y-%m-%d %H:%M")
            session["device_serial"] = serial
            save_session(session)
            console.print(f"\n[bold green]✓ Backup complete![/bold green]")
        else:
            console.print(f"\n[yellow]! Backup encountered issues. Check output/backups/[/yellow]")
    else:
        console.print("[yellow]! Skipping backup — be careful with modifications.[/yellow]")

    session["first_run_done"] = True
    session["device_serial"]  = serial
    save_session(session)
    console.print()
    input("  Press Enter to continue to main menu...")
    return session


# ══════════════════════════════════════════════════════════════════════════════
# MENU DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

# (key, label, submenu_or_action, description)
MAIN_MENU = [
    ("0",  "🚀 Pipelines (Automated Workflows)","pipeline_menu","root→backup→flash→verify chains"),
    ("1",  "📱 Device Info & Status",     "device_menu",     "Scan device, check partitions, root status"),
    ("2",  "💾 Backup & Restore",         "backup_menu",     "Full backup, restore, app backup"),
    ("3",  "🔓 Root Device",              "root_menu",       "Magisk root via boot.img patching"),
    ("4",  "⌚ WearOS Compatibility",     "wearos_menu",     "Make your watch run WearOS apps"),
    ("5",  "🗂  System Image Editor",      "sysimg_menu",     "Extract, edit, repack system.img"),
    ("6",  "📦 APK Tools",                "apk_menu",        "Decompile, edit, recompile, sign APKs"),
    ("7",  "🔧 Partitions",               "partition_menu",  "Dump, flash, manage partitions"),
    ("8",  "🥾 Boot Image Tools",         "bootimg_menu",    "Unpack, edit kernel/ramdisk, repack"),
    ("9",  "🛡  AVB & Security",           "avb_menu",        "Disable verification, sign images"),
    ("10", "📡 OTA Packages",             "ota_menu",        "Extract payload.bin, create OTA zip"),
    ("11", "🏗  ROM Builder",              "rom_menu",        "Build flashable ROM from partitions"),
    ("12", "🔩 Device Tree & TWRP",       "tree_menu",       "Generate device tree, TWRP config"),
    ("13", "🧩 Magisk Modules",           "magisk_menu",     "Create, install, manage Magisk modules"),
    ("14", "📊 Analysis & Diagnostics",   "diag_menu",       "Entropy, strings, diff, logcat"),
    ("15", "🔑 Keys & Signing",           "keys_menu",       "Generate AOSP keys, sign images/APKs"),
    ("16", "🌐 Network & RIL",            "network_menu",    "WiFi, Bluetooth, modem, packet capture"),
    ("17", "⚙  Properties Editor",        "props_menu",      "Edit build.prop, live setprop, presets"),
    ("18", "🔐 SELinux Tools",            "selinux_menu",    "Policy audit, permissive, allow rules"),
    ("19", "🔌 Chipset Tools",            "chipset_menu",    "MTK · Unisoc · Rockchip · Allwinner · Realtek"),
    ("21", "📶 Qualcomm Band & Modem",     "qualcomm_menu",   "LTE/5G bands, EFS backup, EDL, AT commands"),
    ("22", "📡 Band Config (All Vendors)",  "bands_menu",      "Verizon/TMo/ATT/EU/Global — MTK+Unisoc+QC"),
    ("20", "💻 ADB Shell",                "adb_shell",       "Direct ADB shell on device"),
    ("0",  "❌ Exit",                      "exit",            "Exit WatchROM"),
]

DEVICE_MENU = [
    ("1", "Full device scan",           ["device", "info"],                 "Detect chipset, partitions, root"),
    ("2", "Reboot to system",           ["device", "reboot", "system"],     "Normal reboot"),
    ("3", "Reboot to recovery",         ["device", "reboot", "recovery"],   "Boot into recovery"),
    ("4", "Reboot to bootloader",       ["device", "reboot", "bootloader"], "Fastboot / bootloader mode"),
    ("5", "Reboot to EDL/Download",     ["device", "reboot", "edl"],        "Download mode for flashing"),
    ("6", "MTK download mode guide",    ["mtk", "download"],                "MTK BROM entry guide"),
    ("7", "Unisoc download mode guide", ["unisoc", "download"],             "Unisoc FDL entry guide"),
    ("8", "MTK device identify",        ["mtk", "identify"],                "MTK-specific properties"),
    ("9", "Unisoc device identify",     ["unisoc", "identify"],             "Unisoc-specific properties"),
]

BACKUP_MENU = [
    ("1", "Full backup (all partitions + apps)",  ["backup", "full"],       "Recommended before any changes"),
    ("2", "Backup apps only",                     ["backup", "apps"],       "ADB app + data backup"),
    ("3", "List all backups",                     ["backup", "list"],       "Show available backups"),
    ("4", "Restore from backup",                  None,                     "Choose backup to restore"),
]

ROOT_MENU = [
    ("1", "Root via Magisk (auto, recommended)",  ["root", "patch"],        "Patch boot + auto-flash"),
    ("2", "Check root status",                    ["root", "check"],        "Is device rooted?"),
    ("3", "Dump boot.img only",                   ["dump", "boot"],         "Save stock boot.img first"),
    ("4", "Root with custom boot.img",            None,                     "Specify a boot.img to patch"),
]

WEAROS_MENU = [
    ("1", "Check WearOS compatibility",           ["wearos", "status"],        "See what's missing"),
    ("2", "Setup WearOS props (Magisk module)",   ["wearos", "setup"],         "Recommended method"),
    ("3", "Install WearOS APKs",                  None,                        "Install from local folder"),
    ("4", "Patch system image for WearOS",        ["wearos", "patch-sysimg"],  "Bake into ROM"),
    ("5", "Full setup guide",                     ["wearos", "companion-guide"],"Step-by-step instructions"),
    ("6", "Install watch face APK",               None,                        "Sideload a watch face"),
]

SYSIMG_MENU = [
    ("1", "Extract system.img",        None,                                  "Choose image to extract"),
    ("2", "Extract vendor.img",        None,                                  "Choose image to extract"),
    ("3", "Interactive edit session",  None,                                  "Extract → edit → repack"),
    ("4", "Repack edited directory",   None,                                  "Repack after editing"),
    ("5", "Patch build.prop in image", None,                                  "Quick prop change in image"),
    ("6", "Browse files in image",     None,                                  "ls inside image"),
    ("7", "Show image info",           None,                                  "Format, size, entropy"),
    ("8", "WearOS patch system image", ["wearos", "patch-sysimg"],            "Add WearOS support to ROM"),
]

APK_MENU = [
    ("1",  "Decompile APK (smali + Java)",        None,                     "Full decompile"),
    ("2",  "Recompile & sign APK",                None,                     "Rebuild after editing"),
    ("3",  "Pull APK from device",                None,                     "Get APK by package name"),
    ("4",  "Install APK on device",               None,                     "ADB install"),
    ("5",  "List installed packages",             ["apk", "list"],          "All user apps"),
    ("6",  "List ALL packages (inc. system)",     ["apk", "list", "--system"],"Including system apps"),
    ("7",  "Generate signing keys",               ["keys", "generate"],     "AOSP platform keys"),
]

PARTITION_MENU = [
    ("1", "Dump ALL partitions",                  ["dump", "--all"],        "Save everything to output/"),
    ("2", "Dump single partition",                None,                     "Choose which partition"),
    ("3", "Flash image to partition",             None,                     "Choose partition + image"),
    ("4", "Show partition table",                 ["diag", "partitions"],   "Full partition layout"),
]

BOOTIMG_MENU = [
    ("1", "Unpack boot.img",                      None,                     "Extract kernel + ramdisk"),
    ("2", "Repack boot directory",                None,                     "Rebuild boot.img"),
    ("3", "Patch kernel cmdline",                 None,                     "Add/remove kernel params"),
    ("4", "Show boot.img info",                   None,                     "Header fields"),
    ("5", "Dump boot.img from device",            ["dump", "boot"],         "Save stock boot first"),
]

AVB_MENU = [
    ("1", "Create blank vbmeta (disable AVB)",    ["avb", "patch", "--blank"],  "Recommended for custom ROMs"),
    ("2", "Patch + flash vbmeta now",             ["avb", "patch", "--blank", "--flash"], "Auto-flash"),
    ("3", "Show vbmeta info",                     None,                     "Inspect vbmeta image"),
    ("4", "Re-sign image with custom key",        None,                     "Sign with AVB key"),
]

OTA_MENU = [
    ("1", "Extract OTA zip / payload.bin",        None,                     "Get partition images from OTA"),
    ("2", "Show OTA package info",                None,                     "Contents and metadata"),
    ("3", "Create flashable OTA zip",             None,                     "Pack images into OTA zip"),
]

ROM_MENU = [
    ("1", "Build ROM package (MTK scatter)",      None,                     "Repack for SP Flash Tool"),
    ("2", "Build ROM package (Unisoc XML)",       None,                     "Repack for UpgradeDownload"),
    ("3", "Flash GSI (Generic System Image)",     None,                     "Project Treble GSI"),
    ("4", "ROM flash instructions",               None,                     "How to flash with vendor tools"),
]

TREE_MENU = [
    ("1", "Build Android device tree",            ["devtree", "build"],     "Scaffold from live device"),
    ("2", "Build TWRP device tree",               ["twrp", "build"],        "TWRP config + build.sh"),
    ("3", "Extract DTBO entries",                 None,                     "Unpack DTBO image"),
    ("4", "Decompile DTB to DTS",                 None,                     "DTB → readable source"),
    ("5", "Compile DTS to DTB",                   None,                     "DTS source → DTB binary"),
]

MAGISK_MENU = [
    ("1", "Create new Magisk module",             None,                     "Scaffold module structure"),
    ("2", "Pack module → installable zip",        None,                     "Ready to flash"),
    ("3", "Install module on device",             None,                     "Push + install via Magisk"),
    ("4", "List installed modules",               ["magisk", "list"],       "What's installed"),
    ("5", "Create prop-setting module",           None,                     "Quick persistent props"),
    ("6", "Install WearOS compat module",         ["wearos", "setup"],      "WearOS Magisk module"),
]

DIAG_MENU = [
    ("1", "Full diagnostic report",               ["diag", "full"],         "Comprehensive device report"),
    ("2", "Live logcat (errors only)",            ["diag", "logcat", "-l", "E"], "Error log stream"),
    ("3", "Capture bug report",                   ["diag", "bugreport"],    "Full ADB bugreport zip"),
    ("4", "Partition table",                      ["diag", "partitions"],   "All partitions with sizes"),
    ("5", "Analyze firmware image",               None,                     "Format, entropy, strings"),
    ("6", "Diff two images",                      None,                     "Compare stock vs patched"),
    ("7", "Scan firmware directory",              None,                     "Inventory of all images"),
]

KEYS_MENU = [
    ("1", "Generate full AOSP key set",           ["keys", "generate"],     "All signing keys"),
    ("2", "List available keys",                  ["keys", "list"],         "Keys in keys/ folder"),
]

NETWORK_MENU = [
    ("1", "Network overview",                     ["network", "info"],      "WiFi, BT, RIL, interfaces"),
    ("2", "RIL / modem status",                   ["network", "ril"],       "LTE/cellular details"),
    ("3", "Packet capture",                       None,                     "tcpdump via ADB"),
    ("4", "Edit /etc/hosts",                      None,                     "Block ads or add entries"),
    ("5", "Block ads (hosts file)",               None,                     "Quick ad-block install"),
]

PROPS_MENU = [
    ("1", "Get all properties",                   ["props", "get"],         "Full prop dump"),
    ("2", "Search properties",                    None,                     "Filter by keyword"),
    ("3", "Set a property",                       None,                     "Live setprop on device"),
    ("4", "Apply DEBUG preset",                   ["props", "preset", "debug"],        "Enable USB debug, root ADB"),
    ("5", "Apply PERFORMANCE preset",             ["props", "preset", "performance"],  "Speed tweaks"),
    ("6", "Apply WATCH preset",                   ["props", "preset", "watch"],        "Watch-optimized settings"),
    ("7", "Spoof device fingerprint",             ["props", "spoof-fingerprint"],      "Play Integrity bypass"),
    ("8", "Edit build.prop (from dump)",          None,                     "Edit prop file directly"),
    ("9", "Save all props to file",               None,                     "Export props to text file"),
]

SELINUX_MENU = [
    ("1", "Pull SELinux policy",                  ["sepolicy", "pull"],     "Download from device"),
    ("2", "Scan AVC denials (audit2allow)",       ["sepolicy", "audit"],    "Generate allow rules"),
    ("3", "Set SELinux permissive (global)",      ["sepolicy", "permissive"],"Disable enforcement"),
    ("4", "Set domain permissive",                None,                     "Permissive for one domain"),
]

PIPELINE_MENU = [
    ("1",  "root-device         (detect→backup→patch→flash→verify)",    ["pipeline","root-device"],                      "Full root workflow"),
    ("2",  "root-device --dry-run (preview steps only)",                 ["pipeline","root-device","--dry-run"],          "Safe preview"),
    ("3",  "full-backup         (all partitions + apps + manifest)",     ["pipeline","full-backup"],                      "Complete backup"),
    ("4",  "avb-disable         (backup vbmeta → blank → flash)",        ["pipeline","avb-disable"],                      "Disable AVB"),
    ("5",  "avb-disable --dry-run",                                      ["pipeline","avb-disable","--dry-run"],          "Preview"),
    ("6",  "flash-rom           (validate→backup→flash all partitions)", None,                                            "Requires --parts-dir"),
    ("7",  "wearos-setup        (root check→module→install→verify)",     ["pipeline","wearos-setup"],                     "WearOS compat"),
    ("8",  "configure-bands     (backup bands → apply → reboot)",        None,                                            "Choose carrier"),
    ("9",  "list all pipelines  (steps + descriptions)",                 ["pipeline","list"],                             "Reference"),
    ("10", "custom pipeline     (chain any steps manually)",             None,                                            "Advanced"),
    ("11", "resume interrupted  (continue from last failed step)",       None,                                            "Use --resume"),
]

BANDS_MENU = [
    ("1",  "List ALL carrier profiles",                  ["bands","carriers"],                           "US + global"),
    ("2",  "List US carrier profiles",                   ["bands","carriers","--country","us"],          "VZ/TMo/ATT/FirstNet"),
    ("3",  "List EU carrier profiles",                   ["bands","carriers","--country","eu"],          "Europe"),
    ("4",  "List UK carrier profiles",                   ["bands","carriers","--country","uk"],          "Vodafone/EE"),
    ("5",  "List Asia carrier profiles",                 ["bands","carriers","--country","jp"],          "Japan/Korea/India"),
    ("6",  "Current band/network status",                ["bands","status"],                             "No root needed"),
    ("7",  "── VERIZON ──────────────────────",          None,                                           ""),
    ("8",  "Verizon — Full (LTE + 5G Sub6 + mmWave)",    ["bands","verizon","--tier","full"],            "All Verizon bands"),
    ("9",  "Verizon — LTE only (disable 5G)",            ["bands","verizon","--tier","lte-only"],        "B2/4/5/13/48/66"),
    ("10", "Verizon — 5G priority",                      ["bands","verizon","--tier","5g"],              "C-band priority"),
    ("11", "Verizon — CBRS only (B48/n48)",              ["bands","verizon","--tier","cbrs"],            "Enterprise/private"),
    ("12", "Verizon — Dry run (show config only)",       ["bands","verizon","--dry-run"],                "Preview changes"),
    ("13", "── T-MOBILE ─────────────────────",          None,                                           ""),
    ("14", "T-Mobile — Full bands",                      ["bands","apply","--carrier","tmobile"],        "B2/4/5/12/25/41/66/71+n41/71"),
    ("15", "── AT&T ──────────────────────────",         None,                                           ""),
    ("16", "AT&T — Full bands",                          ["bands","apply","--carrier","att"],            "B2/4/5/7/17/29/30/66+n77/78"),
    ("17", "FirstNet (AT&T first responder)",            ["bands","apply","--carrier","firstnet"],       "B14 priority"),
    ("18", "── INTERNATIONAL ────────────────",          None,                                           ""),
    ("19", "Europe — Generic all carriers",              ["bands","apply","--carrier","eu_generic"],     "B1/3/5/7/8/20/28+n78"),
    ("20", "UK — Vodafone",                              ["bands","apply","--carrier","uk_vodafone"],    "UK Vodafone bands"),
    ("21", "UK — EE",                                    ["bands","apply","--carrier","uk_ee"],          "UK EE bands"),
    ("22", "Australia — Telstra",                        ["bands","apply","--carrier","australia_telstra"],"B1/3/5/7/28/40+n78"),
    ("23", "Japan — NTT Docomo",                         ["bands","apply","--carrier","japan_docomo"],   "B1/3/19/21/28/42+n77/78/79"),
    ("24", "South Korea — SK Telecom",                   ["bands","apply","--carrier","korea_skt"],      "B1/3/5/7/8/42+n78"),
    ("25", "India — Jio",                                ["bands","apply","--carrier","india_jio"],      "B3/5/40+n77/78"),
    ("26", "China Telecom",                              ["bands","apply","--carrier","china_telecom"],  "B1/3/5/40/41+n41/78/79"),
    ("27", "Canada — Rogers",                            ["bands","apply","--carrier","canada_rogers"],  "B2/4/5/7/12/17/66+n66/77"),
    ("28", "── UTILITY ──────────────────────",          None,                                           ""),
    ("29", "GLOBAL — All bands (restore defaults)",      ["bands","apply","--carrier","global_roaming"],"Enable everything"),
    ("30", "Custom carrier (choose from list)",          None,                                           "Pick any profile"),
    ("31", "MTK Engineering Mode (GUI band picker)",     ["bands","mtk-engmode"],                       "MTK only"),
    ("32", "Restore band backup",                        None,                                           "Roll back changes"),
]

QUALCOMM_MENU = [
    ("1",  "Identify chip + modem capabilities",    ["qualcomm","identify"],                   "Detect Snapdragon SoC"),
    ("2",  "List all Snapdragon chips",             ["qualcomm","list"],                       "SD450 through SD8 Gen3"),
    ("3",  "5G-capable chips only",                ["qualcomm","list","--5g-only"],            "Filter 5G devices"),
    ("4",  "Network status (carrier/signal/type)",  ["qualcomm","network-status"],             "No root needed"),
    ("5",  "LTE + 5G band info + reference table",  ["qualcomm","bands-info"],                 "Active bands + full table"),
    ("6",  "Show band presets",                     ["qualcomm","band-presets"],               "All preset configs"),
    ("7",  "Apply band preset (US T-Mobile)",       ["qualcomm","band-set","--preset","us_tmobile"],     "US T-Mobile bands"),
    ("8",  "Apply band preset (US AT&T)",           ["qualcomm","band-set","--preset","us_att"],         "US AT&T bands"),
    ("9",  "Apply band preset (US Verizon)",        ["qualcomm","band-set","--preset","us_verizon"],     "US Verizon bands"),
    ("10", "Apply band preset (all bands)",         ["qualcomm","band-set","--preset","all_bands"],      "Restore all bands"),
    ("11", "Apply band preset (global unlocked)",   ["qualcomm","band-set","--preset","global_unlocked"],"All global bands"),
    ("12", "Apply band preset (LTE only)",          ["qualcomm","band-set","--preset","lte_only"],       "Disable 5G NR"),
    ("13", "Apply band preset (5G preferred)",      ["qualcomm","band-set","--preset","5g_preferred"],   "Max 5G priority"),
    ("14", "Set custom LTE bands",                  None,                                      "Enter band numbers"),
    ("15", "Force LTE only (disable 5G)",           ["qualcomm","band-set","--lte-only"],     "Battery saving"),
    ("16", "Enable 5G preferred",                   ["qualcomm","band-set","--5g-preferred"],"Max 5G priority"),
    ("17", "Send AT command to modem",              None,                                      "Query band/signal"),
    ("18", "BACKUP EFS (do this first!)",           ["qualcomm","efs-backup"],                "Critical safety step"),
    ("19", "Restore EFS from backup",               None,                                      "Roll back changes"),
    ("20", "Enable DIAG mode (for QPST/QFIL)",     ["qualcomm","diag-enable"],               "USB diagnostic interface"),
    ("21", "Enter EDL mode (9008)",                 ["qualcomm","edl","--enter"],             "Emergency Download Mode"),
    ("22", "Check EDL device connected",            ["qualcomm","edl","--check"],             "Scan USB 0x05C6:0x9008"),
    ("23", "EDL mode guide + tools info",           ["qualcomm","edl"],                       "Full EDL reference"),
]

CHIPSET_MENU = [
    ("1",  "MTK — Download mode guide",           ["mtk",      "download"],           "BROM mode for SP Flash Tool"),
    ("2",  "MTK — Identify chip",                 ["mtk",      "identify"],           "MTK-specific properties"),
    ("3",  "MTK — List all chips",                ["mtk",      "list"],               "All supported MTK SoCs"),
    ("4",  "MTK — Dump Boot ROM",                 ["mtk",      "dump-brom"],          "BROM dump via mtkclient"),
    ("5",  "Unisoc — Download mode guide",        ["unisoc",   "download"],           "FDL mode for UpgradeDownload"),
    ("6",  "Unisoc — Identify chip",              ["unisoc",   "identify"],           "Unisoc-specific properties"),
    ("7",  "Unisoc — List all chips",             ["unisoc",   "list"],               "All supported Unisoc SoCs"),
    ("8",  "Unisoc — PAC file info",              None,                               "Inspect PAC firmware"),
    ("9",  "Rockchip — Download/MaskROM guide",   ["rockchip", "download"],           "MaskROM mode entry"),
    ("10", "Rockchip — Identify chip",            ["rockchip", "identify"],           "Rockchip-specific properties"),
    ("11", "Rockchip — List all chips",           ["rockchip", "list"],               "PX30 through RK3588S"),
    ("12", "Rockchip — Flash image",              None,                               "Flash via rkdeveloptool"),
    ("13", "Rockchip — Partition table",          ["rockchip", "partition-table"],    "Show partition layout"),
    ("14", "Allwinner — FEL mode guide",          ["allwinner","download"],           "FEL mode entry"),
    ("15", "Allwinner — Identify chip",           ["allwinner","identify"],           "Allwinner-specific properties"),
    ("16", "Allwinner — List all chips",          ["allwinner","list"],               "A10 through H618/R818"),
    ("17", "Allwinner — Flash via sunxi-fel",     None,                               "Flash image in FEL mode"),
    ("18", "Allwinner — Read SoC SID",            ["allwinner","dump-sid"],           "Chip serial number"),
    ("19", "Allwinner — Partition table",         ["allwinner","partition-table"],    "eMMC / NAND / A-B"),
    ("20", "Realtek — Rescue mode guide",         ["realtek",  "download"],           "Rescue mode entry"),
    ("21", "Realtek — Identify chip",             ["realtek",  "identify"],           "Realtek-specific properties"),
    ("22", "Realtek — List all chips",            ["realtek",  "list"],               "RTD1195 through RTD1619B"),
    ("23", "Realtek — Extract rescue image",      None,                               "Inspect rescue.img"),
    ("24", "Realtek — Partition table",           ["realtek",  "partition-table"],    "Show partition layout"),
    ("25", "ALL CHIPS — List watch chips",        ["chips",    "list-all"],           "Every watch-class SoC"),
]

MENU_MAP = {
    "pipeline_menu":  ("Pipelines — Automated Multi-Step Workflows", PIPELINE_MENU),
    "device_menu":    ("Device Info & Status",    DEVICE_MENU),
    "backup_menu":    ("Backup & Restore",        BACKUP_MENU),
    "root_menu":      ("Root Device",             ROOT_MENU),
    "wearos_menu":    ("WearOS Compatibility",    WEAROS_MENU),
    "sysimg_menu":    ("System Image Editor",     SYSIMG_MENU),
    "apk_menu":       ("APK Tools",               APK_MENU),
    "partition_menu": ("Partitions",              PARTITION_MENU),
    "bootimg_menu":   ("Boot Image Tools",        BOOTIMG_MENU),
    "avb_menu":       ("AVB & Security",          AVB_MENU),
    "ota_menu":       ("OTA Packages",            OTA_MENU),
    "rom_menu":       ("ROM Builder",             ROM_MENU),
    "tree_menu":      ("Device Tree & TWRP",      TREE_MENU),
    "magisk_menu":    ("Magisk Modules",          MAGISK_MENU),
    "diag_menu":      ("Analysis & Diagnostics",  DIAG_MENU),
    "keys_menu":      ("Keys & Signing",          KEYS_MENU),
    "network_menu":   ("Network & RIL",           NETWORK_MENU),
    "props_menu":     ("Properties Editor",       PROPS_MENU),
    "selinux_menu":   ("SELinux Tools",           SELINUX_MENU),
    "chipset_menu":   ("Chipset Tools — MTK · Unisoc · Rockchip · Allwinner · Realtek", CHIPSET_MENU),
    "qualcomm_menu":  ("Qualcomm Snapdragon — Band Config, EFS, EDL", QUALCOMM_MENU),
    "bands_menu":     ("Band Config — All Vendors (Verizon/TMo/ATT/EU/JP/Global)", BANDS_MENU),
}


# ══════════════════════════════════════════════════════════════════════════════
# Prompt helpers
# ══════════════════════════════════════════════════════════════════════════════

def prompt_file(label="File path", must_exist=True) -> str:
    while True:
        val = Prompt.ask(f"  [cyan]{label}[/cyan]")
        if not val:
            return ""
        p = Path(val.strip())
        if must_exist and not p.exists():
            console.print(f"  [red]Not found: {p}[/red]")
            continue
        return str(p)


def prompt_serial() -> str:
    devs = adb_devices()
    if not devs:
        console.print("  [red]No device connected.[/red]")
        return ""
    if len(devs) == 1:
        return devs[0]
    for i, d in enumerate(devs, 1):
        console.print(f"  {i}. {d}")
    choice = Prompt.ask("  Select device", default="1")
    try:
        return devs[int(choice) - 1]
    except Exception:
        return devs[0]


def prompt_partition() -> str:
    COMMON = ["boot","recovery","system","vendor","userdata","cache",
              "vbmeta","dtbo","persist","modem","lk","preloader"]
    console.print("  Common: " + "  ".join(f"[cyan]{p}[/cyan]" for p in COMMON))
    return Prompt.ask("  Partition name")


# ══════════════════════════════════════════════════════════════════════════════
# Dynamic action handlers (for menu items that need user input)
# ══════════════════════════════════════════════════════════════════════════════

def handle_dynamic(key: str, menu_name: str, item_label: str, session: dict):
    """Handle menu items that need prompts before running."""
    serial = session.get("device_serial", "")

    # ── BACKUP ────────────────────────────────────────────────────────────────
    if menu_name == "backup_menu" and "Restore" in item_label:
        run_cmd(["backup", "list"], interactive=True)
        bk = Prompt.ask("  Backup directory path")
        if bk:
            run_cmd(["backup", "restore", bk], interactive=True)

    # ── ROOT ──────────────────────────────────────────────────────────────────
    elif menu_name == "root_menu" and "custom" in item_label:
        boot = prompt_file("boot.img path")
        if boot:
            run_cmd(["root", "patch", "--boot", boot, "--flash"], interactive=True)

    # ── WEAROS ────────────────────────────────────────────────────────────────
    elif menu_name == "wearos_menu" and "Install WearOS APKs" in item_label:
        apk_dir = prompt_file("APK directory", must_exist=True)
        if apk_dir:
            system_install = Confirm.ask("  Install as system apps (requires root)?", default=False)
            args = ["wearos", "install-apks", "--apk-dir", apk_dir]
            if system_install:
                args.append("--system")
            run_cmd(args, interactive=True)
    elif menu_name == "wearos_menu" and "watch face" in item_label.lower():
        apk = prompt_file("Watch face APK or folder")
        if apk:
            run_cmd(["wearos", "watchface", apk], interactive=True)

    # ── SYSTEM IMAGE ─────────────────────────────────────────────────────────
    elif menu_name == "sysimg_menu":
        if "Extract system" in item_label:
            img = prompt_file("system.img path")
            if img:
                run_cmd(["sysimg", "extract", img], interactive=True)
        elif "Extract vendor" in item_label:
            img = prompt_file("vendor.img path")
            if img:
                run_cmd(["sysimg", "extract", img, "--label", "vendor"], interactive=True)
        elif "Interactive edit" in item_label:
            img = prompt_file("Image path (system.img / vendor.img)")
            if img:
                run_cmd(["sysimg", "edit", img], interactive=True)
        elif "Repack" in item_label:
            d = prompt_file("Extracted directory", must_exist=True)
            lbl = Prompt.ask("  Label", default="system")
            if d:
                run_cmd(["sysimg", "repack", d, "--label", lbl], interactive=True)
        elif "Patch build.prop" in item_label:
            img = prompt_file("Image path")
            key = Prompt.ask("  Property key (e.g. ro.debuggable)")
            val = Prompt.ask("  New value")
            if img and key and val:
                run_cmd(["sysimg", "patch-prop", img, "--key", key, "--value", val], interactive=True)
        elif "Browse" in item_label:
            img = prompt_file("Image path")
            path = Prompt.ask("  Path inside image", default="/")
            if img:
                run_cmd(["sysimg", "ls", img, path], interactive=True)
        elif "info" in item_label.lower():
            img = prompt_file("Image path")
            if img:
                run_cmd(["sysimg", "info", img], interactive=True)
        elif "WearOS" in item_label:
            d = prompt_file("Extracted system dir", must_exist=True)
            if d:
                run_cmd(["wearos", "patch-sysimg", d], interactive=True)

    # ── APK ───────────────────────────────────────────────────────────────────
    elif menu_name == "apk_menu":
        if "Decompile" in item_label:
            apk = prompt_file("APK file path")
            if apk:
                run_cmd(["apk", "decompile", apk], interactive=True)
        elif "Recompile" in item_label:
            d = prompt_file("Project directory (smali/)", must_exist=True)
            if d:
                run_cmd(["apk", "recompile", d], interactive=True)
        elif "Pull APK" in item_label:
            pkg = Prompt.ask("  Package name (e.g. com.example.app)")
            if pkg:
                run_cmd(["apk", "pull", pkg], interactive=True)
        elif "Install APK" in item_label:
            apk = prompt_file("APK file path")
            if apk:
                run_cmd(["adb", "install", apk], interactive=True)

    # ── PARTITIONS ────────────────────────────────────────────────────────────
    elif menu_name == "partition_menu":
        if "single" in item_label:
            part = prompt_partition()
            if part:
                run_cmd(["dump", part], interactive=True)
        elif "Flash" in item_label:
            part = prompt_partition()
            img  = prompt_file("Image file to flash")
            if part and img:
                run_cmd(["flash", part, img], interactive=True)

    # ── BOOT IMAGE ────────────────────────────────────────────────────────────
    elif menu_name == "bootimg_menu":
        if "Unpack" in item_label:
            img = prompt_file("boot.img path")
            if img:
                run_cmd(["bootimg", "unpack", img], interactive=True)
        elif "Repack" in item_label:
            d = prompt_file("Unpacked directory", must_exist=True)
            if d:
                run_cmd(["bootimg", "repack", d], interactive=True)
        elif "cmdline" in item_label:
            img = prompt_file("boot.img path")
            console.print("  [dim]Enter params to add (e.g. androidboot.selinux=permissive)[/dim]")
            param = Prompt.ask("  Add param")
            if img and param:
                run_cmd(["bootimg", "patch-cmdline", img, "--add", param], interactive=True)
        elif "info" in item_label.lower():
            img = prompt_file("boot.img path")
            if img:
                run_cmd(["bootimg", "info", img], interactive=True)

    # ── AVB ───────────────────────────────────────────────────────────────────
    elif menu_name == "avb_menu":
        if "info" in item_label.lower():
            img = prompt_file("vbmeta.img path")
            if img:
                run_cmd(["avb", "info", img], interactive=True)
        elif "Re-sign" in item_label:
            img = prompt_file("Image to sign")
            key = prompt_file("AVB key (.pem)")
            if img and key:
                run_cmd(["avb", "sign", img, "--key", key], interactive=True)

    # ── OTA ───────────────────────────────────────────────────────────────────
    elif menu_name == "ota_menu":
        if "Extract" in item_label:
            ota = prompt_file("OTA zip or payload.bin path")
            if ota:
                run_cmd(["ota", "extract", ota], interactive=True)
        elif "info" in item_label.lower():
            ota = prompt_file("OTA zip or payload.bin path")
            if ota:
                run_cmd(["ota", "info", ota], interactive=True)
        elif "Create" in item_label:
            d = prompt_file("Partitions directory", must_exist=True)
            v = Prompt.ask("  Vendor", choices=["mtk","unisoc"], default="mtk")
            if d:
                run_cmd(["ota", "create", "--parts-dir", d], interactive=True)

    # ── ROM ───────────────────────────────────────────────────────────────────
    elif menu_name == "rom_menu":
        if "MTK" in item_label:
            d = prompt_file("Partitions directory", must_exist=True)
            if d:
                run_cmd(["rom", "build", "--parts-dir", d, "--vendor", "mtk"], interactive=True)
        elif "Unisoc" in item_label:
            d = prompt_file("Partitions directory", must_exist=True)
            if d:
                run_cmd(["rom", "build", "--parts-dir", d, "--vendor", "unisoc"], interactive=True)
        elif "GSI" in item_label:
            gsi = prompt_file("GSI image path")
            if gsi:
                wipe = Confirm.ask("  Wipe userdata after flash?", default=True)
                args = ["rom", "gsi", gsi]
                if wipe:
                    args.append("--wipe-data")
                run_cmd(args, interactive=True)
        elif "instructions" in item_label.lower():
            v = Prompt.ask("  Vendor", choices=["mtk","unisoc"], default="mtk")
            d = prompt_file("ROM package directory", must_exist=True)
            if d:
                run_cmd(["rom", "flash", d, "--vendor", v], interactive=True)

    # ── DEVICE TREE / TWRP ───────────────────────────────────────────────────
    elif menu_name == "tree_menu":
        if "DTBO" in item_label:
            img = prompt_file("DTBO image path")
            if img:
                run_cmd(["dtb", "extract", img], interactive=True)
        elif "Decompile" in item_label:
            img = prompt_file("DTB file path")
            if img:
                run_cmd(["dtb", "decompile", img], interactive=True)
        elif "Compile" in item_label:
            dts = prompt_file("DTS source file")
            if dts:
                run_cmd(["dtb", "compile", dts], interactive=True)

    # ── MAGISK ───────────────────────────────────────────────────────────────
    elif menu_name == "magisk_menu":
        if "Create" in item_label:
            mod_id = Prompt.ask("  Module ID (no spaces, e.g. my_tweaks)")
            name   = Prompt.ask("  Module name")
            if mod_id and name:
                run_cmd(["magisk", "create", "--id", mod_id, "--name", name], interactive=True)
        elif "Pack" in item_label:
            d = prompt_file("Module directory", must_exist=True)
            if d:
                run_cmd(["magisk", "pack", d], interactive=True)
        elif "Install" in item_label and "WearOS" not in item_label:
            z = prompt_file("Module zip path")
            if z:
                run_cmd(["magisk", "install", z], interactive=True)
        elif "prop" in item_label.lower():
            mod_id = Prompt.ask("  Module ID", default="watchrom_props")
            console.print("  [dim]Enter key=value pairs (blank to finish):[/dim]")
            pairs = []
            while True:
                p = Prompt.ask("  key=value (or Enter to finish)", default="")
                if not p:
                    break
                pairs.append(p)
            if pairs:
                args = ["magisk", "prop-module", "--id", mod_id]
                for p in pairs:
                    args += ["--set", p]
                run_cmd(args, interactive=True)

    # ── DIAGNOSTICS ──────────────────────────────────────────────────────────
    elif menu_name == "diag_menu":
        if "Analyze firmware" in item_label:
            img = prompt_file("Firmware image path")
            if img:
                run_cmd(["analyze", "info", img, "--deep"], interactive=True)
        elif "Diff" in item_label:
            i1 = prompt_file("First image (stock)")
            i2 = prompt_file("Second image (patched)")
            if i1 and i2:
                run_cmd(["analyze", "diff", i1, i2], interactive=True)
        elif "Scan" in item_label:
            d = prompt_file("Firmware directory", must_exist=True)
            if d:
                run_cmd(["analyze", "scan", d], interactive=True)

    # ── NETWORK ──────────────────────────────────────────────────────────────
    elif menu_name == "network_menu":
        if "capture" in item_label.lower():
            iface = Prompt.ask("  Interface", default="wlan0")
            dur   = Prompt.ask("  Duration (seconds)", default="30")
            run_cmd(["network", "capture", "--iface", iface, "--duration", dur], interactive=True)
        elif "hosts" in item_label.lower() and "Block" not in item_label:
            console.print("  [dim]Format: 'ip hostname' e.g. '0.0.0.0 ads.example.com'[/dim]")
            entry = Prompt.ask("  Entry to add")
            if entry:
                run_cmd(["network", "hosts", "--add", entry], interactive=True)
        elif "Block ads" in item_label:
            run_cmd(["network", "hosts", "--block-ads"], interactive=True)

    # ── PROPERTIES ───────────────────────────────────────────────────────────
    elif menu_name == "props_menu":
        if "Search" in item_label:
            kw = Prompt.ask("  Search keyword")
            if kw:
                run_cmd(["props", "get", "--filter", kw], interactive=True)
        elif "Set a property" in item_label:
            key = Prompt.ask("  Property key")
            val = Prompt.ask("  New value")
            perm = Confirm.ask("  Persistent (resetprop)?", default=True)
            if key and val:
                args = ["props", "set", key, val]
                if perm:
                    args.append("--permanent")
                run_cmd(args, interactive=True)
        elif "Edit build.prop" in item_label:
            bp = prompt_file("build.prop file path")
            if bp:
                console.print("  [dim]Enter key=value pairs (blank to finish):[/dim]")
                pairs = []
                while True:
                    p = Prompt.ask("  key=value", default="")
                    if not p:
                        break
                    pairs.append(p)
                if pairs:
                    args = ["props", "edit-buildprop", bp]
                    for p in pairs:
                        args += ["--set", p]
                    run_cmd(args, interactive=True)
        elif "Save all" in item_label:
            out = Prompt.ask("  Save to file", default="props_dump.txt")
            run_cmd(["props", "get", "--out", out], interactive=True)

    # ── SELINUX ──────────────────────────────────────────────────────────────
    elif menu_name == "selinux_menu":
        if "domain" in item_label.lower():
            dom = Prompt.ask("  Domain name (e.g. untrusted_app)")
            if dom:
                run_cmd(["sepolicy", "permissive", "--domain", dom], interactive=True)

    # ── CHIPSET — Rockchip ───────────────────────────────────────────────────
    elif menu_name == "chipset_menu":
        if "PAC" in item_label:
            pac = prompt_file("PAC file path")
            if pac:
                run_cmd(["unisoc", "pac-info", pac], interactive=True)
        elif "Rockchip" in item_label and "Flash" in item_label:
            img = prompt_file("Image file to flash")
            loader = Prompt.ask("  Loader .bin path (optional, press Enter to skip)", default="")
            part   = Prompt.ask("  Partition name (optional, press Enter for full image)", default="")
            if img:
                args = ["rockchip", "flash", img]
                if loader: args += ["--loader", loader]
                if part:   args += ["--partition", part]
                run_cmd(args, interactive=True)
        elif "Allwinner" in item_label and "Flash" in item_label:
            img = prompt_file("Image file to flash")
            if img:
                method = Prompt.ask("  Method", choices=["sunxi-fel","phoenixsuit","livesuit"], default="sunxi-fel")
                run_cmd(["allwinner", "flash", img, "--method", method], interactive=True)
        elif "Realtek" in item_label and "Extract" in item_label:
            img = prompt_file("Rescue/install image path")
            if img:
                run_cmd(["realtek", "extract-rescue", img], interactive=True)
        elif any(x in item_label for x in ["MTK","Unisoc","Rockchip","Allwinner","Realtek","ALL CHIPS"]):
            # All other chipset items have direct actions handled via action list
            console.print("[yellow]  Select the numbered option to run this command.[/yellow]")

    # ── PIPELINES ────────────────────────────────────────────────────────────
    elif menu_name == "pipeline_menu":
        if "flash-rom" in item_label and "parts" in item_label.lower():
            d = prompt_file("Parts directory (containing .img files)", must_exist=True)
            if d:
                dry = Confirm.ask("  Dry run first?", default=True)
                args = ["pipeline","flash-rom","--parts-dir", d]
                if dry: args.append("--dry-run")
                run_cmd(args, interactive=True)
        elif "configure-bands" in item_label:
            console.print("  Carriers: verizon tmobile att eu_generic global_roaming")
            console.print("  Full list: watchrom pipeline configure-bands --help")
            carrier = Prompt.ask("  Carrier name")
            if carrier:
                dry = Confirm.ask("  Dry run first?", default=True)
                args = ["pipeline","configure-bands","--carrier", carrier]
                if dry: args.append("--dry-run")
                run_cmd(args, interactive=True)
        elif "custom" in item_label.lower():
            console.print("  [dim]Enter step names separated by spaces[/dim]")
            console.print("  [dim]Steps: detect backup check-magisk patch-boot flash-boot verify[/dim]")
            console.print("  [dim]       dump-partitions backup-apps create-blank flash-vbmeta[/dim]")
            steps_str = Prompt.ask("  Steps to run")
            if steps_str:
                args = ["pipeline","custom"] + steps_str.split()
                run_cmd(args, interactive=True)
        elif "resume" in item_label.lower():
            console.print("  Available pipelines: root-device full-backup avb-disable flash-rom")
            pl_name = Prompt.ask("  Pipeline name")
            step    = Prompt.ask("  Resume from step")
            if pl_name and step:
                run_cmd(["pipeline", pl_name, "--resume", step], interactive=True)

    # ── BANDS (all vendors) ─────────────────────────────────────────────────
    elif menu_name == "bands_menu":
        if "Custom carrier" in item_label:
            # Show full list then let user pick
            run_cmd(["bands","carriers"], interactive=True)
            carrier = Prompt.ask("  Enter carrier name (from list above)")
            if carrier:
                dry = Confirm.ask("  Dry run first?", default=True)
                args = ["bands","apply","--carrier", carrier]
                if dry: args.append("--dry-run")
                run_cmd(args, interactive=True)
        elif "Restore band" in item_label:
            bk = prompt_file("Band backup directory", must_exist=True)
            if bk:
                run_cmd(["bands","restore", bk], interactive=True)
        elif "────" in item_label:
            # Section headers — just show message
            console.print(f"  [dim]{item_label}[/dim]")

    # ── QUALCOMM ────────────────────────────────────────────────────────────
    elif menu_name == "qualcomm_menu":
        if "custom LTE bands" in item_label:
            console.print("  [dim]Enter comma-separated LTE band numbers (e.g. 2,4,12,66,71)[/dim]")
            bands = Prompt.ask("  Bands")
            if bands:
                mode = Prompt.ask("  Also disable 5G?", choices=["yes","no"], default="no")
                args = ["qualcomm","band-set","--bands", bands]
                if mode == "yes": args.append("--lte-only")
                run_cmd(args, interactive=True)
        elif "AT command" in item_label:
            console.print('  [dim]Examples: AT+QNWINFO  AT+CSQ  AT+COPS?  AT+QCFG="band"[/dim]')
            cmd = Prompt.ask("  AT command", default="AT+QNWINFO")
            run_cmd(["qualcomm","at-cmd","--cmd", cmd], interactive=True)
        elif "Restore EFS" in item_label:
            bk = prompt_file("EFS backup directory", must_exist=True)
            if bk:
                run_cmd(["qualcomm","efs-restore", bk], interactive=True)

    else:
        console.print("[yellow]  (feature coming soon)[/yellow]")

    console.print()
    input("  Press Enter to return to menu...")


# ══════════════════════════════════════════════════════════════════════════════
# Menu renderer + navigator
# ══════════════════════════════════════════════════════════════════════════════

def render_submenu(title: str, items: list):
    """Render a numbered submenu table."""
    console.clear()
    console.print(f"\n[bold cyan]{'═'*58}[/bold cyan]")
    console.print(f"[bold white]  ⌚ WatchROM — {title}[/bold white]")
    console.print(f"[bold cyan]{'═'*58}[/bold cyan]\n")

    t = Table(box=box.SIMPLE, show_header=False, padding=(0,1))
    t.add_column("Num",   style="bold yellow", width=4)
    t.add_column("Label", style="bold white",  width=36)
    t.add_column("Desc",  style="dim",         width=40)

    for key, label, _, desc in items:
        t.add_row(f"[{key}]", label, desc)
    t.add_row("[0]", "← Back to main menu", "")

    console.print(t)
    console.print()


def render_main_menu():
    """Render the main menu in two columns."""
    console.clear()
    console.print(BANNER)

    devs = adb_devices()
    if devs:
        info = get_device_info(devs[0])
        console.print(Panel(
            f"[green]● {info.get('model','?')}[/green]  "
            f"[dim]{info.get('device','?')} | "
            f"Android {info.get('android','?')} | "
            f"{info.get('platform','?')}[/dim]",
            title="Connected Device", border_style="green", padding=(0,2)
        ))
    else:
        console.print(Panel(
            "[yellow]○ No device connected — connect via USB and enable USB Debugging[/yellow]",
            border_style="yellow", padding=(0,2)
        ))

    console.print(f"\n[bold cyan]{'═'*58}[/bold cyan]")
    console.print(f"[bold white]  ⌚ WatchROM — Main Menu[/bold white]")
    console.print(f"[bold cyan]{'═'*58}[/bold cyan]\n")

    t = Table(box=box.SIMPLE, show_header=False, padding=(0,1), expand=True)
    t.add_column("Num",   style="bold yellow", width=5)
    t.add_column("Label", style="bold white",  width=30)
    t.add_column("Desc",  style="dim",         width=40)

    for key, label, _, desc in MAIN_MENU:
        t.add_row(f"[{key}]", label, desc)

    console.print(t)
    console.print()


def navigate_submenu(menu_name: str, session: dict) -> dict:
    title, items = MENU_MAP[menu_name]

    while True:
        render_submenu(title, items)
        choice = Prompt.ask("  [bold yellow]Select[/bold yellow]", default="0").strip()

        if choice == "0":
            return session

        matched = [(k, label, action, desc)
                   for k, label, action, desc in items if k == choice]
        if not matched:
            console.print("[red]  Invalid choice.[/red]")
            time.sleep(0.8)
            continue

        key, label, action, desc = matched[0]
        console.print()

        if action is None:
            # Dynamic — needs prompts
            handle_dynamic(choice, menu_name, label, session)
        elif isinstance(action, list):
            run_cmd(action, interactive=True)
            console.print()
            input("  Press Enter to continue...")

    return session


# ══════════════════════════════════════════════════════════════════════════════
# Main loop
# ══════════════════════════════════════════════════════════════════════════════

def main():
    session = load_session()

    # First-run: scan + backup
    if not session.get("first_run_done"):
        console.clear()
        console.print(BANNER)
        session = first_run_scan(session)

    # Main menu loop
    while True:
        render_main_menu()
        choice = Prompt.ask("  [bold yellow]Select[/bold yellow]", default="0").strip()

        # Find matching item
        matched = [(k, label, action, desc)
                   for k, label, action, desc in MAIN_MENU if k == choice]
        if not matched:
            console.print("[red]  Invalid choice.[/red]")
            time.sleep(0.8)
            continue

        key, label, action, desc = matched[0]

        if action == "exit" or choice == "0":
            console.print(f"\n[bold cyan]  Thanks for using WatchROM! ★[/bold cyan]\n")
            break
        elif action == "adb_shell":
            devs = adb_devices()
            if devs:
                serial = devs[0]
                console.print(f"\n[cyan]  Opening ADB shell on {serial} (type 'exit' to return)...[/cyan]\n")
                subprocess.run(["adb", "-s", serial, "shell"])
            else:
                console.print("[red]  No device connected.[/red]")
                input("  Press Enter...")
        elif action in MENU_MAP:
            session = navigate_submenu(action, session)
        else:
            console.print(f"[yellow]  {action} — coming soon[/yellow]")
            time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[bold cyan]  Goodbye! ★[/bold cyan]\n")
