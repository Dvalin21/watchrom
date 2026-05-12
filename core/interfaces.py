"""
core/interfaces.py — Abstract base interfaces for WatchROM framework

Every vendor implementation and tool wrapper must satisfy these contracts.
This turns WatchROM from a tool aggregator into a proper framework where:
  - New vendors are added by implementing VendorInterface
  - New pipelines are added by composing TaskNode objects
  - New analyzers are added by implementing AnalyzerInterface
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Callable, Any
import time
import hashlib


# ── Result types ──────────────────────────────────────────────────────────────

class Status(Enum):
    OK      = auto()
    FAILED  = auto()
    SKIPPED = auto()
    PARTIAL = auto()


@dataclass
class Result:
    """Standardized return type for all framework operations."""
    status:  Status
    message: str              = ""
    data:    dict             = field(default_factory=dict)
    error:   Optional[str]    = None
    elapsed: float            = 0.0

    @classmethod
    def ok(cls, message: str = "", **data) -> "Result":
        return cls(Status.OK, message, data)

    @classmethod
    def fail(cls, error: str, message: str = "") -> "Result":
        return cls(Status.FAILED, message, error=error)

    @classmethod
    def skip(cls, reason: str = "") -> "Result":
        return cls(Status.SKIPPED, reason)

    def ok_(self) -> bool:
        return self.status == Status.OK

    def __bool__(self) -> bool:
        return self.status == Status.OK


@dataclass
class ImageInfo:
    """Describes any firmware/partition image file."""
    path:        Path
    size_bytes:  int
    sha256:      str
    format:      str           = "unknown"
    vendor:      str           = "unknown"
    partition:   str           = "unknown"
    metadata:    dict          = field(default_factory=dict)

    @classmethod
    def from_path(cls, path: Path, **kwargs) -> "ImageInfo":
        path = Path(path)
        size = path.stat().st_size if path.exists() else 0
        sha  = _sha256(path) if path.exists() else ""
        return cls(path=path, size_bytes=size, sha256=sha, **kwargs)

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Device interface ──────────────────────────────────────────────────────────

@dataclass
class DeviceInfo:
    """Standardized device description returned by all vendor detectors."""
    serial:       str
    vendor:       str           # qualcomm | mtk | unisoc | rockchip | allwinner | realtek
    chipset:      str           # e.g. SM8550, MT6761, SC9863A
    arch:         str           # arm | arm64
    android_ver:  str           = ""
    model:        str           = ""
    device:       str           = ""
    ab_partitions: bool         = False
    rooted:       bool          = False
    bootloader:   str           = "unknown"  # locked | unlocked | unknown
    avb_version:  str           = ""
    adb_online:   bool          = True
    fastboot:     bool          = False
    props:        dict          = field(default_factory=dict)
    partitions:   list          = field(default_factory=list)


# ── Vendor interface ──────────────────────────────────────────────────────────

class VendorInterface(ABC):
    """
    Abstract contract every chipset vendor must implement.
    Concrete classes: MTKVendor, UnisocVendor, RockchipVendor,
                      AllwinnerVendor, RealtekVendor, QualcommVendor
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable vendor name, e.g. 'MediaTek'"""
        ...

    @property
    @abstractmethod
    def key(self) -> str:
        """Short machine key, e.g. 'mtk'"""
        ...

    @abstractmethod
    def detect(self, props: dict) -> Optional[DeviceInfo]:
        """
        Given Android system properties, return a DeviceInfo if this
        vendor matches, else return None.
        """
        ...

    @abstractmethod
    def partition_list(self, device: DeviceInfo) -> list[str]:
        """Return ordered list of partition names for this device."""
        ...

    @abstractmethod
    def download_mode_entry(self) -> str:
        """Return human-readable download/flash mode entry instructions."""
        ...

    @abstractmethod
    def flash_tool_info(self) -> dict:
        """Return dict with keys: name, format, usb_vid, notes."""
        ...

    def supported_chips(self) -> list[str]:
        """Return list of known chip identifiers for this vendor."""
        return []


# ── Flash interface ───────────────────────────────────────────────────────────

class FlashInterface(ABC):
    """
    Standardized flash operation — every flash path goes through this.
    Implementations: FastbootFlash, ADBddFlash, RKFlash, FELFlash, EDLFlash
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this flash method is usable right now."""
        ...

    @abstractmethod
    def flash(self,
              partition: str,
              image:     Path,
              device:    DeviceInfo,
              verify:    bool = True) -> Result:
        """Flash image to partition. Return Result."""
        ...

    @abstractmethod
    def dump(self,
             partition: str,
             output:    Path,
             device:    DeviceInfo) -> Result:
        """Dump partition to output file. Return Result."""
        ...

    def bulk_flash(self,
                   images: dict[str, Path],
                   device: DeviceInfo) -> dict[str, Result]:
        """Flash multiple partitions. Default: call flash() for each."""
        return {part: self.flash(part, img, device)
                for part, img in images.items()}


# ── Image handler interface ───────────────────────────────────────────────────

class ImageHandlerInterface(ABC):
    """
    Standardized image pack/unpack — abstracts over boot.img formats,
    ext4/erofs system images, OTA payload.bin, etc.
    """

    @abstractmethod
    def can_handle(self, image: ImageInfo) -> bool:
        """Return True if this handler knows how to process this image."""
        ...

    @abstractmethod
    def unpack(self, image: ImageInfo, output_dir: Path) -> Result:
        """Unpack image to output_dir. Return Result with unpacked paths in data."""
        ...

    @abstractmethod
    def repack(self, source_dir: Path, output: Path, metadata: dict) -> Result:
        """Repack source_dir back into a flashable image. Return Result."""
        ...

    def patch(self, image: ImageInfo, patches: list[Callable], output: Path) -> Result:
        """
        Apply a list of patch functions to the image.
        Default implementation: unpack → apply patches → repack.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            unpack_result = self.unpack(image, Path(td))
            if not unpack_result:
                return unpack_result
            for patch_fn in patches:
                patch_fn(Path(td), image.metadata)
            return self.repack(Path(td), output, image.metadata)


# ── Analyzer interface ────────────────────────────────────────────────────────

class AnalyzerInterface(ABC):
    """
    Standardized analysis — entropy, strings, format detection, diff.
    """

    @abstractmethod
    def analyze(self, image: ImageInfo) -> Result:
        """Analyze image and return findings in Result.data."""
        ...

    def supports(self, image: ImageInfo) -> bool:
        """Return True if this analyzer applies to this image type."""
        return True


# ── Band config interface ─────────────────────────────────────────────────────

class BandConfigInterface(ABC):
    """
    Standardized modem band configuration across all vendors.
    Implementations: QualcommBandConfig, MTKBandConfig, UnisocBandConfig
    """

    @abstractmethod
    def read_current_bands(self, device: DeviceInfo) -> Result:
        """Read current LTE/5G band config from device. Return Result with bands in data."""
        ...

    @abstractmethod
    def write_bands(self,
                    device:   DeviceInfo,
                    lte_low:  int,
                    lte_high: int,
                    nr_mask:  int) -> Result:
        """
        Write LTE and 5G NR band preference masks.
        lte_low:  bands 1-64  (bit n-1 set for band n)
        lte_high: bands 65-128
        nr_mask:  NR band bitmask
        Returns Result. Does NOT reboot — caller decides.
        """
        ...

    @abstractmethod
    def backup_config(self, device: DeviceInfo, output_dir: Path) -> Result:
        """Backup current band/modem config before any changes."""
        ...

    def restore_config(self, device: DeviceInfo, backup_dir: Path) -> Result:
        """Restore from a previous backup. Default: not implemented."""
        return Result.fail("restore_config not implemented for this vendor")

    def apply_preset(self, device: DeviceInfo, preset: dict) -> Result:
        """Apply a carrier band preset dict. Calls write_bands internally."""
        try:
            lte_low  = int(preset.get("lte_hex_low",  "0x0"), 16)
            lte_high = int(preset.get("lte_hex_high", "0x0"), 16)
            nr_mask  = int(preset.get("nr_hex",       "0x0"), 16)
            backup_r = self.backup_config(device, Path("output/band_backups") / device.serial)
            if not backup_r:
                return backup_r
            return self.write_bands(device, lte_low, lte_high, nr_mask)
        except Exception as e:
            return Result.fail(str(e), "apply_preset failed")
