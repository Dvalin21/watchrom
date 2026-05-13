"""
samsung.py — Samsung device detection, bootloader unlock, and Heimdall flashing

Samsung devices use KVB (Knox Verification Boot) instead of standard AVB.
Fastboot-based vbmeta disable does NOT work on Samsung devices.

Flashing is done via Heimdall (Linux ODIN alternative):
  https://github.com/Benjamin-Dobell/Heimdall

US Snapdragon models have permanently locked bootloaders and cannot be
unlocked via software. Exynos models (international) can be unlocked.

References:
  - Samsung KVB: Knox Verified Boot (proprietary, not standard AOSP AVB)
  - Heimdall: https://glassechidna.com.au/heimdall/
  - Partition layout: Samsung uses vendor-specific names (BOOT, SYSTEM, etc.)
"""
import subprocess
import time
from pathlib import Path
from typing import Optional
from modules import (
    run, run_adb, run_fastboot, adb_devices, fastboot_devices,
    get_device_props, console
)


# ── Samsung detection ──────────────────────────────────────────────────────

# Samsung build fingerprint prefix pattern
SAMSUNG_FINGERPRINT_PREFIX = "samsung/"

# Known Exynos chipset codenames (detected from ro.board.platform)
EXYNOS_PLATFORMS = [
    "exynos2100", "exynos2200", "exynos2400",
    "exynos990", "exynos9820", "exynos9825",
    "exynos9810", "exynos9611", "exynos9610",
    "exynos9609", "exynos8895", "exynos8890",
    "exynos7885", "exynos7884", "exynos7870",
    "exynos7580", "exynos7420", "exynos5433",
    "universal2100", "universal2200", "universal2400",
    "universal990", "universal9820",
]


def is_samsung_device(props: dict) -> bool:
    """Check if device is a Samsung from build properties.

    Checks ro.build.fingerprint for the 'samsung/' prefix.
    Also checks ro.product.manufacturer as fallback.
    """
    fp = props.get("ro.build.fingerprint", "")
    if fp.startswith(SAMSUNG_FINGERPRINT_PREFIX):
        return True
    mfr = props.get("ro.product.manufacturer", "").lower()
    if "samsung" in mfr:
        return True
    brand = props.get("ro.product.brand", "").lower()
    if "samsung" in brand:
        return True
    return False


def is_exynos_device(props: dict) -> bool:
    """Check if device uses Samsung Exynos SoC."""
    platform = props.get("ro.board.platform", "").lower()
    for ex in EXYNOS_PLATFORMS:
        if ex in platform:
            return True
    return False


def get_samsung_model(props: dict) -> str:
    """Return Samsung model number (e.g. SM-S918B) from properties."""
    return props.get("ro.product.model", props.get("ro.product.name", "unknown"))


def check_bootloader_unlock_interactive(serial: str = None) -> bool:
    """Check if a Samsung device has an unlocked bootloader.

    Samsung bootloader unlock is done via:
      1. Enable OEM Unlock in Developer Options
      2. Reboot to Download Mode (Vol- + Vol+ + USB)
      3. Long press Vol+ to unlock

    Returns True if bootloader appears unlocked, False otherwise.
    """
    # Check via getprop
    _, out, _ = run_adb(
        ["shell", "getprop ro.boot.securedboot 2>/dev/null; "
                   "getprop ro.boot.warranty_bit 2>/dev/null; "
                   "getprop ro.boot.verifiedbootstate 2>/dev/null"],
        serial=serial, check=False
    )
    props_out = out.strip()
    # Warranty bit: 0 = unlocked, 1 = locked
    # verifiedbootstate: "orange" = unlocked, "green" or "yellow" = locked
    # securedboot: "0" = unlocked, "1" = locked
    lines = props_out.splitlines()
    if len(lines) >= 3:
        secured = lines[0].strip()
        warranty = lines[1].strip()
        verified = lines[2].strip()
        if secured == "0" or warranty == "0" or "orange" in verified.lower():
            return True
        return False

    # Fallback: check for custom binary indicators
    _, out, _ = run_adb(
        ["shell", "getprop ro.boot.flash.locked 2>/dev/null; "
                   "getprop ro.boot.vbmeta.device_state 2>/dev/null"],
        serial=serial, check=False
    )
    for line in out.splitlines():
        if "unlocked" in line.lower():
            return True
    return False


# ── Download Mode helpers ──────────────────────────────────────────────────

def reboot_download(serial: str = None) -> bool:
    """Reboot Samsung device to Download Mode (ODIN mode).

    Returns True if successful.
    """
    # Try multiple methods
    methods = [
        ["shell", "reboot download"],
        ["shell", "su -c 'reboot download'"],
        ["reboot", "download"],
    ]
    for method in methods:
        rc, _, _ = run_adb(method, serial=serial, check=False, timeout=10)
        if rc == 0:
            return True
    return False


def is_download_mode(serial: str = None) -> bool:
    """Check if device is in Odin Download Mode by trying Heimdall detect."""
    rc, out, _ = run(["heimdall", "detect", "--no-reboot"],
                      check=False, timeout=10)
    return rc == 0


# ── Heimdall wrapper ───────────────────────────────────────────────────────

def heimdall_available() -> bool:
    """Check if heimdall is installed and usable."""
    return subprocess.run(
        ["which", "heimdall"], capture_output=True
    ).returncode == 0


# Samsung → standard Android partition name mapping for Heimdall
# Heimdall uses Samsung's partition naming convention
SAMSUNG_PARTITION_MAP = {
    # Samsung name → standard name (lowered for matching)
    "BOOT":           "boot",
    "RECOVERY":       "recovery",
    "SYSTEM":         "system",
    "USERDATA":       "userdata",
    "CACHE":          "cache",
    "DTBO":           "dtbo",
    "VBMETA":         "vbmeta",
    "VENDOR":         "vendor",
    "MODEM":          "modem",
    "CP":             "modem",      # CP (Cellular Processor) = modem
    "BL":             "bootloader", # Bootloader partition
    "SBYT":           "sbyt",       # Samsung boot config
    "UP_PARAM":       "up_param",   # Samsung param
    "HIDDEN":         "hidden",     # Hidden (OEM) partition
    "OMC":            "omc",        # Samsung OMC (carrier config)
    "CM":             "cm",         # Samsung CM partition
    "KEYMASTER":      "keymaster",
    "PERSISTENT":     "persistent",
    "PROTECT":        "protect",
}
# Reverse map: standard → Samsung
STD_TO_SAMSUNG = {v: k for k, v in SAMSUNG_PARTITION_MAP.items()}


def heimdall_flash(serial: str, samsung_part: str, image_path: Path) -> tuple:
    """Flash a single partition using Heimdall.

    Args:
        serial: Device serial (or empty to auto-detect)
        samsung_part: Samsung partition name (e.g. "BOOT", "SYSTEM")
        image_path: Path to image file

    Returns (rc, stdout, stderr)
    """
    cmd = ["heimdall", "flash"]
    if serial:
        cmd += ["--serial", serial]
    cmd += [f"--{samsung_part}", str(image_path)]
    return run(cmd, check=False, timeout=300)


def heimdall_flash_all(serial: str,
                       images: dict[str, Path],
                       partition_map: dict[str, str] = None) -> dict:
    """Flash multiple partitions using Heimdall (ODIN-style).

    Args:
        serial: Device serial
        images: Dict of standard partition names → image paths
        partition_map: Optional custom partition name mapping.
                       Defaults to SAMSUNG_PARTITION_MAP.

    Returns dict of {samsung_part: "ok" | "FAIL: reason"}
    """
    pmap = partition_map or STD_TO_SAMSUNG
    flash_queue = ["boot", "recovery", "system", "vendor", "vbmeta", "dtbo"]
    results = {}

    for part_std in flash_queue + [p for p in images if p not in flash_queue]:
        img = images.get(part_std)
        if not img:
            continue
        samsung_name = pmap.get(part_std, part_std.upper())
        rc, _, err = heimdall_flash(serial, samsung_name, img)
        results[samsung_name] = "ok" if rc == 0 else f"FAIL: {err[:80]}"

    return results


def heimdall_flash_all_odinalias(
    serial: str,
    images: dict[str, Path]
) -> dict:
    """Flash using ODIN partition name alias mappings.

    Common ODIN partition targets with correct Heimdall names:
      BL  → bootloader (sboot.bin)
      AP  → system (system.img)
      CP  → modem (modem.bin)
      CSC → cache (cache.img) or userdata
    """
    odin_map = {
        "BL":  "bootloader",
        "AP":  "system",
        "CP":  "modem",
        "CSC": "cache",
    }
    results = {}
    for odin_part, std_part in odin_map.items():
        img = images.get(std_part)
        if not img:
            continue
        samsung_name = STD_TO_SAMSUNG.get(std_part, std_part.upper())
        rc, _, err = heimdall_flash(serial, samsung_name, img)
        results[f"{odin_part} ({samsung_name})"] = \
            "ok" if rc == 0 else f"FAIL: {err[:80]}"

    return results


def heimdall_print_pit(serial: str = None) -> str:
    """Download and print PIT partition table."""
    rc, out, err = run(["heimdall", "print-pit", "--no-reboot"],
                        check=False, timeout=30)
    return out or err


# ── Samsung-specific pipeline helpers ──────────────────────────────────────

def samsung_disable_knox(ctx: dict) -> None:
    """Modify device context for Samsung KVB handling.

    Instead of flashing blank vbmeta (AVB method), Samsung needs:
      1. Bootloader unlocked
      2. Custom binary signed with Samsung cert (impossible without keys)
      3. OR use Magisk with Samsung-specific workaround (vbmeta patch)

    This function updates the context to use Samsung-compatible approach.
    """
    console.print("[yellow]  Samsung KVB device detected — standard AVB disable[/yellow]")
    console.print("[yellow]  will NOT work. Using Samsung-compatible method.[/yellow]")
    ctx["samsung_kvb"] = True
    ctx["skip_vbmeta"] = True


# ── Exynos chipset database ────────────────────────────────────────────────

EXYNOS_CHIPS = {
    # Flagship
    "exynos2400":  {"name":"Exynos 2400",  "modem":"Exynos 5300","year":2024,"edl":False,"heimdall":True,"us_model":False},
    "exynos2200":  {"name":"Exynos 2200",  "modem":"Exynos 5300","year":2022,"edl":False,"heimdall":True,"us_model":False},
    "exynos2100":  {"name":"Exynos 2100",  "modem":"Exynos 5123","year":2021,"edl":False,"heimdall":True,"us_model":False},
    "exynos990":   {"name":"Exynos 990",   "modem":"Exynos 5123","year":2020,"edl":False,"heimdall":True,"us_model":False},
    "exynos9820":  {"name":"Exynos 9820",  "modem":"Exynos 5100","year":2019,"edl":False,"heimdall":True,"us_model":False},
    "exynos9825":  {"name":"Exynos 9825",  "modem":"Exynos 5100","year":2019,"edl":False,"heimdall":True,"us_model":False},
    "exynos9810":  {"name":"Exynos 9810",  "modem":"Shannon 360","year":2018,"edl":False,"heimdall":True,"us_model":False},
    # Mid-range
    "exynos9611":  {"name":"Exynos 9611",  "modem":"Shannon 337","year":2019,"edl":False,"heimdall":True,"us_model":False},
    "exynos9610":  {"name":"Exynos 9610",  "modem":"Shannon 337","year":2018,"edl":False,"heimdall":True,"us_model":False},
    "exynos7885":  {"name":"Exynos 7885",  "modem":"Shannon 328","year":2018,"edl":False,"heimdall":True,"us_model":False},
    "exynos7870":  {"name":"Exynos 7870",  "modem":"Shannon 327","year":2016,"edl":False,"heimdall":True,"us_model":False},
    # Legacy
    "exynos8890":  {"name":"Exynos 8890",  "modem":"Shannon 335","year":2016,"edl":False,"heimdall":True,"us_model":False},
    "exynos7420":  {"name":"Exynos 7420",  "modem":"Shannon 333","year":2015,"edl":False,"heimdall":True,"us_model":False},
}

EXYNOS_SIGNATURES = {k: [k, v["name"].lower()] for k, v in EXYNOS_CHIPS.items()}


def identify_exynos(platform_str: str) -> dict:
    """Identify Exynos chip from platform string."""
    pl = platform_str.lower().replace("-", "").replace("_", "")
    for key, info in EXYNOS_CHIPS.items():
        if key in pl:
            return {"vendor": "samsung", "key": key, **info}
    for key, sigs in EXYNOS_SIGNATURES.items():
        for sig in sigs:
            if sig.lower() in pl:
                return {"vendor": "samsung", "key": key,
                        **EXYNOS_CHIPS.get(key, {"name": key, "heimdall": True})}
    return {}
