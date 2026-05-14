"""
Shared utility functions for WatchROM toolkit
Supports: MTK, Unisoc, Rockchip, Allwinner, Realtek, + any Android
"""
import os, subprocess, shutil, hashlib, struct, time, re
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

WORKSPACE  = Path(os.path.dirname(__file__)).parent / "workspace"
OUTPUT_DIR = Path(os.path.dirname(__file__)).parent / "output"
KEYS_DIR   = Path(os.path.dirname(__file__)).parent / "keys"
TOOLS_DIR  = Path(os.path.dirname(__file__)).parent / "tools"
REPOS_DIR  = Path(os.path.dirname(__file__)).parent.parent / "watchrom_repos"

for d in (WORKSPACE, OUTPUT_DIR, KEYS_DIR, TOOLS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── Shell ──────────────────────────────────────────────────────────────────────
def run(cmd, capture=True, check=True, cwd=None, timeout=120):
    if isinstance(cmd, str):
        cmd = cmd.split()
    result = subprocess.run(cmd, capture_output=capture, text=True, cwd=cwd, timeout=timeout)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stdout}\n{result.stderr}")
    return result.returncode, result.stdout, result.stderr

def run_adb(args, serial=None, check=True, timeout=60):
    cmd = ["adb"] + (["-s", serial] if serial else []) + args
    return run(cmd, check=check, timeout=timeout)

def run_fastboot(args, serial=None, check=True, timeout=120):
    cmd = ["fastboot"] + (["-s", serial] if serial else []) + args
    return run(cmd, check=check, timeout=timeout)

def require_tool(name):
    path = shutil.which(name)
    if not path:
        hints = {
            "adb":"sudo apt install adb", "fastboot":"sudo apt install fastboot",
            "apktool":"sudo apt install apktool", "jadx":"https://github.com/skylot/jadx",
            "avbtool":"pip install avbtool", "dtc":"sudo apt install device-tree-compiler",
            "sunxi-fel":"sudo apt install sunxi-tools",
            "rkdeveloptool":"sudo apt install rkdeveloptool",
        }
        raise FileNotFoundError(f"Tool not found: {name}\n→ {hints.get(name, 'Please install '+name)}")
    return path

def tool_available(name): return shutil.which(name) is not None

# ── File helpers ───────────────────────────────────────────────────────────────
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""): h.update(chunk)
    return h.hexdigest()

def file_size_mb(path): return Path(path).stat().st_size / (1024*1024)

def parse_android_image_header(path):
    with open(path, "rb") as f: data = f.read(1648)
    magic = data[:8]
    return {"magic": magic.decode("latin1", errors="replace"),
            "version": 1 if magic[:8] == b"ANDROID!" else 0,
            "size": file_size_mb(path), "sha256": sha256_file(path)}

# ── Device detection ───────────────────────────────────────────────────────────
def adb_devices():
    _, out, _ = run(["adb", "devices"], check=False)
    devices = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) == 2: devices.append((parts[0], parts[1]))
    return devices

def fastboot_devices():
    _, out, _ = run(["fastboot", "devices"], check=False)
    return [l.split()[0] for l in out.splitlines() if l.split()]

_GETPROP_RE = re.compile(r'^\[([^\]]*)\]:\s*\[(.*?)\]$')

def get_device_props(serial=None):
    _, out, _ = run_adb(["shell", "getprop"], serial=serial, check=False)
    props = {}
    for line in out.splitlines():
        m = _GETPROP_RE.match(line.strip())
        if m:
            props[m.group(1)] = m.group(2)
    return props

def wait_for_boot(serial=None, timeout=120, poll_interval=3):
    """
    Poll ADB until sys.boot_completed == 1.
    Returns True if device booted, False on timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        _, out, _ = run_adb(
            ["shell", "getprop sys.boot_completed"],
            serial=serial, check=False, timeout=10
        )
        if out.strip() == "1":
            return True
        time.sleep(poll_interval)
    return False


def wait_for_fastboot(serial=None, timeout=30, poll_interval=1):
    """
    Poll fastboot devices until a device appears.
    Returns serial if found, None on timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        devs = fastboot_devices()
        if serial and serial in devs:
            return serial
        if devs:
            return devs[0]
        time.sleep(poll_interval)
    return None


def detect_chipset_from_props(props: dict) -> tuple:
    """Detect chipset from Android device properties.
    Delegates to chipsets.py identify_chip_universal for single-source-of-truth.
    Returns (vendor, chip_key) tuple.
    """
    from modules.chipsets import identify_chip_universal
    platform = " ".join([
        props.get("ro.board.platform",""),
        props.get("ro.product.board",""),
        props.get("ro.hardware",""),
        props.get("ro.chip.id",""),
    ])
    result = identify_chip_universal(platform)
    return result.get("vendor", "unknown"), result.get("key", "unknown")

# ── Partition maps for all vendors ────────────────────────────────────────────
PARTITION_MAPS = {
    "unisoc":   ["boot","recovery","system","vendor","userdata","cache","persist",
                 "modem","dtbo","vbmeta","sml","tos","prodnv","misc","pm_sys",
                 "l_fixnv1","l_fixnv2"],
    "mtk":      ["boot","recovery","system","vendor","userdata","cache","persist",
                 "lk","preloader","tee1","tee2","logo","para","dtbo","vbmeta","frp"],
    "rockchip": ["loader","uboot","trust","boot","recovery","system","vendor",
                 "userdata","cache","misc","dtbo","vbmeta","persist","frp"],
    "allwinner":["bootloader","boot","recovery","system","vendor","userdata",
                 "cache","misc","dtbo","vbmeta","persist","env"],
    "realtek":  ["bootcode","rescue","hwsetting","factory","boot","recovery",
                 "system","vendor","userdata","cache","misc","vbmeta"],
    "qualcomm": ["abl","aop","apdp","bluetooth","boot","cache","cmnlib",
                 "cmnlib64","devcfg","dsp","featenabler","hyp","imagefv",
                 "keymaster","keystore","limits","logdump","logfs","mdtp",
                 "mdtpsecapp","misc","modem","msadp","persist","qupfw",
                 "recovery","rpm","sec","splash","storsec","system","tz",
                 "uefisecapp","userdata","vbmeta","vendor","xbl","xbl_config"],
    "unknown":  ["boot","recovery","system","vendor","userdata","cache","persist",
                 "dtbo","vbmeta","misc"],
}

def spinner(msg):
    return Progress(SpinnerColumn(), TextColumn(f"[cyan]{msg}"), transient=True)


def check_battery_level(serial: str = None, min_pct: int = 30) -> tuple:
    """Check device battery level via ADB.

    Returns (ok: bool, pct: int, message: str).
    ok=False if below min_pct or can't determine.
    """
    _, out, _ = run_adb(
        ["shell", "dumpsys battery 2>/dev/null | grep 'level:' | awk '{print $2}'"],
        serial=serial, check=False
    )
    level_str = out.strip()
    if level_str and level_str.isdigit():
        level = int(level_str)
        if level < min_pct:
            return (False, level,
                    f"Battery at {level}% — below {min_pct}% threshold. "
                    f"Charge device before flashing.")
        return (True, level, f"Battery at {level}% — OK")
    # Try sysfs fallback
    _, out, _ = run_adb(
        ["shell", "cat /sys/class/power_supply/*/capacity 2>/dev/null | head -1"],
        serial=serial, check=False
    )
    level_str = out.strip()
    if level_str and level_str.isdigit():
        level = int(level_str)
        if level < min_pct:
            return (False, level,
                    f"Battery at {level}% — below {min_pct}% threshold.")
        return (True, level, f"Battery at {level}% — OK")
    return (True, -1, "Could not determine battery level — proceeding anyway")
