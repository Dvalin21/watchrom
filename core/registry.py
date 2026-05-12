"""
core/registry.py — Plugin system, vendor registry, and extension API

Allows third-party modules to register:
  - New vendor implementations
  - New pipeline steps
  - New analyzers
  - New band config backends

Usage (in a plugin file):
    from core.registry import register_vendor, register_analyzer
    from core.interfaces import VendorInterface

    @register_vendor
    class MyCustomVendor(VendorInterface):
        ...
"""

from __future__ import annotations
from typing import Type, Optional, Callable
from core.interfaces import (
    VendorInterface, FlashInterface, AnalyzerInterface,
    BandConfigInterface, DeviceInfo, Result
)

# ── Vendor registry ───────────────────────────────────────────────────────────

_VENDOR_REGISTRY:   dict[str, VendorInterface]     = {}
_FLASH_REGISTRY:    dict[str, FlashInterface]      = {}
_ANALYZER_REGISTRY: dict[str, AnalyzerInterface]   = {}
_BAND_REGISTRY:     dict[str, BandConfigInterface] = {}
_PLUGIN_HOOKS:      dict[str, list[Callable]]      = {}


def register_vendor(cls: Type[VendorInterface]) -> Type[VendorInterface]:
    """Decorator — register a VendorInterface implementation."""
    instance = cls()
    _VENDOR_REGISTRY[instance.key] = instance
    return cls


def register_flash(cls: Type[FlashInterface]) -> Type[FlashInterface]:
    """Decorator — register a FlashInterface implementation."""
    instance = cls()
    _FLASH_REGISTRY[instance.__class__.__name__.lower()] = instance
    return cls


def register_analyzer(cls: Type[AnalyzerInterface]) -> Type[AnalyzerInterface]:
    """Decorator — register an AnalyzerInterface implementation."""
    instance = cls()
    name = getattr(cls, 'name', cls.__name__.lower())
    _ANALYZER_REGISTRY[name] = instance
    return cls


def register_band_config(cls: Type[BandConfigInterface]) -> Type[BandConfigInterface]:
    """Decorator — register a BandConfigInterface implementation."""
    instance = cls()
    vendor_key = getattr(cls, 'vendor_key', cls.__name__.lower())
    _BAND_REGISTRY[vendor_key] = instance
    return cls


def hook(event: str):
    """Decorator — register a function as a hook for a named event."""
    def decorator(fn: Callable) -> Callable:
        _PLUGIN_HOOKS.setdefault(event, []).append(fn)
        return fn
    return decorator


def fire_hook(event: str, *args, **kwargs) -> list:
    """Fire all hooks registered for an event, return list of results."""
    results = []
    for fn in _PLUGIN_HOOKS.get(event, []):
        try:
            results.append(fn(*args, **kwargs))
        except Exception as e:
            results.append(e)
    return results


# ── Lookup helpers ────────────────────────────────────────────────────────────

def get_vendor(key: str) -> Optional[VendorInterface]:
    return _VENDOR_REGISTRY.get(key)


def detect_vendor(props: dict) -> Optional[VendorInterface]:
    """Try all registered vendors and return first that matches."""
    for vendor in _VENDOR_REGISTRY.values():
        result = vendor.detect(props)
        if result:
            return vendor
    return None


def get_flash_backend(name: str) -> Optional[FlashInterface]:
    return _FLASH_REGISTRY.get(name)


def best_flash_backend(device: DeviceInfo) -> Optional[FlashInterface]:
    """Return first available flash backend for this device."""
    for backend in _FLASH_REGISTRY.values():
        if backend.is_available():
            return backend
    return None


def get_analyzer(name: str) -> Optional[AnalyzerInterface]:
    return _ANALYZER_REGISTRY.get(name)


def get_band_config(vendor_key: str) -> Optional[BandConfigInterface]:
    return _BAND_REGISTRY.get(vendor_key)


def all_vendors()   -> dict: return dict(_VENDOR_REGISTRY)
def all_analyzers() -> dict: return dict(_ANALYZER_REGISTRY)
def all_flash()     -> dict: return dict(_FLASH_REGISTRY)
def all_bands()     -> dict: return dict(_BAND_REGISTRY)


# ── Version-pinned dependency spec ────────────────────────────────────────────

PINNED_DEPS = {
    # pip packages
    "pip": {
        "rich":          ">=13.0.0",
        "click":         ">=8.0.0",
        "prompt_toolkit":">=3.0.0",
        "pyserial":      ">=3.5",
        "requests":      ">=2.28.0",
        "avbtool":       ">=1.0.0",
        "pycryptodome":  ">=3.15.0",
        "protobuf":      ">=4.0.0",
    },
    # Git repos with pinned commits/tags
    "git": {
        "mtkclient":      {
            "url":  "https://github.com/bkerler/mtkclient",
            "tag":  "v2.0.1",
            "commit": None,  # Use tag if available, else latest
        },
        "edl":            {
            "url":  "https://github.com/bkerler/edl",
            "tag":  "3.55",
            "commit": None,
        },
        "jadx":           {
            "url":  "https://github.com/skylot/jadx",
            "tag":  "v1.5.0",
            "commit": None,
        },
        "rkdeveloptool":  {
            "url":  "https://github.com/rockchip-linux/rkdeveloptool",
            "tag":  None,
            "commit": "ab703a0",  # last known good
        },
        "sunxi-tools":    {
            "url":  "https://github.com/linux-sunxi/sunxi-tools",
            "tag":  "v1.4.2",
            "commit": None,
        },
        "payload-dumper-go": {
            "url":  "https://github.com/ssut/payload-dumper-go",
            "tag":  "1.2.2",
            "commit": None,
        },
        "twrp-dtg":       {
            "url":  "https://github.com/SebaUbuntu/TWRP-device-tree-generator",
            "tag":  None,
            "commit": "d3a4b21",
        },
    },
    # System packages (apt) — version ranges
    "apt": {
        "adb":                  ">=1:8.0",
        "fastboot":             ">=1:8.0",
        "device-tree-compiler": ">=1.5",
        "e2fsprogs":            ">=1.45",
        "erofs-utils":          ">=1.3",
        "sunxi-tools":          ">=1.4",
    },
}


def check_dep_versions() -> dict:
    """Check installed versions against pins. Returns dict of ok/outdated/missing."""
    import subprocess, shutil, importlib
    status = {}

    # pip packages
    for pkg, req in PINNED_DEPS["pip"].items():
        try:
            mod = importlib.import_module(pkg.replace("-","_").split("[")[0])
            ver = getattr(mod, "__version__", "?")
            status[pkg] = {"status": "ok", "version": ver, "required": req}
        except ImportError:
            status[pkg] = {"status": "missing", "version": None, "required": req}

    # System tools
    for tool in ["adb","fastboot","dtc","debugfs","sunxi-fel","rkdeveloptool"]:
        path = shutil.which(tool)
        status[tool] = {"status": "ok" if path else "missing", "path": path}

    return status
