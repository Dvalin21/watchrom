# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅ Active |
| < 1.0   | ❌ None   |

## Scope

WatchROM is a local CLI tool. It communicates only with:
- Android devices via USB (ADB/fastboot)
- GitHub repositories over HTTPS (during `install.sh` setup only)

It does **not** transmit data to any server, run as a daemon, or store credentials.

## Reporting a Vulnerability

**Do not open a public issue.** Email the maintainer directly (see GitHub profile).

Include: description, reproduction steps, and impact assessment.
Allow up to 7 days for initial response before any public disclosure.

## Dependency Security

All repos are cloned at pinned tags/commits in `core/registry.py`.
If a dependency has a CVE affecting WatchROM's use, report it and
we will update the pin.

Audit current pins:
```bash
python3 -c "from core.registry import PINNED_DEPS; import json; print(json.dumps(PINNED_DEPS['git'], indent=2))"
```
