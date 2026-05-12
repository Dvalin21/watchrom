#WARNING!
#USE AT YOUR OWN RISK!
# WatchROM — One Kit to Rule Them All
### Android ROM Engineering Suite

**109 commands · 29 modules · 5 chipset vendors · Any Android device**

---

## Supported Chipsets

### MediaTek (MTK)
MT6739/W · MT6761/W · MT6762 · MT6763 · MT6765 · MT6768 · MT6769 · MT6771 · MT6785 · MT6789 · MT6833 · MT6853 · MT6877 · MT6879 · MT6886 · MT6893 · MT6895 · MT6983 · MT2601 · MT2625 · MT6580W

### Unisoc / Spreadtrum
SC9832E · SC9863 · SC9863A · SL8541E · SC8541E · SC7731E · SC9820E · UIS8581A · UIS8520E · T310 · T606 · T612 · T616 · T618 · T760 · T820

### Rockchip
PX30 · RK3126 · RK3128 · RK3188 · RK3228 · RK3229 · RK3288 · RK3308 · RK3318 · RK3326 · RK3328 · RK3399 · RK3399Pro · RK3566 · RK3568 · RK3562 · RK3576 · RK3588 · RK3588S · PX5 · PX6

### Allwinner
A10 · A13 · A20 · A23 · A31 · A33 · A50 · A64 · A80 · A83T · A100 · A133 · H2+ · H3 · H5 · H6 · H616 · H618 · H700 · T3 · T507 · T7 · R818 · R528

### Realtek
RTD1073 · RTD1185 · RTD1195 · RTD1295 · RTD1296 · RTD1312 · RTD1315 · RTD1319 · RTD1395 · RTD1619 · RTD1619B

---

## Installation

```bash
git clone https://github.com/yourname/watchrom
cd watchrom
bash install.sh
```

`install.sh` automatically:
- Installs all apt packages (adb, fastboot, apktool, dtc, sunxi-tools, rkdeveloptool, etc.)
- Installs Python packages (rich, click, avbtool, protobuf, etc.)
- Clones 20+ GitHub repos into `../watchrom_repos/`
  - mtkclient, edl, jadx, Apktool, payload-dumper-go
  - rkdeveloptool, rkflashtool, sunxi-tools, awutils
  - twrp-dtg, unisoc-tools, rtd-flash, and more
- Sets USB permissions for all vendors (udev rules)
- Registers `watchrom` as a system-wide command

---

## Usage

```bash
watchrom          # Interactive guided TUI menu (recommended)
watchrom --help   # Full CLI reference
```

### First Run
On first launch, WatchROM automatically:
1. Detects your connected device and identifies the chipset
2. Offers a **full backup** before any modifications
3. Drops you into the guided interactive menu

---

## Module Reference

| Module | Commands | What it does |
|--------|----------|-------------|
| `device` | 3 | Auto-detect chipset, reboot modes |
| `dump` / `flash` | 2 | Partition read/write |
| `bootimg` | 4 | Unpack/repack boot.img, kernel cmdline patch |
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
| `adb` | 6 | shell, push, pull, install, logcat, devices |

---

## Chipset-Specific Workflows

### MTK (SP Flash Tool)
```bash
watchrom mtk identify          # detect chip + props
watchrom mtk download          # BROM mode guide
watchrom dump --all            # dump all partitions
watchrom rom build --vendor mtk --parts-dir output/<serial>/partitions/
# → MT_scatter.txt generated → open in SP Flash Tool
```

### Unisoc (UpgradeDownload)
```bash
watchrom unisoc identify       # detect chip + props
watchrom unisoc download       # FDL mode guide
watchrom dump --all
watchrom rom build --vendor unisoc --parts-dir output/<serial>/partitions/
# → flashconfig.xml → open in UpgradeDownload tool
```

### Rockchip (rkdeveloptool)
```bash
watchrom rockchip identify     # detect chip (RK3566, RK3588, etc.)
watchrom rockchip download     # MaskROM entry guide
watchrom rockchip list         # browse all supported chips
watchrom rockchip dump boot    # dump boot partition
watchrom rockchip flash update.img  # flash via rkdeveloptool
```

### Allwinner (sunxi-fel / PhoenixSuit)
```bash
watchrom allwinner identify    # detect chip (H616, A64, R818, etc.)
watchrom allwinner download    # FEL mode entry guide
watchrom allwinner list        # browse all supported chips
watchrom allwinner dump-sid    # read SoC unique ID
watchrom allwinner flash system.img --method sunxi-fel
```

### Realtek (Rescue mode)
```bash
watchrom realtek identify      # detect chip (RTD1619, RTD1295, etc.)
watchrom realtek download      # rescue mode guide
watchrom realtek list          # browse supported chips
watchrom realtek extract-rescue install.img  # inspect rescue image
```

---

## WearOS on Android Watches

Make a full Android smartwatch (MTK/Unisoc) behave like WearOS:

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

---

## GitHub Repos Cloned by install.sh

Located at `../watchrom_repos/`:

**Chipset tools:** mtkclient, edl, rkdeveloptool, rkflashtool, sunxi-tools, awutils, unisoc-tools, rtd-flash  
**ROM tools:** jadx, Apktool, payload-dumper-go, twrp-dtg, bootimgtools  
**Android tools:** Magisk, Shizuku, android-emulator  
**Firmware tools:** OppoDecrypt, MTK-Tools, rk-uboot, aw-bootloader

---

## Output Directory Layout

```
output/
├── <serial>/
│   ├── partitions/      ← all dumped .img files + MANIFEST.txt
│   └── boot_magisk_patched.img
├── rom_package/
│   ├── MT_scatter.txt   ← MTK / SP Flash Tool
│   ├── flashconfig.xml  ← Unisoc / UpgradeDownload
│   └── rom_manifest.json
├── sysimg_extracted/    ← extracted + editable system/vendor
├── decompiled/          ← APK smali + Java source
├── magisk_modules/      ← built .zip modules
├── twrp/ and device_tree/
└── backups/<serial>_<timestamp>/
keys/
├── platform.pk8 + platform.x509.pem
├── media.pk8 + media.x509.pem
├── releasekey.pk8 + releasekey.x509.pem
├── avb.pem              ← AVB signing key
└── debug.keystore       ← APK debug signing
```

---

## License
MIT — For personal device modification and ROM development.


---

## Qualcomm Snapdragon — LTE/5G Band Configuration

### Supported Chips (38 total)
**Flagship:** SM8650 (Gen 3) · SM8550 (Gen 2) · SM8475/SM8450 (Gen 1) · SM8350 (888) · SM8250 (865) · SM8150 (855) · SDM845 · SDM835  
**Upper-mid:** SM7675/7550/7475/7450 · SM7350 (778G) · SM7250 (765G) · SM7150 (730G) · SDM710  
**Mid/Budget:** SM6375 (695) · SM6350 (690) · SM6225 (680) · SDM660 · SM4350 (480) · SDM450/439/429  
**Tablets:** SM7580 (7c+ Gen3) · SC7280/SC7180 (7c/7c Gen2)

### Modem X-Series Reference
X75 (Gen3, 10Gbps) · X70 (Gen2) · X65 (Gen1/888+) · X62 (7-series) · X60 (888) · X55 (865, first 5G) · X53/X52/X51/X35 · X24/X20/X16/X15/X12

### Band Configuration Commands

```bash
# Check what chip and modem you have
watchrom qualcomm identify

# Check current carrier/network/signal (no root needed)
watchrom qualcomm network-status

# See all available band presets
watchrom qualcomm band-presets

# Apply US carrier presets
watchrom qualcomm band-set --preset us_tmobile    # B2/4/12/25/41/66/71 + n41
watchrom qualcomm band-set --preset us_att         # B2/4/5/17/29/30/66 + C-band
watchrom qualcomm band-set --preset us_verizon     # B2/4/5/13/48/66 + C-band

# International
watchrom qualcomm band-set --preset global_unlocked  # All bands enabled
watchrom qualcomm band-set --preset europe_4g
watchrom qualcomm band-set --preset asia_4g5g

# Mode presets
watchrom qualcomm band-set --lte-only              # Disable 5G (saves battery)
watchrom qualcomm band-set --5g-preferred          # Max 5G priority
watchrom qualcomm band-set --preset all_bands      # Restore defaults

# Set specific bands manually
watchrom qualcomm band-set --bands 2,4,12,66,71   # Custom band selection

# Dry run — shows what would be written without touching device
watchrom qualcomm band-set --preset us_tmobile --dry-run
```

### Safety Workflow (Always Follow This Order)

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

### What Band Configuration Does and Doesn't Do

| ✅ Safe — included | ❌ Not implemented — by design |
|---|---|
| LTE band preference bitmask (which bands to search) | IMEI/MEID modification (illegal) |
| 5G NR band preference mask | RF calibration NV items (brick risk) |
| Network mode preference (LTE-only, 5G-preferred) | SPC/MSL unlock codes |
| EFS backup and restore | Carrier lock bypass |
| AT command query (read-only) | Any irreversible modem changes |

Band changes are **fully reversible** — use `efs-restore` to roll back.

### AT Command Interface (No Root on Most Devices)

```bash
watchrom qualcomm at-cmd --cmd "AT+QNWINFO"    # Current band + operator
watchrom qualcomm at-cmd --cmd "AT+CSQ"         # Signal strength (RSSI)
watchrom qualcomm at-cmd --cmd "AT+COPS?"       # Current operator
watchrom qualcomm at-cmd --cmd "AT+CEREG?"      # LTE registration
watchrom qualcomm at-cmd --cmd "AT+C5GREG?"     # 5G NR registration
watchrom qualcomm at-cmd --cmd 'AT+QCFG="band"' # Current band config
```

### EDL Mode (Emergency Download — USB 9008)

EDL is Qualcomm's Boot ROM download interface. Required for:
- Flashing modem firmware (`.mbn` files)
- Full EFS backup when device won't boot
- Partition operations via firehose

```bash
# Check if EDL device is connected (USB 0x05C6:0x9008)
watchrom qualcomm edl --check

# Reboot into EDL (if device is currently on)
watchrom qualcomm edl --enter

# Full EDL guide + firehose info
watchrom qualcomm edl
```

**Hardware EDL entry:** Hold Vol+ + Vol− simultaneously while connecting USB.  
A wrong firehose loader fails handshake — it does not brick the device.

### DIAG Mode (for QPST/QFIL)

```bash
# Enable DIAG USB interface (no root on most devices)
watchrom qualcomm diag-enable
# Then use QPST or QFIL to connect via the COM port that appears
```

### External 5G Modem Chips

Some devices use a **separate 5G modem chip** alongside the main SoC:

| Device | Main SoC | 5G Modem |
|--------|----------|----------|
| Samsung Galaxy S20 (2020) | Exynos 990 | Exynos 5123 / X55 external |
| iPhone 12 (2020) | Apple A14 | Qualcomm X55 (external) |
| Early Snapdragon 865 phones | SM8250 | X55 external (865 has no integrated 5G) |
| Snapdragon 888+ | SM8350 | X60 **integrated** |

For devices with an external 5G modem, band configuration targets the **same EFS NV items** — the modem firmware handles routing between the main AP and the 5G sub-system transparently. `watchrom qualcomm band-set` works the same way regardless of whether 5G is integrated or external.

---


---

## Universal Band Configuration — All Chipset Vendors

WatchROM handles LTE/5G band configuration on **any Android device** regardless of chipset.
The same workflow applies whether your device is Qualcomm, MTK, Unisoc, Rockchip, or Allwinner.

### How It Works Per Vendor

| Vendor | Write Method | Interface | Root Needed? |
|--------|-------------|-----------|-------------|
| Qualcomm | EFS NV item write | ADB root | Yes (EFS method) |
| Qualcomm | AT+QCFG command | AT port | Sometimes |
| MTK | AT+ERAT + AT+EPBSE | AT port /dev/ttyC0 | Sometimes |
| MTK | Engineering Mode app | GUI intent | No |
| Unisoc | AT+ERAT + AT+EPBSE | AT port /dev/stty0 | Sometimes |
| Rockchip/Allwinner | AT commands (external modem) | /dev/ttyUSB* | Sometimes |

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
```

---

## Verizon Wireless — Complete Band Reference

### LTE Bands

| Band | Frequency | Type | Notes |
|------|-----------|------|-------|
| **B13** ★ | 700 MHz Block C | Primary | Verizon signature band — always needed |
| B2  | 1900 MHz PCS | Core | Primary data/voice |
| B4  | 1700/2100 MHz AWS-1 | Core | Main LTE capacity layer |
| B5  | 850 MHz CLR | Coverage | Rural and building penetration |
| B48 | 3500 MHz CBRS | Capacity | Enterprise/private networks, small cells |
| B66 | 1700/2100 MHz AWS-3 | Capacity | Extended capacity, pairs with B4 |

★ B13 is mandatory for Verizon — without it your device won't connect to Verizon LTE.

### 5G Bands

| Band | Frequency | Type | Notes |
|------|-----------|------|-------|
| **n77** ★ | 3.7 GHz C-band | Primary 5G | Verizon 5G Ultra Wideband — main 5G spectrum |
| n5  | 850 MHz | Nationwide coverage | Verizon extended 5G range |
| n48 | 3.5 GHz CBRS | Capacity | CBRS 5G, private networks |
| n66 | 1700/2100 AWS-3 | Capacity | AWS-3 5G |
| n260 | 39 GHz mmWave | Ultra Wideband | Dense urban only (~100m range) |
| n261 | 28 GHz mmWave | Ultra Wideband | Dense urban only (~100m range) |

★ n77 C-band is Verizon's primary mid-band 5G — this is what Verizon calls "5G Ultra Wideband" in most markets.

### Verizon Configuration Commands

```bash
# Full Verizon — LTE B2/4/5/13/48/66 + 5G n5/n48/n66/n77 + mmWave n260/n261
watchrom bands verizon --tier full

# LTE only — disable 5G (better battery, same coverage)
watchrom bands verizon --tier lte-only

# 5G priority — maximize 5G connection
watchrom bands verizon --tier 5g

# CBRS only — for private network / enterprise use
watchrom bands verizon --tier cbrs

# Preview without writing
watchrom bands verizon --dry-run
```

### Hex Masks (for manual entry in QPST/Engineering Mode)

```
LTE low  (B1-B64) : 0x0000000008880200   covers B2, B4, B5, B13
LTE high (B65+)   : 0x0000000000020001   covers B48, B66
NR mask            : 0x0000000000000118   covers n5, n48, n66, n77
mmWave             : separate n260/n261 config in modem firmware
```

---

## All Supported Carrier Profiles

### United States
| Carrier | LTE Bands | 5G Bands | Command |
|---------|-----------|----------|---------|
| Verizon | B2/4/5/13/48/66 | n5/n48/n66/n77/n260/n261 | `--carrier verizon` |
| T-Mobile | B2/4/5/12/25/26/41/66/71 | n41/n71 | `--carrier tmobile` |
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

Band configuration is **standard telecom engineering** — the same operations performed by:
- Network engineers and carrier technicians
- ROM developers testing carrier compatibility
- Repair shops configuring replacement devices
- Travelers enabling local carrier bands

**All changes are fully reversible.** WatchROM automatically backs up your current band config before every write. To restore:
```bash
watchrom bands apply --carrier global_roaming    # re-enable all bands
watchrom qualcomm efs-restore output/band_backups/<device>/<timestamp>/
```

**What WatchROM never modifies:**
- IMEI/MEID identifiers (illegal to modify in most countries)
- RF calibration data (factory-set, irreversible)
- Carrier lock status
- SPC/MSL codes
