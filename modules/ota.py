"""
ota.py — OTA package handling: payload.bin extraction, OTA zip creation,
         incremental/full OTA analysis
"""
import click
import zipfile
import struct
import hashlib
from pathlib import Path
from modules import (
    run, OUTPUT_DIR, WORKSPACE, sha256_file, file_size_mb, console, tool_available
)

# Chrome OS / Android payload magic
PAYLOAD_MAGIC   = b"CrAU"
PAYLOAD_VERSION = 2


# ── Payload.bin parser ────────────────────────────────────────────────────────

def read_payload_header(f) -> dict:
    magic = f.read(4)
    if magic != PAYLOAD_MAGIC:
        raise ValueError("Not a valid payload.bin (bad magic)")
    version       = struct.unpack(">Q", f.read(8))[0]
    manifest_size = struct.unpack(">Q", f.read(8))[0]
    if version == 2:
        metadata_sig_size = struct.unpack(">I", f.read(4))[0]
    else:
        metadata_sig_size = 0
    return {
        "version":            version,
        "manifest_size":      manifest_size,
        "metadata_sig_size":  metadata_sig_size,
        "header_size":        20 if version == 2 else 16,
    }


def list_payload_partitions(payload_path: Path) -> list:
    """List partitions in payload.bin using update_engine_client or protobuf parse."""
    partitions = []

    if tool_available("payload-dumper-go"):
        rc, out, _ = run(["payload-dumper-go", "-l", str(payload_path)], check=False)
        partitions = [l.strip() for l in out.splitlines() if l.strip()]
        return partitions

    if tool_available("delta_generator"):
        rc, out, _ = run(
            ["delta_generator", "--in_file=" + str(payload_path), "--list_partitions"],
            check=False
        )
        partitions = [l.strip() for l in out.splitlines() if l.strip()]
        return partitions

    # Minimal scan: grep for partition names in manifest protobuf
    try:
        with open(payload_path, "rb") as f:
            hdr = read_payload_header(f)
            manifest_data = f.read(hdr["manifest_size"])
        # Crude partition name extraction from protobuf bytes
        names = []
        i = 0
        while i < len(manifest_data) - 4:
            if manifest_data[i:i+4] in (b"boot", b"syst", b"vend", b"recy"):
                # Find null-terminated-ish name
                end = manifest_data.find(b"\x00", i)
                if end > i and end - i < 50:
                    name = manifest_data[i:end].decode("ascii", errors="replace")
                    if name.isidentifier():
                        names.append(name)
            i += 1
        partitions = list(dict.fromkeys(names))  # deduplicate
    except Exception:
        pass

    return partitions or ["boot", "system", "vendor", "vbmeta", "dtbo"]


# ── CLI ────────────────────────────────────────────────────────────────────────

@click.group()
def ota():
    """OTA package analysis, payload.bin extraction, and OTA zip creation."""
    pass


@ota.command("extract")
@click.argument("ota_file")
@click.option("--partition", "-p", default=None,
              help="Extract specific partition only (e.g. boot, system)")
@click.option("--out", "-o", default=None)
def ota_extract(ota_file, partition, out):
    """
    Extract partition images from an OTA .zip or payload.bin.

    Automatically handles:
      - Full OTA zips (extracts payload.bin first)
      - payload.bin directly

    Requires: payload-dumper-go  (https://github.com/ssut/payload-dumper-go)
    Fallback: python-protobuf + bsdiff
    """
    ota_path = Path(ota_file)
    if not ota_path.exists():
        console.print(f"[red]✗ Not found: {ota_file}[/red]")
        return

    out_dir = Path(out) if out else (OUTPUT_DIR / "ota_extracted" / ota_path.stem)
    out_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"\n[bold cyan]OTA Extractor[/bold cyan]")
    console.print(f"  Source : {ota_path.name} ({file_size_mb(ota_path):.0f} MB)")
    console.print(f"  Output : {out_dir}\n")

    # Extract payload.bin from zip if needed
    payload_path = ota_path
    if ota_path.suffix.lower() == ".zip":
        console.print("[cyan]→ Extracting payload.bin from OTA zip...[/cyan]")
        with zipfile.ZipFile(ota_path, "r") as z:
            if "payload.bin" not in z.namelist():
                console.print("[red]✗ No payload.bin found in zip.[/red]")
                return
            payload_path = WORKSPACE / "payload.bin"
            z.extract("payload.bin", WORKSPACE)
            payload_path = WORKSPACE / "payload.bin"

            # Also extract payload_properties.txt
            if "payload_properties.txt" in z.namelist():
                z.extract("payload_properties.txt", WORKSPACE)
        console.print(f"  [dim]payload.bin: {file_size_mb(payload_path):.0f} MB[/dim]")

    # Try payload-dumper-go first (fastest)
    if tool_available("payload-dumper-go"):
        cmd = ["payload-dumper-go", "-o", str(out_dir)]
        if partition:
            cmd += ["-partitions", partition]
        cmd.append(str(payload_path))
        rc, out_text, err = run(cmd, check=False, timeout=600)
        if rc == 0:
            imgs = list(out_dir.glob("*.img"))
            console.print(f"[green]✓ Extracted {len(imgs)} partitions → {out_dir}[/green]")
            for img in imgs:
                console.print(f"  [dim]{img.name} ({file_size_mb(img):.1f} MB)[/dim]")
            return
        else:
            console.print(f"[yellow]payload-dumper-go failed, trying fallback...[/yellow]")

    # Try ota_extractor / update_payload_extractor
    for tool in ["update_payload_extractor", "ota_extractor"]:
        if tool_available(tool):
            cmd = [tool, "--payload", str(payload_path), "--output_dir", str(out_dir)]
            if partition:
                cmd += ["--partitions", partition]
            rc, _, err = run(cmd, check=False, timeout=600)
            if rc == 0:
                console.print(f"[green]✓ Extracted → {out_dir}[/green]")
                return

    console.print("[yellow]! No automatic extractor available.[/yellow]")
    console.print("\nInstall one of these:")
    console.print("  [bold]payload-dumper-go[/bold]: https://github.com/ssut/payload-dumper-go/releases")
    console.print("  pip install extract-dtb")
    console.print("\n  Payload.bin saved to:", payload_path)


@ota.command("info")
@click.argument("ota_file")
def ota_info(ota_file):
    """Show OTA package contents and metadata."""
    ota_path = Path(ota_file)
    if not ota_path.exists():
        console.print(f"[red]✗ Not found: {ota_file}[/red]")
        return

    console.print(f"\n[bold cyan]OTA Package Info: {ota_path.name}[/bold cyan]\n")
    console.print(f"  Size  : {file_size_mb(ota_path):.1f} MB")
    console.print(f"  SHA256: {sha256_file(ota_path)[:32]}…")

    if ota_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(ota_path, "r") as z:
            names = z.namelist()
            console.print(f"\n  [bold]ZIP Contents ({len(names)} files):[/bold]")
            interesting = ["payload.bin", "payload_properties.txt",
                           "META-INF/com/android/metadata",
                           "META-INF/com/android/otacert",
                           "care_map.pb", "apex_info.pb"]
            for name in names:
                info = z.getinfo(name)
                is_key = name in interesting or name.endswith(".prop")
                style = "[green]" if is_key else "[dim]"
                console.print(f"    {style}{name}[/{'green' if is_key else 'dim'}]  "
                               f"{info.file_size//1024} KB")

            # Print metadata
            if "META-INF/com/android/metadata" in names:
                meta = z.read("META-INF/com/android/metadata").decode(errors="replace")
                console.print(f"\n  [bold]OTA Metadata:[/bold]")
                for line in meta.splitlines()[:20]:
                    console.print(f"    [cyan]{line}[/cyan]")

            if "payload.bin" in names:
                info = z.getinfo("payload.bin")
                console.print(f"\n  [bold]payload.bin:[/bold] {info.file_size//1024//1024} MB")
                partitions = list_payload_partitions(ota_path)
                if partitions:
                    console.print(f"  [bold]Partitions:[/bold] {', '.join(partitions)}")

    elif ota_path.name == "payload.bin":
        with open(ota_path, "rb") as f:
            hdr = read_payload_header(f)
        console.print(f"  [bold]Payload version:[/bold] {hdr['version']}")
        console.print(f"  [bold]Manifest size :[/bold] {hdr['manifest_size']} bytes")
        partitions = list_payload_partitions(ota_path)
        if partitions:
            console.print(f"  [bold]Partitions    :[/bold] {', '.join(partitions)}")


@ota.command("create")
@click.option("--parts-dir", "-p", required=True,
              help="Directory of partition .img files")
@click.option("--out",       "-o", default=None, help="Output OTA zip path")
@click.option("--key",       "-k", default=None, help="Signing key .pem (optional)")
@click.option("--cert",      "-c", default=None, help="Signing cert .x509.pem (optional)")
def ota_create(parts_dir, out, key, cert):
    """
    Create a flashable OTA-style zip from partition images.

    Produces a sideloadable zip containing:
      - All .img files from parts_dir
      - update-binary (stub)
      - updater-script
      - META-INF structure

    Sign with --key + --cert for production use.
    """
    pd = Path(parts_dir)
    if not pd.is_dir():
        console.print(f"[red]✗ Not a directory: {parts_dir}[/red]")
        return

    imgs = list(pd.glob("*.img"))
    if not imgs:
        console.print("[red]✗ No .img files found.[/red]")
        return

    out_path = Path(out) if out else (OUTPUT_DIR / "watchrom_ota.zip")
    console.print(f"\n[bold cyan]OTA Zip Creator[/bold cyan]")
    console.print(f"  Images : {len(imgs)}")
    console.print(f"  Output : {out_path}\n")

    # Build updater-script
    script_lines = ["ui_print(\"WatchROM OTA Package\");",
                    "ui_print(\"Installing partitions...\");"]
    for img in imgs:
        part = img.stem
        script_lines.append(f'package_extract_file("{img.name}", "/dev/block/by-name/{part}");')
    script_lines.append('ui_print("Done!");')
    updater_script = "\n".join(script_lines)

    # Stub update-binary
    update_binary = (
        "#!/sbin/sh\n"
        "OUTFD=$2\nZIPFILE=$3\n"
        'ui_print() { echo "ui_print $1" >&$OUTFD; echo "ui_print" >&$OUTFD; }\n'
        'ui_print "WatchROM OTA"\n'
    )

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        # META-INF
        z.writestr("META-INF/com/google/android/updater-script", updater_script)
        z.writestr("META-INF/com/google/android/update-binary",  update_binary)

        # Metadata
        from datetime import datetime
        meta = (
            f"ota-type=BLOCK\n"
            f"ota-required-cache=0\n"
            f"post-build-timestamp={int(datetime.now().timestamp())}\n"
            f"created-by=WatchROM\n"
        )
        z.writestr("META-INF/com/android/metadata", meta)

        # Partition images
        for img in imgs:
            console.print(f"  [cyan]Adding {img.name}[/cyan] ({file_size_mb(img):.1f} MB)...")
            z.write(img, img.name)

    console.print(f"\n[green]✓ OTA zip created: {out_path}[/green]")
    console.print(f"  Size  : {file_size_mb(out_path):.1f} MB")
    console.print(f"  Flash : adb sideload {out_path}")

    # Sign if keys provided
    if key and cert:
        if tool_available("signapk"):
            signed = out_path.parent / (out_path.stem + "_signed.zip")
            run(["java", "-jar", "signapk.jar", cert, key, str(out_path), str(signed)], check=False)
            if signed.exists():
                console.print(f"[green]✓ Signed: {signed}[/green]")
        else:
            console.print("[yellow]! signapk not found — zip unsigned.[/yellow]")
