"""
props.py — Comprehensive Android properties manager
Live device props, build.prop editing, prop overlays, fingerprint spoofing
"""
import click
import re
from pathlib import Path
from modules import run_adb, adb_devices, get_device_props, OUTPUT_DIR, console

# Common prop tweaks by category
PROP_PRESETS = {
    "debug": {
        "ro.debuggable":            "1",
        "ro.secure":                "0",
        "ro.adb.secure":            "0",
        "persist.sys.usb.config":   "mtp,adb",
        "service.adb.root":         "1",
    },
    "performance": {
        "debug.sf.hw":              "1",
        "video.accelerate.hw":      "1",
        "persist.sys.scrollingcache": "3",
        "ro.config.hw_quickpoweron": "true",
        "windowsmgr.max_events_per_sec": "150",
    },
    "developer": {
        "debug.layout":             "0",
        "persist.sys.strictmode.visual": "0",
        "ro.allow.mock.location":   "0",
        "debug.force_rtl":          "0",
        "persist.log.tag":          "*:V",
    },
    "watch": {
        "ro.sf.lcd_density":        "240",
        "persist.sys.timezone":     "America/New_York",
        "ro.config.ringtone":       "",
        "ro.config.notification_sound": "",
        "persist.sys.dalvik.vm.lib.2": "libart.so",
        "dalvik.vm.heapsize":       "256m",
        "dalvik.vm.heapgrowthlimit": "128m",
    },
}


@click.group()
def props():
    """Android system properties: live edit, build.prop management, presets."""
    pass


@props.command("get")
@click.argument("key", required=False, default=None)
@click.option("--serial",  "-s", default=None)
@click.option("--filter",  "-f", default=None, help="Filter keys by substring")
@click.option("--out",     "-o", default=None, help="Save all props to file")
def props_get(key, serial, filter, out):
    """Get one or all properties from device."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    all_props = get_device_props(target)

    if key:
        val = all_props.get(key, "[not found]")
        console.print(f"[cyan]{key}[/cyan] = [green]{val}[/green]")
        return

    display = dict(all_props)
    if filter:
        display = {k: v for k, v in display.items() if filter.lower() in k.lower() or filter.lower() in v.lower()}

    for k, v in sorted(display.items()):
        console.print(f"  [cyan]{k}[/cyan] = {v}")

    if out:
        with open(out, "w") as f:
            for k, v in sorted(all_props.items()):
                f.write(f"{k}={v}\n")
        console.print(f"\n[green]✓ Props saved: {out}[/green]")
    else:
        console.print(f"\n[dim]{len(display)} properties{f' (filtered: {filter})' if filter else ''}[/dim]")


@props.command("set")
@click.argument("key")
@click.argument("value")
@click.option("--serial",    "-s", default=None)
@click.option("--permanent", "-p", is_flag=True,
              help="Make persistent (survives reboot) via resetprop")
def props_set(key, value, serial, permanent):
    """Set a property on live device (requires root for most props)."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    if permanent:
        # resetprop is Magisk's tool — persists ro. props
        cmd = f"su -c 'resetprop {key} {value}'"
    else:
        cmd = f"setprop {key} {value}"

    _, out, err = run_adb(["shell", cmd], serial=target, check=False)

    # Verify
    _, verify, _ = run_adb(["shell", f"getprop {key}"], serial=target, check=False)
    if verify.strip() == value:
        console.print(f"[green]✓ {key} = {value}[/green]{'  [dim](persistent)[/dim]' if permanent else ''}")
    else:
        console.print(f"[yellow]! Set attempted. Current: {key} = {verify.strip()}[/yellow]")
        if err:
            console.print(f"[dim]{err[:200]}[/dim]")


@props.command("preset")
@click.argument("preset_name",
                type=click.Choice(list(PROP_PRESETS.keys()) + ["list"]))
@click.option("--serial",    "-s", default=None)
@click.option("--permanent", "-p", is_flag=True)
@click.option("--dry-run",   is_flag=True, help="Show what would be set without applying")
def props_preset(preset_name, serial, permanent, dry_run):
    """
    Apply a preset group of properties.

    Presets: debug, performance, developer, watch
    """
    if preset_name == "list":
        for name, entries in PROP_PRESETS.items():
            console.print(f"\n[bold cyan]{name}:[/bold cyan]")
            for k, v in entries.items():
                console.print(f"  [dim]{k}[/dim] = {v}")
        return

    preset = PROP_PRESETS[preset_name]
    console.print(f"\n[bold cyan]Applying preset: {preset_name}[/bold cyan]\n")

    if dry_run:
        for k, v in preset.items():
            console.print(f"  [dim]would set[/dim] [cyan]{k}[/cyan] = {v}")
        return

    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    for k, v in preset.items():
        cmd = f"su -c 'resetprop {k} {v}'" if permanent else f"setprop {k} {v}"
        _, _, err = run_adb(["shell", cmd], serial=target, check=False)
        _, verify, _ = run_adb(["shell", f"getprop {k}"], serial=target, check=False)
        ok = verify.strip() == v
        console.print(f"  [{'green' if ok else 'yellow'}]{'✓' if ok else '?'}[/{'green' if ok else 'yellow'}] {k} = {v}")

    console.print(f"\n[green]✓ Preset '{preset_name}' applied.[/green]")


@props.command("edit-buildprop")
@click.argument("buildprop_file")
@click.option("--set",     "-s",  "set_pairs",  multiple=True,
              help="key=value pair to set/add")
@click.option("--remove",  "-r",  multiple=True, help="Key to remove")
@click.option("--out",     "-o",  default=None,  help="Output file (default: overwrite)")
def props_edit_buildprop(buildprop_file, set_pairs, remove, out):
    """
    Edit a build.prop file from a system image dump.

    Examples:
      --set ro.debuggable=1 --set ro.secure=0
      --remove dalvik.vm.heapsize
    """
    bp = Path(buildprop_file)
    if not bp.exists():
        console.print(f"[red]✗ Not found: {buildprop_file}[/red]")
        return

    lines = bp.read_text(errors="replace").splitlines()
    out_path = Path(out) if out else bp

    changed = []
    result  = []

    # Remove keys
    remove_keys = set(remove)

    # Parse set pairs
    new_vals = {}
    for pair in set_pairs:
        if "=" in pair:
            k, v = pair.split("=", 1)
            new_vals[k] = v

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            result.append(line)
            continue
        if "=" in stripped:
            k = stripped.split("=", 1)[0]
            if k in remove_keys:
                changed.append(f"[red]- removed: {k}[/red]")
                continue
            if k in new_vals:
                old = stripped
                result.append(f"{k}={new_vals.pop(k)}")
                changed.append(f"[yellow]~ changed: {k}[/yellow]")
                continue
        result.append(line)

    # Add any remaining new keys not already present
    for k, v in new_vals.items():
        result.append(f"{k}={v}")
        changed.append(f"[green]+ added: {k}={v}[/green]")

    with open(out_path, "w") as f:
        f.write("\n".join(result) + "\n")

    if changed:
        console.print(f"\n[bold]Changes to {bp.name}:[/bold]")
        for c in changed:
            console.print(f"  {c}")
        console.print(f"\n[green]✓ Written: {out_path}[/green]")
    else:
        console.print("[yellow]! No changes made.[/yellow]")


@props.command("spoof-fingerprint")
@click.option("--serial",  "-s", default=None)
@click.option("--target",  "-t", default=None,
              help="Device to spoof as (e.g. 'Pixel 7 Pro')")
@click.option("--list",    "show_list", is_flag=True, help="Show available fingerprints")
def props_spoof_fingerprint(serial, target, show_list):
    """
    Spoof device fingerprint to pass Play Integrity / SafetyNet.
    Requires Magisk + resetprop (root).
    """
    FINGERPRINTS = {
        "Pixel 6":      "google/oriole/oriole:13/TQ3A.230901.001/10750268:user/release-keys",
        "Pixel 7":      "google/panther/panther:13/TQ3A.230901.001/10750268:user/release-keys",
        "Pixel 7 Pro":  "google/cheetah/cheetah:13/TQ3A.230901.001/10750268:user/release-keys",
        "Pixel 8":      "google/shiba/shiba:14/UD1A.231105.004/10927476:user/release-keys",
        "Samsung S23":  "samsung/dm1qxxx/dm1q:13/TP1A.220624.014/S918BXXS2AWC7:user/release-keys",
        "OnePlus 11":   "OnePlus/salami/salami:13/TP1A.220624.014/R.202302280938:user/release-keys",
    }

    if show_list:
        console.print("\n[bold cyan]Available Fingerprints:[/bold cyan]\n")
        for name, fp in FINGERPRINTS.items():
            console.print(f"  [green]{name:20s}[/green] {fp[:60]}…")
        return

    fp_name   = target or "Pixel 7"
    fingerprint = FINGERPRINTS.get(fp_name)
    if not fingerprint:
        console.print(f"[red]✗ Unknown target: {fp_name}[/red]")
        console.print("  Use --list to see options or provide custom --target")
        return

    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    serial = serial or online[0]

    props_to_set = {
        "ro.build.fingerprint":         fingerprint,
        "ro.system.build.fingerprint":  fingerprint,
        "ro.product.build.fingerprint": fingerprint,
        "ro.vendor.build.fingerprint":  fingerprint,
    }

    console.print(f"\n[bold cyan]Spoofing fingerprint as: {fp_name}[/bold cyan]")
    for k, v in props_to_set.items():
        _, _, _ = run_adb(
            ["shell", f"su -c 'resetprop {k} \"{v}\"'"],
            serial=serial, check=False
        )
        console.print(f"  [green]✓[/green] {k}")

    console.print(f"\n[green]✓ Fingerprint spoofed.[/green]")
    console.print(f"  [dim]Note: Reboot may clear this. Use Magisk module for persistence.[/dim]")
