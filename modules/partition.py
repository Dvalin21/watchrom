"""
partition.py — Dump and flash partitions via ADB/Fastboot
Supports MTK and Unisoc layouts with /dev/block/by-name resolution
"""
import click
import time
from pathlib import Path
from rich.progress import Progress, BarColumn, TextColumn, TaskProgressColumn, TransferSpeedColumn
from modules import (
    run_adb, run_fastboot, adb_devices, get_device_props,
    detect_chipset_from_props, PARTITION_MAPS, OUTPUT_DIR,
    sha256_file, file_size_mb, console
)


def resolve_block_node(partition: str, serial=None) -> str:
    """Resolve /dev/block/by-name/<part> to real block device."""
    for path in [
        f"/dev/block/by-name/{partition}",
        f"/dev/block/platform/*/by-name/{partition}",
        f"/dev/block/bootdevice/by-name/{partition}",
    ]:
        _, out, _ = run_adb(["shell", f"readlink -f {path} 2>/dev/null"], serial=serial, check=False)
        node = out.strip()
        if node and not node.startswith("readlink"):
            return node
    # Fallback: scan by-name
    _, out, _ = run_adb(["shell", f"find /dev/block -name '{partition}' 2>/dev/null"],
                         serial=serial, check=False)
    node = out.strip().split("\n")[0]
    return node or ""


def get_partition_size_bytes(node: str, serial=None) -> int:
    _, out, _ = run_adb(
        ["shell", f"blockdev --getsize64 {node} 2>/dev/null || stat -c%s {node} 2>/dev/null"],
        serial=serial, check=False
    )
    try:
        return int(out.strip())
    except ValueError:
        return 0


def dump_partition_adb(partition: str, out_path: Path, serial=None) -> bool:
    """Dump a partition by reading the block device over ADB."""
    node = resolve_block_node(partition, serial)
    if not node:
        console.print(f"[red]✗ Could not resolve block node for [{partition}][/red]")
        return False

    size = get_partition_size_bytes(node, serial)
    size_str = f"{size/(1024*1024):.1f} MB" if size else "unknown size"
    console.print(f"  [dim]{partition}[/dim] → [cyan]{node}[/cyan] ({size_str})")

    # Use dd over ADB shell + forward to local file
    cmd_str = f"dd if={node} bs=4096 2>/dev/null | base64"
    # For large partitions, use ADB pull from a temp location if we have root
    # Try root dd → /sdcard temp, then pull
    tmp_remote = f"/sdcard/watchrom_{partition}.img"
    _, out, err = run_adb(
        ["shell", f"su -c 'dd if={node} of={tmp_remote} bs=4096' 2>&1"],
        serial=serial, check=False, timeout=300
    )
    if "Permission denied" in err or "not found" not in out:
        # Try without su (some devices run as root)
        run_adb(["shell", f"dd if={node} of={tmp_remote} bs=4096 2>&1"],
                serial=serial, check=False, timeout=300)

    _, out2, _ = run_adb(["shell", f"ls {tmp_remote} 2>/dev/null"], serial=serial, check=False)
    if tmp_remote in out2:
        rc, _, _ = run_adb(["pull", tmp_remote, str(out_path)], serial=serial, check=False, timeout=300)
        run_adb(["shell", f"rm {tmp_remote}"], serial=serial, check=False)
        if rc == 0 and out_path.exists():
            return True

    console.print(f"  [yellow]! Temp-file method failed. Trying pipe...[/yellow]")
    # Pipe method (slower but works without sdcard write)
    import subprocess, base64
    proc = subprocess.Popen(
        ["adb"] + (["-s", serial] if serial else []) + ["shell", f"su -c 'base64 {node}'"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    b64_data, err = proc.communicate(timeout=600)
    if b64_data:
        try:
            raw = base64.b64decode(b64_data)
            with open(out_path, "wb") as f:
                f.write(raw)
            return True
        except Exception as e:
            console.print(f"  [red]Pipe decode error: {e}[/red]")
    return False


# ─────────────────────────────────────────────────────────────────────────────


@click.command("dump")
@click.argument("partition", required=False, default=None)
@click.option("--serial",  "-s", default=None, help="ADB serial")
@click.option("--all",     "-a", "dump_all", is_flag=True, help="Dump all known partitions")
@click.option("--out",     "-o", default=None, help="Output directory (default: output/<serial>/)")
@click.option("--fastboot","-f", "use_fb", is_flag=True, help="Use fastboot fetch (Android 13+)")
def dump(partition, serial, dump_all, out, use_fb):
    """Dump one or all partitions from device to host."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB devices online.[/red]")
        return

    target = serial or online[0]
    props = get_device_props(target)
    vendor, chipset = detect_chipset_from_props(props)

    out_dir = Path(out) if out else (OUTPUT_DIR / target / "partitions")
    out_dir.mkdir(parents=True, exist_ok=True)

    partitions = PARTITION_MAPS.get(vendor, PARTITION_MAPS["mtk"])

    if dump_all:
        targets = partitions
        console.print(f"\n[bold cyan]Dumping all {len(targets)} partitions ({vendor.upper()} / {chipset})[/bold cyan]")
        console.print(f"[dim]Output → {out_dir}[/dim]\n")
    elif partition:
        targets = [partition]
    else:
        console.print("[red]Specify a partition name or use --all[/red]")
        return

    results = []
    for part in targets:
        out_path = out_dir / f"{part}.img"
        console.print(f"[bold]Dumping:[/bold] {part} ...", end="")

        if use_fb:
            # Fastboot fetch (Android 13+)
            rc, _, err = run_fastboot(
                ["fetch", f"partition:{part}", str(out_path)],
                serial=target, check=False
            )
            success = rc == 0 and out_path.exists()
        else:
            success = dump_partition_adb(part, out_path, serial=target)

        if success and out_path.exists():
            size = file_size_mb(out_path)
            chk  = sha256_file(out_path)[:12]
            console.print(f" [green]✓[/green] {size:.1f} MB  sha256:{chk}…")
            results.append((part, True, out_path, size))
        else:
            console.print(f" [red]✗ FAILED[/red]")
            results.append((part, False, None, 0))

    # Summary
    passed = sum(1 for _, ok, _, _ in results if ok)
    console.print(f"\n[bold]Done:[/bold] {passed}/{len(results)} partitions dumped → [cyan]{out_dir}[/cyan]")

    # Write manifest
    manifest = out_dir / "MANIFEST.txt"
    with open(manifest, "w") as mf:
        mf.write(f"WatchROM Partition Dump Manifest\n")
        mf.write(f"Device:  {target}\nChipset: {chipset}\nVendor:  {vendor}\n\n")
        for part, ok, path, size in results:
            if ok:
                chk = sha256_file(path)
                mf.write(f"{part:20s} {size:8.2f} MB  sha256:{chk}\n")
            else:
                mf.write(f"{part:20s} FAILED\n")
    console.print(f"[dim]Manifest written: {manifest}[/dim]")


@click.command("flash")
@click.argument("partition")
@click.argument("image")
@click.option("--serial",  "-s", default=None)
@click.option("--method",  "-m",
              type=click.Choice(["fastboot","adb","auto"]), default="auto")
@click.option("--no-verify", is_flag=True, help="Skip post-flash verification")
def flash(partition, image, serial, method, no_verify):
    """Flash an image file to a device partition."""
    img_path = Path(image)
    if not img_path.exists():
        console.print(f"[red]✗ Image not found: {image}[/red]")
        return

    size = file_size_mb(img_path)
    chk  = sha256_file(img_path)
    console.print(f"\n[bold cyan]Flash Operation[/bold cyan]")
    console.print(f"  Partition : [green]{partition}[/green]")
    console.print(f"  Image     : {img_path.name} ({size:.1f} MB)")
    console.print(f"  SHA256    : {chk[:24]}…")

    # Confirm
    if not click.confirm("\n[yellow]⚠ This will overwrite the partition. Continue?[/yellow]", default=False):
        console.print("[dim]Aborted.[/dim]")
        return

    if method in ("fastboot", "auto"):
        from modules import fastboot_devices
        fb = fastboot_devices()
        if fb or method == "fastboot":
            target = serial or (fb[0] if fb else None)
            console.print(f"\n[cyan]Flashing via Fastboot → {partition}[/cyan]")
            rc, out, err = run_fastboot(
                ["flash", partition, str(img_path)],
                serial=target, check=False, timeout=300
            )
            if rc == 0:
                console.print(f"[green]✓ Flash complete.[/green]")
                if not no_verify:
                    _verify_flash(partition, img_path, target, via="fastboot")
                return
            else:
                console.print(f"[red]✗ Fastboot flash failed:[/red]\n{err}")
                if method == "fastboot":
                    return

    if method in ("adb", "auto"):
        # ADB dd method (requires root)
        target = serial or (adb_devices()[0][0] if adb_devices() else None)
        node = resolve_block_node(partition, target)
        if not node:
            console.print(f"[red]✗ Block node not found for {partition}[/red]")
            return

        tmp = f"/sdcard/watchrom_flash_{partition}.img"
        console.print(f"[cyan]Pushing image to device ({tmp})...[/cyan]")
        rc, _, _ = run_adb(["push", str(img_path), tmp], serial=target, check=False, timeout=300)
        if rc != 0:
            console.print("[red]✗ ADB push failed.[/red]")
            return

        console.print(f"[cyan]Writing {tmp} → {node} (via dd)...[/cyan]")
        rc, _, err = run_adb(
            ["shell", f"su -c 'dd if={tmp} of={node} bs=4096 && sync'"],
            serial=target, check=False, timeout=300
        )
        run_adb(["shell", f"rm {tmp}"], serial=target, check=False)
        if rc == 0:
            console.print(f"[green]✓ Flash complete.[/green]")
        else:
            console.print(f"[red]✗ ADB dd failed:[/red] {err}")


def _verify_flash(partition, img_path, serial, via="fastboot"):
    """Verify flash by comparing checksums."""
    console.print("[dim]Verifying flash...[/dim]")
    local_hash = sha256_file(img_path)
    node = resolve_block_node(partition, serial)
    if not node:
        console.print("[yellow]! Cannot verify — block node not found.[/yellow]")
        return
    _, out, _ = run_adb(
        ["shell", f"su -c 'sha256sum {node}'"],
        serial=serial, check=False
    )
    remote_hash = out.strip().split()[0] if out.strip() else ""
    if local_hash == remote_hash:
        console.print(f"[green]✓ Verified: SHA256 match.[/green]")
    else:
        console.print(f"[red]✗ Hash mismatch! local={local_hash[:12]}… remote={remote_hash[:12]}…[/red]")
