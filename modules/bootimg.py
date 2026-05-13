"""
bootimg.py — boot.img / recovery.img unpacking, editing, and repacking
Handles: Android boot v0/v1/v2/v3/v4, DTBO, kernel extraction, ramdisk editing
"""
import click
import shutil
import struct
import os
from pathlib import Path
from modules import (
    run, OUTPUT_DIR, WORKSPACE, sha256_file, file_size_mb, console, tool_available
)

ANDROID_MAGIC     = b"ANDROID!"
VENDOR_BOOT_MAGIC = b"VNDRBOOT"

# VENDOR_BOOT header v3: 72 bytes, v4: 100 bytes
# For a v3/v4 GKI device:
#   boot.img        → kernel only (no ramdisk)
#   vendor_boot.img → ramdisk + DTBs + vendor cmdline
#   init_boot.img   → init ramdisk (Android 13+, separate partition)

# ── Header parser ──────────────────────────────────────────────────────────────

def parse_boot_header(img: Path) -> dict:
    with open(img, "rb") as f:
        data = f.read(4096)

    if data[:8] != ANDROID_MAGIC:
        raise ValueError(f"Not a valid Android boot image: {img}")

    hdr = {
        "magic":              data[:8].decode(),
        "kernel_size":        struct.unpack_from("<I", data, 8)[0],
        "kernel_addr":        struct.unpack_from("<I", data, 12)[0],
        "ramdisk_size":       struct.unpack_from("<I", data, 16)[0],
        "ramdisk_addr":       struct.unpack_from("<I", data, 20)[0],
        "second_size":        struct.unpack_from("<I", data, 24)[0],
        "second_addr":        struct.unpack_from("<I", data, 28)[0],
        "tags_addr":          struct.unpack_from("<I", data, 32)[0],
        "page_size":          struct.unpack_from("<I", data, 36)[0],
        "header_version":     struct.unpack_from("<I", data, 40)[0],
        "os_version":         struct.unpack_from("<I", data, 44)[0],
        "name":               data[48:64].rstrip(b"\x00").decode("utf-8", errors="replace"),
        "cmdline":            data[64:576].rstrip(b"\x00").decode("utf-8", errors="replace"),
        "id":                 data[576:608].hex(),
        "extra_cmdline":      data[608:672].rstrip(b"\x00").decode("utf-8", errors="replace"),
    }

    # v1: recovery dtbo (header_version == 1 or 2, NOT v3/v4)
    # v3 header = 1640 bytes — 1632+ fields DON'T EXIST
    # v4 header = 1580 bytes — 1632+ is OUTSIDE header (reads kernel data)
    if hdr["header_version"] == 1 or hdr["header_version"] == 2:
        hdr["recovery_dtbo_size"]   = struct.unpack_from("<I",  data, 1632)[0]
        hdr["recovery_dtbo_offset"] = struct.unpack_from("<Q",  data, 1636)[0]
        hdr["header_size"]          = struct.unpack_from("<I",  data, 1644)[0]

    # v2: dtb (header_version == 2 only — v3/v4 dtb lives in vendor_boot)
    if hdr["header_version"] == 2:
        hdr["dtb_size"] = struct.unpack_from("<I", data, 1648)[0]
        hdr["dtb_addr"] = struct.unpack_from("<Q", data, 1652)[0]

    # v3/v4: GKI — ramdisk is in vendor_boot.img or init_boot.img
    if hdr["header_version"] >= 3:
        hdr["gki"] = True
        hdr["ramdisk_in_vendor_boot"] = True
    else:
        hdr["gki"] = False
        hdr["ramdisk_in_vendor_boot"] = False

    return hdr


def parse_vendor_boot_header(img: Path) -> dict:
    """Parse vendor_boot.img header (v3/v4).

    Android GKI devices split the boot image:
      boot.img → kernel only (header v3/v4)
      vendor_boot.img → ramdisk + DTBs + vendor cmdline

    v3 header: 72 bytes
    v4 header: 100 bytes (adds vendor ramdisk table)

    Returns dict with all header fields.
    """
    with open(img, "rb") as f:
        data = f.read(4096)

    if data[:8] != VENDOR_BOOT_MAGIC:
        raise ValueError(f"Not a valid vendor_boot image: {img}")

    hdr = {
        "magic":              data[:8].decode(),
        "header_version":     struct.unpack_from("<I", data, 8)[0],
        "page_size":          struct.unpack_from("<I", data, 12)[0],
        "kernel_addr":        struct.unpack_from("<Q", data, 16)[0],
        "kernel_size":        struct.unpack_from("<I", data, 24)[0],
        "ramdisk_offset":     struct.unpack_from("<Q", data, 28)[0],
        "ramdisk_size":       struct.unpack_from("<Q", data, 36)[0],
        "dtb_offset":         struct.unpack_from("<Q", data, 44)[0],
        "dtb_size":           struct.unpack_from("<Q", data, 52)[0],
        "vendor_cmdline_size": struct.unpack_from("<I", data, 60)[0],
    }

    # vendor_cmdline_offset at byte 64 (8 bytes)
    hdr["vendor_cmdline_offset"] = struct.unpack_from("<Q", data, 64)[0]

    # v4: vendor ramdisk table at bytes 72-83 (4+4+4+reserved)
    ver = hdr["header_version"]
    if ver == 4:
        hdr["vendor_ramdisk_table_size"] = struct.unpack_from("<I", data, 72)[0]
        hdr["vendor_ramdisk_table_entry_num"] = struct.unpack_from("<I", data, 76)[0]
        hdr["vendor_ramdisk_table_entry_size"] = struct.unpack_from("<I", data, 80)[0]
    else:
        hdr["vendor_ramdisk_table_size"] = 0
        hdr["vendor_ramdisk_table_entry_num"] = 0
        hdr["vendor_ramdisk_table_entry_size"] = 0

    hdr["gki"] = True
    hdr["vendor_cmd"] = ""
    if hdr["vendor_cmdline_size"] > 0:
        cmd_offset = hdr.get("vendor_cmdline_offset",
                             hdr["page_size"])  # default: start of page 1
        if cmd_offset < len(data) - hdr["vendor_cmdline_size"]:
            hdr["vendor_cmd"] = data[cmd_offset:cmd_offset + hdr["vendor_cmdline_size"]].rstrip(b"\x00").decode("utf-8", errors="replace")

    return hdr


def unpack_vendor_boot(img: Path, out_dir: Path) -> dict:
    """Unpack vendor_boot.img into component files.

    Extracts:
      ramdisk.cpio.gz — the main ramdisk
      dtb             — device tree blob (if present)
      kernel          — kernel (if kernel_size > 0, rare in GKI)
      vendor_cmdline  — vendor command line
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    hdr = parse_vendor_boot_header(img)
    page = hdr["page_size"]

    console.print(f"\n  [yellow]GKI vendor_boot image (v{hdr['header_version']})[/yellow]")
    console.print(f"  [yellow]  Ramdisk size: {hdr['ramdisk_size']} bytes[/yellow]")

    with open(img, "rb") as f:
        # Page 0 = header
        f.seek(page)

        # Kernel (if present in vendor_boot — unusual for GKI)
        if hdr["kernel_size"] > 0:
            kernel_data = f.read(hdr["kernel_size"])
            (out_dir / "vendor_kernel").write_bytes(kernel_data)
            # Align to page
            remaining = page - (hdr["kernel_size"] % page)
            if remaining < page:
                f.seek(page + (hdr["kernel_size"] + page - 1) // page * page)

        # Ramdisk
        if hdr["ramdisk_size"] > 0:
            ramdisk_offset = int(hdr["ramdisk_offset"])
            f.seek(ramdisk_offset)
            ramdisk_data = f.read(hdr["ramdisk_size"])
            ramdisk_path = out_dir / "ramdisk.cpio.gz"
            ramdisk_path.write_bytes(ramdisk_data)
            console.print(f"  [green]✓ Ramdisk extracted: {ramdisk_path}[/green]")

            # Try to extract ramdisk contents
            ramdisk_dir = out_dir / "ramdisk"
            extract_ramdisk(ramdisk_path, ramdisk_dir)
            file_count = sum(1 for _ in ramdisk_dir.rglob("*")) if ramdisk_dir.exists() else 0
            console.print(f"  [dim]  Ramdisk: {file_count} files[/dim]")
        else:
            console.print(f"  [dim]  No ramdisk in vendor_boot[/dim]")
            (out_dir / "ramdisk.cpio.gz").write_bytes(b"")

        # DTB
        if hdr["dtb_size"] > 0:
            dtb_offset = int(hdr["dtb_offset"])
            f.seek(dtb_offset)
            dtb_data = f.read(hdr["dtb_size"])
            (out_dir / "dtb").write_bytes(dtb_data)
            console.print(f"  [green]✓ DTB extracted: {hdr['dtb_size']} bytes[/green]")

        # Vendor cmdline
        if hdr["vendor_cmd"]:
            (out_dir / "vendor_cmdline").write_text(hdr["vendor_cmd"])
            console.print(f"  [dim]  Vendor cmdline: {hdr['vendor_cmd'][:60]}[/dim]")

    # Save header
    import json
    with open(out_dir / "header.json", "w") as f:
        json.dump(hdr, f, indent=2, default=str)

    return hdr


def repack_vendor_boot(unpacked_dir: Path, out_img: Path):
    """Repack unpacked vendor_boot directory back into vendor_boot.img."""
    import json
    hdr_path = unpacked_dir / "header.json"
    if not hdr_path.exists():
        raise FileNotFoundError("header.json not found — run bootimg unpack-vendor first")

    with open(hdr_path) as f:
        hdr = json.load(f)

    page = hdr["page_size"]
    ramdisk_path = unpacked_dir / "ramdisk.cpio.gz"
    ramdisk_dir = unpacked_dir / "ramdisk"
    dtb_path = unpacked_dir / "dtb"

    # Re-pack ramdisk if directory was modified
    if ramdisk_dir.exists():
        if not ramdisk_path.exists() or \
           ramdisk_dir.stat().st_mtime > ramdisk_path.stat().st_mtime:
            console.print("[cyan]→ Repacking modified ramdisk...[/cyan]")
            repack_ramdisk(ramdisk_dir, ramdisk_path)

    ramdisk_data = ramdisk_path.read_bytes() if ramdisk_path.exists() else b""
    dtb_data = dtb_path.read_bytes() if dtb_path.exists() else b""

    if tool_available("mkbootimg"):
        cmd = [
            "mkbootimg",
            "--vendor_boot", str(out_img),
            "--vendor_boot_version", str(hdr.get("header_version", 3)),
            "--pagesize", str(page),
        ]
        if ramdisk_data:
            cmd += ["--ramdisk", str(ramdisk_path)]
        if dtb_data:
            cmd += ["--dtb", str(dtb_path)]
        run(cmd)
        console.print(f"[green]✓ Repacked vendor_boot: {out_img}[/green]")
        return

    # Manual repack (no mkbootimg)
    _manual_repack_vendor_boot(hdr, ramdisk_data, dtb_data, out_img)


def _manual_repack_vendor_boot(hdr: dict, ramdisk: bytes, dtb: bytes, out: Path):
    """Minimal vendor_boot repack when mkbootimg is unavailable."""
    page = hdr["page_size"]

    def pad(data, p):
        rem = len(data) % p
        return data + b"\x00" * (p - rem) if rem else data

    # Build header
    buf = bytearray(page)
    buf[0:8] = VENDOR_BOOT_MAGIC
    struct.pack_into("<I", buf, 8,  hdr.get("header_version", 3))
    struct.pack_into("<I", buf, 12, page)
    struct.pack_into("<Q", buf, 16, hdr.get("kernel_addr", 0))
    struct.pack_into("<I", buf, 24, hdr.get("kernel_size", 0))
    struct.pack_into("<Q", buf, 28, page * 2)  # ramdisk_offset: after header + kernel pages
    struct.pack_into("<Q", buf, 36, len(ramdisk))
    struct.pack_into("<Q", buf, 44, 0)  # dtb_offset (filled after ramdisk)
    struct.pack_into("<Q", buf, 52, len(dtb))
    struct.pack_into("<I", buf, 60, 0)  # vendor_cmdline_size
    struct.pack_into("<Q", buf, 64, 0)  # vendor_cmdline_offset

    # Compute offsets
    offset = page * 2  # After header + kernel page
    ramdisk_pages = (len(ramdisk) + page - 1) // page
    if len(dtb) > 0:
        struct.pack_into("<Q", buf, 44, offset + ramdisk_pages * page)

    with open(out, "wb") as f:
        f.write(bytes(buf))
        f.write(pad(b"", page))  # kernel page (empty for GKI)
        f.write(pad(ramdisk, page))
        if dtb:
            f.write(pad(dtb, page))

    console.print(f"[yellow]⚠ Manual vendor_boot repack: {out} ([dim]size: {len(ramdisk)//1024}K ramdisk[/dim])[/yellow]")


def pages(size: int, page_size: int) -> int:
    return (size + page_size - 1) // page_size


# ── Unpack ─────────────────────────────────────────────────────────────────────

def unpack_boot(img: Path, out_dir: Path) -> dict:
    """Unpack boot.img into component files.

    v3/v4 (GKI): Only kernel is in boot.img. Ramdisk is in vendor_boot.img
    or init_boot.img. This function extracts what's available and warns.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    hdr = parse_boot_header(img)
    page = hdr["page_size"]

    # v3/v4 GKI check — only kernel lives in boot.img
    if hdr.get("gki"):
        console.print("[yellow]⚠ GKI boot image detected (header v{})[/yellow]".format(
            hdr["header_version"]))
        console.print("[yellow]  Ramdisk is NOT in this image — it lives in vendor_boot.img[/yellow]")
        console.print("[yellow]  or init_boot.img (Android 12+). Only kernel extracted.[/yellow]")
        console.print("[yellow]  To get ramdisk: [bold]watchrom bootimg unpack-vendor vendor_boot.img[/bold][/yellow]")

    with open(img, "rb") as f:
        # Skip header page(s)
        f.seek(page)

        # Kernel
        kernel_data = f.read(hdr["kernel_size"])
        kernel_path = out_dir / "kernel"
        kernel_path.write_bytes(kernel_data)

        # Align to next page
        f.seek(page + pages(hdr["kernel_size"], page) * page)

        # Ramdisk (size is 0 for GKI v3/v4 — skip silently)
        ramdisk_path = out_dir / "ramdisk.cpio.gz"
        if hdr["ramdisk_size"] > 0:
            ramdisk_data = f.read(hdr["ramdisk_size"])
            ramdisk_path.write_bytes(ramdisk_data)
        else:
            # v3/v4: no ramdisk in boot.img — create empty marker
            ramdisk_path.write_bytes(b"")
            console.print("[dim]  (no ramdisk in boot.img — GKI layout)[/dim]")

        # Second stage (if any)
        if hdr["second_size"] > 0:
            ramdisk_pages = pages(hdr["ramdisk_size"], page)
            f.seek(page + (pages(hdr["kernel_size"], page) + ramdisk_pages) * page)
            second_data = f.read(hdr["second_size"])
            (out_dir / "second").write_bytes(second_data)

        # DTB (v2 only — v3/v4 dtb lives in vendor_boot)
        if hdr.get("dtb_size", 0) > 0:
            dtb_data = f.read(hdr["dtb_size"])
            (out_dir / "dtb").write_bytes(dtb_data)

    # Save header info
    import json
    with open(out_dir / "header.json", "w") as f:
        json.dump(hdr, f, indent=2)

    # Extract ramdisk if present
    if hdr["ramdisk_size"] > 0:
        ramdisk_dir = out_dir / "ramdisk"
        extract_ramdisk(ramdisk_path, ramdisk_dir)

    return hdr


def extract_ramdisk(ramdisk_gz: Path, out_dir: Path):
    """Extract ramdisk cpio (gzip or lz4 or plain cpio)."""
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(ramdisk_gz, "rb") as f:
        magic = f.read(4)

    if magic[:2] == b"\x1f\x8b":
        # gzip
        cpio_path = ramdisk_gz.parent / "ramdisk.cpio"
        run(["gunzip", "-k", "-f", str(ramdisk_gz)], check=False)
        if not cpio_path.exists():
            run(["zcat", str(ramdisk_gz)], check=False)
    elif magic[:4] == b"\x02\x21\x4c\x18":
        # lz4
        cpio_path = ramdisk_gz.parent / "ramdisk.cpio"
        run(["lz4", "-d", "-f", str(ramdisk_gz), str(cpio_path)], check=False)
    else:
        cpio_path = ramdisk_gz

    if cpio_path.exists():
        old_cwd = os.getcwd()
        os.chdir(out_dir)
        run(["cpio", "-i", "--no-absolute-filenames", "-F", str(cpio_path)], check=False)
        os.chdir(old_cwd)


def repack_ramdisk(ramdisk_dir: Path, out_path: Path, compression="gzip"):
    """Repack ramdisk directory into cpio.gz."""
    cpio_path = out_path.parent / "ramdisk.cpio"

    # Build file list preserving symlinks
    old_cwd = os.getcwd()
    os.chdir(ramdisk_dir)

    # Use subprocess directly for the shell pipe (run() doesn't support pipes)
    import subprocess
    cpio_cmd = f"find . -print0 | cpio --null -o --format=newc > {str(cpio_path)}"
    subprocess.run(cpio_cmd, shell=True, check=False)

    os.chdir(old_cwd)

    # Compress
    if compression == "gzip":
        run(["gzip", "-9", "-f", str(cpio_path)])
        shutil.move(str(cpio_path) + ".gz", str(out_path))
    elif compression == "lz4":
        run(["lz4", "-9", str(cpio_path), str(out_path)])
    else:
        shutil.copy(cpio_path, out_path)


def repack_boot(unpacked_dir: Path, out_img: Path):
    """Repack unpacked boot directory back into boot.img using mkbootimg."""
    import json
    hdr_path = unpacked_dir / "header.json"
    if not hdr_path.exists():
        raise FileNotFoundError("header.json not found — run bootimg unpack first")

    with open(hdr_path) as f:
        hdr = json.load(f)

    kernel   = unpacked_dir / "kernel"
    ramdisk  = unpacked_dir / "ramdisk.cpio.gz"
    ramdisk_dir = unpacked_dir / "ramdisk"

    # Re-pack ramdisk if directory was modified (or original ramdisk missing)
    if ramdisk_dir.exists():
        ramdisk_newer = (not ramdisk.exists() or
                         ramdisk_dir.stat().st_mtime > ramdisk.stat().st_mtime)
        if ramdisk_newer:
            console.print("[cyan]→ Repacking modified ramdisk...[/cyan]")
            repack_ramdisk(ramdisk_dir, ramdisk)

    if tool_available("mkbootimg"):
        cmd = [
            "mkbootimg",
            "--kernel",         str(kernel),
            "--ramdisk",        str(ramdisk),
            "--base",           hex(hdr["kernel_addr"] - 0x8000),
            "--kernel_offset",  "0x00008000",
            "--ramdisk_offset", hex(hdr["ramdisk_addr"] - hdr["kernel_addr"] + 0x8000),
            "--tags_offset",    hex(hdr["tags_addr"]    - hdr["kernel_addr"] + 0x8000),
            "--pagesize",       str(hdr["page_size"]),
            "--header_version", str(hdr["header_version"]),
            "--cmdline",        hdr["cmdline"],
            "--board",          hdr.get("name", ""),
            "--output",         str(out_img),
        ]
        if hdr.get("dtb_size", 0) > 0:
            dtb = unpacked_dir / "dtb"
            if dtb.exists():
                cmd += ["--dtb", str(dtb)]

        run(cmd)
    else:
        # Manual repack
        _manual_repack_boot(hdr, kernel, ramdisk, out_img)

    console.print(f"[green]✓ Repacked: {out_img} ({file_size_mb(out_img):.1f} MB)[/green]")


def _manual_repack_boot(hdr, kernel: Path, ramdisk: Path, out: Path):
    """Minimal mkbootimg reimplementation when tool isn't available."""
    page = hdr["page_size"]

    def pad(data, page):
        remainder = len(data) % page
        if remainder:
            return data + b"\x00" * (page - remainder)
        return data

    kernel_data  = kernel.read_bytes()
    ramdisk_data = ramdisk.read_bytes()

    # Build header (2048 bytes standard)
    hdr_bytes = bytearray(page)
    hdr_bytes[0:8]   = ANDROID_MAGIC
    struct.pack_into("<I", hdr_bytes, 8,  len(kernel_data))
    struct.pack_into("<I", hdr_bytes, 12, hdr["kernel_addr"])
    struct.pack_into("<I", hdr_bytes, 16, len(ramdisk_data))
    struct.pack_into("<I", hdr_bytes, 20, hdr["ramdisk_addr"])
    struct.pack_into("<I", hdr_bytes, 24, 0)  # second_size
    struct.pack_into("<I", hdr_bytes, 28, hdr["second_addr"])
    struct.pack_into("<I", hdr_bytes, 32, hdr["tags_addr"])
    struct.pack_into("<I", hdr_bytes, 36, page)
    struct.pack_into("<I", hdr_bytes, 40, hdr["header_version"])
    cmdline_bytes = hdr["cmdline"].encode()[:512]
    hdr_bytes[64:64+len(cmdline_bytes)] = cmdline_bytes

    with open(out, "wb") as f:
        f.write(bytes(hdr_bytes))
        f.write(pad(kernel_data, page))
        f.write(pad(ramdisk_data, page))


# ── CLI ────────────────────────────────────────────────────────────────────────

@click.group()
def bootimg():
    """boot.img / recovery.img unpack, edit, and repack."""
    pass


@bootimg.command("unpack")
@click.argument("image")
@click.option("--out", "-o", default=None, help="Output directory")
def bootimg_unpack(image, out):
    """
    Unpack a boot.img or recovery.img into editable components.

    Output:
      kernel          — raw kernel binary
      ramdisk.cpio.gz — compressed ramdisk
      ramdisk/        — extracted ramdisk filesystem (editable)
      dtb             — device tree blob (if present)
      header.json     — all header fields (used by repack)
    """
    img = Path(image)
    if not img.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return

    out_dir = Path(out) if out else (OUTPUT_DIR / "bootimg" / img.stem)
    console.print(f"\n[bold cyan]Boot Image Unpacker[/bold cyan]")
    console.print(f"  Image : {img.name} ({file_size_mb(img):.1f} MB)")

    try:
        hdr = unpack_boot(img, out_dir)
        console.print(f"\n[bold]Header:[/bold]")
        console.print(f"  Version    : v{hdr['header_version']}")
        if hdr.get("gki"):
            console.print(f"  [yellow]GKI        : Yes (ramdisk in vendor_boot.img)[/yellow]")
        console.print(f"  Kernel     : {hdr['kernel_size']//1024} KB")
        console.print(f"  Ramdisk    : {hdr['ramdisk_size']//1024} KB")
        console.print(f"  Page size  : {hdr['page_size']} bytes")
        console.print(f"  Cmdline    : {hdr['cmdline'][:80]}")
        console.print(f"  Board      : {hdr['name']}")
        if hdr.get("dtb_size"):
            console.print(f"  DTB        : {hdr['dtb_size']//1024} KB")

        ramdisk_files = sum(1 for _ in (out_dir/"ramdisk").rglob("*")) if (out_dir/"ramdisk").exists() else 0
        console.print(f"\n[green]✓ Unpacked → {out_dir}[/green]")
        console.print(f"  Ramdisk: {ramdisk_files} files extracted")
        console.print(f"\n  Edit ramdisk in: [cyan]{out_dir}/ramdisk/[/cyan]")
        console.print(f"  Repack with:    [bold]watchrom bootimg repack {out_dir}[/bold]")
    except Exception as e:
        console.print(f"[red]✗ Unpack failed: {e}[/red]")


@bootimg.command("repack")
@click.argument("unpacked_dir")
@click.option("--out", "-o", default=None)
def bootimg_repack(unpacked_dir, out):
    """Repack an unpacked boot directory back into a flashable boot.img."""
    d = Path(unpacked_dir)
    if not d.is_dir():
        console.print(f"[red]✗ Not a directory: {unpacked_dir}[/red]")
        return

    out_path = Path(out) if out else (OUTPUT_DIR / f"{d.name}_repacked.img")
    console.print(f"\n[bold cyan]Boot Image Repacker[/bold cyan]")
    try:
        repack_boot(d, out_path)
        console.print(f"  SHA256: {sha256_file(out_path)[:32]}…")
        console.print(f"\n  Flash: [bold]watchrom flash boot {out_path}[/bold]")
    except Exception as e:
        console.print(f"[red]✗ Repack failed: {e}[/red]")


@bootimg.command("unpack-vendor")
@click.argument("image")
@click.option("--out", "-o", default=None, help="Output directory")
def bootimg_unpack_vendor(image, out):
    """Unpack a vendor_boot.img from a GKI device.

    Output:
      ramdisk.cpio.gz — compressed ramdisk
      ramdisk/        — extracted ramdisk filesystem (editable)
      dtb             — device tree blob (if present)
      vendor_cmdline  — vendor command line
      header.json     — all header fields (used by repack)
    """
    img = Path(image)
    if not img.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return

    out_dir = Path(out) if out else (OUTPUT_DIR / "vendor_boot" / img.stem)
    from modules import file_size_mb
    console.print(f"\n[bold cyan]Vendor Boot Unpacker[/bold cyan]")
    console.print(f"  Image : {img.name} ({file_size_mb(img):.1f} MB)")

    try:
        hdr = unpack_vendor_boot(img, out_dir)
        console.print(f"\n  Header v{hdr['header_version']}")
        console.print(f"  Page size: {hdr['page_size']}")
        console.print(f"  Ramdisk  : {hdr['ramdisk_size']} bytes")
        console.print(f"  DTB      : {hdr['dtb_size']} bytes")
        if hdr.get("vendor_cmd"):
            console.print(f"  Cmdline  : {hdr['vendor_cmd'][:80]}")
        console.print(f"\n[green]✓ Unpacked → {out_dir}[/green]")
        console.print(f"  Repack: [bold]watchrom bootimg repack-vendor {out_dir}[/bold]")
    except Exception as e:
        console.print(f"[red]✗ Unpack failed: {e}[/red]")


@bootimg.command("repack-vendor")
@click.argument("unpacked_dir")
@click.option("--out", "-o", default=None)
def bootimg_repack_vendor(unpacked_dir, out):
    """Repack an unpacked vendor_boot directory into a flashable image."""
    d = Path(unpacked_dir)
    if not d.is_dir():
        console.print(f"[red]✗ Not a directory: {unpacked_dir}[/red]")
        return

    out_path = Path(out) if out else (OUTPUT_DIR / f"{d.name}_vendor_repacked.img")
    console.print(f"\n[bold cyan]Vendor Boot Repacker[/bold cyan]")
    try:
        repack_vendor_boot(d, out_path)
        from modules import sha256_file
        console.print(f"  SHA256: {sha256_file(out_path)[:32]}…")
    except Exception as e:
        console.print(f"[red]✗ Repack failed: {e}[/red]")


@bootimg.command("info")
@click.argument("image")
def bootimg_info(image):
    """Show boot.img or vendor_boot.img header fields without unpacking."""
    img = Path(image)
    if not img.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return

    # Try vendor_boot first (check magic)
    try:
        with open(img, "rb") as f:
            magic = f.read(8)
    except Exception:
        console.print(f"[red]✗ Cannot read: {image}[/red]")
        return

    if magic == VENDOR_BOOT_MAGIC:
        try:
            hdr = parse_vendor_boot_header(img)
            console.print(f"\n[bold cyan]Vendor Boot Header: {img.name}[/bold cyan]\n")
            for k, v in hdr.items():
                console.print(f"  [cyan]{k:28s}[/cyan] {v}")
        except Exception as e:
            console.print(f"[red]✗ {e}[/red]")
        return

    # Standard boot image
    try:
        hdr = parse_boot_header(img)
        console.print(f"\n[bold cyan]Boot Image Header: {img.name}[/bold cyan]\n")
        for k, v in hdr.items():
            if k not in ("id",):
                console.print(f"  [cyan]{k:28s}[/cyan] {v}")
        if hdr.get("gki"):
            console.print(f"\n  [yellow]⚠ GKI image (header v{hdr['header_version']})[/yellow]")
            console.print(f"  [yellow]  Ramdisk is in vendor_boot.img or init_boot.img[/yellow]")
            console.print(f"  [yellow]  Use: [bold]watchrom bootimg unpack-vendor vendor_boot.img[/bold][/yellow]")
    except Exception as e:
        console.print(f"[red]✗ {e}[/red]")


@bootimg.command("patch-cmdline")
@click.argument("image")
@click.option("--add",    "-a", multiple=True, help="Add kernel param (e.g. androidboot.selinux=permissive)")
@click.option("--remove", "-r", multiple=True, help="Remove kernel param by key")
@click.option("--out",    "-o", default=None)
def bootimg_patch_cmdline(image, add, remove, out):
    """
    Patch kernel command line in boot.img without full unpack/repack.

    Examples:
      --add androidboot.selinux=permissive
      --add ro.debuggable=1
      --remove quiet
    """
    img = Path(image)
    if not img.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return

    hdr = parse_boot_header(img)
    cmdline = hdr["cmdline"]
    console.print(f"\n[cyan]Original cmdline:[/cyan] {cmdline}\n")

    params = dict(p.split("=", 1) if "=" in p else (p, "") for p in cmdline.split())

    for p in remove:
        key = p.split("=")[0]
        if key in params:
            del params[key]
            console.print(f"  [red]- removed:[/red] {key}")

    for p in add:
        if "=" in p:
            k, v = p.split("=", 1)
        else:
            k, v = p, ""
        params[k] = v
        console.print(f"  [green]+ added:[/green] {k}={v}")

    new_cmdline = " ".join(f"{k}={v}" if v else k for k, v in params.items())
    console.print(f"\n[cyan]New cmdline:[/cyan] {new_cmdline}")

    if len(new_cmdline) > 512:
        console.print("[red]✗ Cmdline too long (>512 bytes)[/red]")
        return

    out_path = Path(out) if out else (OUTPUT_DIR / f"{img.stem}_patched_cmdline.img")
    shutil.copy(img, out_path)

    with open(out_path, "r+b") as f:
        f.seek(64)
        encoded = new_cmdline.encode("utf-8")
        f.write(encoded + b"\x00" * (512 - len(encoded)))

    console.print(f"\n[green]✓ Patched: {out_path}[/green]")
    console.print(f"  Flash: [bold]watchrom flash boot {out_path}[/bold]")
