> # ⚠️⚠️⚠️ WARNING! USE AT YOUR OWN RISK! ⚠️⚠️⚠️
>
> **WatchROM modifies device partitions, boot images, modem configurations,
> and low-level system properties. Incorrect use can permanently brick your
> device, corrupt IMEI/calibration data, or trigger anti-rollback fuses.**
>
> - **You are responsible for your own device.**
> - **Always create a full backup before making ANY changes.**
> - **Some operations (flashing bootloader/preloader/persist/fsg partitions)
>   are blocked by default and require `--force` — you have been warned.**
> - **This tool is for educational and development purposes only.**
> - **Do NOT flash partitions you don't understand.**
>
> All band configuration changes are **fully reversible**. WatchROM automatically
> backs up your current config before every write. What WatchROM never touches:
> IMEI/MEID identifiers (illegal), RF calibration data (brick risk), carrier
> lock status, SPC/MSL codes.

# WatchROM — One Kit to Rule Them All
### Android ROM Engineering Suite

**137 commands · 29 modules · 6 chipset vendors · Android devices**

---

## Compatibility & Known Limitations

| Capability | Status | Details |
|------------|--------|---------|
| MTK chips (MT6739–MT6983) | ✅ Full | BROM, identify, dump, partitions, band config |
| Unisoc chips (SC9832E–T820) | ✅ Full | FDL, identify, dump, partitions, band config |
| Rockchip chips (PX30–RK3588) | ✅ Full | MaskROM, identify, dump, partition table |
| Allwinner chips (A10–H700) | ✅ Full | FEL, identify, dump, SID read, partition table |
| Realtek chips (RTD1073–RTD1619B) | ✅ Full | Rescue mode, identify, dump, partition table |
| Qualcomm Snapdragon (SD429–SM8650) | ✅ Full | EDL, EFS, band config, AT commands, DIAG, band presets |
| Boot image unpack/repack (v0/v1/v2/v3/v4) | ✅ Full | kernel + ramdisk + dtb + vendor_boot |
| Magisk root + WearOS setup | ✅ Tested | Auto-detect, patch, flash, verify |
| AVB disable (blank vbmeta) | ✅ Tested | Backup + flash via fastboot |
| ADB/Fastboot flashing (safe partitions) | ✅ Guarded | Danger-zone partitions blocked by default |
| Full device backup (all partitions) | ✅ Tested | Manifest with SHA256 |
| **GKI/Android 12+ (v3/v4 boot headers + vendor_boot)** | ✅ Full | Vendor_boot header parser (v3=72B, v4=100B), `unpack-vendor`/`repack-vendor` for ramdisk + DTB + vendor cmdline. Kernel extracted from boot.img, ramdisk from vendor_boot.img |
| **Samsung devices (Exynos/Snapdragon)** | ✅ Full | 13 Exynos chips supported (2400–7420), Heimdall flash, Download Mode helpers, Samsung KVB detection in pipelines + Knox handling guide |
| **Dynamic partitions (super)** | ⚠️ Read-only | Can be dumped but not flash-merged |
| **IMEI/MEID modification** | ❌ By design | Illegal in most countries |
| **RF calibration NV items** | ❌ By design | Factory-set, irreversible |
| **Carrier lock bypass / SIM unlock** | ❌ By design | Not supported |

---

## Supported Chipsets

**MediaTek (MTK):** MT6739/W · MT6761/W · MT6762 · MT6763 · MT6765 · MT6768 · MT6769 · MT6771 · MT6785 · MT6789 · MT6833 · MT6853 · MT6877 · MT6879 · MT6886 · MT6893 · MT6895 · MT6983 · MT2601 · MT2625 · MT6580W

**Unisoc / Spreadtrum:** SC9832E · SC9863 · SC9863A · SL8541E · SC8541E · SC7731E · SC9820E · UIS8581A · UIS8520E · T310 · T606 · T612 · T616 · T618 · T760 · T820

**Rockchip:** PX30 · RK3126 · RK3128 · RK3188 · RK3228 · RK3229 · RK3288 · RK3308 · RK3318 · RK3326 · RK3328 · RK3399 · RK3399Pro · RK3566 · RK3568 · RK3562 · RK3576 · RK3588 · RK3588S · PX5 · PX6

**Allwinner:** A10 · A13 · A20 · A23 · A31 · A33 · A50 · A64 · A80 · A83T · A100 · A133 · H2+ · H3 · H5 · H6 · H616 · H618 · H700 · T3 · T507 · T7 · R818 · R528

**Realtek:** RTD1073 · RTD1185 · RTD1195 · RTD1295 · RTD1296 · RTD1312 · RTD1315 · RTD1319 · RTD1395 · RTD1619 · RTD1619B

**Qualcomm Snapdragon (38 chips):** SM8650 (Gen 3) · SM8550 (Gen 2) · SM8475/SM8450 (Gen 1) · SM8350 (888) · SM8250 (865) · SM8150 (855) · SDM845 · SDM835 · SM7675/7550/7475/7450 · SM7350 (778G) · SM7250 (765G) · SM7150 (730G) · SDM710 · SM6375 (695) · SM6350 (690) · SM6225 (680) · SDM660 · SM4350 (480) · SDM450/439/429 · SM7580 (7c+) · SC7280/SC7180 (7c)

---

## Installation

```bash
git clone https://github.com/yourname/watchrom
cd watchrom
bash install.sh
```

`install.sh` auto-installs: apt packages (adb, fastboot, apktool, dtc, sunxi-tools, rkdeveloptool, etc.), Python packages (rich, click, avbtool, protobuf, etc.), clones 20+ GitHub repos into `../watchrom_repos/`, sets udev USB permissions for all vendors, and registers `watchrom` as a system command.

---

## Usage

```bash
watchrom          # Interactive guided TUI menu (recommended)
watchrom --help   # Full CLI reference
```

On first launch, WatchROM auto-detects the connected device, offers a full backup before any modifications, and drops you into the guided interactive menu.

---

## Module Reference

| Module | Commands | What it does |
|--------|----------|-------------|
| `device` | 3 | Auto-detect chipset, reboot modes |
| `dump` / `flash` | 2 | Partition read/write |
| `bootimg` | 6 | Unpack/repack boot.img + vendor_boot.img, kernel cmdline patch, GKI vendor_boot ramdisk extract |
| `root` | 2 | Magisk root via boot.img patch |
| `wearos` | 6 | WearOS compatibility on full Android watches |
| `sysimg` | 7 | Extract/repack/edit system.img, vendor.img |
| `avb` | 3 | Disable AVB, blank vbmeta, re-sign |
| `ota` | 3 | Extract payload.bin, create OTA zips |
| `rom` | 3 | MTK scatter, Unisoc XML, GSI flash |
| `apk` | 4 | decompile (smali+Java), recompile, sign |
| `twrp` | 1 | TWRP device tree + build script |
| `devtree` | 1 | Android device tree scaffold |
| `dtb` | 5 | DTB/DTBO extract, decompile/compile, patch |
| `props` | 5 | Live setprop, build.prop edit, presets, fingerprint spoof |
| `sepolicy` | 4 | Pull policy, audit2allow, set permissive |
| `magisk` | 5 | Create/pack/install modules, prop-module builder |
| `keys` | 2 | Full AOSP signing key set (platform/AVB/APK) |
| `analyze` | 5 | Entropy, strings, format detect, image diff, scan |
| `diag` | 4 | Full report, logcat, bugreport, partition table |
| `network` | 4 | WiFi/BT/RIL, packet capture, hosts editor |
| `backup` | 4 | Full partition backup, restore, app backup |
| `mtk` | 4 | BROM mode, identify, chip list, BROM dump |
| `unisoc` | 4 | FDL mode, identify, chip list, PAC info |
| `chips` | 1 | All watch-class chips across all vendors |
| `rockchip` | 6 | MaskROM mode, identify, list, flash, dump, partition table |
| `allwinner` | 6 | FEL mode, identify, list, flash, SID dump, partition table |
| `realtek` | 5 | Rescue mode, identify, list, rescue extract, partition table |
| `qualcomm` | 14 | EDL, EFS backup/restore, band-set, AT commands, DIAG mode |
| `bands` | 11 | Universal carrier profiles, hex mask verify/derive, MTK Engineering Mode |
| `pipeline` | 9 | Automated workflows (root-device, backup, flash-rom, wearos-setup, bands) |
| `adb` | 6 | shell, push, pull, install, logcat, devices |

---

## Chipset-Specific Workflows

### MTK (SP Flash Tool)
```
watchrom mtk identify          # detect chip + props
watchrom mtk download          # BROM mode guide
watchrom dump --all            # dump all partitions
watchrom rom build --vendor mtk --parts-dir output/<serial>/partitions/
```

### Unisoc (UpgradeDownload)
```
watchrom unisoc identify       # detect chip + props
watchrom unisoc download       # FDL mode guide
watchrom dump --all
watchrom rom build --vendor unisoc --parts-dir output/<serial>/partitions/
```

### Rockchip (rkdeveloptool)
```
watchrom rockchip identify     # detect chip (RK3566, RK3588, etc.)
watchrom rockchip download     # MaskROM entry guide
watchrom rockchip list         # browse all supported chips
watchrom rockchip dump boot    # dump boot partition
watchrom rockchip flash update.img
```

### Allwinner (sunxi-fel / PhoenixSuit)
```
watchrom allwinner identify    # detect chip (H616, A64, R818, etc.)
watchrom allwinner download    # FEL mode entry guide
watchrom allwinner list        # browse all supported chips
watchrom allwinner dump-sid    # read SoC unique ID
watchrom allwinner flash system.img --method sunxi-fel
```

### Realtek (Rescue mode)
```
watchrom realtek identify      # detect chip (RTD1619, RTD1295, etc.)
watchrom realtek download      # rescue mode guide
watchrom realtek list          # browse supported chips
watchrom realtek extract-rescue install.img
```

---

## WearOS on Android Watches

```bash
# Step 1 — Root
watchrom root patch

# Step 2 — Configure WearOS compatibility (systemless Magisk module)
watchrom wearos setup --method magisk

# Step 3 — Install Magisk module + reboot
watchrom magisk install output/magisk_modules/watchrom_wearos.zip
watchrom adb shell reboot

# Step 4 — Install WearOS APKs (get from APKMirror)
watchrom wearos install-apks --apk-dir ~/wear_apks/

# Full guide
watchrom wearos companion-guide
```

---

## Download Mode Quick Reference

| Vendor | Mode | Entry | USB VID |
|--------|------|-------|---------|
| MTK | BROM | Power off + Vol− + USB | 0x0E8D |
| Unisoc | FDL | Power off + Vol− + USB | 0x1782 |
| Rockchip | MaskROM | Recovery button + USB, or short MaskROM pads | 0x2207 |
| Allwinner | FEL | FEL button + USB, or blank SD card boot | 0x1F3A |
| Realtek | Rescue | Rescue button + power on | 0x0BDA |
| Qualcomm | EDL (9008) | Vol+ + Vol− + USB, or `adb reboot edl` | 0x05C6 |

---

## Band Configuration — All Vendors

WatchROM handles LTE/5G band configuration on any Android device regardless of
chipset. All changes are fully reversible and backup is created automatically before
every write.

### How It Works Per Vendor

| Vendor | Write Method | Interface | Root Needed? |
|--------|-------------|-----------|-------------|
| Qualcomm | EFS NV item write | ADB root | Yes (EFS method) |
| Qualcomm | AT+QCFG command | AT port | Sometimes |
| MTK | AT+ERAT + AT+EPBSE | AT port /dev/ttyC0 | Sometimes |
| Unisoc | AT+ERAT + AT+EPBSE | AT port /dev/stty0 | Sometimes |
| Rockchip/Allwinner | AT commands (external modem) | /dev/ttyUSB* | Sometimes |

### Qualcomm-Specific Details

**Modem Reference**: X75 (Gen3, 10Gbps) · X70 (Gen2) · X65 (Gen1/888+) · X62 (7-series) · X60 (888) · X55 (865, first 5G) · X24/X20/X16/X15/X12

**Safety workflow** (always follow this order):
```bash
# 1. BACKUP FIRST — always before any band changes
watchrom qualcomm efs-backup

# 2. Check current network status
watchrom qualcomm network-status
watchrom qualcomm bands-info

# 3. Apply desired band config
watchrom qualcomm band-set --preset us_tmobile

# 4. If something goes wrong — restore from backup
watchrom qualcomm efs-restore output/qualcomm_backups/<device>/<timestamp>/
```

**AT commands** (no root, read-only on most devices):
```bash
watchrom qualcomm at-cmd --cmd "AT+QNWINFO"    # Current band + operator
watchrom qualcomm at-cmd --cmd "AT+CSQ"         # Signal strength (RSSI)
watchrom qualcomm at-cmd --cmd "AT+COPS?"       # Current operator
watchrom qualcomm at-cmd --cmd "AT+CEREG?"      # LTE registration
watchrom qualcomm at-cmd --cmd "AT+C5GREG?"     # 5G NR registration
watchrom qualcomm at-cmd --cmd 'AT+QCFG="band"' # Current band config
```

**EDL and DIAG modes**:
```bash
watchrom qualcomm edl --check        # Check if EDL device is connected
watchrom qualcomm edl --enter        # Reboot into EDL
watchrom qualcomm diag-enable        # Enable DIAG mode for QPST/QFIL
```

**External 5G modem note**: On devices with a separate 5G modem chip (e.g. SM8250 + X55), band configuration targets the same EFS NV items — the modem firmware handles routing transparently.

### Quick Start

```bash
# See your current bands + carrier
watchrom bands status

# Apply a carrier preset
watchrom bands apply --carrier verizon
watchrom bands apply --carrier tmobile
watchrom bands apply --carrier eu_generic

# Restore all bands (undo any changes)
watchrom bands apply --carrier global_roaming

# Verify hex masks match declared band lists (detect stale masks)
watchrom bands verify-masks

# Apply a carrier preset with runtime mask derivation (bypasses stored hex)
watchrom bands apply --carrier verizon --derive-masks

# Derive hex masks manually from band lists (useful for custom carrier profiles)
python3 -c "from modules.qualcomm import build_lte_bitmask; l,h=build_lte_bitmask([2,4,5,13,48,66]); print(f'low=0x{l:016X} high=0x{h:016X}')"
```

---

## Verizon Wireless Reference

| Band | Frequency | Type | Notes |
|------|-----------|------|-------|
| **B13** ★ | 700 MHz Block C | Primary | Verizon signature band — always needed |
| B2 | 1900 MHz PCS | Core | Primary data/voice |
| B4 | 1700/2100 MHz AWS-1 | Core | Main LTE capacity layer |
| B5 | 850 MHz CLR | Coverage | Rural and building penetration |
| B48 | 3500 MHz CBRS | Capacity | Enterprise/private networks |
| B66 | 1700/2100 MHz AWS-3 | Capacity | Extended capacity |
| **n77** ★ | 3.7 GHz C-band | Primary 5G | Verizon 5G Ultra Wideband |
| n260 | 39 GHz mmWave | Ultra Wideband | Dense urban only |
| n261 | 28 GHz mmWave | Ultra Wideband | Dense urban only |

★ B13 is mandatory for Verizon — without it your device won't connect.
★ n77 C-band is Verizon's primary 5G spectrum.

### Hex Masks (for manual entry in QPST/Engineering Mode)

```
LTE low  (B1-B64) : 0x0000000008880200   covers B2, B4, B5, B13
LTE high (B65+)   : 0x0000000000020001   covers B48, B66
NR mask            : 0x0000000000000118   covers n5, n48, n66, n77
```

---

## All Supported Carrier Profiles

### United States
| Carrier | LTE Bands | 5G Bands | Command |
|---------|-----------|----------|---------|
| Verizon | B2/4/5/13/48/66 | n5/n48/n66/n77/n260/n261 | `--carrier verizon` |
| T-Mobile | B2/4/5/12/25/26/41/66/71 | n2/n25/n41/n71 + n258/n260/n261 mmWave | `--carrier tmobile` |
| AT&T | B2/4/5/7/14/17/29/30/66 | n77/n78 | `--carrier att` |
| FirstNet (AT&T) | B2/4/14/17/29/30 | n77 | `--carrier firstnet` |
| Dish/Boost | B2/26/41/66 | n66/n70 | `--carrier dish_boost` |
| CBRS (private) | B48 | n48 | `--carrier cbrs` |

### International
| Region/Carrier | Primary Bands | 5G | Command |
|----------------|--------------|-----|---------|
| Europe (generic) | B1/3/5/7/8/20/28 | n1/3/7/28/78 | `--carrier eu_generic` |
| UK Vodafone | B1/2/3/7/8/20/28 | n1/3/28/78 | `--carrier uk_vodafone` |
| UK EE | B1/3/7/8/20/28/32 | n1/3/78 | `--carrier uk_ee` |
| Australia Telstra | B1/3/5/7/28/40 | n28/n78 | `--carrier australia_telstra` |
| Japan NTT Docomo | B1/3/19/21/28/42 | n77/78/79 + mmWave | `--carrier japan_docomo` |
| South Korea SKT | B1/3/5/7/8/42 | n78 + mmWave | `--carrier korea_skt` |
| India Jio | B3/5/40 | n28/77/78 | `--carrier india_jio` |
| China Telecom | B1/3/5/18/40/41 | n41/78/79 | `--carrier china_telecom` |
| Canada Rogers | B2/4/5/7/12/17/66 | n66/77 | `--carrier canada_rogers` |
| **Global (all)** | All bands | All bands | `--carrier global_roaming` |

---

## Safety Notes

### Danger-Zone Partitions
WatchROM blocks flashing of **60+ partitions** that can **brick your device**:
- **Bootloaders**: preloader, lk, uboot, abl, xbl, spl — brick if wrong
- **TrustZone**: tee, trust, tz, hyp — boot security, brick if corrupted
- **Calibration**: persist, nvram, fsg, modemst — IMEI/MAC/signal loss (may be permanent)
- **Attestation**: keymaster, cmnlib, keystore — kills biometrics/DRM
- **Fuses**: otp — one-time programmable, permanent
- **Boot control**: misc, frp — boot loops if corrupted

Use `--force` only if you have a backup AND know why you're doing it.

### Battery Requirement
All flash operations require **≥30% battery** to prevent bricking from power loss during write.
The root-device and flash-rom pipelines automatically check this before any write operation
using `check_battery_level()` (dumpsys battery + sysfs fallback).

---

## License
MIT — For personal device modification and ROM development.
