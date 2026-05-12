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

ANDROID_MAGIC = b"ANDROID!"

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

    # v1+: recovery dtbo
    if hdr["header_version"] >= 1:
        hdr["recovery_dtbo_size"]   = struct.unpack_from("<I",  data, 1632)[0]
        hdr["recovery_dtbo_offset"] = struct.unpack_from("<Q",  data, 1636)[0]
        hdr["header_size"]          = struct.unpack_from("<I",  data, 1644)[0]

    # v2+: dtb
    if hdr["header_version"] >= 2:
        hdr["dtb_size"] = struct.unpack_from("<I", data, 1648)[0]
        hdr["dtb_addr"] = struct.unpack_from("<Q", data, 1652)[0]

    return hdr


def pages(size: int, page_size: int) -> int:
    return (size + page_size - 1) // page_size


# ── Unpack ─────────────────────────────────────────────────────────────────────

def unpack_boot(img: Path, out_dir: Path) -> dict:
    """Unpack boot.img into component files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    hdr = parse_boot_header(img)
    page = hdr["page_size"]

    with open(img, "rb") as f:
        # Skip header page(s)
        f.seek(page)

        # Kernel
        kernel_data = f.read(hdr["kernel_size"])
        kernel_path = out_dir / "kernel"
        kernel_path.write_bytes(kernel_data)

        # Align to next page
        f.seek(page + pages(hdr["kernel_size"], page) * page)

        # Ramdisk
        ramdisk_data = f.read(hdr["ramdisk_size"])
        ramdisk_path = out_dir / "ramdisk.cpio.gz"
        ramdisk_path.write_bytes(ramdisk_data)

        # Second stage (if any)
        if hdr["second_size"] > 0:
            f.seek(page + (pages(hdr["kernel_size"], page) +
                           pages(hdr["ramdisk_size"], page)) * page)
            second_data = f.read(hdr["second_size"])
            (out_dir / "second").write_bytes(second_data)

        # DTB (v2+)
        if hdr.get("dtb_size", 0) > 0:
            dtb_data = f.read(hdr["dtb_size"])
            (out_dir / "dtb").write_bytes(dtb_data)

    # Save header info
    import json
    with open(out_dir / "header.json", "w") as f:
        json.dump(hdr, f, indent=2)

    # Detect ramdisk compression and extract
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


@bootimg.command("info")
@click.argument("image")
def bootimg_info(image):
    """Show boot.img header fields without unpacking."""
    img = Path(image)
    if not img.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return
    try:
        hdr = parse_boot_header(img)
        console.print(f"\n[bold cyan]Boot Image Header: {img.name}[/bold cyan]\n")
        for k, v in hdr.items():
            if k != "id":
                console.print(f"  [cyan]{k:28s}[/cyan] {v}")
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
