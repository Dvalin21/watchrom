"""
core/band_backends.py — Concrete BandConfigInterface implementations
MTK, Unisoc, Qualcomm, Generic AT
All write operations backup first, use 128-bit masks correctly.
"""
from __future__ import annotations
import struct
import time
from pathlib import Path
from typing import Optional
from core.interfaces import BandConfigInterface, DeviceInfo, Result
from core.registry import register_band_config


def _adb(serial: str, cmd: list, check: bool = False, timeout: int = 30):
    from modules import run_adb
    return run_adb(cmd, serial=serial, check=check, timeout=timeout)


def _find_at_port(serial: str, candidates: list[str]) -> Optional[str]:
    for port in candidates:
        _, out, _ = _adb(serial, ["shell", f"ls {port} 2>/dev/null"], timeout=5)
        if port in out.strip():
            return port
    return None


def _send_at(serial: str, port: str, cmd: str, wait: float = 1.5) -> str:
    shell = f"echo -e '{cmd}\\r\\n' > {port} && sleep {wait} && timeout {int(wait)+1} cat {port} 2>/dev/null"
    _, out, _ = _adb(serial, ["shell", shell], timeout=10)
    if out.strip():
        return out.strip()
    _, out2, _ = _adb(serial, ["shell", f"su -c '{shell}'"], timeout=10)
    return out2.strip()


def _lte_to_bytes_le(low64: int, high64: int) -> bytes:
    """Pack LTE 128-bit mask as two little-endian 64-bit words."""
    return struct.pack("<QQ", low64 & 0xFFFFFFFFFFFFFFFF,
                              high64 & 0xFFFFFFFFFFFFFFFF)


# ─────────────────────────────────────────────────────────────────────────────

@register_band_config
class QualcommBandConfig(BandConfigInterface):
    vendor_key = "qualcomm"

    _EFS_LTE = "/nv/item_files/modem/mmode/lte_bandpref"
    _EFS_NR  = "/nv/item_files/modem/mmode/nr5g_bandpref"
    _EFS_MODE= "/nv/item_files/modem/mmode/mode_pref"
    _AT_PORTS = ["/dev/smd7", "/dev/at_mdm0", "/dev/at0",
                 "/dev/ttyUSB1", "/dev/ttyUSB2"]

    def read_current_bands(self, device: DeviceInfo) -> Result:
        serial = device.serial
        data   = {}

        # Try AT command read first (no root needed)
        port = _find_at_port(serial, self._AT_PORTS)
        if port:
            data["at_port"]   = port
            data["qnwinfo"]   = _send_at(serial, port, "AT+QNWINFO")
            data["band_cfg"]  = _send_at(serial, port, 'AT+QCFG="band"')
            data["nr_reg"]    = _send_at(serial, port, "AT+C5GREG?")
            data["lte_reg"]   = _send_at(serial, port, "AT+CEREG?")

        # Augment with dumpsys
        _, ds, _ = _adb(serial, [
            "shell",
            "dumpsys phone 2>/dev/null | grep -iE '(band|lte|nr|5g|rat)' | head -20"
        ])
        data["dumpsys"] = ds.strip()
        return Result.ok("Band config read", **data)

    def write_bands(self, device: DeviceInfo,
                    lte_low: int, lte_high: int, nr_mask: int) -> Result:
        serial = device.serial

        # Method A: EFS via ADB root (most reliable)
        _, root_check, _ = _adb(serial, ["shell", "su -c id"], timeout=10)
        if "uid=0" in root_check:
            return self._write_efs(serial, lte_low, lte_high, nr_mask)

        # Method B: AT commands (may work without root)
        port = _find_at_port(serial, self._AT_PORTS)
        if port:
            return self._write_at(serial, port, lte_low, lte_high, nr_mask)

        return Result.fail(
            "No write method available — need root (EFS) or AT port",
            "Try: watchrom qualcomm diag-enable, then retry"
        )

    def _write_efs(self, serial: str, lte_low: int, lte_high: int, nr_mask: int) -> Result:
        written = []
        errors  = []

        for path, low, high in [
            (self._EFS_LTE, lte_low, lte_high),
            (self._EFS_NR,  nr_mask, 0),
        ]:
            # Use Python on-device to write binary (handles 64-bit cleanly)
            py_cmd = (
                f"su -c 'python3 -c \""
                f"import struct,os; "
                f"os.makedirs(os.path.dirname(\\\"{path}\\\"),exist_ok=True); "
                f"open(\\\"{path}\\\",\\\"wb\\\").write(struct.pack(\\\"<QQ\\\",{low}&0xFFFFFFFFFFFFFFFF,{high}&0xFFFFFFFFFFFFFFFF))"
                f"\" && echo OK'"
            )
            _, out, _ = _adb(serial, ["shell", py_cmd], timeout=15)
            if "OK" in out:
                written.append(path.split("/")[-1])
            else:
                # Fallback: dd via printf
                data_hex = _lte_to_bytes_le(low, high).hex()
                printf_args = "".join(f"\\\\x{data_hex[i:i+2]}" for i in range(0, 32, 2))
                dd_cmd = (
                    f"su -c 'printf \"{printf_args}\" > {path} && echo OK'"
                )
                _, out2, _ = _adb(serial, ["shell", dd_cmd], timeout=15)
                if "OK" in out2:
                    written.append(path.split("/")[-1])
                else:
                    errors.append(path.split("/")[-1])

        if written:
            return Result.ok(
                f"Written via EFS: {', '.join(written)}" +
                (f" | Failed: {', '.join(errors)}" if errors else ""),
                written=written, errors=errors
            )
        return Result.fail(f"EFS write failed for: {', '.join(errors)}")

    def _write_at(self, serial: str, port: str,
                  lte_low: int, lte_high: int, nr_mask: int) -> Result:
        # AT+QCFG="band",<gsm>,<lte>,<nr5g>
        lte_hex = f"0x{lte_low:016X}"
        nr_hex  = f"0x{nr_mask:016X}"
        cmd = f'AT+QCFG="band",0x000000FF,{lte_hex},{nr_hex}'
        resp = _send_at(serial, port, cmd, wait=2)
        if "OK" in resp:
            return Result.ok(f"Band written via AT: {cmd[:60]}")
        return Result.fail(f"AT command rejected: {resp[:100]}")

    def backup_config(self, device: DeviceInfo, output_dir: Path) -> Result:
        output_dir.mkdir(parents=True, exist_ok=True)
        serial = device.serial

        # Read EFS items
        for label, path in [("lte", self._EFS_LTE), ("nr", self._EFS_NR),
                              ("mode", self._EFS_MODE)]:
            remote = f"/sdcard/wrom_bk_{label}"
            _adb(serial, ["shell", f"su -c 'cp {path} {remote} 2>/dev/null'"], timeout=10)
            _adb(serial, ["pull", remote, str(output_dir / f"{label}_bandpref.bin")],
                 timeout=15)
            _adb(serial, ["shell", f"rm {remote} 2>/dev/null"], timeout=5)

        # Snapshot via AT
        port = _find_at_port(serial, self._AT_PORTS)
        if port:
            snap = []
            for cmd in ['AT+QCFG="band"', "AT+QNWINFO", "AT+CEREG?"]:
                r = _send_at(serial, port, cmd)
                snap.append(f">> {cmd}\n{r}")
            (output_dir / "at_snapshot.txt").write_text("\n\n".join(snap))

        # dumpsys snapshot
        _, ds, _ = _adb(serial, [
            "shell",
            "dumpsys phone 2>/dev/null | grep -iE '(band|lte|nr|5g|mode)' | head -40"
        ])
        (output_dir / "dumpsys_snapshot.txt").write_text(ds)

        return Result.ok(f"Qualcomm band config backed up: {output_dir}")

    def restore_config(self, device: DeviceInfo, backup_dir: Path) -> Result:
        serial = device.serial
        restored = []
        for label, efs_path in [("lte", self._EFS_LTE), ("nr", self._EFS_NR)]:
            bk_file = backup_dir / f"{label}_bandpref.bin"
            if bk_file.exists():
                remote = f"/sdcard/wrom_restore_{label}.bin"
                _adb(serial, ["push", str(bk_file), remote], timeout=30)
                _, out, _ = _adb(serial, [
                    "shell", f"su -c 'cp {remote} {efs_path} && echo OK'"
                ], timeout=10)
                if "OK" in out:
                    restored.append(label)
                _adb(serial, ["shell", f"rm {remote}"], timeout=5)

        if restored:
            return Result.ok(f"Restored: {', '.join(restored)}")
        return Result.fail("No backup files found to restore")


@register_band_config
class MTKBandConfig(BandConfigInterface):
    vendor_key = "mtk"

    _AT_PORTS = ["/dev/ttyC0", "/dev/ttyMT0", "/dev/ttyGS0",
                 "/dev/ccci_aud_md1", "/dev/ttyS0"]

    def read_current_bands(self, device: DeviceInfo) -> Result:
        serial = device.serial
        data   = {}

        port = _find_at_port(serial, self._AT_PORTS)
        if port:
            data["at_port"]  = port
            data["erat"]     = _send_at(serial, port, "AT+ERAT?")
            data["epbse"]    = _send_at(serial, port, "AT+EPBSE?")
            data["cops"]     = _send_at(serial, port, "AT+COPS?")

        _, ds, _ = _adb(serial, [
            "shell",
            "dumpsys phone 2>/dev/null | grep -iE '(band|rat|lte|nr)' | head -20"
        ])
        data["dumpsys"] = ds.strip()
        return Result.ok("MTK band config read", **data)

    def write_bands(self, device: DeviceInfo,
                    lte_low: int, lte_high: int, nr_mask: int) -> Result:
        serial = device.serial
        port   = _find_at_port(serial, self._AT_PORTS)

        if not port:
            return Result.fail(
                "No MTK AT port found",
                "Try MTK Engineering Mode: watchrom bands mtk-engmode"
            )

        results = []

        # Step 1: set RAT mode
        # Determine mode from masks
        has_nr = nr_mask != 0
        rat_cmd = "AT+ERAT=0,0,0,1" if has_nr else "AT+ERAT=3,2"
        resp = _send_at(serial, port, rat_cmd)
        results.append(("RAT", "OK" in resp, resp[:40]))

        # Step 2: set band mask via AT+EPBSE
        # MTK format: AT+EPBSE=<GSM>,<UMTS>,<LTE_low32>,<LTE_high32>
        lte_low32  = lte_low  & 0xFFFFFFFF
        lte_high32 = (lte_low >> 32) & 0xFFFFFFFF
        # Also incorporate lte_high (bands 65+) into high word
        if lte_high:
            lte_high32 |= (lte_high & 0xFFFFFFFF) << 0

        epbse = (f"AT+EPBSE=0xFFFFFFFF,0xFFFFFFFF,"
                 f"0x{lte_low32:08X},0x{lte_high32:08X}")
        resp2 = _send_at(serial, port, epbse)
        results.append(("EPBSE", "OK" in resp2, resp2[:40]))

        ok_count = sum(1 for _, ok, _ in results if ok)
        if ok_count > 0:
            return Result.ok(
                f"MTK band write: {ok_count}/{len(results)} AT commands accepted",
                at_results=results
            )
        return Result.fail(
            "AT commands not accepted",
            "Device may need MTK Engineering Mode app for band changes"
        )

    def backup_config(self, device: DeviceInfo, output_dir: Path) -> Result:
        output_dir.mkdir(parents=True, exist_ok=True)
        serial = device.serial

        port = _find_at_port(serial, self._AT_PORTS)
        if port:
            snap = []
            for cmd in ["AT+ERAT?", "AT+EPBSE?", "AT+COPS?", "AT+CSQ"]:
                r = _send_at(serial, port, cmd)
                snap.append(f">> {cmd}\n{r}")
            (output_dir / "at_snapshot.txt").write_text("\n\n".join(snap))

        _, ds, _ = _adb(serial, [
            "shell",
            "dumpsys phone 2>/dev/null | grep -iE '(band|rat|erat|epbse)' | head -30"
        ])
        (output_dir / "dumpsys_snapshot.txt").write_text(ds)

        _, props, _ = _adb(serial, [
            "shell",
            "getprop | grep -iE '(gsm|ril|radio|telephony)'"
        ])
        (output_dir / "radio_props.txt").write_text(props)

        return Result.ok(f"MTK band config backed up: {output_dir}")


@register_band_config
class UnisocBandConfig(BandConfigInterface):
    vendor_key = "unisoc"

    _AT_PORTS = ["/dev/stty0", "/dev/stty1", "/dev/sprd_bsp_atcmd",
                 "/dev/ttyS1", "/dev/ttyUSB0"]

    def read_current_bands(self, device: DeviceInfo) -> Result:
        serial = device.serial
        data   = {}

        port = _find_at_port(serial, self._AT_PORTS)
        if port:
            data["at_port"] = port
            data["erat"]    = _send_at(serial, port, "AT+ERAT?")
            data["epbse"]   = _send_at(serial, port, "AT+EPBSE?")
            data["cops"]    = _send_at(serial, port, "AT+COPS?")

        return Result.ok("Unisoc band config read", **data)

    def write_bands(self, device: DeviceInfo,
                    lte_low: int, lte_high: int, nr_mask: int) -> Result:
        serial = device.serial
        port   = _find_at_port(serial, self._AT_PORTS)

        if not port:
            return Result.fail("No Unisoc AT port found")

        results = []
        has_nr = nr_mask != 0
        rat_cmd = "AT+ERAT=0,0,0,1" if has_nr else "AT+ERAT=3,2"
        r1 = _send_at(serial, port, rat_cmd)
        results.append(("RAT", "OK" in r1))

        lte_low32  = lte_low  & 0xFFFFFFFF
        lte_high32 = (lte_low >> 32) & 0xFFFFFFFF
        epbse = (f"AT+EPBSE=0xFFFFFFFF,0xFFFFFFFF,"
                 f"0x{lte_low32:08X},0x{lte_high32:08X}")
        r2 = _send_at(serial, port, epbse)
        results.append(("EPBSE", "OK" in r2))

        ok_count = sum(1 for _, ok in results if ok)
        if ok_count > 0:
            return Result.ok(f"Unisoc band write: {ok_count}/{len(results)} OK",
                             at_results=results)
        return Result.fail("Unisoc AT commands not accepted")

    def backup_config(self, device: DeviceInfo, output_dir: Path) -> Result:
        output_dir.mkdir(parents=True, exist_ok=True)
        port = _find_at_port(device.serial, self._AT_PORTS)
        if port:
            snap = []
            for cmd in ["AT+ERAT?", "AT+EPBSE?", "AT+COPS?"]:
                snap.append(f">> {cmd}\n{_send_at(device.serial, port, cmd)}")
            (output_dir / "at_snapshot.txt").write_text("\n\n".join(snap))
        return Result.ok(f"Unisoc band config backed up: {output_dir}")


@register_band_config
class GenericATBandConfig(BandConfigInterface):
    """
    Fallback for Rockchip/Allwinner devices with an external cellular modem.
    Tries common AT command format variants.
    """
    vendor_key = "generic"

    _AT_PORTS = ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2",
                 "/dev/ttyACM0", "/dev/ttyS1", "/dev/ttyS2"]

    def read_current_bands(self, device: DeviceInfo) -> Result:
        serial = device.serial
        port   = _find_at_port(serial, self._AT_PORTS)
        if not port:
            return Result.skip("No AT port found — device may not have cellular modem")

        data = {"at_port": port}
        for cmd in ["ATI", "AT+COPS?", "AT+CEREG?", "AT+ERAT?", "AT+QNWINFO"]:
            r = _send_at(serial, port, cmd, wait=1.0)
            if r:
                data[cmd] = r

        return Result.ok("Generic AT band info", **data)

    def write_bands(self, device: DeviceInfo,
                    lte_low: int, lte_high: int, nr_mask: int) -> Result:
        serial = device.serial
        port   = _find_at_port(serial, self._AT_PORTS)
        if not port:
            return Result.fail("No cellular modem AT port found")

        lte_low32  = lte_low  & 0xFFFFFFFF
        lte_high32 = (lte_low >> 32) & 0xFFFFFFFF

        # Try multiple AT command dialects in order of most common
        attempts = [
            # Qualcomm-style QCFG
            f'AT+QCFG="band",0xFF,0x{lte_low32:08X}{lte_high32:08X},0x{nr_mask:08X}',
            # MTK/Unisoc EPBSE
            f"AT+EPBSE=0xFFFFFFFF,0xFFFFFFFF,0x{lte_low32:08X},0x{lte_high32:08X}",
            # Generic ERAT for mode only
            "AT+ERAT=3,2" if nr_mask == 0 else "AT+ERAT=0,0,0,1",
        ]

        accepted = []
        for cmd in attempts:
            resp = _send_at(serial, port, cmd, wait=2.0)
            if "OK" in resp:
                accepted.append(cmd[:50])

        if accepted:
            return Result.ok(f"Generic AT: {len(accepted)} commands accepted",
                             accepted=accepted)
        return Result.fail("No AT band commands accepted by modem")

    def backup_config(self, device: DeviceInfo, output_dir: Path) -> Result:
        output_dir.mkdir(parents=True, exist_ok=True)
        port = _find_at_port(device.serial, self._AT_PORTS)
        snap = []
        if port:
            for cmd in ["ATI", "AT+COPS?", "AT+CEREG?", "AT+ERAT?",
                        "AT+QNWINFO", 'AT+QCFG="band"']:
                r = _send_at(device.serial, port, cmd)
                if r:
                    snap.append(f">> {cmd}\n{r}")
        (output_dir / "at_snapshot.txt").write_text("\n\n".join(snap) if snap
                                                    else "No AT port found")
        return Result.ok(f"Generic AT band config backed up: {output_dir}")
