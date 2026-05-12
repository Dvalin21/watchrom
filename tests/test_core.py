"""
tests/test_core.py — Core framework tests (pytest)
Run: python3 -m pytest tests/test_core.py -v
     OR: python3 tests/run_tests.py (no pytest needed)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestResult:
    def setup_method(self):
        from core.interfaces import Result, Status
        self.Result = Result
        self.Status = Status

    def test_ok_truthy(self):
        assert bool(self.Result.ok("success")) is True

    def test_fail_falsy(self):
        assert bool(self.Result.fail("error")) is False

    def test_skip_status(self):
        assert self.Result.skip("n/a").status == self.Status.SKIPPED

    def test_ok_carries_data(self):
        r = self.Result.ok("done", foo="bar", count=42)
        assert r.data["foo"] == "bar"
        assert r.data["count"] == 42

    def test_fail_carries_error(self):
        r = self.Result.fail("boom", "context")
        assert r.error == "boom"
        assert r.message == "context"


class TestRegistry:
    def setup_method(self):
        import core
        from core.registry import all_vendors, all_bands
        self.vendors = all_vendors()
        self.bands   = all_bands()

    def test_six_vendors(self):
        assert len(self.vendors) == 6

    def test_all_keys(self):
        for k in ["mtk","unisoc","rockchip","allwinner","realtek","qualcomm"]:
            assert k in self.vendors

    def test_four_band_backends(self):
        assert len(self.bands) >= 4


class TestPipeline:
    def setup_method(self):
        from core.pipeline import list_pipelines
        from core.interfaces import Result
        self.pipes  = list_pipelines()
        self.Result = Result

    def test_six_pipelines(self):
        assert len(self.pipes) >= 6

    def test_root_device_7_steps(self):
        assert len(self.pipes["root-device"].dry_run({})) == 7

    def test_full_backup_4_steps(self):
        assert len(self.pipes["full-backup"].dry_run({})) == 4

    def test_avb_disable_4_steps(self):
        assert len(self.pipes["avb-disable"].dry_run({})) == 4

    def test_wearos_setup_6_steps(self):
        assert len(self.pipes["wearos-setup"].dry_run({})) == 6

    def test_configure_bands_4_steps(self):
        assert len(self.pipes["configure-bands"].dry_run({})) == 4

    def test_dry_run_no_execution(self):
        from core.pipeline import Pipeline, Task
        ran = []
        def side(ctx): ran.append(1); return self.Result.ok("ran")
        p = Pipeline("dry","test")
        p.add(Task("s", side, "step", required=True))
        p.dry_run({})
        assert len(ran) == 0

    def test_context_shared(self):
        from core.pipeline import Pipeline, Task
        def w(ctx): ctx["x"]=99; return self.Result.ok("w")
        def r(ctx):
            assert ctx.get("x") == 99
            return self.Result.ok("r")
        p = Pipeline("ctx","test")
        p.add(Task("w",w,"W",True))
        p.add(Task("r",r,"R",True))
        assert p.run({}).success


class TestVendorDetection:
    def setup_method(self):
        import core
        from core.vendors import (MTKVendor, UnisocVendor, RockchipVendor,
                                   AllwinnerVendor, RealtekVendor, QualcommVendor)
        self.mtk      = MTKVendor()
        self.unisoc   = UnisocVendor()
        self.rockchip = RockchipVendor()
        self.allwinner= AllwinnerVendor()
        self.realtek  = RealtekVendor()
        self.qualcomm = QualcommVendor()

    def _p(self, platform, hw=""):
        return {"ro.board.platform": platform, "ro.hardware": hw}

    def test_mtk_detects(self):
        r = self.mtk.detect(self._p("mt6761"))
        assert r is not None and r.vendor == "mtk"

    def test_rk_detects(self):
        r = self.rockchip.detect(self._p("rk3588"))
        assert r is not None and r.vendor == "rockchip"

    def test_unisoc_detects(self):
        r = self.unisoc.detect(self._p("sc9863a"))
        assert r is not None and r.vendor == "unisoc"

    def test_cross_detect_none(self):
        assert self.mtk.detect(self._p("rk3588")) is None
        assert self.rockchip.detect(self._p("mt6761")) is None
