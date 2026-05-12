# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [Unreleased]

*Changes staged for next release.*

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
