"""
tests/test_bands.py — Band configuration and carrier profile tests
Run: python3 -m pytest tests/test_bands.py -v
"""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestLTEBitmask:
    def setup_method(self):
        from modules.qualcomm import build_lte_bitmask, parse_lte_bitmask
        self.build = build_lte_bitmask
        self.parse = parse_lte_bitmask

    def test_returns_tuple_of_two_ints(self):
        low, high = self.build([1, 2, 3])
        assert isinstance(low, int) and isinstance(high, int)

    def test_both_words_fit_64_bits(self):
        low, high = self.build(list(range(1, 129)))
        assert low < (1 << 64) and high < (1 << 64)

    def test_band1_bit0_of_low(self):
        low, high = self.build([1])
        assert low & 1 and high == 0

    def test_band64_bit63_of_low(self):
        low, high = self.build([64])
        assert low & (1 << 63) and high == 0

    def test_band65_bit0_of_high(self):
        low, high = self.build([65])
        assert low == 0 and high & 1

    def test_band66_in_high_word(self):
        """B66 AWS-3 - critical for T-Mobile and AT&T."""
        low, high = self.build([66])
        assert low == 0 and high & (1 << 1)

    def test_band71_in_high_word(self):
        """B71 600MHz - T-Mobile primary coverage."""
        low, high = self.build([71])
        assert low == 0 and high & (1 << 6)

    def test_round_trip_basic(self):
        bands = [1, 2, 4, 5, 12, 13, 20]
        low, high = self.build(bands)
        assert sorted(self.parse(low, high)) == sorted(bands)

    def test_round_trip_high_bands(self):
        bands = [2, 4, 5, 12, 13, 48, 66, 71]
        low, high = self.build(bands)
        assert sorted(self.parse(low, high)) == sorted(bands)

    def test_round_trip_all_1_to_128(self):
        bands = list(range(1, 129))
        low, high = self.build(bands)
        assert sorted(self.parse(low, high)) == sorted(bands)

    def test_empty_returns_zeros(self):
        low, high = self.build([])
        assert low == 0 and high == 0

    def test_verizon_b13_survives(self):
        bands = [2, 4, 5, 13, 48, 66]
        low, high = self.build(bands)
        assert 13 in self.parse(low, high)

    def test_tmobile_b71_survives(self):
        bands = [2, 4, 5, 12, 25, 41, 66, 71]
        low, high = self.build(bands)
        assert high != 0
        decoded = self.parse(low, high)
        assert 71 in decoded and 66 in decoded


class TestCarrierProfiles:
    def setup_method(self):
        from modules.modem_bands import CARRIER_PROFILES
        self.profiles = CARRIER_PROFILES
        self.required = {
            "display","lte_bands","nr_sub6",
            "primary_lte","primary_nr","lte_hex_low","nr_hex"
        }

    def test_minimum_sixteen_carriers(self):
        assert len(self.profiles) >= 16

    def test_all_have_required_fields(self):
        for name, p in self.profiles.items():
            missing = self.required - set(p.keys())
            assert not missing, f"Carrier '{name}' missing: {missing}"

    def test_all_hex_masks_parse(self):
        for name, p in self.profiles.items():
            try:
                int(p["lte_hex_low"], 16)
                int(p["nr_hex"], 16)
            except ValueError as e:
                pytest.fail(f"Carrier '{name}' invalid hex: {e}")

    def test_all_lte_bands_ints(self):
        for name, p in self.profiles.items():
            for b in p["lte_bands"]:
                assert isinstance(b, int), f"{name}: band {b!r} not int"

    def test_verizon_b13_primary(self):
        vz = self.profiles["verizon"]
        assert 13 in vz["lte_bands"]
        assert vz["primary_lte"] == 13

    def test_verizon_n77_cband(self):
        assert "n77" in self.profiles["verizon"]["nr_sub6"]

    def test_verizon_mmwave_n260_n261(self):
        vz = self.profiles["verizon"]
        assert "n260" in vz.get("nr_mmwave", [])
        assert "n261" in vz.get("nr_mmwave", [])

    def test_verizon_b48_cbrs(self):
        assert 48 in self.profiles["verizon"]["lte_bands"]

    def test_verizon_b66_aws3(self):
        assert 66 in self.profiles["verizon"]["lte_bands"]

    def test_tmobile_b71_600mhz(self):
        assert 71 in self.profiles["tmobile"]["lte_bands"]

    def test_tmobile_n41_midband(self):
        assert "n41" in self.profiles["tmobile"]["nr_sub6"]

    def test_att_b14_firstnet(self):
        assert 14 in self.profiles["att"]["lte_bands"]

    def test_firstnet_primary_b14(self):
        assert self.profiles["firstnet"]["primary_lte"] == 14

    def test_global_roaming_exists(self):
        assert "global_roaming" in self.profiles

    def test_global_roaming_has_many_bands(self):
        gr = self.profiles["global_roaming"]
        assert len(gr["lte_bands"]) > 10

    def test_eu_has_b20(self):
        assert 20 in self.profiles["eu_generic"]["lte_bands"]

    def test_australia_has_b28(self):
        assert 28 in self.profiles["australia_telstra"]["lte_bands"]

    def test_japan_has_b19(self):
        assert 19 in self.profiles["japan_docomo"]["lte_bands"]


class TestVerizonReference:
    def setup_method(self):
        from modules.qualcomm_chips import VERIZON_BANDS
        self.vz = VERIZON_BANDS

    def test_has_all_sections(self):
        for section in ["lte", "nr_sub6", "nr_mmwave", "notes"]:
            assert section in self.vz

    def test_b13_is_primary_type(self):
        assert 13 in self.vz["lte"]
        assert self.vz["lte"][13]["type"] == "primary"

    def test_n77_is_primary5g_type(self):
        assert "n77" in self.vz["nr_sub6"]
        assert self.vz["nr_sub6"]["n77"]["type"] == "primary5g"

    def test_mmwave_n260_n261(self):
        assert "n260" in self.vz["nr_mmwave"]
        assert "n261" in self.vz["nr_mmwave"]

    def test_has_at_least_three_notes(self):
        assert len(self.vz["notes"]) >= 3

    def test_b13_freq_is_700(self):
        assert "700" in self.vz["lte"][13]["freq"]

    def test_n77_freq_is_cband(self):
        assert "3.7" in self.vz["nr_sub6"]["n77"]["freq"] or                "C-band" in self.vz["nr_sub6"]["n77"]["notes"]


class TestBandPresets:
    def setup_method(self):
        from modules.qualcomm_chips import BAND_PRESETS
        self.presets = BAND_PRESETS

    def test_minimum_27_presets(self):
        assert len(self.presets) >= 27

    def test_all_have_lte_nr_desc(self):
        for name, p in self.presets.items():
            for key in ("lte", "nr", "desc"):
                assert key in p, f"Preset '{name}' missing '{key}'"

    def test_all_hex_values_parse(self):
        for name, p in self.presets.items():
            try:
                int(p["lte"], 16)
                int(p["nr"],  16)
            except ValueError as e:
                pytest.fail(f"Preset '{name}' bad hex: {e}")

    def test_lte_only_has_zero_nr(self):
        assert int(self.presets["lte_only"]["nr"], 16) == 0

    def test_all_bands_nonzero(self):
        p = self.presets["all_bands"]
        assert int(p["lte"], 16) > 0
        assert int(p["nr"],  16) > 0

    def test_verizon_full_encodes_b13(self):
        from modules.qualcomm import parse_lte_bitmask
        low = int(self.presets["us_verizon_full"]["lte"], 16) & 0xFFFFFFFFFFFFFFFF
        bands = parse_lte_bitmask(low)
        assert 13 in bands

    def test_us_tmobile_full_has_nr(self):
        p = self.presets["us_tmobile_full"]
        assert int(p["nr"], 16) > 0


class TestChipDatabase:
    def setup_method(self):
        from modules.chipsets import (MTK_CHIPS, UNISOC_CHIPS, ROCKCHIP_CHIPS,
                                       ALLWINNER_CHIPS, REALTEK_CHIPS)
        from modules.qualcomm_chips import SNAPDRAGON_CHIPS
        self.all_dbs = [
            ("mtk",      MTK_CHIPS,
             {"name","platform","arch","year","watch","brom"}),
            ("unisoc",   UNISOC_CHIPS,
             {"name","platform","arch","year","watch","fdl"}),
            ("rockchip", ROCKCHIP_CHIPS,
             {"name","platform","arch","year","type","maskrom"}),
            ("allwinner",ALLWINNER_CHIPS,
             {"name","platform","arch","year","type","fel"}),
            ("realtek",  REALTEK_CHIPS,
             {"name","platform","arch","year","type"}),
            ("qualcomm", SNAPDRAGON_CHIPS,
             {"name","modem","year","tier","edl","bands_5g"}),
        ]

    def test_total_at_least_137(self):
        total = sum(len(db) for _, db, _ in self.all_dbs)
        assert total >= 137, f"Expected >=137 chips, got {total}"

    def test_all_entries_have_required_fields(self):
        for vendor, db, required in self.all_dbs:
            for chip_id, info in db.items():
                missing = required - set(info.keys())
                assert not missing, f"{vendor}/{chip_id} missing: {missing}"

    def test_mtk_has_watch_chips(self):
        from modules.chipsets import MTK_CHIPS
        watch = [k for k, v in MTK_CHIPS.items() if v.get("watch")]
        assert len(watch) >= 3

    def test_unisoc_has_watch_chips(self):
        from modules.chipsets import UNISOC_CHIPS
        watch = [k for k, v in UNISOC_CHIPS.items() if v.get("watch")]
        assert len(watch) >= 5

    def test_detect_mtk_from_platform_string(self):
        from modules.chipsets import identify_mtk_chip, MTK_CHIPS
        for chip_id, info in list(MTK_CHIPS.items())[:6]:
            result = identify_mtk_chip(info["platform"])
            assert result, f"Could not detect {chip_id}"
            assert result.get("vendor") == "mtk"

    def test_detect_unisoc_from_platform_string(self):
        from modules.chipsets import identify_unisoc_chip, UNISOC_CHIPS
        for chip_id, info in list(UNISOC_CHIPS.items())[:6]:
            result = identify_unisoc_chip(info["platform"])
            assert result, f"Could not detect {chip_id}"
            assert result.get("vendor") == "unisoc"

    def test_detect_rockchip_from_platform_string(self):
        from modules.chipsets import identify_rockchip_chip, ROCKCHIP_CHIPS
        for chip_id, info in list(ROCKCHIP_CHIPS.items())[:6]:
            result = identify_rockchip_chip(info["platform"])
            assert result, f"Could not detect {chip_id}"
            assert result.get("vendor") == "rockchip"

    def test_qualcomm_all_have_modem(self):
        from modules.qualcomm_chips import SNAPDRAGON_CHIPS
        for chip_id, info in SNAPDRAGON_CHIPS.items():
            assert info.get("modem"), f"{chip_id} missing modem field"
