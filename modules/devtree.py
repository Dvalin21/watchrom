"""
devtree.py — Android device tree scaffolding from partition dumps
Generates: device.mk, BoardConfig, init.rc, sepolicy stubs, PRODUCT makefiles
"""
import click
import json
from pathlib import Path
from datetime import datetime
from modules import (
    run_adb, adb_devices, get_device_props, detect_chipset_from_props,
    OUTPUT_DIR, console
)


def collect_device_info(serial: str) -> dict:
    """Collect all relevant Android properties for device tree generation."""
    props = get_device_props(serial)
    chip_vendor, chipset = detect_chipset_from_props(props)

    # Enumerate partitions
    _, part_out, _ = run_adb(
        ["shell", "ls /dev/block/by-name/ 2>/dev/null"],
        serial=serial, check=False
    )
    partitions = [p.strip() for p in part_out.splitlines() if p.strip()]

    # Check for A/B
    is_ab = props.get("ro.build.ab_update", "false") == "true"

    # Screen info
    _, wm_out, _ = run_adb(["shell", "wm size 2>/dev/null"], serial=serial, check=False)
    screen = "360x360"
    if "Physical size" in wm_out:
        screen = wm_out.split("Physical size:")[-1].strip()

    # Installed HALs
    _, hal_out, _ = run_adb(
        ["shell", "ls /vendor/lib*/hw/ 2>/dev/null | grep -E '\\.(so)$'"],
        serial=serial, check=False
    )
    hals = [h.strip() for h in hal_out.splitlines() if h.strip()]

    return {
        "serial":       serial,
        "manufacturer": props.get("ro.product.manufacturer", "unknown").lower(),
        "brand":        props.get("ro.product.brand", "unknown"),
        "model":        props.get("ro.product.model", "Unknown Watch"),
        "device":       props.get("ro.product.device", "unknown").lower(),
        "board":        props.get("ro.product.board", ""),
        "platform":     props.get("ro.board.platform", ""),
        "chipset":      chipset,
        "chip_vendor":  chip_vendor,
        "android_ver":  props.get("ro.build.version.release", "11"),
        "sdk":          props.get("ro.build.version.sdk", "30"),
        "abi":          props.get("ro.product.cpu.abi", "arm64-v8a"),
        "abi2":         props.get("ro.product.cpu.abi2", ""),
        "arch":         "arm64" if "arm64" in props.get("ro.product.cpu.abi","") else "arm",
        "treble":       props.get("ro.treble.enabled", "false") == "true",
        "ab_update":    is_ab,
        "avb_version":  props.get("ro.boot.avb_version", ""),
        "screen":       screen,
        "partitions":   partitions,
        "hals":         hals[:20],
        "fingerprint":  props.get("ro.build.fingerprint", ""),
        "security_patch": props.get("ro.build.version.security_patch",""),
    }


def make_dt_board_config(info: dict) -> str:
    vendor  = info["manufacturer"]
    device  = info["device"]
    arch    = info["arch"]
    platform = info["platform"] or info["chipset"].lower()

    return f"""\
#
# BoardConfig.mk
# Device: {vendor}/{device}   Chipset: {info['chipset']}
# Generated: {datetime.now().strftime("%Y-%m-%d")} by WatchROM devtree
#
LOCAL_PATH := device/{vendor}/{device}

# Platform
TARGET_BOARD_PLATFORM          := {platform}
TARGET_BOOTLOADER_BOARD_NAME   := {info.get('board', device)}
TARGET_NO_BOOTLOADER           := true

# Architecture
TARGET_ARCH                    := {arch}
TARGET_ARCH_VARIANT            := {"armv8-a" if arch=="arm64" else "armv7-a-neon"}
TARGET_CPU_ABI                 := {info['abi']}
TARGET_CPU_ABI2                := {info['abi2']}
TARGET_CPU_VARIANT             := generic

# Kernel — stub (replace with actual prebuilt or source)
TARGET_PREBUILT_KERNEL         := $(LOCAL_PATH)/prebuilt/Image.gz-dtb
BOARD_KERNEL_IMAGE_NAME        := Image.gz-dtb
BOARD_KERNEL_BASE              := 0x00000000
BOARD_KERNEL_PAGESIZE          := 2048
BOARD_KERNEL_CMDLINE           := console=ttyS1,115200n8 androidboot.hardware={device} loglevel=4

# Partitions (tune to match your device)
BOARD_BOOTIMAGE_PARTITION_SIZE      := 0x4000000
BOARD_RECOVERYIMAGE_PARTITION_SIZE  := 0x4000000
BOARD_SYSTEMIMAGE_PARTITION_SIZE    := 0xC0000000
BOARD_VENDORIMAGE_PARTITION_SIZE    := 0x20000000
BOARD_USERDATAIMAGE_PARTITION_SIZE  := 0x100000000
BOARD_FLASH_BLOCK_SIZE              := 131072

TARGET_USERIMAGES_USE_EXT4         := true
TARGET_USERIMAGES_USE_F2FS         := true
BOARD_SYSTEMIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_VENDORIMAGE_FILE_SYSTEM_TYPE := ext4

# Treble
{"BOARD_VNDK_VERSION := current" if info['treble'] else "# Treble not enabled on this device"}

# A/B
{"AB_OTA_UPDATER := true" if info['ab_update'] else "# A-only device"}

# AVB — disable for development
BOARD_AVB_ENABLE := false

# Vendor — needed for TARGET_COPY_OUT_VENDOR
TARGET_COPY_OUT_VENDOR := vendor

# Soong
BUILD_BROKEN_DUP_RULES := true
"""


def make_dt_device_mk(info: dict) -> str:
    vendor = info["manufacturer"]
    device = info["device"]
    return f"""\
#
# device.mk
# {info['brand']} {info['model']} ({device})
#
LOCAL_PATH := device/{vendor}/{device}

# Soong
PRODUCT_SOONG_NAMESPACES += $(LOCAL_PATH)

# Inherit AOSP base
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/base.mk)
{"$(call inherit-product, $(SRC_TARGET_DIR)/product/treble_common_64.mk)" if info['treble'] else ""}

PRODUCT_DEVICE      := {device}
PRODUCT_NAME        := aosp_{device}
PRODUCT_BRAND       := {info['brand']}
PRODUCT_MODEL       := {info['model']}
PRODUCT_MANUFACTURER := {info['manufacturer']}

PRODUCT_BUILD_PROP_OVERRIDES += \
    TARGET_DEVICE={device} \
    PRODUCT_NAME=aosp_{device}

# Fingerprint
PRODUCT_BUILD_PROP_OVERRIDES += \
    BUILD_FINGERPRINT="{info['fingerprint']}"

# API level
PRODUCT_SHIPPING_API_LEVEL := {info['sdk']}

# HAL stubs (add detected HALs here)
PRODUCT_PACKAGES += \\
    android.hardware.graphics.allocator@2.0-impl \\
    android.hardware.graphics.mapper@2.0-impl \\
    hwservicemanager
"""


def make_init_rc(info: dict) -> str:
    device  = info["device"]
    platform = info["platform"] or "default"
    return f"""\
# init.{device}.rc — generated by WatchROM devtree
# Customize for your device's init requirements

on early-init
    setprop ro.hardware {device}

on init
    # Storage
    symlink /data/tombstones /tombstones

on fs
    mount_all /vendor/etc/fstab.{device} --early
    mount_all /vendor/etc/fstab.{device} --late

on post-fs-data
    mkdir /data/vendor 0771 root root
    mkdir /data/vendor/logs 0771 root root

on boot
    # Set performance governor
    write /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor interactive

service vendor.sensors-hal-2-0 /vendor/bin/hw/android.hardware.sensors@2.0-service
    class hal
    user system
    group system
    disabled

on property:sys.boot_completed=1
    start vendor.sensors-hal-2-0
"""


def make_fstab(info: dict) -> str:
    device = info["device"]
    parts  = info["partitions"]
    lines  = [f"# fstab.{device} — generated by WatchROM devtree", ""]
    common = [
        ("system",  "/system",  "ext4", "ro,barrier=1",          "wait,slotselect,avb=vbmeta,logical"),
        ("vendor",  "/vendor",  "ext4", "ro,barrier=1",          "wait,slotselect,avb"),
        ("userdata","/data",    "f2fs", "nosuid,nodev,noatime",   "wait,fileencryption=aes-256-xts"),
        ("cache",   "/cache",   "ext4", "nosuid,nodev,noatime",   "wait"),
        ("persist", "/persist", "ext4", "nosuid,nodev,noatime",   "wait"),
    ]
    lines.append(f"# <block>                                     <mount>    <type> <mnt_flags>              <fsmgr_flags>")
    for (part, mnt, fstype, flags, fsmgr) in common:
        if part in parts or True:
            node = f"/dev/block/by-name/{part}"
            lines.append(f"{node:<48} {mnt:<12} {fstype:<6} {flags:<24} {fsmgr}")
    return "\n".join(lines) + "\n"


@click.group()
def devtree():
    """Scaffold an Android device tree from a connected device or dumps."""
    pass


@devtree.command("build")
@click.option("--serial", "-s", default=None, help="ADB serial of source device")
@click.option("--out",    "-o", default=None, help="Output directory")
@click.option("--no-props", is_flag=True, help="Skip device property probe (use defaults)")
def devtree_build(serial, out, no_props):
    """
    Generate an Android device tree scaffold.

    Probes the connected device for properties, partition layout, HALs,
    and generates BoardConfig.mk, device.mk, init.rc, fstab, and more.
    """
    console.print("\n[bold cyan]WatchROM — Device Tree Builder[/bold cyan]\n")

    if not no_props:
        devs = adb_devices()
        online = [s for s, st in devs if st == "device"]
        if not online:
            console.print("[red]✗ No ADB device online. Use --no-props for stub generation.[/red]")
            return
        target = serial or online[0]
        console.print(f"[cyan]→ Probing device: {target}[/cyan]")
        info = collect_device_info(target)
    else:
        info = {
            "serial":"offline","manufacturer":"unknown","brand":"Generic",
            "model":"SmartWatch","device": click.prompt("Device codename","watch1"),
            "board":"","platform": click.prompt("Platform","sc9863a"),
            "chipset":"SC9863A","chip_vendor":"unisoc",
            "android_ver":"11","sdk":"30","abi":"arm64-v8a","abi2":"",
            "arch":"arm64","treble":False,"ab_update":False,"avb_version":"",
            "screen":"360x360","partitions":[],"hals":[],"fingerprint":"","security_patch":"",
        }

    vendor = info["manufacturer"]
    device = info["device"]
    out_dir = Path(out) if out else (OUTPUT_DIR / "device_tree" / f"{vendor}_{device}")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "prebuilt").mkdir(exist_ok=True)
    (out_dir / "sepolicy").mkdir(exist_ok=True)
    (out_dir / "rootdir" / "etc").mkdir(parents=True, exist_ok=True)

    # Dump info JSON
    with open(out_dir / "device_info.json", "w") as f:
        json.dump(info, f, indent=2)

    # Generate files
    gen_files = {
        "BoardConfig.mk":              make_dt_board_config(info),
        "device.mk":                   make_dt_device_mk(info),
        f"rootdir/etc/init.{device}.rc": make_init_rc(info),
        f"rootdir/etc/fstab.{device}":   make_fstab(info),
        "Android.mk": (
            f"LOCAL_PATH := $(call my-dir)\n"
            f"ifeq ($(TARGET_DEVICE),{device})\n"
            f"include $(call all-makefiles-under,$(LOCAL_PATH))\n"
            f"endif\n"
        ),
        "AndroidProducts.mk": (
            f"PRODUCT_MAKEFILES := $(LOCAL_DIR)/device.mk\n"
            f"COMMON_LUNCH_CHOICES := aosp_{device}-user aosp_{device}-userdebug aosp_{device}-eng\n"
        ),
        "sepolicy/file_contexts": (
            f"# {device} SELinux file contexts\n"
            f"/vendor/bin/hw/{device}_daemon  u:object_r:vendor_file:s0\n"
        ),
        "prebuilt/README.txt": (
            "Place prebuilt kernel: Image.gz-dtb\n"
            "Extract from boot.img: watchrom dump boot\n"
            "Then: unpackbootimg -i boot.img --out ./\n"
        ),
    }

    for filename, content in gen_files.items():
        path = out_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        console.print(f"  [green]✓[/green] {filename}")

    console.print(f"\n[bold green]✓ Device tree: {out_dir}[/bold green]")
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Device    : {info['brand']} {info['model']} ({device})")
    console.print(f"  Chipset   : {info['chipset']} ({info['chip_vendor'].upper()})")
    console.print(f"  Arch      : {info['arch']} | ABI: {info['abi']}")
    console.print(f"  Partitions: {len(info['partitions'])} detected")
    console.print(f"  Treble    : {'Yes' if info['treble'] else 'No'}")
    console.print(f"  A/B       : {'Yes' if info['ab_update'] else 'No'}")
    console.print(f"\n[dim]Copy tree to AOSP/device/{vendor}/{device}/ and run lunch aosp_{device}-eng[/dim]")
