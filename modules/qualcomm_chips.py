"""
qualcomm_chips.py — Qualcomm Snapdragon chipset database
Covers: modem variants, EDL support, band capabilities, firehose loaders
"""

# ── Snapdragon SoC database ────────────────────────────────────────────────────
# modem: X-series modem variant (determines band support)
# edl: supports EDL (Emergency Download) mode via 9008
# firehose_known: firehose loader is publicly documented
# bands_5g: supports 5G NR
# sub6: Sub-6 GHz 5G
# mmwave: mmWave 5G (high-frequency, short range)

SNAPDRAGON_CHIPS = {
    # ── Flagship ────────────────────────────────────────────────────────────
    "SM8650":  {"name":"Snapdragon 8 Gen 3",  "modem":"X75",  "year":2023,"tier":"flagship","edl":True,"bands_5g":True,"sub6":True,"mmwave":True},
    "SM8550":  {"name":"Snapdragon 8 Gen 2",  "modem":"X70",  "year":2022,"tier":"flagship","edl":True,"bands_5g":True,"sub6":True,"mmwave":True},
    "SM8475":  {"name":"Snapdragon 8+ Gen 1", "modem":"X65",  "year":2022,"tier":"flagship","edl":True,"bands_5g":True,"sub6":True,"mmwave":True},
    "SM8450":  {"name":"Snapdragon 8 Gen 1",  "modem":"X65",  "year":2021,"tier":"flagship","edl":True,"bands_5g":True,"sub6":True,"mmwave":True},
    "SM8350":  {"name":"Snapdragon 888",       "modem":"X60",  "year":2020,"tier":"flagship","edl":True,"bands_5g":True,"sub6":True,"mmwave":True},
    "SM8250":  {"name":"Snapdragon 865",       "modem":"X55",  "year":2019,"tier":"flagship","edl":True,"bands_5g":True,"sub6":True,"mmwave":False},
    "SM8150":  {"name":"Snapdragon 855",       "modem":"X24",  "year":2018,"tier":"flagship","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    "SDM845":  {"name":"Snapdragon 845",       "modem":"X20",  "year":2017,"tier":"flagship","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    "SDM835":  {"name":"Snapdragon 835",       "modem":"X16",  "year":2016,"tier":"flagship","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    "MSM8998": {"name":"Snapdragon 835 (alt)", "modem":"X16",  "year":2016,"tier":"flagship","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    # ── Upper-mid ────────────────────────────────────────────────────────────
    "SM7675":  {"name":"Snapdragon 7s Gen 3",  "modem":"X62",  "year":2023,"tier":"upper_mid","edl":True,"bands_5g":True,"sub6":True,"mmwave":False},
    "SM7550":  {"name":"Snapdragon 7 Gen 2",   "modem":"X62",  "year":2023,"tier":"upper_mid","edl":True,"bands_5g":True,"sub6":True,"mmwave":False},
    "SM7475":  {"name":"Snapdragon 7+ Gen 2",  "modem":"X62",  "year":2023,"tier":"upper_mid","edl":True,"bands_5g":True,"sub6":True,"mmwave":False},
    "SM7450":  {"name":"Snapdragon 7 Gen 1",   "modem":"X62",  "year":2022,"tier":"upper_mid","edl":True,"bands_5g":True,"sub6":True,"mmwave":False},
    "SM7350":  {"name":"Snapdragon 778G",       "modem":"X53",  "year":2021,"tier":"upper_mid","edl":True,"bands_5g":True,"sub6":True,"mmwave":False},
    "SM7325":  {"name":"Snapdragon 778G+",      "modem":"X53",  "year":2021,"tier":"upper_mid","edl":True,"bands_5g":True,"sub6":True,"mmwave":False},
    "SM7250":  {"name":"Snapdragon 765G",       "modem":"X52",  "year":2019,"tier":"upper_mid","edl":True,"bands_5g":True,"sub6":True,"mmwave":False},
    "SM7150":  {"name":"Snapdragon 730G",       "modem":"X15",  "year":2019,"tier":"upper_mid","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    "SDM730":  {"name":"Snapdragon 730",        "modem":"X15",  "year":2019,"tier":"upper_mid","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    "SDM710":  {"name":"Snapdragon 710",        "modem":"X15",  "year":2018,"tier":"upper_mid","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    # ── Mid-range ────────────────────────────────────────────────────────────
    "SM6375":  {"name":"Snapdragon 695",        "modem":"X51",  "year":2021,"tier":"mid","edl":True,"bands_5g":True,"sub6":True,"mmwave":False},
    "SM6350":  {"name":"Snapdragon 690",        "modem":"X51",  "year":2020,"tier":"mid","edl":True,"bands_5g":True,"sub6":True,"mmwave":False},
    "SM6225":  {"name":"Snapdragon 680",        "modem":"X13",  "year":2021,"tier":"mid","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    "SM6150":  {"name":"Snapdragon 675",        "modem":"X12",  "year":2018,"tier":"mid","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    "SDM660":  {"name":"Snapdragon 660",        "modem":"X12",  "year":2017,"tier":"mid","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    "SDM636":  {"name":"Snapdragon 636",        "modem":"X12",  "year":2017,"tier":"mid","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    # ── Budget ───────────────────────────────────────────────────────────────
    "SM4450":  {"name":"Snapdragon 4 Gen 2",    "modem":"X35",  "year":2023,"tier":"budget","edl":True,"bands_5g":True,"sub6":True,"mmwave":False},
    "SM4375":  {"name":"Snapdragon 4 Gen 1",    "modem":"X35",  "year":2022,"tier":"budget","edl":True,"bands_5g":True,"sub6":True,"mmwave":False},
    "SM4350":  {"name":"Snapdragon 480",        "modem":"X51",  "year":2020,"tier":"budget","edl":True,"bands_5g":True,"sub6":True,"mmwave":False},
    "SDM450":  {"name":"Snapdragon 450",        "modem":"X9",   "year":2017,"tier":"budget","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    "SDM439":  {"name":"Snapdragon 439",        "modem":"X8",   "year":2018,"tier":"budget","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    "SDM429":  {"name":"Snapdragon 429",        "modem":"X6",   "year":2018,"tier":"budget","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    # ── Automotive / specialized ──────────────────────────────────────────
    "SA8295P": {"name":"Snapdragon 8295 Auto",  "modem":"X65",  "year":2023,"tier":"auto","edl":True,"bands_5g":True,"sub6":True,"mmwave":False},
    "SDA660":  {"name":"Snapdragon 660 Auto",   "modem":"X12",  "year":2018,"tier":"auto","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    # ── Tablets (Wi-Fi only models — no modem) ───────────────────────────
    "SM8650-AB":{"name":"Snapdragon 8 Gen 3 Tab","modem":"none","year":2023,"tier":"tablet","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    "SM7580":  {"name":"Snapdragon 7c+ Gen 3",  "modem":"X35",  "year":2022,"tier":"tablet","edl":True,"bands_5g":True,"sub6":True,"mmwave":False},
    "SC7280":  {"name":"Snapdragon 7c Gen 2",   "modem":"X15",  "year":2021,"tier":"tablet","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
    "SC7180":  {"name":"Snapdragon 7c",         "modem":"X15",  "year":2020,"tier":"tablet","edl":True,"bands_5g":False,"sub6":False,"mmwave":False},
}

SNAPDRAGON_SIGNATURES = {
    "SM8650": ["sm8650","8 gen 3","gen3"],
    "SM8550": ["sm8550","8 gen 2","gen2"],
    "SM8475": ["sm8475","8+ gen 1"],
    "SM8450": ["sm8450","8 gen 1"],
    "SM8350": ["sm8350","888","lahaina"],
    "SM8250": ["sm8250","865","kona"],
    "SM8150": ["sm8150","855","msmnile"],
    "SDM845": ["sdm845","845","sdm845"],
    "SDM835": ["sdm835","835","msm8998"],
    "SM7550": ["sm7550","7 gen 2"],
    "SM7450": ["sm7450","7 gen 1"],
    "SM7350": ["sm7350","778"],
    "SM7250": ["sm7250","765"],
    "SM7150": ["sm7150","730"],
    "SDM710": ["sdm710","710"],
    "SM6375": ["sm6375","695"],
    "SM6350": ["sm6350","690"],
    "SM6225": ["sm6225","680"],
    "SDM660": ["sdm660","660"],
    "SM4350": ["sm4350","480"],
    "SDM450": ["sdm450","450"],
}

# ── Modem (X-series) database ──────────────────────────────────────────────────
# Maps X-series modem to its capabilities

QUALCOMM_MODEMS = {
    "X75":  {"max_dl":"10 Gbps", "max_ul":"3.5 Gbps","lte_cat":22,"5g_sub6":True,"5g_mmwave":True,"bands_lte":64,"bands_5g_nr":26},
    "X70":  {"max_dl":"10 Gbps", "max_ul":"3.5 Gbps","lte_cat":22,"5g_sub6":True,"5g_mmwave":True,"bands_lte":60,"bands_5g_nr":24},
    "X65":  {"max_dl":"10 Gbps", "max_ul":"3.5 Gbps","lte_cat":22,"5g_sub6":True,"5g_mmwave":True,"bands_lte":55,"bands_5g_nr":22},
    "X62":  {"max_dl":"4.4 Gbps","max_ul":"2.1 Gbps","lte_cat":19,"5g_sub6":True,"5g_mmwave":False,"bands_lte":50,"bands_5g_nr":18},
    "X60":  {"max_dl":"7.5 Gbps","max_ul":"3.0 Gbps","lte_cat":22,"5g_sub6":True,"5g_mmwave":True,"bands_lte":48,"bands_5g_nr":20},
    "X55":  {"max_dl":"7.5 Gbps","max_ul":"3.0 Gbps","lte_cat":22,"5g_sub6":True,"5g_mmwave":True,"bands_lte":45,"bands_5g_nr":18},
    "X53":  {"max_dl":"3.3 Gbps","max_ul":"1.5 Gbps","lte_cat":18,"5g_sub6":True,"5g_mmwave":False,"bands_lte":40,"bands_5g_nr":15},
    "X52":  {"max_dl":"3.7 Gbps","max_ul":"1.6 Gbps","lte_cat":18,"5g_sub6":True,"5g_mmwave":False,"bands_lte":40,"bands_5g_nr":14},
    "X51":  {"max_dl":"2.9 Gbps","max_ul":"1.3 Gbps","lte_cat":16,"5g_sub6":True,"5g_mmwave":False,"bands_lte":36,"bands_5g_nr":12},
    "X35":  {"max_dl":"1.8 Gbps","max_ul":"900 Mbps","lte_cat":16,"5g_sub6":True,"5g_mmwave":False,"bands_lte":30,"bands_5g_nr":10},
    "X24":  {"max_dl":"2.0 Gbps","max_ul":"316 Mbps","lte_cat":20,"5g_sub6":False,"5g_mmwave":False,"bands_lte":28,"bands_5g_nr":0},
    "X20":  {"max_dl":"1.2 Gbps","max_ul":"150 Mbps","lte_cat":16,"5g_sub6":False,"5g_mmwave":False,"bands_lte":25,"bands_5g_nr":0},
    "X16":  {"max_dl":"1.0 Gbps","max_ul":"150 Mbps","lte_cat":16,"5g_sub6":False,"5g_mmwave":False,"bands_lte":22,"bands_5g_nr":0},
    "X15":  {"max_dl":"800 Mbps","max_ul":"150 Mbps","lte_cat":15,"5g_sub6":False,"5g_mmwave":False,"bands_lte":20,"bands_5g_nr":0},
    "X12":  {"max_dl":"600 Mbps","max_ul":"150 Mbps","lte_cat":12,"5g_sub6":False,"5g_mmwave":False,"bands_lte":18,"bands_5g_nr":0},
    "X9":   {"max_dl":"300 Mbps","max_ul":"150 Mbps","lte_cat": 9,"5g_sub6":False,"5g_mmwave":False,"bands_lte":14,"bands_5g_nr":0},
    "X6":   {"max_dl":"150 Mbps","max_ul":"75 Mbps", "lte_cat": 6,"5g_sub6":False,"5g_mmwave":False,"bands_lte":10,"bands_5g_nr":0},
}

# ── Common LTE band reference ──────────────────────────────────────────────────
LTE_BANDS = {
    1:  {"name":"B1",  "freq":"2100 MHz",  "region":"Global"},
    2:  {"name":"B2",  "freq":"1900 MHz",  "region":"Americas"},
    3:  {"name":"B3",  "freq":"1800 MHz",  "region":"Global"},
    4:  {"name":"B4",  "freq":"1700/2100 MHz","region":"Americas"},
    5:  {"name":"B5",  "freq":"850 MHz",   "region":"Global"},
    7:  {"name":"B7",  "freq":"2600 MHz",  "region":"Global"},
    8:  {"name":"B8",  "freq":"900 MHz",   "region":"Global/Europe"},
    12: {"name":"B12", "freq":"700 MHz",   "region":"T-Mobile US"},
    13: {"name":"B13", "freq":"700 MHz",   "region":"Verizon US"},
    14: {"name":"B14", "freq":"700 MHz",   "region":"FirstNet US"},
    17: {"name":"B17", "freq":"700 MHz",   "region":"AT&T US"},
    20: {"name":"B20", "freq":"800 MHz",   "region":"Europe"},
    25: {"name":"B25", "freq":"1900 MHz",  "region":"Sprint/T-Mo"},
    26: {"name":"B26", "freq":"850 MHz",   "region":"Sprint US"},
    28: {"name":"B28", "freq":"700 MHz",   "region":"Asia-Pacific"},
    29: {"name":"B29", "freq":"700 MHz",   "region":"AT&T US (SDL)"},
    30: {"name":"B30", "freq":"2300 MHz",  "region":"AT&T US"},
    38: {"name":"B38", "freq":"2600 MHz",  "region":"China/Europe TDD"},
    40: {"name":"B40", "freq":"2300 MHz",  "region":"Asia TDD"},
    41: {"name":"B41", "freq":"2500 MHz",  "region":"Sprint/T-Mo TDD"},
    42: {"name":"B42", "freq":"3500 MHz",  "region":"Global TDD"},
    48: {"name":"B48", "freq":"3500 MHz",  "region":"CBRS US"},
    66: {"name":"B66", "freq":"1700/2100 MHz","region":"Americas AWS-3"},
    71: {"name":"B71", "freq":"600 MHz",   "region":"T-Mobile US"},
    # Additional important bands
    14: {"name":"B14", "freq":"700 MHz",   "region":"FirstNet US (AT&T)"},
    18: {"name":"B18", "freq":"850 MHz",   "region":"Japan (au/KDDI)"},
    19: {"name":"B19", "freq":"850 MHz",   "region":"Japan (Docomo)"},
    21: {"name":"B21", "freq":"1500 MHz",  "region":"Japan (Docomo)"},
    26: {"name":"B26", "freq":"850 MHz",   "region":"Sprint US / Asia"},
    34: {"name":"B34", "freq":"2100 MHz",  "region":"China TDD"},
    39: {"name":"B39", "freq":"1900 MHz",  "region":"China TDD"},
    41: {"name":"B41", "freq":"2500 MHz",  "region":"Sprint/T-Mobile TDD"},
    46: {"name":"B46", "freq":"5 GHz",     "region":"LTE-U / LAA unlicensed"},
    47: {"name":"B47", "freq":"5 GHz",     "region":"LSA / NR-U"},
    48: {"name":"B48", "freq":"3500 MHz",  "region":"CBRS US (private LTE/5G)"},
    70: {"name":"B70", "freq":"1900 MHz",  "region":"T-Mobile US (AWS-4 SDL)"},
    71: {"name":"B71", "freq":"600 MHz",   "region":"T-Mobile US"},
}

# ── Verizon band reference (complete) ────────────────────────────────────────
VERIZON_BANDS = {
    "lte": {
        2:  {"name":"B2",  "freq":"1900 MHz PCS", "type":"core",     "notes":"Primary data/voice"},
        4:  {"name":"B4",  "freq":"1700/2100 AWS","type":"core",     "notes":"AWS-1, main LTE layer"},
        5:  {"name":"B5",  "freq":"850 MHz CLR",  "type":"coverage", "notes":"Coverage layer, rural"},
        13: {"name":"B13", "freq":"700 MHz C",     "type":"primary",  "notes":"PRIMARY — Verizon signature band"},
        48: {"name":"B48", "freq":"3500 CBRS",     "type":"capacity", "notes":"CBRS small cells, enterprise"},
        66: {"name":"B66", "freq":"1700/2100 AWS", "type":"capacity", "notes":"AWS-3, extended capacity"},
    },
    "nr_sub6": {
        "n5":  {"freq":"850 MHz",  "type":"coverage",  "notes":"Nationwide 5G coverage layer"},
        "n48": {"freq":"3.5 GHz",  "type":"capacity",  "notes":"CBRS 5G, private networks"},
        "n66": {"freq":"AWS-3",    "type":"capacity",  "notes":"AWS-3 5G capacity"},
        "n77": {"freq":"3.7 GHz C-band","type":"primary5g","notes":"C-band — main 5G Ultra Wideband"},
    },
    "nr_mmwave": {
        "n260":{"freq":"39 GHz",   "type":"mmwave",    "notes":"mmWave Ultra Wideband (dense urban)"},
        "n261":{"freq":"28 GHz",   "type":"mmwave",    "notes":"mmWave Ultra Wideband (dense urban)"},
    },
    "deprecated": {
        "1xRTT / EvDO": "CDMA legacy — being shut down",
    },
    "notes": [
        "B13 (700 MHz) is the most important Verizon band — always include it",
        "n77 C-band (3.7 GHz) is Verizon's primary 5G ultra-wideband spectrum",
        "mmWave (n260/n261) only works within ~100m of a small cell node",
        "B48/n48 CBRS used for private LTE/5G enterprise deployments",
        "Verizon roaming internationally uses B1/B3/B7 via agreements",
    ],
}

# Common 5G NR band reference
NR_BANDS = {
    "n1":  {"freq":"2100 MHz",  "type":"sub6","region":"Global"},
    "n2":  {"freq":"1900 MHz",  "type":"sub6","region":"Americas"},
    "n3":  {"freq":"1800 MHz",  "type":"sub6","region":"Global"},
    "n5":  {"freq":"850 MHz",   "type":"sub6","region":"Global"},
    "n7":  {"freq":"2600 MHz",  "type":"sub6","region":"Global"},
    "n8":  {"freq":"900 MHz",   "type":"sub6","region":"Global"},
    "n12": {"freq":"700 MHz",   "type":"sub6","region":"T-Mobile US"},
    "n20": {"freq":"800 MHz",   "type":"sub6","region":"Europe"},
    "n25": {"freq":"1900 MHz",  "type":"sub6","region":"T-Mobile US"},
    "n28": {"freq":"700 MHz",   "type":"sub6","region":"Asia-Pacific"},
    "n38": {"freq":"2600 MHz",  "type":"sub6","region":"China TDD"},
    "n40": {"freq":"2300 MHz",  "type":"sub6","region":"Asia TDD"},
    "n41": {"freq":"2500 MHz",  "type":"sub6","region":"T-Mobile US"},
    "n48": {"freq":"3500 MHz",  "type":"sub6","region":"CBRS US"},
    "n66": {"freq":"AWS-3",     "type":"sub6","region":"Americas"},
    "n71": {"freq":"600 MHz",   "type":"sub6","region":"T-Mobile US"},
    "n77": {"freq":"3.7 GHz",   "type":"sub6","region":"Global C-Band"},
    "n78": {"freq":"3.5 GHz",   "type":"sub6","region":"Global"},
    "n79": {"freq":"4.7 GHz",   "type":"sub6","region":"Japan/China"},
    "n258":{"freq":"26 GHz",    "type":"mmwave","region":"US mmWave"},
    "n260":{"freq":"39 GHz",    "type":"mmwave","region":"US mmWave"},
    "n261":{"freq":"28 GHz",    "type":"mmwave","region":"US mmWave"},
}

# ── NV item reference (safe read-only items) ─────────────────────────────────
# These are modem Non-Volatile items that control band config.
# Only band-related items are included — calibration items are excluded.

NV_ITEMS = {
    # Band preference masks (safe to read and write)
    "nv_mode_pref":          {"id": 10,  "desc": "Network mode preference (LTE/5G/WCDMA/GSM)", "safe_write": True},
    "nv_band_pref":          {"id": 441, "desc": "GSM/WCDMA band preference bitmask",           "safe_write": True},
    "nv_lte_band_pref":      {"id": 6828,"desc": "LTE band preference bitmask (64-bit)",         "safe_write": True},
    "nv_nr5g_band_pref":     {"id": 7296,"desc": "5G NR band preference bitmask",                "safe_write": True},
    "nv_roam_pref":          {"id": 15,  "desc": "Roaming preference",                           "safe_write": True},
    "nv_accolc":             {"id": 6,   "desc": "Access overload class (CDMA)",                  "safe_write": False},
    # EFS paths for band config (modern method)
    "efs_lte_band_pref":     {"path":"/nv/item_files/modem/mmode/lte_bandpref","desc":"LTE band config EFS item","safe_write":True},
    "efs_nr_band_pref":      {"path":"/nv/item_files/modem/mmode/nr5g_bandpref","desc":"5G NR band config EFS item","safe_write":True},
    "efs_mode_pref":         {"path":"/nv/item_files/modem/mmode/mode_pref","desc":"Network mode preference EFS item","safe_write":True},
    # Carrier aggregation
    "efs_ca_combo":          {"path":"/nv/item_files/modem/lte/ca_combo","desc":"CA combo config","safe_write":False},
}

# ── Band bitmask presets ───────────────────────────────────────────────────────
# These are hex bitmasks for common band combinations
BAND_PRESETS = {
    "all_bands":       {"lte": "0x7FFFFFFFFFFFFFFF", "nr": "0x7FFFFFFFFFFFFFFF",
                        "desc": "All bands enabled (device default)"},
    "us_tmobile":      {"lte": "0x000021400D8A08AA", "nr": "0x0000000000000002",
                        "desc": "T-Mobile US: B2/4/5/12/25/26/41/66/71 + n41"},
    "us_att":          {"lte": "0x000021400D8A0200", "nr": "0x0000000000000008",
                        "desc": "AT&T US: B2/4/5/17/29/30/66 + n77/n78"},
    "us_verizon":      {"lte": "0x000080000000101A", "nr": "0x0000000000000008",
                        "desc": "Verizon US: B2/4/5/13/48/66 + C-band"},
    "global_unlocked": {"lte": "0x00007FFFFFFFFFFF", "nr": "0x000000000003E23F",
                        "desc": "All global bands — for unlocked international use"},
    "europe_4g":       {"lte": "0x0000000000180923", "nr": "0x0000000000002000",
                        "desc": "Europe: B1/2/3/5/7/8/20 + n78"},
    "asia_4g5g":       {"lte": "0x00000027083C0E1F", "nr": "0x0000000000012000",
                        "desc": "Asia: B1/3/5/8/28/38/40/41 + n41/n78"},
    "lte_only":        {"lte": "0x00007FFFFFFFFFFF", "nr": "0x0000000000000000",
                        "desc": "Force LTE only — disable 5G (saves battery)"},
    "5g_preferred":    {"lte": "0x00007FFFFFFFFFFF", "nr": "0x7FFFFFFFFFFFFFFF",
                        "desc": "5G preferred with LTE fallback"},
    "sub6_only":       {"lte": "0x00007FFFFFFFFFFF", "nr": "0x000000000003E23F",
                        "desc": "5G sub-6 only — no mmWave"},
    # ── US Carriers (complete) ─────────────────────────────────────────────
    "us_verizon_full": {
        "lte": "0x000080000000101A",
        "nr":  "0x0000000000000118",
        "desc": "Verizon full: B2/4/5/13/48/66 LTE + n5/n48/n66/n77 C-band + n260/n261 mmWave",
        "lte_bands":  [2, 4, 5, 13, 48, 66],
        "nr_bands":   ["n5","n48","n66","n77","n260","n261"],
        "notes":      "Verizon uses B13 as primary LTE + C-band (n77) for 5G Ultra Wideband",
    },
    "us_verizon_lte":  {
        "lte": "0x000000000000100A",
        "nr":  "0x0000000000000000",
        "desc": "Verizon LTE only: B2/4/13 core bands (most reliable)",
        "lte_bands": [2, 4, 13],
        "nr_bands":  [],
        "notes":     "Conservative — core Verizon bands only, LTE only",
    },
    "us_verizon_cbrs": {
        "lte": "0x0000214008880200",
        "nr":  "0x0000000000008118",
        "desc": "Verizon + CBRS (B48/n48): B2/4/5/13/48/66 + n48/n77/n260/n261",
        "lte_bands": [2, 4, 5, 13, 48, 66],
        "nr_bands":  ["n48","n77","n260","n261"],
        "notes":     "Includes CBRS B48/n48 for private network compatibility",
    },
    "us_tmobile_full": {
        "lte": "0x000001000300081A",
        "nr":  "0x0000000000020002",
        "desc": "T-Mobile full: B2/4/5/12/25/26/41/66/71 + n41/n71",
        "lte_bands": [2, 4, 5, 12, 25, 26, 41, 66, 71],
        "nr_bands":  ["n41","n71"],
        "notes":     "T-Mobile primary 5G: n41 (2.5GHz mid-band), n71 (600MHz coverage)",
    },
    "us_att_full": {
        "lte": "0x000000003001205A",
        "nr":  "0x0000000000000008",
        "desc": "AT&T full: B2/4/5/7/17/29/30/66 + n77/n78",
        "lte_bands": [2, 4, 5, 7, 17, 29, 30, 66],
        "nr_bands":  ["n77","n78"],
        "notes":     "AT&T uses B14 (FirstNet), B29 downlink-only, n77 C-band for 5G",
    },
    "us_firstnet": {
        "lte": "0x000000003001200A",
        "nr":  "0x0000000000000008",
        "desc": "FirstNet (AT&T): B2/4/14/17/29/30 priority bands",
        "lte_bands": [2, 4, 14, 17, 29, 30],
        "nr_bands":  ["n77"],
        "notes":     "B14 is FirstNet priority spectrum — first responder network",
    },
    "us_dish_boost": {
        "lte": "0x0000010000000002",
        "nr":  "0x0000000000002080",
        "desc": "Dish/Boost: B2/B66 LTE + n66/n70 5G",
        "lte_bands": [2, 66],
        "nr_bands":  ["n66","n70"],
        "notes":     "Dish Network uses AWS spectrum (B66/n66) as primary",
    },
    "us_cbrs_only": {
        "lte": "0x0000000080000000",
        "nr":  "0x0000000000008000",
        "desc": "CBRS only: B48 LTE + n48 5G (private/enterprise networks)",
        "lte_bands": [48],
        "nr_bands":  ["n48"],
        "notes":     "Citizens Broadband Radio Service — 3.5GHz private LTE/5G",
    },
    # ── International carriers ────────────────────────────────────────────
    "uk_full": {
        "lte": "0x000000000009A28B",
        "nr":  "0x0000000000004000",
        "desc": "UK all carriers: B1/2/3/4/7/8/20/28 + n78",
        "lte_bands": [1, 2, 3, 4, 7, 8, 20, 28],
        "nr_bands":  ["n78"],
    },
    "eu_full": {
        "lte": "0x000000000009A22B",
        "nr":  "0x0000000000006000",
        "desc": "Europe full: B1/2/3/5/7/8/20/28 + n78/n79",
        "lte_bands": [1, 2, 3, 5, 7, 8, 20, 28],
        "nr_bands":  ["n78","n79"],
    },
    "canada_full": {
        "lte": "0x000001000D8A08AA",
        "nr":  "0x0000000000002002",
        "desc": "Canada: B2/4/5/12/25/41/66/71 + n41/n66",
        "lte_bands": [2, 4, 5, 12, 25, 41, 66, 71],
        "nr_bands":  ["n41","n66"],
    },
    "australia_full": {
        "lte": "0x0000000008108823",
        "nr":  "0x0000000000004000",
        "desc": "Australia: B1/2/3/5/7/28/40 + n78",
        "lte_bands": [1, 2, 3, 5, 7, 28, 40],
        "nr_bands":  ["n78"],
    },
    "japan_full": {
        "lte": "0x0000000040108923",
        "nr":  "0x0000000000078000",
        "desc": "Japan: B1/2/3/8/18/19/21/28/42 + n77/n78/n79",
        "lte_bands": [1, 2, 3, 8, 18, 19, 21, 28, 42],
        "nr_bands":  ["n77","n78","n79"],
    },
    "korea_full": {
        "lte": "0x000000004008A061",
        "nr":  "0x0000000000004000",
        "desc": "South Korea: B1/3/5/6/7/8/18/42 + n78",
        "lte_bands": [1, 3, 5, 6, 7, 8, 18, 42],
        "nr_bands":  ["n78"],
    },
    "india_full": {
        "lte": "0x0000000000108823",
        "nr":  "0x0000000000004000",
        "desc": "India: B1/2/3/5/28/40 + n78",
        "lte_bands": [1, 2, 3, 5, 28, 40],
        "nr_bands":  ["n78"],
    },
    "china_full": {
        "lte": "0x0000000201800027",
        "nr":  "0x0000000000068000",
        "desc": "China: B1/2/3/4/5/34/38/39/40/41 + n41/n78/n79",
        "lte_bands": [1, 2, 3, 4, 5, 34, 38, 39, 40, 41],
        "nr_bands":  ["n41","n78","n79"],
    },
    "latam_full": {
        "lte": "0x00000000000D8A2B",
        "nr":  "0x0000000000002000",
        "desc": "Latin America: B1/2/3/4/5/7/12/28/66 + n66",
        "lte_bands": [1, 2, 3, 4, 5, 7, 12, 28, 66],
        "nr_bands":  ["n66"],
    },
}

# ── Firehose loaders (publicly known) ─────────────────────────────────────────
# Only listing chips where firehose is publicly documented.
# A wrong loader will not run — it simply fails handshake, no brick risk.

FIREHOSE_INFO = {
    "SDM845": {"notes": "Available from TWRP/LineageOS repos for many devices"},
    "SM8150": {"notes": "Available from TWRP/LineageOS for Pixel 4, OnePlus 7"},
    "SM8250": {"notes": "Available for OnePlus 8, Pixel 5 series"},
    "SM8350": {"notes": "Available for OnePlus 9, Pixel 6 (requires signed)"},
    "SDM710": {"notes": "Available for Pixel 3a series"},
    "SDM660": {"notes": "Wide availability — many Xiaomi/Redmi devices"},
    "SDM636": {"notes": "Available for Xiaomi devices"},
    "SM6150": {"notes": "Available for Pixel 3a XL"},
    "SM7150": {"notes": "Available for OnePlus Nord, Pixel 4a"},
    "SDM450": {"notes": "Wide availability — budget devices"},
}

def identify_snapdragon(platform_str: str, hardware_str: str = "") -> dict:
    """Identify Snapdragon chip from platform/hardware strings."""
    combined = f"{platform_str} {hardware_str}".lower()
    for chip_id, sigs in SNAPDRAGON_SIGNATURES.items():
        for sig in sigs:
            if sig.lower() in combined:
                info = SNAPDRAGON_CHIPS.get(chip_id, {})
                return {"vendor": "qualcomm", "key": chip_id, **info}
    # Try direct platform match
    for chip_id, info in SNAPDRAGON_CHIPS.items():
        if chip_id.lower() in combined:
            return {"vendor": "qualcomm", "key": chip_id, **info}
    return {}

def get_modem_info(modem_name: str) -> dict:
    """Return modem capability dict for a given X-series modem."""
    return QUALCOMM_MODEMS.get(modem_name, {})
