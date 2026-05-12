"""
wearos.py — WearOS Compatibility Layer for Full Android Smartwatches
Installs WearOS APKs, configures system props, patches framework for
WearOS app compatibility on MTK/Unisoc full-Android watch hardware
"""
import click
import shutil
import json
import zipfile
from pathlib import Path
from modules import (
    run, run_adb, adb_devices, get_device_props,
    detect_chipset_from_props, OUTPUT_DIR, WORKSPACE, KEYS_DIR,
    console, tool_available, file_size_mb, sha256_file
)

# ── WearOS core APKs that need to be present for compatibility ────────────────
WEAROS_PACKAGES = {
    # Core WearOS framework
    "com.google.android.wearable.app": {
        "name":     "WearOS by Google",
        "apk":      "WearOS.apk",
        "priv":     True,
        "required": True,
        "desc":     "Core WearOS application framework",
    },
    "com.google.android.clockwork": {
        "name":     "WearOS Clockwork",
        "apk":      "Clockwork.apk",
        "priv":     True,
        "required": True,
        "desc":     "WearOS clockwork host service",
    },
    "com.google.android.clockwork.home": {
        "name":     "WearOS Home",
        "apk":      "ClockworkHome.apk",
        "priv":     True,
        "required": True,
        "desc":     "WearOS launcher and home screen",
    },
    "com.google.android.gms": {
        "name":     "Google Play Services",
        "apk":      "GmsCore.apk",
        "priv":     True,
        "required": True,
        "desc":     "Google Play Services (required for all WearOS apps)",
    },
    "com.google.android.gsf": {
        "name":     "Google Services Framework",
        "apk":      "GoogleServicesFramework.apk",
        "priv":     True,
        "required": True,
        "desc":     "Google Services Framework",
    },
    "com.android.vending": {
        "name":     "Play Store (Watch)",
        "apk":      "Phonesky.apk",
        "priv":     True,
        "required": False,
        "desc":     "Google Play Store for watches",
    },
    "com.google.android.apps.fitness": {
        "name":     "Google Fit",
        "apk":      "GoogleFit.apk",
        "priv":     False,
        "required": False,
        "desc":     "Health and fitness tracking",
    },
    "com.google.android.apps.maps": {
        "name":     "Google Maps (Watch)",
        "apk":      "MapsWear.apk",
        "priv":     False,
        "required": False,
        "desc":     "Navigation and maps",
    },
}

# System props required for WearOS mode
WEAROS_PROPS = {
    "ro.build.characteristics":          "watch,nosdcard",
    "ro.product.characteristics":        "watch",
    "com.google.android.clockwork.mark": "1",
    "ro.wear.version":                   "4.0",
    "persist.sys.timezone":              "America/New_York",
    "ro.config.low_ram":                 "false",
    "dalvik.vm.heapsize":                "256m",
    "dalvik.vm.heapgrowthlimit":         "128m",
    "dalvik.vm.heapstartsize":           "16m",
    "dalvik.vm.heaptargetutilization":   "0.75",
    "dalvik.vm.heapminfree":             "512k",
    "dalvik.vm.heapmaxfree":             "8m",
    # Tell apps this is a WearOS device
    "ro.build.type":                     "user",
    "ro.build.tags":                     "release-keys",
    # Enable OK Google on watch
    "com.google.android.hotword.service": "enabled",
    # Round screen support (override for square/round)
    "ro.sf.lcd_density":                 "240",
}

# Permissions needed for WearOS apps
WEAROS_PERMISSIONS = [
    "android.permission.BODY_SENSORS",
    "android.permission.RECEIVE_BOOT_COMPLETED",
    "android.permission.VIBRATE",
    "android.permission.WAKE_LOCK",
    "android.permission.BLUETOOTH",
    "android.permission.BLUETOOTH_ADMIN",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.RECORD_AUDIO",
    "android.permission.INTERNET",
    "android.permission.ACCESS_NETWORK_STATE",
    "android.permission.ACCESS_WIFI_STATE",
    "android.permission.CHANGE_WIFI_STATE",
    "android.permission.NFC",
    "android.permission.FLASHLIGHT",
]

# Magisk module template for WearOS mode (systemless)
WEAROS_MODULE_SERVICE_SH = """\
#!/system/bin/sh
# WearOS Compatibility Layer — WatchROM
# Sets system properties to enable WearOS app compatibility

resetprop ro.build.characteristics "watch,nosdcard"
resetprop ro.product.characteristics "watch"
resetprop com.google.android.clockwork.mark "1"
resetprop ro.wear.version "4.0"
resetprop dalvik.vm.heapsize "256m"
resetprop dalvik.vm.heapgrowthlimit "128m"
resetprop ro.config.low_ram "false"

# Ensure ADB stays enabled for watch management
resetprop persist.sys.usb.config "mtp,adb"
resetprop service.adb.root "1"

log -t WatchROM "WearOS compatibility layer active"
"""


# ── System image patching helpers ─────────────────────────────────────────────

def patch_build_prop_for_wearos(build_prop_path: Path) -> list:
    """Add WearOS-required props to a build.prop file. Returns list of changes."""
    content = build_prop_path.read_text(errors="replace")
    lines   = content.splitlines()
    changes = []
    existing_keys = {}
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k = line.split("=", 1)[0].strip()
            existing_keys[k] = True

    result = list(lines)
    for key, val in WEAROS_PROPS.items():
        if key in existing_keys:
            # Replace existing
            new_lines = []
            for l in result:
                if l.startswith(f"{key}="):
                    old_val = l.split("=", 1)[1]
                    new_lines.append(f"{key}={val}")
                    changes.append(("changed", key, old_val, val))
                else:
                    new_lines.append(l)
            result = new_lines
        else:
            result.append(f"{key}={val}")
            changes.append(("added", key, None, val))

    build_prop_path.write_text("\n".join(result) + "\n")
    return changes


def create_privapp_permissions_xml(pkg_name: str, perms: list) -> str:
    """Generate a priv-app permissions XML for a WearOS package."""
    perm_lines = "\n".join(
        f'        <permission name="{p}"/>' for p in perms
    )
    return f"""\
<?xml version="1.0" encoding="utf-8"?>
<permissions>
    <privapp-permissions package="{pkg_name}">
{perm_lines}
    </privapp-permissions>
</permissions>
"""


# ── CLI ───────────────────────────────────────────────────────────────────────

@click.group()
def wearos():
    """WearOS compatibility layer — run WearOS apps on full Android watches."""
    pass


@wearos.command("status")
@click.option("--serial", "-s", default=None)
def wearos_status(serial):
    """Check WearOS compatibility status on connected device."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    props = get_device_props(target)
    vendor, chipset = detect_chipset_from_props(props)

    console.print(f"\n[bold cyan]WearOS Compatibility Status — {target}[/bold cyan]")
    console.print(f"  Chipset: [yellow]{chipset}[/yellow] ({vendor.upper()})\n")

    # Check key props
    checks = [
        ("ro.build.characteristics",   "watch,nosdcard",  "Device type = watch"),
        ("ro.product.characteristics",  "watch",           "Product characteristics"),
        ("com.google.android.clockwork.mark", "1",         "Clockwork flag"),
        ("ro.wear.version",             None,              "WearOS version declared"),
        ("ro.debuggable",               "1",               "Debug mode (for sideload)"),
    ]

    console.print("[bold]System Properties:[/bold]")
    for key, expected, label in checks:
        val = props.get(key, "")
        if expected:
            match = val == expected
        else:
            match = bool(val)
        icon  = "[green]✓[/green]" if match else "[red]✗[/red]"
        console.print(f"  {icon} {label:35s} [dim]{val or '(not set)'}[/dim]")

    # Check installed WearOS packages
    console.print(f"\n[bold]WearOS Packages:[/bold]")
    for pkg, info_d in WEAROS_PACKAGES.items():
        _, out, _ = run_adb(
            ["shell", f"pm path {pkg} 2>/dev/null || echo MISSING"],
            serial=target, check=False
        )
        installed = "MISSING" not in out and out.strip()
        icon = "[green]✓[/green]" if installed else "[dim]✗[/dim]"
        req  = "[bold red]*[/bold red]" if info_d["required"] and not installed else ""
        console.print(f"  {icon}{req} {info_d['name']:35s} [dim]{pkg}[/dim]")

    # Overall score
    console.print()
    prop_score = sum(1 for k, e, _ in checks
                     if (e and props.get(k,"") == e) or (not e and props.get(k,"")))
    pkg_installed = sum(1 for pkg in WEAROS_PACKAGES
                        if "MISSING" not in run_adb(["shell", f"pm path {pkg} 2>/dev/null || echo MISSING"],
                                                    serial=target, check=False)[1])
    req_count = sum(1 for p in WEAROS_PACKAGES.values() if p["required"])

    console.print(f"  Props : {prop_score}/{len(checks)} configured")
    console.print(f"  APKs  : {pkg_installed}/{len(WEAROS_PACKAGES)} installed")
    if prop_score == len(checks) and pkg_installed >= req_count:
        console.print(f"\n  [bold green]✓ Device appears WearOS-compatible![/bold green]")
    else:
        console.print(f"\n  [yellow]! Device needs configuration. Run:[/yellow]")
        console.print(f"    [bold]watchrom wearos setup[/bold]   — configure props")
        console.print(f"    [bold]watchrom wearos install-apks[/bold] — install WearOS APKs")


@wearos.command("setup")
@click.option("--serial",     "-s", default=None)
@click.option("--method",     "-m",
              type=click.Choice(["magisk", "props", "sysimg"]),
              default="magisk",
              help="magisk=systemless (recommended), props=live setprop, sysimg=patch system image")
@click.option("--screen",     default="round",
              type=click.Choice(["round", "square"]),
              help="Watch screen shape")
@click.option("--density",    default=240, type=int,
              help="Screen DPI (default 240 for most watches)")
def wearos_setup(serial, method, screen, density):
    """
    Configure device for WearOS app compatibility.

    Three methods:
      magisk  — Systemless Magisk module (survives OTA, recommended)
      props   — Live setprop via root (resets on reboot without Magisk)
      sysimg  — Patch mounted system image (permanent, for ROM building)
    """
    console.print(f"\n[bold cyan]WearOS Compatibility Setup[/bold cyan]")
    console.print(f"  Method : {method}")
    console.print(f"  Screen : {screen}  DPI: {density}\n")

    props_to_set = dict(WEAROS_PROPS)
    props_to_set["ro.sf.lcd_density"] = str(density)
    if screen == "round":
        props_to_set["ro.sf.hwrotation"] = "0"

    if method == "magisk":
        _setup_magisk_module(props_to_set)

    elif method == "props":
        devs = adb_devices()
        online = [s for s, st in devs if st == "device"]
        if not online:
            console.print("[red]✗ No ADB device.[/red]")
            return
        target = serial or online[0]

        console.print("[cyan]→ Applying props via resetprop (requires root)...[/cyan]\n")
        for key, val in props_to_set.items():
            _, out, _ = run_adb(
                ["shell", f"su -c 'resetprop \"{key}\" \"{val}\"'"],
                serial=target, check=False
            )
            _, verify, _ = run_adb(
                ["shell", f"getprop {key}"], serial=target, check=False
            )
            ok_flag = verify.strip() == val
            console.print(f"  [{'green' if ok_flag else 'yellow'}]"
                          f"{'✓' if ok_flag else '?'}[/{'green' if ok_flag else 'yellow'}]"
                          f" {key} = {val}")
        console.print(f"\n[yellow]! Props are temporary. Use --method magisk for persistence.[/yellow]")

    elif method == "sysimg":
        console.print("[yellow]! sysimg method: extract system.img first:[/yellow]")
        console.print("  [bold]watchrom sysimg extract system.img[/bold]")
        console.print("  [bold]watchrom wearos patch-sysimg <extracted_dir>[/bold]")


def _setup_magisk_module(props: dict):
    """Build and output a Magisk module for WearOS compat."""
    from modules.magisk import create_module_structure, pack_module

    mod_id  = "watchrom_wearos"
    out_dir = OUTPUT_DIR / "magisk_modules" / mod_id
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "id":           mod_id,
        "name":         "WatchROM WearOS Compat",
        "version":      "v1.0",
        "version_code": "1",
        "author":       "WatchROM",
        "description":  "Enables WearOS app compatibility on full Android watches",
    }
    create_module_structure(out_dir, meta)

    # Write service.sh with all props
    svc_lines = ["#!/system/bin/sh", "# WatchROM WearOS Compatibility Layer", ""]
    for key, val in props.items():
        svc_lines.append(f'resetprop "{key}" "{val}"')
    svc_lines.append("")
    svc_lines.append("log -t WatchROM 'WearOS compat layer active'")
    (out_dir / "service.sh").write_text("\n".join(svc_lines))

    # Create permissions XML for WearOS apps
    perm_dir = out_dir / "system" / "etc" / "permissions"
    perm_dir.mkdir(parents=True, exist_ok=True)
    for pkg in ["com.google.android.wearable.app", "com.google.android.gms"]:
        xml = create_privapp_permissions_xml(pkg, WEAROS_PERMISSIONS)
        (perm_dir / f"privapp-permissions-{pkg.split('.')[-2]}.xml").write_text(xml)

    zip_path = OUTPUT_DIR / "magisk_modules" / f"{mod_id}.zip"
    pack_module(out_dir, zip_path)

    console.print(f"[green]✓ WearOS Magisk module: {zip_path}[/green]")
    console.print(f"\n  Install on device:")
    console.print(f"  [bold]watchrom magisk install {zip_path}[/bold]")
    console.print(f"  Then reboot → WearOS apps will be compatible.")


@wearos.command("install-apks")
@click.option("--serial",  "-s", default=None)
@click.option("--apk-dir", "-d", required=True,
              help="Directory containing WearOS APK files")
@click.option("--system",  is_flag=True,
              help="Install as system apps (requires root + system rw)")
def wearos_install_apks(serial, apk_dir, system):
    """
    Install WearOS APKs on the device.

    Provide a directory containing the WearOS APK files.
    Get WearOS APKs from:
      - APKMirror.com (search: WearOS, Google Play Services for Wear)
      - Your existing WearOS device:  adb pull /system/priv-app/
      - GApps packages for WearOS (opengapps.org wear variant)

    System install (--system) places APKs in /system/priv-app/
    for full integration. Regular install works for testing.
    """
    apk_path = Path(apk_dir)
    if not apk_path.is_dir():
        console.print(f"[red]✗ Not a directory: {apk_dir}[/red]")
        return

    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    apks = list(apk_path.glob("*.apk")) + list(apk_path.glob("**/*.apk"))
    if not apks:
        console.print(f"[red]✗ No APK files found in {apk_dir}[/red]")
        return

    console.print(f"\n[bold cyan]WearOS APK Installer[/bold cyan]")
    console.print(f"  Found {len(apks)} APK(s)\n")

    for apk in apks:
        console.print(f"  [cyan]Installing {apk.name}...[/cyan]")

        if system:
            # Install as system app via root dd
            pkg_name = _get_apk_package(apk)
            if pkg_name:
                priv_dir = f"/system/priv-app/{pkg_name}"
                run_adb(["shell", f"su -c 'mkdir -p {priv_dir}'"],
                        serial=target, check=False)
                run_adb(["push", str(apk), f"/sdcard/{apk.name}"],
                        serial=target, check=False, timeout=120)
                run_adb(["shell",
                         f"su -c 'cp /sdcard/{apk.name} {priv_dir}/{pkg_name}.apk "
                         f"&& chmod 644 {priv_dir}/{pkg_name}.apk'"],
                        serial=target, check=False)
                console.print(f"    [green]✓ System install: {priv_dir}[/green]")
            else:
                console.print(f"    [yellow]! Could not detect package name, skipping system install[/yellow]")
        else:
            # Regular ADB install
            rc, out, err = run_adb(
                ["install", "-r", "-d", str(apk)],
                serial=target, check=False, timeout=120
            )
            if rc == 0 and "Success" in out:
                console.print(f"    [green]✓ Installed[/green]")
            else:
                console.print(f"    [yellow]! {(out + err).strip()[:80]}[/yellow]")

    if system:
        console.print(f"\n[cyan]→ Restarting system server to apply changes...[/cyan]")
        run_adb(["shell", "su -c 'stop; start'"], serial=target, check=False, timeout=30)

    console.print(f"\n[bold]Next steps:[/bold]")
    console.print(f"  1. [bold]watchrom wearos setup --method magisk[/bold]  ← configure WearOS props")
    console.print(f"  2. Install Magisk module, reboot")
    console.print(f"  3. Open WearOS app on device")
    console.print(f"  4. Pair with phone running WearOS companion app")


def _get_apk_package(apk_path: Path) -> str:
    """Extract package name from APK using aapt or zipfile."""
    if tool_available("aapt"):
        rc, out, _ = run(["aapt", "dump", "badging", str(apk_path)], check=False)
        for line in out.splitlines():
            if line.startswith("package:"):
                for part in line.split():
                    if part.startswith("name='"):
                        return part[6:].rstrip("'")
    # Fallback: read AndroidManifest.xml from APK
    try:
        with zipfile.ZipFile(apk_path, "r") as z:
            if "AndroidManifest.xml" in z.namelist():
                # Binary XML — look for package name in raw bytes
                data = z.read("AndroidManifest.xml")
                # Crude search for package string
                idx = data.find(b"package")
                if idx > 0:
                    substr = data[idx+8:idx+200]
                    chars = []
                    for b in substr:
                        if 0x20 <= b <= 0x7e:
                            chars.append(chr(b))
                        elif chars and chars[-1] != " ":
                            break
                    pkg = "".join(chars).strip().strip("\"'")
                    if "." in pkg and len(pkg) > 4:
                        return pkg
    except Exception:
        pass
    return apk_path.stem


@wearos.command("patch-sysimg")
@click.argument("extracted_dir")
@click.option("--out", "-o", default=None)
def wearos_patch_sysimg(extracted_dir, out):
    """
    Patch an extracted system image directory for WearOS compatibility.
    Run after: watchrom sysimg extract system.img
    """
    src = Path(extracted_dir)
    if not src.is_dir():
        console.print(f"[red]✗ Not a directory: {extracted_dir}[/red]")
        return

    console.print(f"\n[bold cyan]WearOS System Image Patcher[/bold cyan]")
    console.print(f"  Source: {src}\n")

    # Find build.prop
    bp_candidates = [
        src / "build.prop",
        src / "system" / "build.prop",
    ]
    build_prop = next((p for p in bp_candidates if p.exists()), None)
    if not build_prop:
        console.print("[red]✗ build.prop not found.[/red]")
        return

    console.print(f"[cyan]→ Patching {build_prop}...[/cyan]")
    changes = patch_build_prop_for_wearos(build_prop)
    for action, key, old, new in changes:
        if action == "changed":
            console.print(f"  [yellow]~[/yellow] {key}: {old} → {new}")
        else:
            console.print(f"  [green]+[/green] {key} = {new}")

    # Create WearOS permissions XMLs
    perm_dir = src / "etc" / "permissions"
    if not perm_dir.exists():
        perm_dir = src / "system" / "etc" / "permissions"
    perm_dir.mkdir(parents=True, exist_ok=True)

    for pkg in ["com.google.android.wearable.app", "com.google.android.gms"]:
        xml_path = perm_dir / f"privapp-permissions-{pkg}.xml"
        xml_path.write_text(create_privapp_permissions_xml(pkg, WEAROS_PERMISSIONS))
        console.print(f"  [green]+[/green] {xml_path.name}")

    # Create features XML for WearOS hardware
    features_xml = """\
<?xml version="1.0" encoding="utf-8"?>
<permissions>
    <feature name="android.hardware.type.watch"/>
    <feature name="android.software.app_widgets"/>
    <feature name="com.google.android.wearable.feature.STANDALONE_APPS"/>
    <feature name="com.google.android.wearable.feature.WATCH_FACES"/>
    <feature name="com.google.android.wearable.feature.TILES"/>
    <feature name="com.google.android.wearable.feature.COMPLICATIONS"/>
</permissions>
"""
    features_path = perm_dir / "watchrom_wearos_features.xml"
    features_path.write_text(features_xml)
    console.print(f"  [green]+[/green] {features_path.name}")

    console.print(f"\n[green]✓ System image patched for WearOS compatibility[/green]")
    console.print(f"\n  Repack: [bold]watchrom sysimg repack {src} --label system[/bold]")
    console.print(f"  Flash:  [bold]watchrom flash system system_repacked.img[/bold]")


@wearos.command("companion-guide")
def wearos_companion_guide():
    """Show step-by-step guide to pair your watch with the WearOS phone app."""
    console.print(f"""
[bold cyan]════════════════════════════════════════════════════════[/bold cyan]
[bold white]  WearOS on Full Android Watch — Complete Setup Guide[/bold white]
[bold cyan]════════════════════════════════════════════════════════[/bold cyan]

[bold yellow]PHASE 1 — Prepare the Watch[/bold yellow]

  1. Root your watch:
     [cyan]watchrom root patch[/cyan]

  2. Configure WearOS compatibility:
     [cyan]watchrom wearos setup --method magisk[/cyan]

  3. Install the Magisk module:
     [cyan]watchrom magisk install output/magisk_modules/watchrom_wearos.zip[/cyan]

  4. Reboot watch:
     [cyan]watchrom adb shell reboot[/cyan]

[bold yellow]PHASE 2 — Install WearOS APKs[/bold yellow]

  Get WearOS APKs from APKMirror.com:
    • WearOS by Google (com.google.android.wearable.app)
    • Google Play Services for Wear (com.google.android.gms)
    • Google Services Framework (com.google.android.gsf)
    • Play Store (com.android.vending) — Wear variant

  Download to a folder, then:
  [cyan]watchrom wearos install-apks --apk-dir ~/wear_apks/[/cyan]

  For full system integration (best compatibility):
  [cyan]watchrom wearos install-apks --apk-dir ~/wear_apks/ --system[/cyan]

[bold yellow]PHASE 3 — System Image Method (Permanent)[/bold yellow]

  If you want to bake WearOS into the ROM itself:
  [cyan]watchrom dump boot system vendor[/cyan]
  [cyan]watchrom sysimg extract output/<serial>/partitions/system.img[/cyan]
  [cyan]watchrom wearos patch-sysimg output/sysimg_extracted/system/[/cyan]
  [cyan]watchrom sysimg repack output/sysimg_extracted/system/ --label system[/cyan]
  [cyan]watchrom avb patch --blank[/cyan]
  [cyan]watchrom flash system output/system_repacked.img[/cyan]
  [cyan]watchrom flash vbmeta output/vbmeta_blank.img[/cyan]

[bold yellow]PHASE 4 — Phone Companion Setup[/bold yellow]

  On your Android phone:
    1. Install [bold]WearOS by Google[/bold] from Play Store
    2. Open WearOS app → Add new watch
    3. Select "Set up without phone" if watch not detected
    4. Manually pair via Bluetooth

  Alternatively use [bold]Galaxy Wearable[/bold] or [bold]Zepp[/bold] app
  if your watch was originally designed for those platforms.

[bold yellow]PHASE 5 — WearOS App Sideloading[/bold yellow]

  Any WearOS APK can be sideloaded:
  [cyan]watchrom apk pull com.example.wearapp[/cyan]     ← from paired phone
  [cyan]watchrom adb install WearApp.apk[/cyan]           ← direct install

  Enable unknown sources on watch:
  [cyan]watchrom props set ro.adb.secure 0[/cyan]
  [cyan]watchrom props preset debug[/cyan]

[bold yellow]SUPPORTED WATCH CHIPS[/bold yellow]

  [green]✓ MTK:[/green]  MT6739, MT6761, MT6762, MT6765, MT6768, MT6771, MT6785, MT6789
  [green]✓ Unisoc:[/green] SC9832E, SC9863A, SL8541E, SC8541E, SC9863, UIS8581A

[bold cyan]════════════════════════════════════════════════════════[/bold cyan]
""")


@wearos.command("watchface")
@click.argument("apk_or_dir")
@click.option("--serial", "-s", default=None)
def wearos_watchface(apk_or_dir, serial):
    """Install a WearOS watch face APK on device."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    src = Path(apk_or_dir)
    apks = [src] if src.suffix == ".apk" else list(src.glob("*.apk"))
    if not apks:
        console.print(f"[red]✗ No APKs found.[/red]")
        return

    console.print(f"\n[bold cyan]Watch Face Installer[/bold cyan]")
    for apk in apks:
        console.print(f"  [cyan]Installing {apk.name}...[/cyan]")
        rc, out, err = run_adb(
            ["install", "-r", str(apk)],
            serial=target, check=False, timeout=60
        )
        if rc == 0 and "Success" in out:
            console.print(f"  [green]✓ Installed: {apk.name}[/green]")
            console.print(f"    Open WearOS → Watch faces → Find new faces")
        else:
            console.print(f"  [yellow]! {(out+err).strip()[:80]}[/yellow]")
