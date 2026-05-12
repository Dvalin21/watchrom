# Contributing to WatchROM

Thank you for contributing. Every improvement — from a chip entry to a full
vendor backend — makes WatchROM better for the entire Android development community.

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/watchrom.git
cd watchrom
./install.sh
git checkout -b feature/add-mt6899-chip
```

## Types of Contributions

| Type | Effort | Files |
|------|--------|-------|
| New chip entry | Low | `modules/chipsets.py` |
| New carrier profile | Low | `modules/modem_bands.py` |
| Bug fix | Variable | See open issues |
| New CLI command | Medium | Appropriate `modules/*.py` |
| New pipeline | Medium | `core/pipeline.py` |
| New vendor backend | High | `core/vendors.py` + `core/band_backends.py` |

## Adding a New Chip

Edit `modules/chipsets.py` and add to the appropriate dict:

```python
# MTK_CHIPS:
"MT6899": {
    "name":    "Dimensity 9300 / MT6899",
    "platform":"mt6899",
    "arch":    "arm64",
    "year":    2024,
    "watch":   False,
    "brom":    True,
},
# MTK_SIGNATURES:
"mt6899": ["mt6899", "dimensity 9300"],
```

## Adding a Carrier Profile

Edit `modules/modem_bands.py`, add to `CARRIER_PROFILES`:

```python
"my_carrier": {
    "display":     "My Carrier (Country)",
    "lte_bands":   [1, 3, 7, 20],
    "nr_sub6":     ["n78"],
    "nr_mmwave":   [],
    "primary_lte": 3,
    "primary_nr":  "n78",
    "lte_hex_low":  "0x...",   # calculated via build_lte_bitmask()
    "lte_hex_high": "0x0000000000000000",
    "nr_hex":       "0x...",
    "notes": ["Key note about this carrier"],
},
```

Calculate hex masks:
```python
from modules.qualcomm import build_lte_bitmask
low, high = build_lte_bitmask([1, 3, 7, 20])
print(f"low=0x{low:016X}  high=0x{high:016X}")
```

## Code Standards

- Python 3.8+ compatible (no walrus operator, no match statements)
- Type hints on all public functions in `core/`
- 100-character line limit
- All write operations must backup before writing
- New CLI commands need `--dry-run` support
- All framework functions return `Result`

## PR Checklist

- [ ] No binary firmware, keys, or device dumps committed
- [ ] New chips added to both database and signatures dict
- [ ] Carrier hex masks verified with `build_lte_bitmask()`
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] CI passes
