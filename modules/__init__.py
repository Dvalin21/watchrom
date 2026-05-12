"""
Shared utility functions for WatchROM toolkit
Supports: MTK, Unisoc, Rockchip, Allwinner, Realtek, + any Android
"""
import os, subprocess, shutil, hashlib, struct, time
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

def get_device_props(serial=None):
    _, out, _ = run_adb(["shell", "getprop"], serial=serial, check=False)
    props = {}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("[") and "]: [" in line:
            key = line[1:line.index("]")]
            val = line[line.index("]: [")+4:-1]
            props[key] = val
    return props

# ── Universal chipset signatures (MTK + Unisoc + Rockchip + Allwinner + Realtek) ─
CHIPSET_SIGNATURES = {
    # Unisoc / Spreadtrum
    "SC9832E":["sc9832e","9832e","sp9832e"], "SC9863A":["sc9863a","9863a"],
    "SC9863":["sc9863"], "SL8541E":["sl8541e","8541e"], "SC8541E":["sc8541e"],
    "SC7731E":["sc7731e"], "UIS8581A":["uis8581a"], "UIS8520E":["uis8520e"],
    # MTK
    "MT6739":["mt6739","6739"], "MT6761":["mt6761","6761"], "MT6762":["mt6762"],
    "MT6765":["mt6765","6765"], "MT6768":["mt6768"], "MT6771":["mt6771"],
    "MT6785":["mt6785","helio g90"], "MT6789":["mt6789","helio g99"],
    "MT6833":["mt6833","dimensity 700"], "MT6853":["mt6853","dimensity 720"],
    "MT6877":["mt6877","dimensity 900"], "MT6893":["mt6893","dimensity 1200"],
    "MT6895":["mt6895","dimensity 8200"], "MT6983":["mt6983","dimensity 9000"],
    "MT2601":["mt2601"], "MT6580W":["mt6580"],
    # Rockchip
    "PX30":["px30"], "RK3126":["rk3126"], "RK3128":["rk3128"],
    "RK3288":["rk3288"], "RK3308":["rk3308"], "RK3318":["rk3318"],
    "RK3326":["rk3326"], "RK3328":["rk3328"], "RK3399":["rk3399"],
    "RK3566":["rk3566"], "RK3568":["rk3568"], "RK3576":["rk3576"],
    "RK3588":["rk3588"], "RK3588S":["rk3588s"], "PX5":["px5"], "PX6":["px6"],
    # Allwinner
    "A10":["a10","sun4i"], "A20":["a20","sun7i"], "A33":["a33"],
    "A64":["a64"], "A100":["a100"], "A133":["a133"],
    "H3":["h3"], "H5":["h5"], "H6":["h6"],
    "H616":["h616"], "H618":["h618"], "H700":["h700"],
    "R818":["r818"], "T507":["t507"],
    # Realtek
    "RTD1195":["rtd1195","1195"], "RTD1295":["rtd1295","1295"],
    "RTD1319":["rtd1319","1319"], "RTD1395":["rtd1395","1395"],
    "RTD1619":["rtd1619","1619"], "RTD1619B":["rtd1619b"],
    # Qualcomm Snapdragon
    "SM8650":["sm8650","8 gen 3"], "SM8550":["sm8550","8 gen 2"],
    "SM8475":["sm8475","8+ gen 1"],"SM8450":["sm8450","8 gen 1"],
    "SM8350":["sm8350","888","lahaina"], "SM8250":["sm8250","865","kona"],
    "SM8150":["sm8150","855","msmnile"], "SDM845":["sdm845","845"],
    "SDM835":["sdm835","835","msm8998"],
    "SM7550":["sm7550","7 gen 2"], "SM7450":["sm7450","7 gen 1"],
    "SM7350":["sm7350","778"],     "SM7250":["sm7250","765"],
    "SM7150":["sm7150","730"],     "SDM710":["sdm710","710"],
    "SM6375":["sm6375","695"],     "SM6350":["sm6350","690"],
    "SM6225":["sm6225","680"],     "SDM660":["sdm660","660"],
    "SM4350":["sm4350","480"],     "SDM450":["sdm450","450"],
}

def _vendor_from_chip(chip: str) -> str:
    uc = chip.upper()
    if uc.startswith(("SC","SL","UIS")): return "unisoc"
    if uc.startswith("MT"):              return "mtk"
    if uc.startswith(("RK","PX")):       return "rockchip"
    if uc.startswith("RTD"):             return "realtek"
    if uc.startswith(("SM","SDM","MSM","SA","SC7")): return "qualcomm"
    if uc[0] in "AHR" and len(uc) > 1:  return "allwinner"
    return "unknown"

def detect_chipset_from_props(props: dict) -> tuple:
    combined = " ".join([
        props.get("ro.board.platform",""),
        props.get("ro.product.board",""),
        props.get("ro.hardware",""),
        props.get("ro.chip.id",""),
    ]).lower()
    for chip, sigs in CHIPSET_SIGNATURES.items():
        for sig in sigs:
            if sig in combined:
                return _vendor_from_chip(chip), chip
    return "unknown", "unknown"

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
