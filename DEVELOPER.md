# WatchROM — Developer & Extension Guide

## Architecture

WatchROM is built as a proper framework, not just a tool aggregator.

```
watchrom/
├── core/                    # Framework layer
│   ├── interfaces.py        # Abstract base classes (contracts)
│   ├── registry.py          # Plugin registry + version pins
│   ├── pipeline.py          # Task graph + state machine
│   ├── vendors.py           # Concrete vendor implementations
│   └── band_backends.py     # Concrete band config implementations
├── modules/                 # CLI layer
│   ├── pipeline_cmd.py      # watchrom pipeline <name>
│   ├── qualcomm.py          # watchrom qualcomm <cmd>
│   ├── modem_bands.py       # watchrom bands <cmd>
│   └── ...                  # All other CLI modules
└── main.py                  # Entry point (TUI or CLI)
```

## Standard Interfaces

Every operation maps to one of these abstract contracts:

### `VendorInterface` — Chipset vendor detection and info
```python
class VendorInterface(ABC):
    @property
    def name(self) -> str: ...         # "MediaTek"
    @property
    def key(self) -> str: ...          # "mtk"
    def detect(self, props) -> Optional[DeviceInfo]: ...
    def partition_list(self, device) -> list[str]: ...
    def download_mode_entry(self) -> str: ...
    def flash_tool_info(self) -> dict: ...
```

### `BandConfigInterface` — Modem band configuration
```python
class BandConfigInterface(ABC):
    def read_current_bands(self, device) -> Result: ...
    def write_bands(self, device, lte_low, lte_high, nr_mask) -> Result: ...
    def backup_config(self, device, output_dir) -> Result: ...
    def restore_config(self, device, backup_dir) -> Result: ...
    def apply_preset(self, device, preset) -> Result: ...  # default impl
```

### `Result` — Standardized return type
```python
Result.ok("message", key=value)   # success with data
Result.fail("error message")       # failure
Result.skip("reason")              # skipped/not applicable

if result:  # bool(result) == result.ok_()
    data = result.data["key"]
```

## Writing a Plugin

### 1. New Vendor
```python
# my_plugin/my_vendor.py
from core.interfaces import VendorInterface, DeviceInfo
from core.registry import register_vendor

@register_vendor
class ExampleVendor(VendorInterface):
    name = "Example Corp"
    key  = "example"

    def detect(self, props: dict) -> Optional[DeviceInfo]:
        if "example" not in props.get("ro.hardware","").lower():
            return None
        return DeviceInfo(
            serial  = props.get("_serial","?"),
            vendor  = "example",
            chipset = "EX1000",
            arch    = "arm64",
            props   = props,
        )

    def partition_list(self, device):
        return ["boot","system","vendor","userdata","misc"]

    def download_mode_entry(self):
        return "Hold Vol- + connect USB  (USB VID: 0xXXXX)"

    def flash_tool_info(self):
        return {"name":"ExFlash","format":"scatter","usb_vid":"0xXXXX","notes":""}
```

Auto-registered on import. WatchROM's `device info` command will detect this vendor.

### 2. New Band Config Backend
```python
from core.interfaces import BandConfigInterface, DeviceInfo, Result
from core.registry import register_band_config

@register_band_config
class ExampleBandConfig(BandConfigInterface):
    vendor_key = "example"

    def read_current_bands(self, device: DeviceInfo) -> Result:
        # query modem and return Result with band data
        return Result.ok("Bands read", lte_bands=[1,3,7], nr_bands=["n78"])

    def write_bands(self, device, lte_low, lte_high, nr_mask) -> Result:
        # send AT commands or write NV items
        # lte_low  = 64-bit mask for bands 1-64
        # lte_high = 64-bit mask for bands 65-128
        # nr_mask  = 64-bit 5G NR mask
        return Result.ok("Bands written")

    def backup_config(self, device, output_dir) -> Result:
        output_dir.mkdir(parents=True, exist_ok=True)
        # save current config to output_dir
        return Result.ok("Backed up")
```

### 3. New Pipeline
```python
from core.pipeline import Pipeline, Task, register_pipeline
from core.interfaces import Result

def my_task(ctx: dict) -> Result:
    serial = ctx.get("serial")
    # do work...
    ctx["my_result"] = "value"  # share with downstream tasks
    return Result.ok("Done", my_result="value")

my_pipeline = Pipeline("my-workflow", "Does something useful")
my_pipeline.add(Task("step1", my_task, "Does the thing", required=True))
register_pipeline(my_pipeline)
```

Run it: `watchrom pipeline my-workflow`

### 4. Hook into existing events
```python
from core.registry import hook

@hook("before_flash")
def my_pre_flash_check(device, partition, image):
    print(f"About to flash {partition}")

@hook("after_backup")
def notify_backup_done(device, backup_dir):
    # send notification, log to DB, etc.
    pass
```

## Pipeline System

### State machine
```
PENDING → RUNNING → DONE
                  → FAILED  (if required=True, pipeline stops + rollbacks)
                  → SKIPPED (condition returned False)
```

### Built-in pipelines
| Name | Steps | Purpose |
|------|-------|---------|
| `root-device` | 7 | detect→backup→patch→flash→verify |
| `full-backup` | 4 | detect→dump→apps→manifest |
| `avb-disable` | 4 | detect→backup-vbmeta→blank→flash |
| `flash-rom` | 4 | validate→backup→avb-disable→flash-all |
| `wearos-setup` | 6 | detect→root-check→backup→module→install→verify |
| `configure-bands` | 4 | detect→backup→apply→reboot |

### Pipeline options
```bash
watchrom pipeline root-device --dry-run          # preview steps
watchrom pipeline flash-rom --resume flash-all   # skip to step
watchrom pipeline flash-rom --state ./run.json   # persist state
watchrom pipeline custom detect backup verify    # compose ad-hoc
```

### Context dict
The `context` dict is shared across all steps:
```python
# After "detect" step runs, these are available:
ctx["serial"]    # ADB serial
ctx["vendor"]    # "mtk" | "unisoc" | "rockchip" etc.
ctx["chipset"]   # "MT6761" | "RK3588" etc.
ctx["props"]     # full Android properties dict

# Each step stores its outputs:
ctx["stock_boot"]     # Path to stock boot.img (after "backup")
ctx["patched_boot"]   # Path to Magisk-patched boot (after "patch-boot")
ctx["blank_vbmeta"]   # Path to blank vbmeta.img (after "disable-avb")
```

## Version Pinning

All external deps are pinned in `core/registry.py`:
```python
PINNED_DEPS = {
    "pip": {"rich": ">=13.0.0", "avbtool": ">=1.0.0", ...},
    "git": {
        "mtkclient":  {"url": "...", "tag": "v2.0.1"},
        "edl":        {"url": "...", "tag": "3.55"},
        "jadx":       {"url": "...", "tag": "v1.5.0"},
        ...
    },
}
```

Check installed versions: `python3 -c "from core.registry import check_dep_versions; print(check_dep_versions())"`

## Band Config Architecture

The 128-bit extended LTE band mask:
```
low_64  bits 0-63  = LTE bands 1-64   (bit n-1 set for band n)
high_64 bits 0-63  = LTE bands 65-128 (bit n-65 set for band n)

Examples:
  B13  = low_64  bit 12  = 0x0000000000001000
  B66  = high_64 bit 1   = 0x0000000000000002
  B71  = high_64 bit 6   = 0x0000000000000040
```

This handles T-Mobile B71 (600MHz) and B66 (AWS-3) correctly —
both are > band 64 and live in the upper word.

### Carrier preset format
```python
{
    "display":       "Verizon Wireless (US)",
    "lte_bands":     [2, 4, 5, 13, 48, 66],
    "nr_sub6":       ["n5", "n48", "n66", "n77"],
    "nr_mmwave":     ["n260", "n261"],
    "primary_lte":   13,
    "primary_nr":    "n77",
    "lte_hex_low":   "0x0000000008880200",  # B2/4/5/13
    "lte_hex_high":  "0x0000000000020001",  # B48/B66
    "nr_hex":        "0x0000000000000118",  # n5/n48/n66/n77
    "notes":         ["B13 is mandatory for Verizon", ...],
}
```
