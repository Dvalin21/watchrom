## Summary

One paragraph describing what this PR does and why.

## Type of Change

- [ ] Bug fix
- [ ] New chip / SoC entry
- [ ] New carrier band profile
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Refactor

## Changes Made

- `modules/chipsets.py` — Added MT6899 to MTK_CHIPS and MTK_SIGNATURES
- `modules/modem_bands.py` — Added malaysia_celcom carrier profile

## Testing

**Device tested on:** e.g. Ticwatch Pro 3, Unisoc SC9863A, Android 11

**Commands verified:**
```bash
watchrom mtk list | grep MT6899
watchrom bands apply --carrier malaysia_celcom --dry-run
```

## Checklist

- [ ] Code follows style guide (100 char lines, type hints in core/)
- [ ] New write operations backup before writing
- [ ] New CLI commands support `--dry-run`
- [ ] New chips added to both database dict AND signatures dict
- [ ] Carrier hex masks verified with `build_lte_bitmask()`
- [ ] No private keys, device dumps, or firmware committed
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] CI passes

## Related Issues

Fixes #123
