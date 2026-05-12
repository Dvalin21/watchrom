"""
core/vendors.py — Concrete VendorInterface implementations for all 6 vendors
MTK, Unisoc, Rockchip, Allwinner, Realtek, Qualcomm
"""
from __future__ import annotations
from typing import Optional
from core.interfaces import VendorInterface, DeviceInfo
from core.registry import register_vendor


def _props_match(props: dict, signatures: list[str]) -> bool:
    combined = " ".join([
        props.get("ro.board.platform",""),
        props.get("ro.hardware",""),
        props.get("ro.product.board",""),
        props.get("ro.chip.id",""),
        props.get("gsm.version.baseband",""),
    ]).lower()
    return any(sig.lower() in combined for sig in signatures)


@register_vendor
class MTKVendor(VendorInterface):
    name = "MediaTek"
    key  = "mtk"

    _SIGS = ["mt6739","mt6761","mt6762","mt6765","mt6768","mt6771",
             "mt6785","mt6789","mt6833","mt6853","mt6877","mt6893",
             "mt6895","mt6983","mt2601","mt6580","mediatek","helio",
             "dimensity"]

    def detect(self, props: dict) -> Optional[DeviceInfo]:
        if not _props_match(props, self._SIGS):
            return None
        from modules.chipsets import identify_mtk_chip
        platform = props.get("ro.board.platform","")
        chip = identify_mtk_chip(platform)
        return DeviceInfo(
            serial    = props.get("_serial","?"),
            vendor    = "mtk",
            chipset   = chip.get("key", platform.upper()),
            arch      = chip.get("arch","arm64"),
            android_ver = props.get("ro.build.version.release",""),
            model       = props.get("ro.product.model",""),
            device      = props.get("ro.product.device",""),
            ab_partitions = props.get("ro.build.ab_update","false") == "true",
            props       = props,
        )

    def partition_list(self, device: DeviceInfo) -> list[str]:
        from modules import PARTITION_MAPS
        layout = "ab" if device.ab_partitions else "standard"
        try:
            from modules.chipsets import MTK_PARTITIONS
            return MTK_PARTITIONS.get(layout, MTK_PARTITIONS["standard"])
        except Exception:
            return PARTITION_MAPS["mtk"]

    def download_mode_entry(self) -> str:
        return ("MTK BROM mode:\n"
                "  1. Power off device\n"
                "  2. Hold Vol− and connect USB\n"
                "  3. Release when SP Flash Tool shows COM port\n"
                "  USB VID: 0x0E8D  PID: 0x0003")

    def flash_tool_info(self) -> dict:
        return {
            "name":    "SP Flash Tool",
            "format":  "MT_scatter.txt + partition images",
            "usb_vid": "0x0E8D",
            "notes":   "Also: mtkclient (github.com/bkerler/mtkclient)",
        }

    def supported_chips(self) -> list[str]:
        try:
            from modules.chipsets import MTK_CHIPS
            return list(MTK_CHIPS.keys())
        except Exception:
            return []


@register_vendor
class UnisocVendor(VendorInterface):
    name = "Unisoc / Spreadtrum"
    key  = "unisoc"

    _SIGS = ["sc9832","sc9863","sl8541","sc8541","sc7731","uis8581",
             "uis8520","spreadtrum","sprd","sc9820","t606","t612",
             "t618","t760","t820"]

    def detect(self, props: dict) -> Optional[DeviceInfo]:
        if not _props_match(props, self._SIGS):
            return None
        from modules.chipsets import identify_unisoc_chip
        platform = props.get("ro.board.platform","")
        chip = identify_unisoc_chip(platform)
        return DeviceInfo(
            serial    = props.get("_serial","?"),
            vendor    = "unisoc",
            chipset   = chip.get("key", platform.upper()),
            arch      = chip.get("arch","arm64"),
            android_ver = props.get("ro.build.version.release",""),
            model       = props.get("ro.product.model",""),
            device      = props.get("ro.product.device",""),
            ab_partitions = props.get("ro.build.ab_update","false") == "true",
            props       = props,
        )

    def partition_list(self, device: DeviceInfo) -> list[str]:
        try:
            from modules.chipsets import UNISOC_PARTITIONS
            layout = "ab" if device.ab_partitions else "standard"
            return UNISOC_PARTITIONS.get(layout, UNISOC_PARTITIONS["standard"])
        except Exception:
            from modules import PARTITION_MAPS
            return PARTITION_MAPS["unisoc"]

    def download_mode_entry(self) -> str:
        return ("Unisoc FDL mode:\n"
                "  1. Power off device\n"
                "  2. Hold Vol− and connect USB\n"
                "  3. SPD tool shows 'Connected'\n"
                "  USB VID: 0x1782  PID: 0x4D00")

    def flash_tool_info(self) -> dict:
        return {
            "name":    "UpgradeDownload / SPD Research Tool",
            "format":  "PAC file or flashconfig.xml",
            "usb_vid": "0x1782",
            "notes":   "Device must be in FDL mode",
        }

    def supported_chips(self) -> list[str]:
        try:
            from modules.chipsets import UNISOC_CHIPS
            return list(UNISOC_CHIPS.keys())
        except Exception:
            return []


@register_vendor
class RockchipVendor(VendorInterface):
    name = "Rockchip"
    key  = "rockchip"

    _SIGS = ["rk3126","rk3128","rk3188","rk3228","rk3288","rk3308",
             "rk3318","rk3326","rk3328","rk3399","rk3566","rk3568",
             "rk3576","rk3588","px30","px5","px6"]

    def detect(self, props: dict) -> Optional[DeviceInfo]:
        if not _props_match(props, self._SIGS):
            return None
        from modules.chipsets import identify_rockchip_chip
        platform = props.get("ro.board.platform","")
        chip = identify_rockchip_chip(platform)
        return DeviceInfo(
            serial    = props.get("_serial","?"),
            vendor    = "rockchip",
            chipset   = chip.get("key", platform.upper()),
            arch      = chip.get("arch","arm64"),
            android_ver = props.get("ro.build.version.release",""),
            model       = props.get("ro.product.model",""),
            device      = props.get("ro.product.device",""),
            props       = props,
        )

    def partition_list(self, device: DeviceInfo) -> list[str]:
        try:
            from modules.chipsets import ROCKCHIP_PARTITIONS
            layout = "ab" if device.ab_partitions else "gpt"
            return ROCKCHIP_PARTITIONS.get(layout, ROCKCHIP_PARTITIONS["gpt"])
        except Exception:
            from modules import PARTITION_MAPS
            return PARTITION_MAPS["rockchip"]

    def download_mode_entry(self) -> str:
        return ("Rockchip MaskROM mode:\n"
                "  1. Hold Recovery button and connect USB\n"
                "  2. OR short the MaskROM pads on PCB\n"
                "  USB VID: 0x2207")

    def flash_tool_info(self) -> dict:
        return {
            "name":    "rkdeveloptool / RKDevTool",
            "format":  "loader.bin + update.img",
            "usb_vid": "0x2207",
            "notes":   "Linux: rkdeveloptool  Windows: RKDevTool",
        }

    def supported_chips(self) -> list[str]:
        try:
            from modules.chipsets import ROCKCHIP_CHIPS
            return list(ROCKCHIP_CHIPS.keys())
        except Exception:
            return []


@register_vendor
class AllwinnerVendor(VendorInterface):
    name = "Allwinner"
    key  = "allwinner"

    _SIGS = ["sun4i","sun5i","sun6i","sun7i","sun8i","sun9i","sun50i",
             "sun55i","a10","a13","a20","a33","a64","a100","h3","h5",
             "h6","h616","h618","r818","t507"]

    def detect(self, props: dict) -> Optional[DeviceInfo]:
        if not _props_match(props, self._SIGS):
            return None
        from modules.chipsets import identify_allwinner_chip
        platform = props.get("ro.board.platform","")
        chip = identify_allwinner_chip(platform)
        return DeviceInfo(
            serial    = props.get("_serial","?"),
            vendor    = "allwinner",
            chipset   = chip.get("key", platform.upper()),
            arch      = chip.get("arch","arm64"),
            android_ver = props.get("ro.build.version.release",""),
            model       = props.get("ro.product.model",""),
            device      = props.get("ro.product.device",""),
            props       = props,
        )

    def partition_list(self, device: DeviceInfo) -> list[str]:
        try:
            from modules.chipsets import ALLWINNER_PARTITIONS
            layout = "ab" if device.ab_partitions else "emmc"
            return ALLWINNER_PARTITIONS.get(layout, ALLWINNER_PARTITIONS["emmc"])
        except Exception:
            from modules import PARTITION_MAPS
            return PARTITION_MAPS["allwinner"]

    def download_mode_entry(self) -> str:
        return ("Allwinner FEL mode:\n"
                "  1. Hold FEL button and connect USB OTG\n"
                "  2. OR boot from blank SD card\n"
                "  USB VID: 0x1F3A  PID: 0xEFE8")

    def flash_tool_info(self) -> dict:
        return {
            "name":    "sunxi-fel / PhoenixSuit",
            "format":  "Raw image or packed .img",
            "usb_vid": "0x1F3A",
            "notes":   "Linux: sunxi-fel  Windows: PhoenixSuit/LiveSuit",
        }

    def supported_chips(self) -> list[str]:
        try:
            from modules.chipsets import ALLWINNER_CHIPS
            return list(ALLWINNER_CHIPS.keys())
        except Exception:
            return []


@register_vendor
class RealtekVendor(VendorInterface):
    name = "Realtek"
    key  = "realtek"

    _SIGS = ["rtd1195","rtd1295","rtd1296","rtd1312","rtd1319",
             "rtd1395","rtd1619","rtd1619b","realtek"]

    def detect(self, props: dict) -> Optional[DeviceInfo]:
        if not _props_match(props, self._SIGS):
            return None
        from modules.chipsets import identify_realtek_chip
        platform = props.get("ro.board.platform","")
        chip = identify_realtek_chip(platform)
        return DeviceInfo(
            serial    = props.get("_serial","?"),
            vendor    = "realtek",
            chipset   = chip.get("key", platform.upper()),
            arch      = chip.get("arch","arm64"),
            android_ver = props.get("ro.build.version.release",""),
            model       = props.get("ro.product.model",""),
            device      = props.get("ro.product.device",""),
            props       = props,
        )

    def partition_list(self, device: DeviceInfo) -> list[str]:
        from modules import PARTITION_MAPS
        return PARTITION_MAPS["realtek"]

    def download_mode_entry(self) -> str:
        return ("Realtek Rescue mode:\n"
                "  Hold Rescue button while powering on\n"
                "  USB VID: 0x0BDA")

    def flash_tool_info(self) -> dict:
        return {
            "name":    "Realtek rescue / rtd-flash",
            "format":  "install.img / rescue filesystem",
            "usb_vid": "0x0BDA",
            "notes":   "Linux: rtd-flash  OR Ethernet TFTP rescue",
        }

    def supported_chips(self) -> list[str]:
        try:
            from modules.chipsets import REALTEK_CHIPS
            return list(REALTEK_CHIPS.keys())
        except Exception:
            return []


@register_vendor
class QualcommVendor(VendorInterface):
    name = "Qualcomm Snapdragon"
    key  = "qualcomm"

    _SIGS = ["sm8","sm7","sm6","sm4","sdm","msm","qcom","snapdragon",
             "lahaina","kona","msmnile","sdm845","sdm835"]

    def detect(self, props: dict) -> Optional[DeviceInfo]:
        if not _props_match(props, self._SIGS):
            return None
        from modules.qualcomm_chips import identify_snapdragon
        platform = props.get("ro.board.platform","")
        hardware = props.get("ro.hardware","")
        chip = identify_snapdragon(f"{platform} {hardware}")
        return DeviceInfo(
            serial    = props.get("_serial","?"),
            vendor    = "qualcomm",
            chipset   = chip.get("key", platform.upper()),
            arch      = "arm64",
            android_ver = props.get("ro.build.version.release",""),
            model       = props.get("ro.product.model",""),
            device      = props.get("ro.product.device",""),
            ab_partitions = props.get("ro.build.ab_update","false") == "true",
            props       = props,
        )

    def partition_list(self, device: DeviceInfo) -> list[str]:
        from modules import PARTITION_MAPS
        return PARTITION_MAPS.get("qualcomm", PARTITION_MAPS["unknown"])

    def download_mode_entry(self) -> str:
        return ("Qualcomm EDL mode (9008):\n"
                "  Hold Vol+ + Vol− simultaneously while connecting USB\n"
                "  OR: adb reboot edl\n"
                "  USB VID: 0x05C6  PID: 0x9008")

    def flash_tool_info(self) -> dict:
        return {
            "name":    "QFIL / bkerler/edl",
            "format":  "Firehose .elf/.mbn + partition images",
            "usb_vid": "0x05C6",
            "notes":   "Requires correct firehose loader for device",
        }

    def supported_chips(self) -> list[str]:
        try:
            from modules.qualcomm_chips import SNAPDRAGON_CHIPS
            return list(SNAPDRAGON_CHIPS.keys())
        except Exception:
            return []
