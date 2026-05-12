"""
adb_cmds.py — ADB utility commands: shell, push, pull, install, logcat
"""
import click
import subprocess
from pathlib import Path
from modules import run_adb, adb_devices, console


@click.group("adb")
def adb_grp():
    """ADB utility commands (shell, push, pull, logcat, install)."""
    pass


def _target(serial):
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device online.[/red]")
        return None
    return serial or online[0]


@adb_grp.command("shell")
@click.argument("cmd", nargs=-1)
@click.option("--serial", "-s", default=None)
def adb_shell(cmd, serial):
    """Run an ADB shell command (or interactive shell if no command given)."""
    target = _target(serial)
    if not target:
        return
    adb_cmd = ["adb", "-s", target, "shell"]
    if cmd:
        adb_cmd += list(cmd)
    subprocess.run(adb_cmd)


@adb_grp.command("push")
@click.argument("local")
@click.argument("remote")
@click.option("--serial", "-s", default=None)
def adb_push(local, remote, serial):
    """Push a file or directory to device."""
    target = _target(serial)
    if not target:
        return
    rc, out, err = run_adb(["push", local, remote], serial=target, check=False, timeout=300)
    if rc == 0:
        console.print(f"[green]✓ Pushed: {local} → {remote}[/green]")
    else:
        console.print(f"[red]✗ Push failed: {err}[/red]")


@adb_grp.command("pull")
@click.argument("remote")
@click.argument("local", required=False, default=".")
@click.option("--serial", "-s", default=None)
def adb_pull(remote, local, serial):
    """Pull a file or directory from device."""
    target = _target(serial)
    if not target:
        return
    rc, out, err = run_adb(["pull", remote, local], serial=target, check=False, timeout=300)
    if rc == 0:
        console.print(f"[green]✓ Pulled: {remote} → {local}[/green]")
    else:
        console.print(f"[red]✗ Pull failed: {err}[/red]")


@adb_grp.command("install")
@click.argument("apk")
@click.option("--serial", "-s", default=None)
@click.option("--replace", "-r", is_flag=True, default=True)
@click.option("--downgrade", "-d", is_flag=True)
def adb_install(apk, serial, replace, downgrade):
    """Install an APK on device."""
    target = _target(serial)
    if not target:
        return
    args = ["install"]
    if replace:    args.append("-r")
    if downgrade:  args.append("-d")
    args.append(apk)
    rc, out, err = run_adb(args, serial=target, check=False, timeout=120)
    if rc == 0 and "Success" in out:
        console.print(f"[green]✓ Installed: {Path(apk).name}[/green]")
    else:
        console.print(f"[red]✗ Install failed: {out or err}[/red]")


@adb_grp.command("logcat")
@click.option("--serial", "-s", default=None)
@click.option("--filter", "-f", "tag_filter", default="*:D", help="Logcat filter spec")
@click.option("--out",    "-o", default=None, help="Save to file")
def adb_logcat(serial, tag_filter, out):
    """Stream device logcat (Ctrl+C to stop)."""
    target = _target(serial)
    if not target:
        return
    cmd = ["adb", "-s", target, "logcat", "-v", "threadtime", tag_filter]
    console.print(f"[cyan]Streaming logcat from {target} (Ctrl+C to stop)...[/cyan]\n")
    if out:
        with open(out, "w") as f:
            subprocess.run(cmd, stdout=f, text=True)
    else:
        subprocess.run(cmd)


@adb_grp.command("devices")
def adb_devices_cmd():
    """List all connected ADB and Fastboot devices."""
    from modules import adb_devices, fastboot_devices
    console.print("\n[bold cyan]Connected Devices[/bold cyan]\n")
    adb_list = adb_devices()
    fb_list  = fastboot_devices()
    if adb_list:
        console.print("[bold]ADB:[/bold]")
        for s, st in adb_list:
            console.print(f"  [green]{s}[/green]  {st}")
    if fb_list:
        console.print("[bold]Fastboot:[/bold]")
        for s in fb_list:
            console.print(f"  [magenta]{s}[/magenta]  fastboot")
    if not adb_list and not fb_list:
        console.print("[yellow]No devices found.[/yellow]")
