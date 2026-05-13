"""
chipsets.py — Comprehensive MTK and Unisoc chipset database
Used for auto-detection, partition mapping, and tool selection
"""

# ── MTK chipset database ──────────────────────────────────────────────────────
# Format: codename → {display_name, platform_string, arch, year, notes}

MTK_CHIPS = {
    # Budget / Watch tier
    "MT6739":  {"name":"Helio A22 / MT6739",  "platform":"mt6739",  "arch":"arm64","year":2018,"watch":True,  "brom":True},
    "MT6761":  {"name":"Helio A22 / MT6761",  "platform":"mt6761",  "arch":"arm64","year":2019,"watch":True,  "brom":True},
    "MT6762":  {"name":"Helio P22 / MT6762",  "platform":"mt6762",  "arch":"arm64","year":2018,"watch":False, "brom":True},
    "MT6763":  {"name":"Helio P23 / MT6763",  "platform":"mt6763",  "arch":"arm64","year":2017,"watch":False, "brom":True},
    "MT6765":  {"name":"Helio G35 / MT6765",  "platform":"mt6765",  "arch":"arm64","year":2019,"watch":False, "brom":True},
    "MT6768":  {"name":"Helio G85 / MT6768",  "platform":"mt6768",  "arch":"arm64","year":2020,"watch":False, "brom":True},
    "MT6769":  {"name":"Helio G85 / MT6769",  "platform":"mt6769",  "arch":"arm64","year":2021,"watch":False, "brom":True},
    "MT6771":  {"name":"Helio P60 / MT6771",  "platform":"mt6771",  "arch":"arm64","year":2018,"watch":False, "brom":True},
    "MT6785":  {"name":"Helio G90T / MT6785", "platform":"mt6785",  "arch":"arm64","year":2019,"watch":False, "brom":True},
    "MT6789":  {"name":"Helio G99 / MT6789",  "platform":"mt6789",  "arch":"arm64","year":2022,"watch":False, "brom":True},
    "MT6833":  {"name":"Dimensity 700 / MT6833","platform":"mt6833","arch":"arm64","year":2021,"watch":False, "brom":True},
    "MT6853":  {"name":"Dimensity 720 / MT6853","platform":"mt6853","arch":"arm64","year":2020,"watch":False, "brom":True},
    "MT6873":  {"name":"Dimensity 800 / MT6873","platform":"mt6873","arch":"arm64","year":2020,"watch":False, "brom":True},
    "MT6877":  {"name":"Dimensity 900 / MT6877","platform":"mt6877","arch":"arm64","year":2021,"watch":False, "brom":True},
    "MT6879":  {"name":"Dimensity 1080/ MT6879","platform":"mt6879","arch":"arm64","year":2022,"watch":False, "brom":True},
    "MT6886":  {"name":"Dimensity 6080/ MT6886","platform":"mt6886","arch":"arm64","year":2023,"watch":False, "brom":True},
    "MT6893":  {"name":"Dimensity 1200/MT6893","platform":"mt6893","arch":"arm64","year":2021,"watch":False, "brom":True},
    "MT6895":  {"name":"Dimensity 8200/MT6895","platform":"mt6895","arch":"arm64","year":2022,"watch":False, "brom":True},
    "MT6983":  {"name":"Dimensity 9000/MT6983","platform":"mt6983","arch":"arm64","year":2022,"watch":False, "brom":True},
    # Wearable specific
    "MT2601":  {"name":"Wear MT2601",          "platform":"mt2601",  "arch":"arm",  "year":2015,"watch":True,  "brom":True},
    "MT2625":  {"name":"NB-IoT MT2625",        "platform":"mt2625",  "arch":"arm",  "year":2018,"watch":True,  "brom":False},
    "MT6580W": {"name":"MT6580W Watch",        "platform":"mt6580",  "arch":"arm",  "year":2016,"watch":True,  "brom":True},
    "MT6739W": {"name":"MT6739W Watch",        "platform":"mt6739",  "arch":"arm64","year":2019,"watch":True,  "brom":True},
    "MT6761W": {"name":"MT6761W Watch",        "platform":"mt6761",  "arch":"arm64","year":2020,"watch":True,  "brom":True},
}

# Signature strings used for auto-detection from ro.board.platform etc.
MTK_SIGNATURES = {
    "mt6739":  ["MT6739"],
    "mt6761":  ["MT6761","helio a20","helio a22"],
    "mt6762":  ["MT6762","helio p22"],
    "mt6765":  ["MT6765","helio g35"],
    "mt6768":  ["MT6768","helio g85"],
    "mt6771":  ["MT6771","helio p60"],
    "mt6785":  ["MT6785","helio g90"],
    "mt6789":  ["MT6789","helio g99"],
    "mt6833":  ["MT6833","dimensity 700"],
    "mt6853":  ["MT6853","dimensity 720"],
    "mt6873":  ["MT6873","dimensity 800"],
    "mt6877":  ["MT6877","dimensity 900"],
    "mt6893":  ["MT6893","dimensity 1200"],
    "mt6895":  ["MT6895","dimensity 8200"],
    "mt6983":  ["MT6983","dimensity 9000"],
    "mt2601":  ["MT2601","wear2601"],
    "mt6580":  ["MT6580","mt6580w"],
}

# ── Unisoc chipset database ───────────────────────────────────────────────────

UNISOC_CHIPS = {
    # Watch / IoT tier
    "SC9832E": {"name":"Unisoc SC9832E",  "platform":"sc9832e", "arch":"arm",  "year":2018,"watch":True,  "fdl":True, "avb_weak":True},
    "SC9863A": {"name":"Unisoc SC9863A",  "platform":"sc9863a", "arch":"arm64","year":2019,"watch":True,  "fdl":True, "avb_weak":True},
    "SC9863":  {"name":"Unisoc SC9863",   "platform":"sc9863",  "arch":"arm64","year":2018,"watch":True,  "fdl":True, "avb_weak":True},
    "SL8541E": {"name":"Unisoc SL8541E",  "platform":"sl8541e", "arch":"arm64","year":2020,"watch":True,  "fdl":True, "avb_weak":True},
    "SC8541E": {"name":"Unisoc SC8541E",  "platform":"sc8541e", "arch":"arm64","year":2021,"watch":True,  "fdl":True, "avb_weak":True},
    "SC7731E": {"name":"Unisoc SC7731E",  "platform":"sc7731e", "arch":"arm",  "year":2019,"watch":False, "fdl":True, "avb_weak":True},
    "SC9820E": {"name":"Unisoc SC9820E",  "platform":"sc9820e", "arch":"arm64","year":2018,"watch":False, "fdl":True, "avb_weak":True},
    "UIS8581A":{"name":"Unisoc UIS8581A", "platform":"uis8581a","arch":"arm64","year":2022,"watch":True,  "fdl":True, "avb_weak":True},
    "UIS8520E":{"name":"Unisoc UIS8520E", "platform":"uis8520e","arch":"arm64","year":2023,"watch":True,  "fdl":True, "avb_weak":True},
    # Mid-range
    "T310":    {"name":"Unisoc Tiger T310","platform":"t310",   "arch":"arm64","year":2020,"watch":False, "fdl":True, "avb_weak":False},
    "T606":    {"name":"Unisoc Tiger T606","platform":"t606",   "arch":"arm64","year":2021,"watch":False, "fdl":True, "avb_weak":False},
    "T612":    {"name":"Unisoc Tiger T612","platform":"t612",   "arch":"arm64","year":2021,"watch":False, "fdl":True, "avb_weak":False},
    "T616":    {"name":"Unisoc Tiger T616","platform":"t616",   "arch":"arm64","year":2022,"watch":False, "fdl":True, "avb_weak":False},
    "T618":    {"name":"Unisoc Tiger T618","platform":"t618",   "arch":"arm64","year":2021,"watch":False, "fdl":True, "avb_weak":False},
    "T760":    {"name":"Unisoc Tiger T760","platform":"t760",   "arch":"arm64","year":2022,"watch":False, "fdl":True, "avb_weak":False},
    "T820":    {"name":"Unisoc Tiger T820","platform":"t820",   "arch":"arm64","year":2022,"watch":False, "fdl":True, "avb_weak":False},
}

UNISOC_SIGNATURES = {
    "sc9832e": ["SC9832E","sc9832e","sp9832e"],
    "sc9863a": ["SC9863A","sc9863a"],
    "sc9863":  ["SC9863","sc9863"],
    "sl8541e": ["SL8541E","sl8541e"],
    "sc8541e": ["SC8541E","sc8541e"],
    "sc7731e": ["SC7731E","sc7731e"],
    "sc9820e": ["SC9820E","sc9820e"],
    "uis8581a":["UIS8581A","uis8581a"],
    "t606":    ["T606","t606"],
    "t612":    ["T612","t612"],
    "t618":    ["T618","t618"],
    "t760":    ["T760","t760"],
    "t820":    ["T820","t820"],
}

# ── Partition layouts by vendor ───────────────────────────────────────────────

MTK_PARTITIONS = {
    "standard": [
        "preloader","lk","lk2","boot","recovery","system","vendor",
        "userdata","cache","persist","tee1","tee2","logo","para",
        "dtbo","vbmeta","frp","protect1","protect2","nvram","nvcfg",
        "proinfo","otp","metadata",
    ],
    "a_only": [
        "preloader","lk","boot","recovery","system","vendor","userdata",
        "cache","persist","tee1","tee2","logo","para","dtbo","vbmeta","frp",
    ],
    "ab": [
        "preloader","lk_a","lk_b","boot_a","boot_b","system_a","system_b",
        "vendor_a","vendor_b","userdata","persist","tee1","tee2",
        "dtbo_a","dtbo_b","vbmeta_a","vbmeta_b","frp",
    ],
}

UNISOC_PARTITIONS = {
    "standard": [
        "boot","recovery","system","vendor","userdata","cache","persist",
        "modem","dtbo","vbmeta","sml","tos","prodnv","misc","pm_sys",
        "l_fixnv1","l_fixnv2","l_runtimenv1","l_runtimenv2",
        "socko","odmko","l_gdsp","l_lccdsp","l_agdsp","l_cdsp",
    ],
    "ab": [
        "boot_a","boot_b","system_a","system_b","vendor_a","vendor_b",
        "userdata","persist","modem","dtbo_a","dtbo_b","vbmeta_a","vbmeta_b",
        "sml","tos","prodnv","misc",
    ],
}

# ── Flash tool mapping ────────────────────────────────────────────────────────

FLASH_TOOLS = {
    "mtk": {
        "primary":   "SP Flash Tool (spflashtools.com)",
        "secondary": "MTK Client (github.com/bkerler/mtkclient)",
        "format":    "scatter file (MT_scatter.txt)",
        "mode":      "BROM — hold Vol- while connecting USB",
    },
    "unisoc": {
        "primary":   "Unisoc UpgradeDownload Tool",
        "secondary": "SPD Research Tool",
        "format":    "PAC file or flashconfig.xml",
        "mode":      "FDL — hold Vol- while connecting USB",
    },
}

# ── Helper functions ──────────────────────────────────────────────────────────

def identify_mtk_chip(platform_str: str) -> dict:
    """Return MTK chip info dict from platform string."""
    pl = platform_str.lower().replace("-","").replace("_","")
    # Direct match
    for key, chip in MTK_CHIPS.items():
        if chip["platform"] in pl or pl in chip["platform"]:
            return {"vendor": "mtk", "key": key, **chip}
    # Signature scan
    for platform, sigs in MTK_SIGNATURES.items():
        for sig in sigs:
            if sig.lower() in pl:
                key = platform.upper().replace("MT","MT")
                return {"vendor": "mtk", "key": key,
                        **MTK_CHIPS.get(key, {"name": key, "arch": "arm64",
                                              "watch": False, "brom": True})}
    return {}


def identify_unisoc_chip(platform_str: str) -> dict:
    """Return Unisoc chip info dict from platform string."""
    pl = platform_str.lower().replace("-","").replace("_","")
    for key, chip in UNISOC_CHIPS.items():
        if chip["platform"] in pl or pl in chip["platform"]:
            return {"vendor": "unisoc", "key": key, **chip}
    for platform, sigs in UNISOC_SIGNATURES.items():
        for sig in sigs:
            if sig.lower() in pl:
                key = platform.upper()
                return {"vendor": "unisoc", "key": key,
                        **UNISOC_CHIPS.get(key, {"name": key, "arch": "arm64",
                                                 "watch": True, "fdl": True, "avb_weak": True})}
    return {}


def get_partition_list(vendor: str, ab: bool = False) -> list:
    """Return appropriate partition list for vendor + AB flag."""
    if vendor == "mtk":
        return MTK_PARTITIONS["ab" if ab else "standard"]
    elif vendor == "unisoc":
        return UNISOC_PARTITIONS["ab" if ab else "standard"]
    # Generic fallback
    return ["boot","recovery","system","vendor","userdata","cache",
            "persist","dtbo","vbmeta"]


def get_flash_tool_info(vendor: str) -> dict:
    return FLASH_TOOLS.get(vendor, FLASH_TOOLS["mtk"])


def all_watch_chips() -> list:
    """Return list of all known watch-class chipsets."""
    result = []
    for key, info in MTK_CHIPS.items():
        if info["watch"]:
            result.append({"vendor": "mtk", "key": key, **info})
    for key, info in UNISOC_CHIPS.items():
        if info["watch"]:
            result.append({"vendor": "unisoc", "key": key, **info})
    return result

# ══════════════════════════════════════════════════════════════════════════════
# ROCKCHIP CHIPSET DATABASE
# ══════════════════════════════════════════════════════════════════════════════

ROCKCHIP_CHIPS = {
    # Budget / IoT / Watch
    "PX30":    {"name":"Rockchip PX30",     "platform":"px30",   "arch":"arm64","year":2019,"type":"tablet/iot",  "maskrom":True,  "notes":"4x Cortex-A35, common in budget tablets"},
    "RK3126":  {"name":"Rockchip RK3126",   "platform":"rk3126", "arch":"arm",  "year":2015,"type":"tablet",      "maskrom":True,  "notes":"4x Cortex-A7"},
    "RK3128":  {"name":"Rockchip RK3128",   "platform":"rk3128", "arch":"arm",  "year":2015,"type":"tablet",      "maskrom":True,  "notes":"4x Cortex-A7, budget tablets"},
    "RK3188":  {"name":"Rockchip RK3188",   "platform":"rk3188", "arch":"arm",  "year":2012,"type":"tablet",      "maskrom":True,  "notes":"4x Cortex-A9, legacy"},
    # Mid-range
    "RK3228":  {"name":"Rockchip RK3228",   "platform":"rk3228", "arch":"arm64","year":2016,"type":"tv_box",      "maskrom":True,  "notes":"4x Cortex-A7, TV boxes"},
    "RK3229":  {"name":"Rockchip RK3229",   "platform":"rk3229", "arch":"arm64","year":2016,"type":"tv_box",      "maskrom":True,  "notes":"4x Cortex-A7"},
    "RK3288":  {"name":"Rockchip RK3288",   "platform":"rk3288", "arch":"arm",  "year":2014,"type":"tablet",      "maskrom":True,  "notes":"4x Cortex-A17, Chromebook/tablet"},
    "RK3308":  {"name":"Rockchip RK3308",   "platform":"rk3308", "arch":"arm64","year":2018,"type":"iot",         "maskrom":True,  "notes":"4x Cortex-A35, voice/IoT"},
    "RK3318":  {"name":"Rockchip RK3318",   "platform":"rk3318", "arch":"arm64","year":2018,"type":"tv_box",      "maskrom":True,  "notes":"4x Cortex-A53, popular TV box"},
    "RK3326":  {"name":"Rockchip RK3326",   "platform":"rk3326", "arch":"arm64","year":2019,"type":"gaming",      "maskrom":True,  "notes":"4x Cortex-A35, handhelds"},
    "RK3328":  {"name":"Rockchip RK3328",   "platform":"rk3328", "arch":"arm64","year":2017,"type":"tv_box",      "maskrom":True,  "notes":"4x Cortex-A53, Rock64/TV boxes"},
    "RK3399":  {"name":"Rockchip RK3399",   "platform":"rk3399", "arch":"arm64","year":2016,"type":"sbc/tablet",  "maskrom":True,  "notes":"big.LITTLE A72+A53, ROCKPro64"},
    "RK3399Pro":{"name":"Rockchip RK3399Pro","platform":"rk3399pro","arch":"arm64","year":2018,"type":"ai/sbc",   "maskrom":True,  "notes":"RK3399 + NPU"},
    # Modern / High-performance
    "RK3566":  {"name":"Rockchip RK3566",   "platform":"rk3566", "arch":"arm64","year":2021,"type":"tablet/sbc",  "maskrom":True,  "notes":"4x Cortex-A55, Quartz64"},
    "RK3568":  {"name":"Rockchip RK3568",   "platform":"rk3568", "arch":"arm64","year":2021,"type":"tablet/sbc",  "maskrom":True,  "notes":"4x Cortex-A55, Rock3A"},
    "RK3562":  {"name":"Rockchip RK3562",   "platform":"rk3562", "arch":"arm64","year":2023,"type":"tablet",      "maskrom":True,  "notes":"4x Cortex-A53 + 1x A73"},
    "RK3576":  {"name":"Rockchip RK3576",   "platform":"rk3576", "arch":"arm64","year":2024,"type":"tablet/sbc",  "maskrom":True,  "notes":"4x A72 + 4x A53"},
    "RK3588":  {"name":"Rockchip RK3588",   "platform":"rk3588", "arch":"arm64","year":2022,"type":"flagship/sbc","maskrom":True,  "notes":"4x A76 + 4x A55, Rock5B"},
    "RK3588S": {"name":"Rockchip RK3588S",  "platform":"rk3588s","arch":"arm64","year":2022,"type":"tablet/sbc",  "maskrom":True,  "notes":"Stripped RK3588, Orange Pi 5"},
    # Automotive / Embedded
    "RK3358":  {"name":"Rockchip RK3358",   "platform":"rk3358", "arch":"arm64","year":2020,"type":"auto",        "maskrom":True,  "notes":"Automotive grade"},
    "PX5":     {"name":"Rockchip PX5",      "platform":"px5",    "arch":"arm64","year":2017,"type":"auto",        "maskrom":True,  "notes":"8x Cortex-A53, car head units"},
    "PX6":     {"name":"Rockchip PX6",      "platform":"px6",    "arch":"arm64","year":2019,"type":"auto",        "maskrom":True,  "notes":"6x Cortex-A72, car head units"},
}

ROCKCHIP_SIGNATURES = {
    "px30":     ["px30","PX30","rk3326"],
    "rk3126":   ["rk3126","RK3126"],
    "rk3128":   ["rk3128","RK3128"],
    "rk3188":   ["rk3188","RK3188"],
    "rk3228":   ["rk3228","RK3228"],
    "rk3288":   ["rk3288","RK3288"],
    "rk3308":   ["rk3308","RK3308"],
    "rk3318":   ["rk3318","RK3318"],
    "rk3326":   ["rk3326","RK3326"],
    "rk3328":   ["rk3328","RK3328"],
    "rk3399":   ["rk3399","RK3399"],
    "rk3566":   ["rk3566","RK3566"],
    "rk3568":   ["rk3568","RK3568"],
    "rk3576":   ["rk3576","RK3576"],
    "rk3588":   ["rk3588","RK3588"],
    "rk3588s":  ["rk3588s","RK3588S"],
    "px5":      ["px5","PX5"],
    "px6":      ["px6","PX6"],
}

# Rockchip partition layouts
ROCKCHIP_PARTITIONS = {
    "standard": [
        "loader","parameter","trust","uboot","boot","recovery",
        "backup","cache","system","vendor","userdata","misc",
        "oem","persist","frp","dtbo","vbmeta","metadata",
    ],
    "gpt": [
        "uboot","trust","boot","system","vendor","userdata",
        "cache","recovery","misc","dtbo","vbmeta","persist",
    ],
    "ab": [
        "uboot_a","uboot_b","trust_a","trust_b",
        "boot_a","boot_b","system_a","system_b",
        "vendor_a","vendor_b","dtbo_a","dtbo_b",
        "vbmeta_a","vbmeta_b","userdata","misc","persist",
    ],
}

# ══════════════════════════════════════════════════════════════════════════════
# ALLWINNER CHIPSET DATABASE
# ══════════════════════════════════════════════════════════════════════════════

ALLWINNER_CHIPS = {
    # Legacy
    "A10":   {"name":"Allwinner A10",  "platform":"sun4i","arch":"arm",  "year":2011,"type":"tablet","fel":True, "notes":"Cortex-A8, very common legacy tablet"},
    "A13":   {"name":"Allwinner A13",  "platform":"sun5i","arch":"arm",  "year":2011,"type":"tablet","fel":True, "notes":"Cortex-A8 low-cost"},
    "A20":   {"name":"Allwinner A20",  "platform":"sun7i","arch":"arm",  "year":2012,"type":"tablet","fel":True, "notes":"dual Cortex-A7"},
    "A23":   {"name":"Allwinner A23",  "platform":"sun8i","arch":"arm",  "year":2013,"type":"tablet","fel":True, "notes":"dual Cortex-A7"},
    "A31":   {"name":"Allwinner A31",  "platform":"sun6i","arch":"arm",  "year":2012,"type":"tablet","fel":True, "notes":"quad Cortex-A7"},
    "A33":   {"name":"Allwinner A33",  "platform":"sun8i","arch":"arm",  "year":2014,"type":"tablet","fel":True, "notes":"quad Cortex-A7, many budget tablets"},
    # Modern tablet / TV
    "A50":   {"name":"Allwinner A50",  "platform":"sun50i","arch":"arm64","year":2017,"type":"tablet","fel":True, "notes":"quad Cortex-A53"},
    "A64":   {"name":"Allwinner A64",  "platform":"sun50i","arch":"arm64","year":2016,"type":"tablet/sbc","fel":True,"notes":"quad Cortex-A53, Pine A64"},
    "A80":   {"name":"Allwinner A80",  "platform":"sun9i","arch":"arm",  "year":2014,"type":"tablet","fel":True, "notes":"big.LITTLE A15+A7"},
    "A83T":  {"name":"Allwinner A83T", "platform":"sun8i","arch":"arm",  "year":2015,"type":"tablet","fel":True, "notes":"octa Cortex-A7"},
    "A100":  {"name":"Allwinner A100", "platform":"sun50i","arch":"arm64","year":2020,"type":"tablet","fel":True, "notes":"quad Cortex-A53, tablets"},
    "A133":  {"name":"Allwinner A133", "platform":"sun50i","arch":"arm64","year":2021,"type":"tablet","fel":True, "notes":"quad Cortex-A55"},
    # H series (TV box / SBC)
    "H2+":   {"name":"Allwinner H2+",  "platform":"sun8i","arch":"arm",  "year":2015,"type":"tv_box/sbc","fel":True,"notes":"quad Cortex-A7, OrangePi Zero"},
    "H3":    {"name":"Allwinner H3",   "platform":"sun8i","arch":"arm",  "year":2015,"type":"tv_box/sbc","fel":True,"notes":"quad Cortex-A7, OrangePi PC"},
    "H5":    {"name":"Allwinner H5",   "platform":"sun50i","arch":"arm64","year":2016,"type":"tv_box/sbc","fel":True,"notes":"quad Cortex-A53"},
    "H6":    {"name":"Allwinner H6",   "platform":"sun50i","arch":"arm64","year":2018,"type":"tv_box/sbc","fel":True,"notes":"quad Cortex-A53"},
    "H616":  {"name":"Allwinner H616", "platform":"sun50i","arch":"arm64","year":2020,"type":"tv_box","fel":True, "notes":"quad Cortex-A53, X96 Air"},
    "H618":  {"name":"Allwinner H618", "platform":"sun50i","arch":"arm64","year":2022,"type":"tv_box/sbc","fel":True,"notes":"quad Cortex-A53"},
    "H700":  {"name":"Allwinner H700", "platform":"sun50i","arch":"arm64","year":2022,"type":"handheld","fel":True,"notes":"handheld gaming"},
    # T series (automotive/industrial)
    "T3":    {"name":"Allwinner T3",   "platform":"sun8i","arch":"arm",  "year":2016,"type":"auto","fel":True,"notes":"quad Cortex-A7, car"},
    "T7":    {"name":"Allwinner T7",   "platform":"sun55i","arch":"arm64","year":2022,"type":"auto","fel":True,"notes":"automotive grade"},
    "T507":  {"name":"Allwinner T507", "platform":"sun50i","arch":"arm64","year":2020,"type":"auto/iot","fel":True,"notes":"quad Cortex-A53"},
    # R series (IoT/RISC-V hybrid)
    "R818":  {"name":"Allwinner R818", "platform":"sun50i","arch":"arm64","year":2020,"type":"iot/watch","fel":True,"notes":"quad Cortex-A53, smart watches"},
    "R528":  {"name":"Allwinner R528", "platform":"sun8i","arch":"arm",  "year":2022,"type":"iot","fel":True,"notes":"dual Cortex-A7 + RISC-V"},
}

ALLWINNER_SIGNATURES = {
    "sun4i": ["A10","a10","sun4i"],
    "sun5i": ["A13","a13","sun5i"],
    "sun7i": ["A20","a20","sun7i"],
    "sun8i": ["A23","A33","A83T","H2","H3","sun8i"],
    "sun50i":["A50","A64","A100","H5","H6","H616","H618","R818","sun50i"],
    "sun9i": ["A80","sun9i"],
    "sun6i": ["A31","sun6i"],
    "sun55i":["T7","sun55i"],
    "r818":  ["R818","r818"],
    "h616":  ["H616","h616"],
    "h618":  ["H618","h618"],
    "a64":   ["A64","a64"],
    "h6":    ["H6","h6"],
    "h3":    ["H3","h3"],
}

# Allwinner partition layouts (NAND and eMMC differ)
ALLWINNER_PARTITIONS = {
    "emmc": [
        "bootloader","env","boot","system","vendor","userdata",
        "cache","recovery","misc","dtbo","vbmeta","persist",
    ],
    "nand": [
        "bootloader","boot-resource","env","boot","system",
        "vendor","userdata","cache","recovery","UDISK",
    ],
    "ab": [
        "bootloader","boot_a","boot_b","system_a","system_b",
        "vendor_a","vendor_b","userdata","misc","dtbo_a","dtbo_b",
    ],
}

# ══════════════════════════════════════════════════════════════════════════════
# REALTEK CHIPSET DATABASE
# ══════════════════════════════════════════════════════════════════════════════

REALTEK_CHIPS = {
    # Media/Smart TV
    "RTD1073": {"name":"Realtek RTD1073", "platform":"rtd1073","arch":"arm",  "year":2013,"type":"tv","notes":"media player SoC"},
    "RTD1185": {"name":"Realtek RTD1185", "platform":"rtd1185","arch":"arm",  "year":2014,"type":"tv","notes":"Android TV box"},
    "RTD1195": {"name":"Realtek RTD1195", "platform":"rtd1195","arch":"arm64","year":2015,"type":"tv","notes":"4K Android TV, Shield-like"},
    "RTD1295": {"name":"Realtek RTD1295", "platform":"rtd1295","arch":"arm64","year":2016,"type":"tv/nas","notes":"4x Cortex-A53, ZIDOO"},
    "RTD1296": {"name":"Realtek RTD1296", "platform":"rtd1296","arch":"arm64","year":2017,"type":"tv/nas","notes":"4x Cortex-A53 + Gigabit"},
    "RTD1312": {"name":"Realtek RTD1312", "platform":"rtd1312","arch":"arm64","year":2019,"type":"tv","notes":"smart TV SoC"},
    "RTD1315": {"name":"Realtek RTD1315", "platform":"rtd1315","arch":"arm64","year":2020,"type":"tv","notes":"AV1 decode"},
    "RTD1319": {"name":"Realtek RTD1319", "platform":"rtd1319","arch":"arm64","year":2020,"type":"tv","notes":"4K 8K Android TV"},
    "RTD1395": {"name":"Realtek RTD1395", "platform":"rtd1395","arch":"arm64","year":2018,"type":"tv","notes":"4x Cortex-A53, ZIDOO X9S"},
    "RTD1619": {"name":"Realtek RTD1619", "platform":"rtd1619","arch":"arm64","year":2020,"type":"tv/nas","notes":"4x A55, flagship media"},
    "RTD1619B":{"name":"Realtek RTD1619B","platform":"rtd1619b","arch":"arm64","year":2022,"type":"tv/nas","notes":"Upgraded 1619"},
    # Wi-Fi / Networking (with embedded CPU)
    "RTL8197": {"name":"Realtek RTL8197", "platform":"rtl8197","arch":"mips","year":2014,"type":"router","notes":"router SoC"},
    "RTL8881A": {"name":"Realtek RTL8881A","platform":"rtl8881","arch":"mips","year":2016,"type":"router","notes":"router/AP SoC"},
}

REALTEK_SIGNATURES = {
    "rtd1195": ["RTD1195","rtd1195","1195"],
    "rtd1295": ["RTD1295","rtd1295","1295"],
    "rtd1296": ["RTD1296","rtd1296","1296"],
    "rtd1312": ["RTD1312","rtd1312"],
    "rtd1319": ["RTD1319","rtd1319"],
    "rtd1395": ["RTD1395","rtd1395","1395"],
    "rtd1619": ["RTD1619","rtd1619","1619"],
    "rtd1619b":["RTD1619B","rtd1619b"],
}

# Realtek partition layouts
REALTEK_PARTITIONS = {
    "standard": [
        "bootcode","rescue","hwsetting","factory","boot",
        "system","vendor","userdata","cache","misc",
    ],
    "android_tv": [
        "bootcode","rescue","hwsetting","factory",
        "boot","recovery","system","vendor","userdata",
        "cache","misc","vbmeta","dtbo",
    ],
}

# ══════════════════════════════════════════════════════════════════════════════
# UPDATED HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def identify_rockchip_chip(platform_str: str) -> dict:
    pl = platform_str.lower().replace("-","").replace("_","")
    for key, chip in ROCKCHIP_CHIPS.items():
        if chip["platform"] in pl or pl in chip["platform"]:
            return {"vendor":"rockchip","key":key,**chip}
    for platform, sigs in ROCKCHIP_SIGNATURES.items():
        for sig in sigs:
            if sig.lower() in pl:
                key = platform.upper()
                return {"vendor":"rockchip","key":key,
                        **ROCKCHIP_CHIPS.get(key,{"name":key,"arch":"arm64","maskrom":True})}
    return {}


def identify_allwinner_chip(platform_str: str) -> dict:
    pl = platform_str.lower().replace("-","").replace("_","")
    for key, chip in ALLWINNER_CHIPS.items():
        if chip["platform"] in pl or pl in chip["platform"]:
            return {"vendor":"allwinner","key":key,**chip}
    for platform, sigs in ALLWINNER_SIGNATURES.items():
        for sig in sigs:
            if sig.lower() in pl:
                key = platform.upper()
                return {"vendor":"allwinner","key":key,
                        **ALLWINNER_CHIPS.get(key,{"name":key,"arch":"arm64","fel":True})}
    return {}


def identify_realtek_chip(platform_str: str) -> dict:
    pl = platform_str.lower().replace("-","").replace("_","")
    for key, chip in REALTEK_CHIPS.items():
        if chip["platform"] in pl or pl in chip["platform"]:
            return {"vendor":"realtek","key":key,**chip}
    for platform, sigs in REALTEK_SIGNATURES.items():
        for sig in sigs:
            if sig.lower() in pl:
                key = platform.upper()
                return {"vendor":"realtek","key":key,
                        **REALTEK_CHIPS.get(key,{"name":key,"arch":"arm64"})}
    return {}


def identify_chip_universal(platform_str: str, hardware_str: str = "") -> dict:
    """
    Try all known vendors and return the first match.
    Returns dict with 'vendor' key indicating the manufacturer.
    """
    combined = f"{platform_str} {hardware_str}".lower()

    # MTK
    result = identify_mtk_chip(combined)
    if result: return result

    # Unisoc
    result = identify_unisoc_chip(combined)
    if result: return result

    # Rockchip
    result = identify_rockchip_chip(combined)
    if result: return result

    # Allwinner
    result = identify_allwinner_chip(combined)
    if result: return result

    # Realtek
    result = identify_realtek_chip(combined)
    if result: return result

    # Qualcomm
    result = identify_qualcomm_chip(platform_str, hardware_str)
    if result: return result

    # Samsung Exynos
    try:
        from modules.samsung import identify_exynos
        result = identify_exynos(platform_str)
        if result: return result
    except ImportError:
        pass

    return {"vendor":"unknown","key":"unknown","name":"Unknown SoC","arch":"arm64"}


def get_partition_list(vendor: str, ab: bool = False) -> list:
    """Return appropriate partition list for vendor + AB flag."""
    if vendor == "mtk":
        return MTK_PARTITIONS["ab" if ab else "standard"]
    elif vendor == "unisoc":
        return UNISOC_PARTITIONS["ab" if ab else "standard"]
    elif vendor == "rockchip":
        return ROCKCHIP_PARTITIONS["ab" if ab else "gpt"]
    elif vendor == "allwinner":
        return ALLWINNER_PARTITIONS["ab" if ab else "emmc"]
    elif vendor == "realtek":
        return REALTEK_PARTITIONS.get("android_tv", REALTEK_PARTITIONS["standard"])
    return ["boot","recovery","system","vendor","userdata","cache","persist","dtbo","vbmeta"]


def all_watch_chips() -> list:
    result = []
    for key, info in MTK_CHIPS.items():
        if info.get("watch"):
            result.append({"vendor":"mtk","key":key,**info})
    for key, info in UNISOC_CHIPS.items():
        if info.get("watch"):
            result.append({"vendor":"unisoc","key":key,**info})
    for key, info in ALLWINNER_CHIPS.items():
        if info.get("type","") in ("iot/watch","watch"):
            result.append({"vendor":"allwinner","key":key,**info})
    return result


# Flash tool info for all vendors
FLASH_TOOLS["rockchip"] = {
    "primary":   "rkdeveloptool / upgrade_tool (Rockchip)",
    "secondary": "AndroidTool (Windows), rkflashtool",
    "format":    "loader.bin + update.img or individual partition images",
    "mode":      "MaskROM — hold Recovery + connect USB (or short MaskROM pads)",
    "usb_vid":   "0x2207",
}
FLASH_TOOLS["allwinner"] = {
    "primary":   "sunxi-fel / PhoenixSuit / LiveSuit",
    "secondary": "AllwinnerTool, PhoenixCard (SD boot)",
    "format":    "img (raw) or xz compressed, script.bin + boot_package.fex",
    "mode":      "FEL mode — hold Vol-/U-boot/recovery + connect USB",
    "usb_vid":   "0x1F3A",
}
FLASH_TOOLS["realtek"] = {
    "primary":   "Realtek Rescue Mode (Ethernet or USB)",
    "secondary": "RTD1xxx USB flashing tool",
    "format":    "install.img / rescue filesystem",
    "mode":      "Rescue mode — hold rescue button while powering on",
    "usb_vid":   "0x0BDA",
}


# ══════════════════════════════════════════════════════════════════════════════
# QUALCOMM UNIFIED DETECTION HOOK
# ══════════════════════════════════════════════════════════════════════════════

def identify_qualcomm_chip(platform_str: str, hardware_str: str = "") -> dict:
    """Identify Qualcomm Snapdragon from platform/hardware strings."""
    try:
        from modules.qualcomm_chips import identify_snapdragon
        result = identify_snapdragon(platform_str, hardware_str)
        if result:
            return result
    except ImportError:
        pass
    return {}


# Flash tool for Qualcomm
FLASH_TOOLS["qualcomm"] = {
    "primary":   "QFIL (Qualcomm Flash Image Loader) / bkerler/edl",
    "secondary": "QPST, Fastboot (for unlocked devices)",
    "format":    "Firehose .elf/.mbn loader + partition images",
    "mode":      "EDL — hold Vol+ + Vol− while powering on, or short EDL pad",
    "usb_vid":   "0x05C6 PID:0x9008",
}
