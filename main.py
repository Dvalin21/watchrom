#!/usr/bin/env python3
"""
WatchROM — Entry Point
No args = interactive TUI | With args = direct CLI
Supports: MTK, Unisoc, Rockchip, Allwinner, Realtek + any Android
"""
import sys, os
TOOLKIT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLKIT_DIR)

if len(sys.argv) == 1:
    from launcher import main as tui_main
    tui_main()
    sys.exit(0)

import click
from rich.console import Console
from rich.table   import Table
from rich         import box

console = Console()

BANNER = """[bold cyan]
 ██╗    ██╗ █████╗ ████████╗ ██████╗██╗  ██╗██████╗  ██████╗ ███╗   ███╗
 ██║    ██║██╔══██╗╚══██╔══╝██╔════╝██║  ██║██╔══██╗██╔═══██╗████╗ ████║
 ██║ █╗ ██║███████║   ██║   ██║     ███████║██████╔╝██║   ██║██╔████╔██║
 ██║███╗██║██╔══██║   ██║   ██║     ██╔══██║██╔══██╗██║   ██║██║╚██╔╝██║
 ╚███╔███╔╝██║  ██║   ██║   ╚██████╗██║  ██║██║  ██║╚██████╔╝██║ ╚═╝ ██║
  ╚══╝╚══╝ ╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝
[/bold cyan][bold yellow]  ★  One Kit to Rule Them All  ★  Android ROM Engineering Suite[/bold yellow]
[dim]  MTK · Unisoc · Rockchip · Allwinner · Realtek · Any Android[/dim]
[dim]  Run without arguments for the interactive guided menu.[/dim]
"""

SECTIONS = [
    ("PIPELINES — AUTOMATED WORKFLOWS","yellow",[
        ("pipeline root-device","Detect→backup→Magisk patch→flash→verify","Any"),
        ("pipeline full-backup","Dump all partitions + apps + manifest","Any"),
        ("pipeline avb-disable","Backup vbmeta→blank→flash (disable AVB)","Any"),
        ("pipeline flash-rom -p <dir>","Validate→backup→AVB off→flash all","Any"),
        ("pipeline wearos-setup","Root check→build module→install→verify","Any"),
        ("pipeline configure-bands -c verizon","Backup→apply carrier bands→reboot","Any"),
        ("pipeline list","Show all pipelines with steps","Any"),
        ("pipeline custom <step1> <step2>","Chain any steps into custom pipeline","Any"),
        ("pipeline root-device --dry-run","Preview steps without running","Any"),
        ("pipeline flash-rom --resume flash-all","Resume interrupted pipeline","Any"),
    ]),
    ("DEVICE & DETECTION","cyan",[
        ("device info","Auto-detect chipset/partitions/root/AVB","Any"),
        ("device reboot <mode>","Reboot: system/recovery/bootloader/edl","Any"),
    ]),
    ("PARTITIONS","green",[
        ("dump [part] --all","Dump one or all partitions","Any"),
        ("flash <part> <img>","Flash image to partition","Any"),
    ]),
    ("BOOT IMAGE","magenta",[
        ("bootimg unpack <img>","Unpack boot.img → kernel+ramdisk/+dtb","Any"),
        ("bootimg repack <dir>","Repack edited dir → boot.img","Any"),
        ("bootimg patch-cmdline","Add/remove kernel cmdline params","Any"),
        ("bootimg info <img>","Show boot.img header","Any"),
    ]),
    ("ROOT","red",[
        ("root patch","Patch boot.img with Magisk","Any"),
        ("root check","Check root status","Any"),
    ]),
    ("WEAROS","yellow",[
        ("wearos status","Check WearOS compatibility","Any"),
        ("wearos setup","Configure WearOS (Magisk module)","Any"),
        ("wearos install-apks -d <dir>","Install WearOS APKs","Any"),
        ("wearos patch-sysimg <dir>","Patch system image for WearOS","Any"),
        ("wearos companion-guide","Step-by-step setup guide","Any"),
    ]),
    ("SYSTEM IMAGE","blue",[
        ("sysimg extract <img>","Extract system/vendor.img","Any"),
        ("sysimg repack <dir>","Repack → flashable image","Any"),
        ("sysimg edit <img>","Interactive extract→edit→repack","Any"),
        ("sysimg patch-prop","Patch build.prop inside image","Any"),
        ("sysimg ls/cat <img>","Browse/read files inside image","Any"),
    ]),
    ("AVB / VBMETA","cyan",[
        ("avb patch --blank","Disable AVB / blank vbmeta","Any"),
        ("avb sign <img> -k key","Re-sign with custom AVB key","Any"),
        ("avb info <img>","Show AVB metadata","Any"),
    ]),
    ("OTA","green",[
        ("ota extract <file>","Extract from OTA/payload.bin","Any"),
        ("ota info <file>","Show OTA package contents","Any"),
        ("ota create -p <dir>","Create flashable OTA zip","Any"),
    ]),
    ("DTB / DTBO","magenta",[
        ("dtb extract <dtbo>","Extract DTBO entries","Any"),
        ("dtb decompile <dtb>","DTB binary → DTS source","Any"),
        ("dtb compile <dts>","DTS source → DTB binary","Any"),
        ("dtb patch-prop","Patch DT node property","Any"),
    ]),
    ("PROPERTIES","yellow",[
        ("props get [key]","Get device properties","Any"),
        ("props set <k> <v>","Set property (live)","Any root"),
        ("props preset debug|watch","Apply property preset","Any root"),
        ("props edit-buildprop <f>","Edit build.prop from dump","Any"),
        ("props spoof-fingerprint","Spoof device fingerprint","Any root"),
    ]),
    ("SELINUX","red",[
        ("sepolicy pull","Pull policy from device","Any"),
        ("sepolicy audit","AVC denials → allow rules","Any"),
        ("sepolicy permissive","Set permissive mode","Any root"),
    ]),
    ("APK TOOLS","blue",[
        ("apk decompile <apk>","apktool+jadx full decompile","Any"),
        ("apk recompile <dir>","Rebuild and sign APK","Any"),
        ("apk pull <package>","Pull APK from device","Any"),
        ("apk list","List installed packages","Any"),
    ]),
    ("MAGISK MODULES","cyan",[
        ("magisk create","Scaffold Magisk module","Any"),
        ("magisk pack <dir>","Pack → installable zip","Any"),
        ("magisk install <zip>","Install module on device","Any root"),
        ("magisk prop-module","Quick prop-setting module","Any root"),
    ]),
    ("ROM BUILDING","green",[
        ("rom build -p <dir>","MTK scatter / Unisoc XML","MTK/Unisoc"),
        ("rom gsi <img>","Flash Generic System Image","Treble"),
        ("devtree build","Android device tree scaffold","Any"),
        ("twrp build","TWRP device tree + build.sh","Any"),
    ]),
    ("KEYS & SIGNING","magenta",[
        ("keys generate","Generate full AOSP key set","Any"),
        ("keys list","List available keys","Any"),
    ]),
    ("ANALYSIS","yellow",[
        ("analyze info <img>","Format, entropy, signatures","Any"),
        ("analyze entropy <img>","Block entropy map","Any"),
        ("analyze strings <img>","Extract strings from binary","Any"),
        ("analyze diff <a> <b>","Diff two images","Any"),
        ("analyze scan <dir>","Scan firmware directory","Any"),
    ]),
    ("DIAGNOSTICS","red",[
        ("diag full","Full device diagnostic","Any"),
        ("diag logcat","Filtered logcat","Any"),
        ("diag bugreport","ADB bug report","Any"),
        ("diag partitions","Partition table","Any"),
    ]),
    ("NETWORK","blue",[
        ("network info","WiFi/BT/RIL overview","Any"),
        ("network capture","Packet capture (tcpdump)","Any root"),
        ("network ril","RIL/modem status","Any"),
        ("network hosts","Edit /etc/hosts","Any root"),
    ]),
    ("BACKUP & RESTORE","cyan",[
        ("backup full","Full backup (all partitions+apps)","Any"),
        ("backup restore <dir>","Restore from backup","Any"),
        ("backup apps","ADB app backup","Any"),
        ("backup list","List all backups","Any"),
    ]),
    ("MTK CHIPSET","green",[
        ("mtk download","BROM download mode guide","MTK"),
        ("mtk identify","MTK-specific properties","MTK"),
        ("mtk list","All supported MTK chips","MTK"),
        ("mtk dump-brom","Dump Boot ROM via mtkclient","MTK"),
    ]),
    ("UNISOC CHIPSET","yellow",[
        ("unisoc download","FDL download mode guide","Unisoc"),
        ("unisoc identify","Unisoc-specific properties","Unisoc"),
        ("unisoc list","All supported Unisoc chips","Unisoc"),
        ("unisoc pac-info <file>","Inspect PAC firmware file","Unisoc"),
    ]),
    ("ROCKCHIP CHIPSET","magenta",[
        ("rockchip download","MaskROM mode guide","Rockchip"),
        ("rockchip identify","Rockchip-specific properties","Rockchip"),
        ("rockchip list","All supported Rockchip chips","Rockchip"),
        ("rockchip flash <img>","Flash via rkdeveloptool","Rockchip"),
        ("rockchip dump <part>","Dump partition (ADB/MaskROM)","Rockchip"),
        ("rockchip partition-table","Show partition layout","Rockchip"),
    ]),
    ("ALLWINNER CHIPSET","red",[
        ("allwinner download","FEL mode guide","Allwinner"),
        ("allwinner identify","Allwinner-specific properties","Allwinner"),
        ("allwinner list","All supported Allwinner chips","Allwinner"),
        ("allwinner flash <img>","Flash via sunxi-fel","Allwinner"),
        ("allwinner dump-sid","Read SoC SID/serial","Allwinner"),
        ("allwinner partition-table","Show partition layout","Allwinner"),
    ]),
    ("REALTEK CHIPSET","blue",[
        ("realtek download","Rescue mode guide","Realtek"),
        ("realtek identify","Realtek-specific properties","Realtek"),
        ("realtek list","All supported Realtek chips","Realtek"),
        ("realtek extract-rescue","Inspect rescue image","Realtek"),
        ("realtek partition-table","Show partition layout","Realtek"),
    ]),
    ("QUALCOMM SNAPDRAGON","red",[
        ("qualcomm identify","Detect Snapdragon chip + modem capabilities","Qualcomm"),
        ("qualcomm list","All Snapdragon chips (SD450→SD8 Gen3)","Qualcomm"),
        ("qualcomm network-status","Live network/signal/carrier info","Qualcomm"),
        ("qualcomm bands-info","LTE+5G band reference + active bands","Qualcomm"),
        ("qualcomm band-presets","Show all band config presets","Qualcomm"),
        ("qualcomm band-set --preset us_tmobile","Apply a band preset","Qualcomm root"),
        ("qualcomm band-set --bands 2,4,12,66,71","Set specific LTE bands","Qualcomm root"),
        ("qualcomm band-set --lte-only","Force LTE only (disable 5G)","Qualcomm root"),
        ("qualcomm at-cmd -c AT+QNWINFO","Send AT command to modem","Qualcomm"),
        ("qualcomm efs-backup","Backup modem EFS (do this first!)","Qualcomm"),
        ("qualcomm efs-restore <dir>","Restore EFS from backup","Qualcomm root"),
        ("qualcomm edl --enter","Reboot into EDL mode (9008)","Qualcomm"),
        ("qualcomm edl --check","Detect EDL USB device","Qualcomm"),
        ("qualcomm diag-enable","Enable DIAG mode for QPST/QFIL","Qualcomm"),
    ]),
    ("BAND CONFIG — ALL VENDORS","cyan",[
        ("bands carriers","List all carrier profiles (US+global)","Any"),
        ("bands carriers --country us","US carrier profiles (Verizon/TMo/ATT)","Any"),
        ("bands verizon","Full Verizon band config (LTE+5G+mmWave)","Any vendor"),
        ("bands verizon --tier lte-only","Verizon LTE only (no 5G)","Any vendor"),
        ("bands apply --carrier tmobile","Apply T-Mobile band profile","Any vendor"),
        ("bands apply --carrier eu_generic","Apply EU band profile","Any vendor"),
        ("bands apply --carrier global_roaming","All bands (restore default)","Any vendor"),
        ("bands status","Current band/signal/carrier status","Any vendor"),
        ("bands restore <dir>","Restore from band backup","Any vendor"),
        ("bands mtk-engmode","Open MTK Engineering Mode app","MTK"),
    ]),
    ("CHIPS OVERVIEW","cyan",[
        ("chips list-all","All watch-class chips (all vendors)","All"),
        ("mtk list --watch-only","MTK watch chips only","MTK"),
        ("unisoc list --watch-only","Unisoc watch chips only","Unisoc"),
    ]),
    ("ADB UTILS","dim",[
        ("adb shell [cmd]","ADB shell","Any"),
        ("adb push/pull <f>","Push/pull files","Any"),
        ("adb install <apk>","Install APK","Any"),
        ("adb logcat","Stream logcat","Any"),
        ("adb devices","List ADB/fastboot devices","Any"),
    ]),
]


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """WatchROM — run without args for interactive guided menu"""
    console.print(BANNER)
    if ctx.invoked_subcommand is None:
        for section, color, cmds in SECTIONS:
            t = Table(title=f"[bold {color}]{section}[/bold {color}]",
                      box=box.SIMPLE_HEAVY, border_style=color,
                      show_header=False, padding=(0,1), title_justify="left")
            t.add_column("Command",     style=f"bold {color}", width=34)
            t.add_column("Description", style="white",          width=42)
            t.add_column("Target",      style="dim",            width=12)
            for cmd, desc, tgt in cmds:
                t.add_row(f"watchrom {cmd}", desc, tgt)
            console.print(t)
        console.print("\n[dim]Run [bold]watchrom[/bold] for the interactive guided menu. "
                      "Run [bold]watchrom <command> --help[/bold] for details.[/dim]\n")


# ── Register all modules ────────────────────────────────────────────────────
from modules.device      import device
from modules.partition   import dump, flash
from modules.bootimg     import bootimg
from modules.root        import root
from modules.wearos      import wearos
from modules.sysimg      import sysimg
from modules.avb         import avb
from modules.ota         import ota
from modules.rom         import rom
from modules.apk         import apk
from modules.twrp        import twrp
from modules.devtree     import devtree
from modules.dtb         import dtb
from modules.props       import props
from modules.sepolicy    import sepolicy
from modules.magisk      import magisk
from modules.keys        import keys
from modules.analyze     import analyze
from modules.diag        import diag
from modules.network     import network
from modules.backup      import backup
from modules.chipset     import mtk, unisoc, chips
from modules.rk_aw_rtk  import rockchip, allwinner, realtek
from modules.qualcomm   import qualcomm
from modules.modem_bands  import bands
from modules.pipeline_cmd import pipeline
from modules.adb_cmds    import adb_grp

for cmd in [device, dump, flash, bootimg, root, wearos, sysimg, avb, ota,
            rom, apk, twrp, devtree, dtb, props, sepolicy, magisk, keys,
            analyze, diag, network, backup,
            mtk, unisoc, chips,
            rockchip, allwinner, realtek,
            qualcomm, bands, pipeline]:
    cli.add_command(cmd)
cli.add_command(adb_grp, name="adb")

if __name__ == "__main__":
    cli()
