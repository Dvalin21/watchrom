"""
network.py — Network, WiFi, BT, and RIL diagnostics for Android devices
Packet capture, interface inspection, network stack info
"""
import click
import subprocess
from pathlib import Path
from modules import run_adb, adb_devices, OUTPUT_DIR, console


@click.group()
def network():
    """Network, WiFi, Bluetooth, and RIL/modem diagnostics."""
    pass


@network.command("info")
@click.option("--serial", "-s", default=None)
def network_info(serial):
    """Show full network configuration: WiFi, BT, cellular, interfaces."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    console.print(f"\n[bold cyan]Network Info — {target}[/bold cyan]\n")

    sections = [
        ("Network Interfaces",   "ip addr show 2>/dev/null || ifconfig 2>/dev/null"),
        ("Routing Table",        "ip route show 2>/dev/null || route 2>/dev/null"),
        ("DNS",                  "getprop net.dns1; getprop net.dns2"),
        ("WiFi State",           "dumpsys wifi 2>/dev/null | grep -E '(mWifiState|SSID|BSSID|linkspeed|rssi)' | head -10"),
        ("WiFi Scan Results",    "dumpsys wifi 2>/dev/null | grep 'ScanResult' | head -10"),
        ("Bluetooth State",      "dumpsys bluetooth_manager 2>/dev/null | grep -E '(state|enabled|address)' | head -8"),
        ("RIL / Cellular",       "getprop gsm.network.type; getprop gsm.operator.alpha; getprop ril.iccid.sim1 2>/dev/null"),
        ("APN Settings",         "content query --uri content://telephony/carriers/preferapn 2>/dev/null | head -5"),
        ("Network Props",        "getprop | grep -E '(net\\.|wifi\\.|ril\\.)' | head -20"),
    ]

    for title, cmd in sections:
        console.print(f"[bold yellow]── {title} ──[/bold yellow]")
        _, out, _ = run_adb(["shell", cmd], serial=target, check=False)
        for line in out.strip().splitlines()[:12]:
            console.print(f"  [dim]{line}[/dim]")
        console.print()


@network.command("capture")
@click.option("--serial",    "-s", default=None)
@click.option("--iface",     "-i", default="wlan0", help="Interface to capture on")
@click.option("--duration",  "-d", default=30,      type=int,  help="Capture duration seconds")
@click.option("--out",       "-o", default=None,    help="Output .pcap file")
@click.option("--filter",    "-f", default="",      help="tcpdump filter expression")
def network_capture(serial, iface, duration, out, filter):
    """
    Capture network packets from device via tcpdump over ADB.

    Requires tcpdump on device (Magisk module or pre-installed).
    Output is a .pcap file openable in Wireshark.
    """
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    out_path  = Path(out) if out else (OUTPUT_DIR / f"capture_{iface}.pcap")
    remote_cap = f"/sdcard/watchrom_capture.pcap"

    console.print(f"[cyan]Capturing on {iface} for {duration}s → {out_path}[/cyan]")
    console.print("[dim]Requires tcpdump on device. Ctrl+C to stop early.[/dim]\n")

    filter_str = f" {filter}" if filter else ""
    cmd_str = f"su -c 'tcpdump -i {iface} -w {remote_cap}{filter_str}'"

    # Start tcpdump in background, kill after duration
    import time
    proc = subprocess.Popen(
        ["adb", "-s", target, "shell", cmd_str],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    try:
        time.sleep(duration)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped early.[/yellow]")
    finally:
        proc.terminate()
        run_adb(["shell", "su -c 'pkill tcpdump'"], serial=target, check=False)

    time.sleep(1)
    rc, _, _ = run_adb(["pull", remote_cap, str(out_path)], serial=target, check=False)
    if rc == 0 and out_path.exists():
        from modules import file_size_mb
        console.print(f"[green]✓ Capture saved: {out_path} ({file_size_mb(out_path):.1f} MB)[/green]")
        console.print(f"  Open in Wireshark: wireshark {out_path}")
    else:
        console.print("[red]✗ Capture failed. Is tcpdump installed on device?[/red]")
        console.print("  Install via Magisk module: 'Busybox for Android NDK' includes tcpdump")


@network.command("ril")
@click.option("--serial", "-s", default=None)
def network_ril(serial):
    """Show RIL (Radio Interface Layer) and modem status — useful for watch LTE debugging."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    console.print(f"\n[bold cyan]RIL / Modem Status — {target}[/bold cyan]\n")

    ril_props = [
        "gsm.version.ril-impl",
        "gsm.network.type",
        "gsm.operator.alpha",
        "gsm.operator.numeric",
        "gsm.operator.iso-country",
        "gsm.sim.state",
        "ril.iccid.sim1",
        "ril.iccid.sim2",
        "persist.vendor.radio.multisim.config",
        "ro.vendor.build.rf_version",
        "ro.telephony.default_network",
    ]
    for prop in ril_props:
        _, val, _ = run_adb(["shell", f"getprop {prop}"], serial=target, check=False)
        val = val.strip()
        if val:
            console.print(f"  [cyan]{prop:45s}[/cyan] {val}")

    console.print()
    _, rild, _ = run_adb(
        ["shell", "ps -A 2>/dev/null | grep -E '(rild|ril|modem)' | head -5"],
        serial=target, check=False
    )
    console.print(f"[bold]RIL processes:[/bold]")
    for line in rild.strip().splitlines():
        console.print(f"  [dim]{line}[/dim]")


@network.command("hosts")
@click.option("--serial",  "-s", default=None)
@click.option("--add",     "-a", multiple=True,
              help="Add host entry: 'ip hostname' (e.g. '0.0.0.0 ads.example.com')")
@click.option("--block-ads", is_flag=True,
              help="Push a basic ad-blocking hosts file")
@click.option("--show",    is_flag=True, help="Show current hosts file")
def network_hosts(serial, add, block_ads, show):
    """
    Manage the device /etc/hosts file (requires root).
    Block domains, add custom entries, or show current state.
    """
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    if show:
        _, out, _ = run_adb(["shell", "cat /etc/hosts"], serial=target, check=False)
        console.print(f"\n[bold]/etc/hosts:[/bold]\n{out}")
        return

    if not add and not block_ads:
        console.print("[dim]Use --show, --add 'ip host', or --block-ads[/dim]")
        return

    _, current_hosts, _ = run_adb(["shell", "cat /etc/hosts"], serial=target, check=False)
    new_hosts = current_hosts.rstrip()

    if add:
        for entry in add:
            new_hosts += f"\n{entry}"
            console.print(f"[green]+ {entry}[/green]")

    if block_ads:
        # Basic ad/tracker block list
        block_list = [
            "0.0.0.0 doubleclick.net",
            "0.0.0.0 googleadservices.com",
            "0.0.0.0 googlesyndication.com",
            "0.0.0.0 ads.google.com",
            "0.0.0.0 adservice.google.com",
            "0.0.0.0 pagead2.googlesyndication.com",
            "0.0.0.0 ads.facebook.com",
            "0.0.0.0 an.facebook.com",
            "0.0.0.0 analytics.facebook.com",
            "0.0.0.0 graph.facebook.com",
        ]
        for entry in block_list:
            if entry.split()[-1] not in current_hosts:
                new_hosts += f"\n{entry}"
        console.print(f"[green]+ {len(block_list)} ad-block entries added[/green]")

    # Push new hosts file
    hosts_tmp = Path("/tmp/watchrom_hosts")
    hosts_tmp.write_text(new_hosts + "\n")
    run_adb(["push", str(hosts_tmp), "/sdcard/hosts_new"], serial=target, check=False)
    run_adb(
        ["shell", "su -c 'mount -o rw,remount /system && "
         "cp /sdcard/hosts_new /etc/hosts && "
         "chmod 644 /etc/hosts && "
         "mount -o ro,remount /system'"],
        serial=target, check=False
    )
    console.print(f"[green]✓ Hosts file updated.[/green]")
