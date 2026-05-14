# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [Unreleased]

### Added
- **Band hex mask auto-computation**: `compute_lte_mask()`/`compute_lte_mask_hex()` using
  standard 3GPP bit mapping (bit position = band_number − 1). `compute_nr_mask()` with
  documented firmware-specific mapping table. `--derive-masks` flag for `bands apply`,
  `bands verify-masks` CLI command to detect stale hex masks against declared band lists.
- **Samsung/Heimdall support**: `modules/samsung.py` (320 lines) with Samsung device detection,
  bootloader unlock check, Download Mode helpers, Heimdall flash wrapper, and 13 Exynos chips
  (2400/2200/2100/990/982x/9810/961x/7885/7870/8890/7420). 19 Samsung-to-standard partition
  name mappings. Exynos detection integrated into `identify_chip_universal()`. Samsung KVB
  (Knox) detection in root-device and avb-disable pipelines with user guidance.
- **GKI vendor_boot ramdisk support**: Vendor boot header parser (magic VNDRBOOT, v3=72 bytes,
  v4=100 bytes). `unpack_vendor_boot()` extracts ramdisk.cpio.gz + DTB + vendor cmdline.
  `repack_vendor_boot()` rebuilds from modified contents (mkbootimg or manual fallback).
  `bootimg unpack-vendor`/`repack-vendor` CLI commands. GKI unpack warnings now point to
  vendor_boot commands.
- **Danger-zone partition protection**: 60+ critical partitions blocked by default
  (preloader, persist, fsg, abl, xbl, tz, keymaster, etc.). Requires `--force` to override.
- **Battery level pre-flight check**: Root-device and flash-rom pipelines check battery ≥30%
  before any write operation, preventing brick from power loss.
- **`wait_for_boot()` / `wait_for_fastboot()` poll loops**: Replaces fragile `time.sleep()`
  with polling-based device wait. `wait_for_boot()` polls `sys.boot_completed` up to 120s.
  `wait_for_fastboot()` polls `fastboot devices` up to 30s.
- **Proper getprop regex parsing**: `_GETPROP_RE` replaces fragile bracket-splitting in
  `get_device_props()`.

### Fixed
- **LTE hex mask computation**: Recalculated 16 CARRIER_PROFILES + 13 BAND_PRESETS hex masks
  that had stale/incorrect values not matching declared band lists. `global_roaming` bands
  1–68 had wrong masks (only 63 bits, high word wrong).
- **MTK band write dead code**: Removed `lte_high << 0` no-op — MTK EPBSE only supports
  64-bit masks.
- **vbmeta flash rollback**: Proper restore of stock vbmeta backup on flash failure.
- **Duplicate LTE_BANDS key 34** in qualcomm_chips.py — caused data corruption.
- **CHIPSET_SIGNATURES duplication**: `detect_chipset_from_props()` now delegates to
  `chipsets.py` as single source of truth. Removed Qualcomm monkey-patch.
- **launcher.py error handling**: Improved rich import with clear error messages and graceful
  failure instead of silent auto-install attempt.
- **Direct chipsets import in vendors.py**: Removed try/except fallbacks to `PARTITION_MAPS` —
  all vendors now use `modules.chipsets` directly.
- **T-Mobile band profile**: Added n25 (sub6), n258/n260/n261 (mmWave) to match official
  T-Mobile 5GUC spec. Primary 5G remains n41 (mid-band).
- **NR hex mask corruption in all profiles**: 15 CARRIER_PROFILES + 15 BAND_PRESETS had
  NR hex masks that encoded completely wrong bands (e.g. n5 where n77 was declared, n38
  where n48 was declared, n2 where n41 was declared). Root cause: commit c898717 fixed
  LTE hex masks but never recalculated NR masks. All NR hex values now correctly computed
  via `compute_nr_mask_hex()` from declared band lists. 5 simple presets (us_tmobile,
  us_att, us_verizon, europe_4g, asia_4g5g) also fixed to match descriptions.

---

## [1.0.0] — 2024-01-15

### Added — Framework
- `core/interfaces.py` — `VendorInterface`, `FlashInterface`, `BandConfigInterface`, `Result`
- `core/registry.py` — `@register_vendor`, `@register_band_config`, version-pinned deps
- `core/pipeline.py` — Task graph state machine with resume, rollback, dry-run
- `core/vendors.py` — Concrete implementations for MTK, Unisoc, Rockchip, Allwinner, Realtek, Qualcomm
- `core/band_backends.py` — Qualcomm EFS, MTK AT, Unisoc AT, Generic AT backends

### Added — Pipelines
- `root-device` (7 steps): detect → backup → Magisk patch → flash → verify
- `full-backup` (4 steps): detect → dump all → apps → manifest
- `avb-disable` (4 steps): detect → backup vbmeta → blank → flash
- `flash-rom` (4 steps): validate → backup → AVB disable → flash all
- `wearos-setup` (6 steps): detect → root check → backup → module → install → verify
- `configure-bands` (4 steps): detect → backup → apply carrier → reboot

### Added — Chipset Support (137 total)
- MTK: 24 SoCs (MT6739–MT6983, watch variants)
- Unisoc: 16 SoCs (SC9832E–T820, UIS-series)
- Rockchip: 22 SoCs (PX30–RK3588S, PX5/PX6)
- Allwinner: 24 SoCs (A10–R818, H2+–H618)
- Realtek: 13 SoCs (RTD1073–RTD1619B)
- Qualcomm: 38 SoCs (SDM429–SM8650)

### Added — Band Configuration
- 27 band presets, 16 carrier profiles (US + international)
- Verizon complete: B2/4/5/13/48/66 LTE + n5/48/66/77/260/261 5G
- 128-bit extended LTE mask (B66/B71 handled correctly in high word)
- Per-vendor write: Qualcomm EFS, MTK AT+EPBSE, Unisoc AT+ERAT, Generic AT

### Fixed
- `build_lte_bitmask` type mismatch — was returning tuple where int expected
- `struct.pack("<Q")` overflow — 128-bit mask passed to 64-bit packer
- `sysimg.py` hardcoded `sudo` — replaced with `_sudo_or_root()` fallback helper
- `repack_boot` mtime crash on missing ramdisk — added existence guard
- US carrier preset hex masks — recalculated from actual band lists using `build_lte_bitmask()`

---

[Unreleased]: https://github.com/yourusername/watchrom/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yourusername/watchrom/releases/tag/v1.0.0
