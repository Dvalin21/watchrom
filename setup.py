#!/usr/bin/env python3
"""
WatchROM — Dependency Installer & First-Run Setup
Installs all system packages, pip modules, and GitHub tools
"""

import os
import sys
import subprocess
import shutil
import json
import time
from pathlib import Path

# ── Colors (no rich yet — installs it) ────────────────────────────────────────
R  = "\033[0;31m";  G  = "\033[0;32m";  Y  = "\033[1;33m"
C  = "\033[0;36m";  M  = "\033[0;35m";  B  = "\033[0;34m"
W  = "\033[1;37m";  DIM= "\033[2m";     NC = "\033[0m"
BOLD="\033[1m"

BANNER = f"""{C}
 ██╗    ██╗ █████╗ ████████╗ ██████╗██╗  ██╗██████╗  ██████╗ ███╗   ███╗
 ██║    ██║██╔══██╗╚══██╔══╝██╔════╝██║  ██║██╔══██╗██╔═══██╗████╗ ████║
 ██║ █╗ ██║███████║   ██║   ██║     ███████║██████╔╝██║   ██║██╔████╔██║
 ██║███╗██║██╔══██║   ██║   ██║     ██╔══██║██╔══██╗██║   ██║██║╚██╔╝██║
 ╚███╔███╔╝██║  ██║   ██║   ╚██████╗██║  ██║██║  ██║╚██████╔╝██║ ╚═╝ ██║
  ╚══╝╚══╝ ╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝
{NC}{Y}  ★  One Kit to Rule Them All  ★  Dependency Installer & Setup{NC}
{DIM}  MTK (MT6739/MT6761/MT6762/MT6765/MT6768/MT6771/MT6785/MT6789){NC}
{DIM}  Unisoc (SC9832E/SC9863A/SL8541E/SC8541E/SC9863/UIS8581A){NC}
"""

TOOLKIT_ROOT = Path(__file__).resolve().parent
REPOS_DIR    = TOOLKIT_ROOT.parent / "watchrom_repos"
STATUS_FILE  = TOOLKIT_ROOT / ".setup_status.json"


def title(msg):
    print(f"\n{BOLD}{C}{'─'*60}{NC}")
    print(f"{BOLD}{W}  {msg}{NC}")
    print(f"{BOLD}{C}{'─'*60}{NC}")


def ok(msg):    print(f"  {G}✓{NC} {msg}")
def warn(msg):  print(f"  {Y}!{NC} {msg}")
def err(msg):   print(f"  {R}✗{NC} {msg}")
def info(msg):  print(f"  {DIM}{msg}{NC}")
def step(msg):  print(f"  {C}→{NC} {msg}", end=" ", flush=True)


def run(cmd, capture=True, timeout=300, cwd=None):
    try:
        result = subprocess.run(
            cmd if isinstance(cmd, list) else cmd.split(),
            capture_output=capture, text=True,
            timeout=timeout, cwd=cwd
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"
    except FileNotFoundError:
        return 1, "", "not found"
    except Exception as e:
        return 1, "", str(e)


def load_status():
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text())
        except Exception:
            pass
    return {}


def save_status(status):
    STATUS_FILE.write_text(json.dumps(status, indent=2))


# ═══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

APT_PACKAGES = [
    # Core Android tools
    "adb", "fastboot",
    # Java (needed for apktool, signapk, jadx)
    "default-jdk",
    # Build essentials
    "build-essential", "git", "wget", "curl", "unzip", "zip",
    # Python
    "python3", "python3-pip", "python3-dev",
    # Filesystem tools
    "e2fsprogs",          # ext4: debugfs, dumpe2fs, fsck.ext4
    "erofs-utils",        # erofs: fsck.erofs, mkfs.erofs
    "f2fs-tools",         # f2fs filesystem
    "android-sdk-libsparse-utils",  # simg2img, img2simg
    # Device tree tools
    "device-tree-compiler",  # dtc, fdtput, fdtget
    # Compression
    "lz4", "zstd", "xz-utils",
    # Crypto / signing
    "openssl",
    # Reverse engineering
    "apktool",
    # Network tools
    "tcpdump", "net-tools",
    # Misc utils
    "xxd", "binutils", "file", "patchelf",
    "libusb-1.0-0", "udev",
    # SELinux tools
    "setools",
    # mkbootimg / unpackbootimg
    "mkbootimg",
    # Rockchip tools
    "rkdeveloptool",
    # Allwinner / sunxi tools
    "sunxi-tools",
    # Filesystem tools (squashfs for Realtek rescue images)
    "squashfs-tools",
    # binwalk for unknown firmware analysis
    "binwalk",
    # Qualcomm / serial port tools
    "minicom",
    "screen",
    "picocom",
    # Additional signing tools
    "signapk",
]

PIP_PACKAGES = [
    "rich", "click", "prompt_toolkit", "pyserial", "requests",
    "avbtool", "pycryptodome", "protobuf", "bsdiff4",
]

# GitHub repos to clone into REPOS_DIR
# Format: (repo_url, clone_name, install_cmd_or_None, binary_to_link)
GITHUB_REPOS = [
    {
        "url":     "https://github.com/bkerler/mtkclient",
        "name":    "mtkclient",
        "desc":    "MTK BROM exploit + full flash toolkit",
        "install": "pip3 install --break-system-packages -e . 2>/dev/null || pip3 install -e .",
        "bins":    ["mtk"],
        "chip":    "MTK",
    },
    {
        "url":     "https://github.com/bkerler/edl",
        "name":    "edl",
        "desc":    "Qualcomm / Unisoc EDL protocol tool",
        "install": "pip3 install --break-system-packages -r requirements.txt 2>/dev/null || true",
        "bins":    ["edl"],
        "chip":    "Unisoc/MTK",
    },
    {
        "url":     "https://github.com/topjohnwu/Magisk",
        "name":    "Magisk",
        "desc":    "Magisk root manager (source reference)",
        "install": None,
        "bins":    [],
        "chip":    "Any",
    },
    {
        "url":     "https://github.com/skylot/jadx",
        "name":    "jadx",
        "desc":    "Java decompiler for APK analysis",
        "install": "cd jadx && ./gradlew dist 2>/dev/null || true",
        "bins":    ["jadx/build/jadx/bin/jadx"],
        "chip":    "Any",
    },
    {
        "url":     "https://github.com/iBotPeaches/Apktool",
        "name":    "Apktool",
        "desc":    "APK decode/rebuild tool",
        "install": None,
        "bins":    [],
        "chip":    "Any",
    },
    {
        "url":     "https://github.com/ssut/payload-dumper-go",
        "name":    "payload-dumper-go",
        "desc":    "OTA payload.bin extractor",
        "install": "go build -o payload-dumper-go . 2>/dev/null || true",
        "bins":    ["payload-dumper-go"],
        "chip":    "Any",
    },
    {
        "url":     "https://github.com/cfig/Android_boot_image_editor",
        "name":    "bootimgtools",
        "desc":    "Boot image pack/unpack (Kotlin)",
        "install": None,
        "bins":    [],
        "chip":    "Any",
    },
    {
        "url":     "https://github.com/unix3dgforce/OppoDecrypt",
        "name":    "OppoDecrypt",
        "desc":    "Decrypt Oppo/Realme/OnePlus firmware",
        "install": "pip3 install --break-system-packages -r requirements.txt 2>/dev/null || true",
        "bins":    [],
        "chip":    "MTK",
    },
    {
        "url":     "https://github.com/nkk71/MTK-Tools",
        "name":    "MTK-Tools",
        "desc":    "MTK scatter, preloader, logo tools",
        "install": None,
        "bins":    [],
        "chip":    "MTK",
    },
    {
        "url":     "https://github.com/SGS-Ikaros/unisoc-tools",
        "name":    "unisoc-tools",
        "desc":    "Unisoc PAC pack/unpack tools",
        "install": "pip3 install --break-system-packages -r requirements.txt 2>/dev/null || true",
        "bins":    [],
        "chip":    "Unisoc",
    },
    {
        "url":     "https://github.com/SebaUbuntu/TWRP-device-tree-generator",
        "name":    "twrp-dtg",
        "desc":    "TWRP device tree auto-generator",
        "install": "pip3 install --break-system-packages -r requirements.txt 2>/dev/null || true",
        "bins":    ["twrp-device-tree-generator"],
        "chip":    "Any",
    },
    {
        "url":     "https://github.com/WerWolv/ImHex",
        "name":    "ImHex",
        "desc":    "Hex editor with pattern matching",
        "install": None,
        "bins":    [],
        "chip":    "Any",
    },
    {
        "url":     "https://github.com/RikkaApps/Shizuku",
        "name":    "Shizuku",
        "desc":    "Privileged API access framework",
        "install": None,
        "bins":    [],
        "chip":    "Any",
    },
    {
        "url":     "https://github.com/google/android-emulator-container-scripts",
        "name":    "android-emulator",
        "desc":    "Android emulator container scripts",
        "install": None,
        "bins":    [],
        "chip":    "Any",
    },
    # ── Rockchip tools ─────────────────────────────────────────────────────
    {
        "url":     "https://github.com/rockchip-linux/rkdeveloptool",
        "name":    "rkdeveloptool",
        "desc":    "Rockchip MaskROM flash tool (Linux)",
        "install": "sudo apt-get install -y libusb-1.0-0-dev 2>/dev/null; "
                   "autoreconf -i && ./configure && make 2>/dev/null || true",
        "bins":    ["rkdeveloptool"],
        "chip":    "Rockchip",
    },
    {
        "url":     "https://github.com/linux-rockchip/rkflashtool",
        "name":    "rkflashtool",
        "desc":    "Alternative Rockchip flash tool",
        "install": "make 2>/dev/null || true",
        "bins":    ["rkflashtool"],
        "chip":    "Rockchip",
    },
    {
        "url":     "https://github.com/rockchip-linux/u-boot",
        "name":    "rk-uboot",
        "desc":    "Rockchip U-Boot source (loaders)",
        "install": None,
        "bins":    [],
        "chip":    "Rockchip",
    },
    {
        "url":     "https://github.com/TeeFirefly/rk3399-android",
        "name":    "rk3399-tools",
        "desc":    "RK3399 partition/flash tools",
        "install": None,
        "bins":    [],
        "chip":    "Rockchip",
    },
    # ── Allwinner tools ────────────────────────────────────────────────────
    {
        "url":     "https://github.com/linux-sunxi/sunxi-tools",
        "name":    "sunxi-tools",
        "desc":    "Allwinner FEL/flash tools (sunxi-fel, sunxi-nand-image-builder)",
        "install": "make 2>/dev/null || true",
        "bins":    ["sunxi-fel","sunxi-nand-image-builder","sunxi-fexc"],
        "chip":    "Allwinner",
    },
    {
        "url":     "https://github.com/linux-sunxi/u-boot-sunxi",
        "name":    "u-boot-sunxi",
        "desc":    "Allwinner U-Boot (SPL loaders for FEL)",
        "install": None,
        "bins":    [],
        "chip":    "Allwinner",
    },
    {
        "url":     "https://github.com/allwinner-zh/bootloader",
        "name":    "aw-bootloader",
        "desc":    "Allwinner boot0/boot1 sources",
        "install": None,
        "bins":    [],
        "chip":    "Allwinner",
    },
    {
        "url":     "https://github.com/Ithamar/awutils",
        "name":    "awutils",
        "desc":    "Allwinner firmware image utilities",
        "install": "make 2>/dev/null || true",
        "bins":    [],
        "chip":    "Allwinner",
    },
    # ── Realtek tools ──────────────────────────────────────────────────────
    {
        "url":     "https://github.com/jrior001/rtd-flash",
        "name":    "rtd-flash",
        "desc":    "Realtek RTD1xxx USB flash tool",
        "install": "pip3 install --break-system-packages -r requirements.txt 2>/dev/null || true",
        "bins":    [],
        "chip":    "Realtek",
    },
    {
        "url":     "https://github.com/iamgroot42/Realtek-RTD1195",
        "name":    "rtd1195-tools",
        "desc":    "RTD1195 recovery and flash utilities",
        "install": None,
        "bins":    [],
        "chip":    "Realtek",
    },
    # ── Qualcomm / Snapdragon tools ────────────────────────────────────────
    {
        "url":     "https://github.com/bkerler/edl",
        "name":    "edl",
        "desc":    "Qualcomm EDL 9008 protocol tool — EFS backup, partition ops",
        "install": "pip3 install --break-system-packages -r requirements.txt 2>/dev/null || true",
        "bins":    ["edl"],
        "chip":    "Qualcomm",
    },
    {
        "url":     "https://github.com/NationalSecurityAgency/ghidra",
        "name":    "ghidra",
        "desc":    "Reverse engineering suite (modem firmware analysis)",
        "install": None,
        "bins":    [],
        "chip":    "Any",
    },
    {
        "url":     "https://github.com/openpst/openpst",
        "name":    "openpst",
        "desc":    "Open source QPST alternative — EFS read/write, NV items",
        "install": None,
        "bins":    [],
        "chip":    "Qualcomm",
    },
    {
        "url":     "https://github.com/forth32/qpst-linux",
        "name":    "qpst-linux",
        "desc":    "Linux QPST NV item read/write tool",
        "install": "make 2>/dev/null || true",
        "bins":    [],
        "chip":    "Qualcomm",
    },
    {
        "url":     "https://github.com/JohnBel/EfsTools",
        "name":    "EfsTools",
        "desc":    "Cross-platform Qualcomm EFS explorer (.NET)",
        "install": None,
        "bins":    [],
        "chip":    "Qualcomm",
    },
]

# Standalone binary downloads
BINARY_DOWNLOADS = [
    {
        "name":    "apktool",
        "url":     "https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/linux/apktool",
        "jar_url": "https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar",
        "dest":    "/usr/local/bin/apktool",
        "jar_dest":"/usr/local/lib/apktool.jar",
        "wrapper": True,
    },
    {
        "name":    "jadx",
        "url":     "https://github.com/skylot/jadx/releases/download/v1.5.0/jadx-1.5.0.zip",
        "dest":    "/opt/jadx",
        "zip":     True,
        "bin_src": "/opt/jadx/bin/jadx",
        "bin_dst": "/usr/local/bin/jadx",
    },
]

# udev rules for MTK + Unisoc + generic Android
UDEV_RULES = """\
# WatchROM — Android Device USB Rules
# MediaTek
SUBSYSTEM=="usb", ATTR{idVendor}=="0e8d", MODE="0666", GROUP="plugdev", TAG+="uaccess"
# Unisoc / Spreadtrum
SUBSYSTEM=="usb", ATTR{idVendor}=="1782", MODE="0666", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="04e8", MODE="0666", GROUP="plugdev", TAG+="uaccess"
# Google ADB/Fastboot
SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", MODE="0666", GROUP="plugdev", TAG+="uaccess"
# Qualcomm EDL
SUBSYSTEM=="usb", ATTR{idVendor}=="05c6", MODE="0666", GROUP="plugdev", TAG+="uaccess"
# Xiaomi
SUBSYSTEM=="usb", ATTR{idVendor}=="2717", MODE="0666", GROUP="plugdev", TAG+="uaccess"
# Samsung
SUBSYSTEM=="usb", ATTR{idVendor}=="04e8", MODE="0666", GROUP="plugdev", TAG+="uaccess"
# OnePlus
SUBSYSTEM=="usb", ATTR{idVendor}=="2a70", MODE="0666", GROUP="plugdev", TAG+="uaccess"
# Huawei
SUBSYSTEM=="usb", ATTR{idVendor}=="12d1", MODE="0666", GROUP="plugdev", TAG+="uaccess"
# LG
SUBSYSTEM=="usb", ATTR{idVendor}=="1004", MODE="0666", GROUP="plugdev", TAG+="uaccess"
# HTC
SUBSYSTEM=="usb", ATTR{idVendor}=="0bb4", MODE="0666", GROUP="plugdev", TAG+="uaccess"
# Motorola
SUBSYSTEM=="usb", ATTR{idVendor}=="22b8", MODE="0666", GROUP="plugdev", TAG+="uaccess"
# Sony
SUBSYSTEM=="usb", ATTR{idVendor}=="0fce", MODE="0666", GROUP="plugdev", TAG+="uaccess"
# OPPO / Realme
SUBSYSTEM=="usb", ATTR{idVendor}=="22d9", MODE="0666", GROUP="plugdev", TAG+="uaccess"
# Vivo
SUBSYSTEM=="usb", ATTR{idVendor}=="2d95", MODE="0666", GROUP="plugdev", TAG+="uaccess"
"""


# ═══════════════════════════════════════════════════════════════════════════════
# INSTALL FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def install_apt_packages(status: dict) -> dict:
    title("System Packages (apt)")
    if status.get("apt_done"):
        ok("apt packages already installed — skipping")
        return status

    step("Updating apt cache...")
    rc, _, _ = run(["sudo", "apt-get", "update", "-qq"], timeout=120)
    print(f"{G}OK{NC}" if rc == 0 else f"{Y}warn{NC}")

    failed = []
    for pkg in APT_PACKAGES:
        step(f"Installing {pkg}...")
        rc, _, err = run(
            ["sudo", "apt-get", "install", "-y", "-qq", pkg],
            timeout=120
        )
        if rc == 0:
            print(f"{G}✓{NC}")
        else:
            print(f"{Y}skip{NC}")
            failed.append(pkg)
            info(f"  (may be unavailable on this distro)")

    if failed:
        warn(f"Could not install via apt: {', '.join(failed)}")
    else:
        ok("All apt packages installed")

    status["apt_done"] = True
    return status


def install_pip_packages(status: dict) -> dict:
    title("Python Packages (pip)")
    if status.get("pip_done"):
        ok("pip packages already installed — skipping")
        return status

    for pkg in PIP_PACKAGES:
        step(f"pip install {pkg}...")
        rc, _, _ = run(
            [sys.executable, "-m", "pip", "install", "--break-system-packages",
             "-q", pkg],
            timeout=120
        )
        if rc != 0:
            # Try without --break-system-packages
            rc, _, _ = run(
                [sys.executable, "-m", "pip", "install", "-q", pkg],
                timeout=120
            )
        print(f"{G}✓{NC}" if rc == 0 else f"{Y}skip{NC}")

    status["pip_done"] = True
    return status


def install_binary_tools(status: dict) -> dict:
    title("Standalone Binary Tools")

    # apktool
    if not shutil.which("apktool"):
        step("Installing apktool...")
        try:
            import urllib.request
            jar_path  = Path("/usr/local/lib/apktool.jar")
            wrap_path = Path("/usr/local/bin/apktool")

            urllib.request.urlretrieve(
                "https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar",
                str(jar_path)
            )
            wrap_path.write_text(
                "#!/bin/bash\nexec java -jar /usr/local/lib/apktool.jar \"$@\"\n"
            )
            os.chmod(wrap_path, 0o755)
            print(f"{G}✓{NC}")
        except Exception as e:
            print(f"{Y}skip ({e}){NC}")
    else:
        ok(f"apktool already available: {shutil.which('apktool')}")

    # jadx
    if not shutil.which("jadx"):
        step("Installing jadx 1.5.0...")
        try:
            import urllib.request, zipfile, io
            url  = "https://github.com/skylot/jadx/releases/download/v1.5.0/jadx-1.5.0.zip"
            dest = Path("/opt/jadx")
            dest.mkdir(parents=True, exist_ok=True)
            data = urllib.request.urlopen(url, timeout=60).read()
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                z.extractall(str(dest))
            jadx_bin = dest / "bin" / "jadx"
            if jadx_bin.exists():
                os.chmod(jadx_bin, 0o755)
                link = Path("/usr/local/bin/jadx")
                if link.exists(): link.unlink()
                link.symlink_to(jadx_bin)
                print(f"{G}✓{NC}")
            else:
                print(f"{Y}skip (bin not found in zip){NC}")
        except Exception as e:
            print(f"{Y}skip ({e}){NC}")
    else:
        ok(f"jadx already available")

    # zipalign (from android build tools)
    if not shutil.which("zipalign"):
        step("Looking for zipalign in SDK paths...")
        sdk_root = os.environ.get("ANDROID_HOME",
                    os.path.expanduser("~/Android/Sdk"))
        found = list(Path(sdk_root).glob("build-tools/*/zipalign")) if Path(sdk_root).exists() else []
        if found:
            os.chmod(found[-1], 0o755)
            link = Path("/usr/local/bin/zipalign")
            if not link.exists():
                link.symlink_to(found[-1])
            print(f"{G}✓{NC}")
        else:
            print(f"{DIM}not found in SDK{NC}")

    # apksigner
    if not shutil.which("apksigner"):
        sdk_root = os.environ.get("ANDROID_HOME",
                    os.path.expanduser("~/Android/Sdk"))
        found = list(Path(sdk_root).glob("build-tools/*/apksigner")) if Path(sdk_root).exists() else []
        if found:
            link = Path("/usr/local/bin/apksigner")
            if not link.exists():
                link.symlink_to(found[-1])
            ok("apksigner linked from SDK")

    return status


def clone_github_repos(status: dict) -> dict:
    title(f"GitHub Repositories → {REPOS_DIR}")
    REPOS_DIR.mkdir(parents=True, exist_ok=True)

    cloned = status.get("cloned_repos", [])

    for repo in GITHUB_REPOS:
        name     = repo["name"]
        url      = repo["url"]
        desc     = repo["desc"]
        dest     = REPOS_DIR / name
        install  = repo.get("install")
        bins     = repo.get("bins", [])

        step(f"[{repo['chip']}] {name} — {desc}...")

        if name in cloned and dest.exists():
            print(f"{DIM}already cloned{NC}")
            continue

        # Determine clone strategy: pinned tag > pinned commit > latest
        from core.registry import PINNED_DEPS
        pin = PINNED_DEPS.get("git", {}).get(name, {})
        tag    = pin.get("tag")
        commit = pin.get("commit")

        if tag:
            clone_cmd = ["git", "clone", "--depth=1", "--quiet",
                         "--branch", tag, url, str(dest)]
        else:
            clone_cmd = ["git", "clone", "--depth=1", "--quiet", url, str(dest)]

        rc, _, err = run(clone_cmd, timeout=180)

        # If tag clone failed, fall back to latest
        if rc != 0 and tag:
            rc, _, err = run(
                ["git", "clone", "--depth=1", "--quiet", url, str(dest)],
                timeout=180
            )

        # Checkout specific commit if pinned
        if rc == 0 and commit and dest.exists():
            run(["git", "-C", str(dest), "checkout", commit, "--quiet"],
                check=False, timeout=30)
        if rc != 0:
            if dest.exists() and any(dest.iterdir()):
                print(f"{DIM}already exists{NC}")
            else:
                print(f"{Y}failed — offline?{NC}")
            continue

        print(f"{G}✓ cloned{NC}")
        cloned.append(name)

        # Run install command
        if install:
            step(f"  Installing {name} dependencies...")
            rc2, _, _ = run(
                install, capture=True, timeout=300, cwd=str(dest)
            )
            print(f"{G}OK{NC}" if rc2 == 0 else f"{Y}partial{NC}")

        # Link binaries
        for bin_rel in bins:
            bin_path = dest / bin_rel if not bin_rel.startswith("/") else Path(bin_rel)
            if bin_path.exists():
                link_name = bin_path.name
                link_dest = Path("/usr/local/bin") / link_name
                try:
                    if link_dest.exists() or link_dest.is_symlink():
                        link_dest.unlink()
                    link_dest.symlink_to(bin_path.resolve())
                    os.chmod(bin_path, 0o755)
                    info(f"  → linked {link_name} to /usr/local/bin/")
                except Exception:
                    pass

    status["cloned_repos"] = cloned
    return status


def setup_udev(status: dict) -> dict:
    title("udev Rules (USB device permissions)")
    if status.get("udev_done"):
        ok("udev rules already installed")
        return status

    rules_path = Path("/etc/udev/rules.d/99-watchrom.rules")
    try:
        tmp = Path("/tmp/watchrom_udev.rules")
        tmp.write_text(UDEV_RULES)
        rc, _, _ = run(["sudo", "cp", str(tmp), str(rules_path)])
        if rc == 0:
            run(["sudo", "udevadm", "control", "--reload-rules"])
            run(["sudo", "udevadm", "trigger"])
            # Add current user to plugdev group
            user = os.environ.get("USER", os.environ.get("USERNAME", ""))
            if user:
                run(["sudo", "usermod", "-aG", "plugdev", user])
            ok(f"udev rules installed → {rules_path}")
            ok("User added to plugdev group (re-login may be needed)")
        else:
            warn("Could not write udev rules (no sudo?)")
    except Exception as e:
        warn(f"udev setup: {e}")

    status["udev_done"] = True
    return status


def install_watchrom_cli(status: dict) -> dict:
    title("WatchROM CLI Registration")
    launcher = Path("/usr/local/bin/watchrom")
    main_py  = TOOLKIT_ROOT / "main.py"

    script = (
        "#!/usr/bin/env bash\n"
        f"exec {sys.executable} {main_py} \"$@\"\n"
    )
    try:
        tmp = Path("/tmp/watchrom_launcher")
        tmp.write_text(script)
        os.chmod(tmp, 0o755)
        rc, _, _ = run(["sudo", "cp", str(tmp), str(launcher)])
        if rc == 0:
            ok(f"watchrom CLI → {launcher}")
        else:
            # Try without sudo (user bin)
            user_bin = Path.home() / ".local/bin"
            user_bin.mkdir(parents=True, exist_ok=True)
            (user_bin / "watchrom").write_text(script)
            os.chmod(user_bin / "watchrom", 0o755)
            ok(f"watchrom CLI → {user_bin}/watchrom")
    except Exception as e:
        warn(f"CLI registration: {e}")

    # Also make main.py itself executable
    try:
        os.chmod(main_py, 0o755)
    except Exception:
        pass

    status["cli_done"] = True
    return status


def verify_tools() -> dict:
    title("Tool Availability Check")
    tools = {
        "adb":          ("Android Debug Bridge",     "sudo apt install adb"),
        "fastboot":     ("Android Fastboot",         "sudo apt install fastboot"),
        "java":         ("Java Runtime",             "sudo apt install default-jdk"),
        "apktool":      ("APK decode/rebuild",       "watchrom installs this"),
        "jadx":         ("Java decompiler",          "watchrom installs this"),
        "dtc":          ("Device tree compiler",     "sudo apt install device-tree-compiler"),
        "openssl":      ("Crypto / key generation",  "sudo apt install openssl"),
        "simg2img":     ("Sparse image converter",   "sudo apt install android-sdk-libsparse-utils"),
        "debugfs":      ("ext4 inspection",          "sudo apt install e2fsprogs"),
        "git":          ("Version control",          "sudo apt install git"),
        "avbtool":      ("AVB signing tool",         "pip install avbtool"),
        "mkbootimg":    ("Boot image builder",       "sudo apt install mkbootimg"),
        "python3":      ("Python 3",                 "sudo apt install python3"),
    }
    results = {}
    for tool, (desc, hint) in tools.items():
        path = shutil.which(tool)
        if path:
            ok(f"{tool:16s} {DIM}{desc}{NC}")
            results[tool] = True
        else:
            warn(f"{tool:16s} {DIM}NOT FOUND — {hint}{NC}")
            results[tool] = False

    # mtkclient check
    mtk_path = REPOS_DIR / "mtkclient" / "mtk"
    if mtk_path.exists() or shutil.which("mtk"):
        ok(f"{'mtkclient':16s} {DIM}MTK BROM tool{NC}")
        results["mtkclient"] = True
    else:
        warn(f"{'mtkclient':16s} {DIM}Not available (clone watchrom_repos/mtkclient){NC}")
        results["mtkclient"] = False

    return results


def print_summary(tool_status: dict, status: dict):
    title("Setup Complete")
    ready    = sum(1 for v in tool_status.values() if v)
    not_ready= sum(1 for v in tool_status.values() if not v)
    cloned   = len(status.get("cloned_repos", []))

    print(f"\n  {G}Tools ready  : {ready}{NC}")
    if not_ready:
        print(f"  {Y}Tools missing: {not_ready} (optional — core functions still work){NC}")
    print(f"  {C}GitHub repos : {cloned} cloned → {REPOS_DIR}{NC}")

    print(f"""
  {BOLD}{G}╔══════════════════════════════════════════════════╗{NC}
  {BOLD}{G}║  WatchROM is ready!                              ║{NC}
  {BOLD}{G}║                                                  ║{NC}
  {BOLD}{G}║  Run:  watchrom                                  ║{NC}
  {BOLD}{G}║  OR:   python3 {str(TOOLKIT_ROOT)}/launcher.py  ║{NC}
  {BOLD}{G}╚══════════════════════════════════════════════════╝{NC}

  {DIM}Connect your device and run: watchrom{NC}
  {DIM}The tool will auto-scan and offer to backup before anything else.{NC}
""")


def main():
    print(BANNER)

    # Check if re-run or first run
    status = load_status()
    first_run = not status.get("setup_complete", False)

    if first_run:
        print(f"  {W}First-run setup detected. Installing all dependencies...{NC}\n")
    else:
        print(f"  {DIM}Re-running setup (use --force to reinstall everything){NC}")
        if "--force" not in sys.argv:
            # Just show verify and exit
            tools = verify_tools()
            print_summary(tools, status)
            return

    # Run all installers
    try:
        status = install_apt_packages(status)
        save_status(status)

        status = install_pip_packages(status)
        save_status(status)

        status = install_binary_tools(status)
        save_status(status)

        status = clone_github_repos(status)
        save_status(status)

        status = setup_udev(status)
        save_status(status)

        status = install_watchrom_cli(status)
        save_status(status)

        tool_status = verify_tools()
        status["setup_complete"] = True
        status["setup_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_status(status)

        print_summary(tool_status, status)

    except KeyboardInterrupt:
        print(f"\n\n  {Y}Setup interrupted. Run again to continue.{NC}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n  {R}Setup error: {e}{NC}")
        import traceback; traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
