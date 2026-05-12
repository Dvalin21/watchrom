"""
analyze.py — Firmware, partition, and binary analysis tools
Strings extraction, entropy analysis, format detection, diff between images
"""
import click
import struct
import math
import hashlib
from pathlib import Path
from collections import Counter
from modules import run, OUTPUT_DIR, sha256_file, file_size_mb, console, tool_available


# ── Entropy analysis ──────────────────────────────────────────────────────────

def block_entropy(data: bytes) -> float:
    """Shannon entropy of a byte block (0=uniform, 8=random/encrypted)."""
    if not data:
        return 0.0
    counts = Counter(data)
    total  = len(data)
    return -sum((c/total) * math.log2(c/total) for c in counts.values())


def analyze_entropy(img: Path, block_size: int = 65536) -> list:
    """Return list of (offset, entropy) for the image."""
    results = []
    with open(img, "rb") as f:
        offset = 0
        while True:
            block = f.read(block_size)
            if not block:
                break
            results.append((offset, block_entropy(block)))
            offset += len(block)
    return results


# ── File format signatures ────────────────────────────────────────────────────

SIGNATURES = {
    b"\x7fELF":                    "ELF binary",
    b"PK\x03\x04":                 "ZIP / APK / JAR",
    b"ANDROID!":                   "Android boot image",
    b"\x3a\xff\x26\xed":           "Android sparse image",
    b"\xe2\xe1\xf5\xe0":           "erofs filesystem",
    b"\xd0\x0d\xfe\xed":           "DTB (big-endian FDT)",
    b"\xd7\xb7\xab\x1e":           "DTBO image",
    b"CrAU":                       "OTA payload.bin",
    b"\x1f\x8b":                   "gzip",
    b"\x02\x21\x4c\x18":           "LZ4 frame",
    b"\x28\xb5\x2f\xfd":           "Zstandard",
    b"\x53\xef":                   "ext2/3/4 superblock",
    b"AVB0":                       "AVB vbmeta",
    b"DHTB":                       "MediaTek header",
    b"BFBF":                       "Unisoc firmware header",
    b"\x89PNG":                    "PNG image",
    b"MZ":                         "DOS/PE executable",
    b"dex\n":                      "Android DEX",
    b"ODEX":                       "Android ODEX",
    b"magic":                      "CPIO archive",
    b"\xfe\xed\xfa\xce":           "Mach-O binary",
    b"#!/":                        "Shell script",
}


def detect_format(data: bytes) -> str:
    for sig, name in SIGNATURES.items():
        if data[:len(sig)] == sig:
            return name
    # ext4 superblock at offset 1024
    if len(data) > 1028 and data[1080:1082] == b"\x53\xef":
        return "ext4 filesystem (raw)"
    return "unknown"


# ── String extraction ─────────────────────────────────────────────────────────

def extract_strings(data: bytes, min_len: int = 6) -> list:
    """Extract printable ASCII strings from binary data."""
    strings = []
    current = []
    for byte in data:
        if 0x20 <= byte <= 0x7E:
            current.append(chr(byte))
        else:
            if len(current) >= min_len:
                strings.append("".join(current))
            current = []
    if len(current) >= min_len:
        strings.append("".join(current))
    return strings


# ── Image diff ────────────────────────────────────────────────────────────────

def diff_images(img1: Path, img2: Path, block_size: int = 4096) -> list:
    """Find differing blocks between two binary images."""
    diffs = []
    with open(img1, "rb") as f1, open(img2, "rb") as f2:
        offset = 0
        while True:
            b1 = f1.read(block_size)
            b2 = f2.read(block_size)
            if not b1 and not b2:
                break
            if b1 != b2:
                diffs.append({
                    "offset":     offset,
                    "offset_hex": hex(offset),
                    "size":       block_size,
                })
            offset += block_size
    return diffs


# ── CLI ───────────────────────────────────────────────────────────────────────

@click.group()
def analyze():
    """Firmware and binary analysis: entropy, strings, format detection, diff."""
    pass


@analyze.command("info")
@click.argument("image")
@click.option("--deep", "-d", is_flag=True, help="Scan for embedded signatures throughout file")
def analyze_info(image, deep):
    """
    Show comprehensive information about any firmware image or binary.

    Detects: format, entropy, embedded signatures, key strings.
    """
    img = Path(image)
    if not img.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return

    data = img.read_bytes()
    console.print(f"\n[bold cyan]Image Analysis: {img.name}[/bold cyan]\n")

    # Basic info
    console.print(f"  [bold]Size    :[/bold] {file_size_mb(img):.3f} MB ({img.stat().st_size:,} bytes)")
    console.print(f"  [bold]SHA256  :[/bold] {sha256_file(img)}")
    console.print(f"  [bold]MD5     :[/bold] {hashlib.md5(data).hexdigest()}")
    console.print(f"  [bold]Format  :[/bold] [yellow]{detect_format(data)}[/yellow]")

    # Entropy
    total_entropy = block_entropy(data[:65536])
    entropy_label = (
        "[green]low (uncompressed data)[/green]" if total_entropy < 4 else
        "[yellow]medium (mixed)[/yellow]"         if total_entropy < 7 else
        "[red]high (compressed/encrypted)[/red]"
    )
    console.print(f"  [bold]Entropy :[/bold] {total_entropy:.2f}/8.0 — {entropy_label}")

    # Magic bytes
    console.print(f"  [bold]Magic   :[/bold] {data[:16].hex()} ({data[:8]})")

    if deep:
        console.print(f"\n  [bold]Embedded Signatures:[/bold]")
        found_sigs = []
        step = 512
        for off in range(0, min(len(data), 50 * 1024 * 1024), step):
            chunk = data[off:off+8]
            for sig, name in SIGNATURES.items():
                if chunk[:len(sig)] == sig:
                    found_sigs.append((off, name))
        seen = set()
        for off, name in found_sigs:
            if name not in seen:
                console.print(f"    [dim]0x{off:08x}[/dim]  [cyan]{name}[/cyan]")
                seen.add(name)

    # Interesting strings
    strings = extract_strings(data[:2 * 1024 * 1024], min_len=8)
    interesting = [s for s in strings if any(k in s.lower() for k in
        ["android","build","version","kernel","platform","vendor","copyright",
         "qualcomm","mediatek","spreadtrum","unisoc","selinux","boot","flash"])]
    if interesting:
        console.print(f"\n  [bold]Interesting Strings (first 15):[/bold]")
        for s in interesting[:15]:
            console.print(f"    [dim]{s[:80]}[/dim]")


@analyze.command("entropy")
@click.argument("image")
@click.option("--block-kb", "-b", default=64, type=int,
              help="Block size in KB (default 64)")
@click.option("--out",      "-o", default=None, help="Save CSV report")
def analyze_entropy_cmd(image, block_kb, out):
    """
    Plot block-by-block entropy of a firmware image.
    High entropy = compressed/encrypted regions.
    Low entropy  = plaintext/padding regions.
    """
    img = Path(image)
    if not img.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return

    console.print(f"\n[bold cyan]Entropy Map: {img.name}[/bold cyan]")
    console.print(f"  Block size : {block_kb} KB")
    console.print(f"  File size  : {file_size_mb(img):.1f} MB\n")

    results = analyze_entropy(img, block_kb * 1024)

    # ASCII bar chart
    console.print(f"  {'Offset':>12}  {'Entropy':>8}  Map")
    console.print(f"  {'─'*12}  {'─'*8}  {'─'*40}")

    csv_lines = ["offset_bytes,entropy"]
    for offset, entropy in results:
        bar_len = int(entropy / 8.0 * 40)
        color   = "red" if entropy > 7.0 else "yellow" if entropy > 5.0 else "green"
        bar     = f"[{color}]{'█' * bar_len}[/{color}]{'░' * (40 - bar_len)}"
        console.print(f"  0x{offset:010x}  {entropy:8.4f}  {bar}")
        csv_lines.append(f"{offset},{entropy:.4f}")

    avg = sum(e for _, e in results) / len(results) if results else 0
    console.print(f"\n  Average entropy: {avg:.4f}/8.0")

    if out:
        Path(out).write_text("\n".join(csv_lines))
        console.print(f"  [green]✓ CSV saved: {out}[/green]")


@analyze.command("strings")
@click.argument("image")
@click.option("--min-len", "-n", default=8, type=int)
@click.option("--filter",  "-f", default=None, help="Filter strings containing substring")
@click.option("--out",     "-o", default=None)
@click.option("--limit",   "-l", default=200, type=int, help="Max strings to show")
def analyze_strings(image, min_len, filter, out, limit):
    """Extract printable strings from a binary image (like Unix strings(1))."""
    img = Path(image)
    if not img.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return

    data = img.read_bytes()
    all_strings = extract_strings(data, min_len)

    if filter:
        all_strings = [s for s in all_strings if filter.lower() in s.lower()]

    console.print(f"\n[bold cyan]Strings: {img.name}[/bold cyan]")
    console.print(f"  Found: {len(all_strings)} strings (min_len={min_len})\n")

    shown = all_strings[:limit]
    for s in shown:
        console.print(f"  [dim]{s[:120]}[/dim]")

    if len(all_strings) > limit:
        console.print(f"\n  [dim]... {len(all_strings) - limit} more. Use --out to save all.[/dim]")

    if out:
        Path(out).write_text("\n".join(all_strings))
        console.print(f"\n[green]✓ Saved {len(all_strings)} strings → {out}[/green]")


@analyze.command("diff")
@click.argument("image1")
@click.argument("image2")
@click.option("--block-kb", "-b", default=4, type=int)
@click.option("--out",      "-o", default=None, help="Save diff report")
def analyze_diff(image1, image2, block_kb, out):
    """
    Find differing blocks between two binary images.

    Useful for:
      - Comparing stock vs patched boot.img
      - Finding what changed between firmware versions
      - Verifying partial flashes
    """
    i1, i2 = Path(image1), Path(image2)
    for p in (i1, i2):
        if not p.exists():
            console.print(f"[red]✗ Not found: {p}[/red]")
            return

    console.print(f"\n[bold cyan]Image Diff[/bold cyan]")
    console.print(f"  A: {i1.name}  ({file_size_mb(i1):.1f} MB)  sha256:{sha256_file(i1)[:12]}…")
    console.print(f"  B: {i2.name}  ({file_size_mb(i2):.1f} MB)  sha256:{sha256_file(i2)[:12]}…")

    if sha256_file(i1) == sha256_file(i2):
        console.print(f"\n[green]✓ Images are IDENTICAL.[/green]")
        return

    diffs = diff_images(i1, i2, block_kb * 1024)
    total_diff = len(diffs) * block_kb / 1024

    console.print(f"\n  [bold]{len(diffs)} differing blocks[/bold]  ({total_diff:.1f} MB changed)\n")

    if diffs:
        console.print(f"  {'Offset':>14}  {'Size':>8}")
        for d in diffs[:50]:
            console.print(f"  [yellow]{d['offset_hex']:>14}[/yellow]  {d['size']//1024} KB")
        if len(diffs) > 50:
            console.print(f"  [dim]... {len(diffs)-50} more blocks[/dim]")

    if out:
        import json
        Path(out).write_text(json.dumps({
            "image_a": str(i1), "image_b": str(i2),
            "sha256_a": sha256_file(i1), "sha256_b": sha256_file(i2),
            "diff_blocks": len(diffs),
            "diff_bytes": len(diffs) * block_kb * 1024,
            "blocks": diffs[:500],
        }, indent=2))
        console.print(f"\n[green]✓ Diff report: {out}[/green]")


@analyze.command("scan")
@click.argument("directory")
@click.option("--out", "-o", default=None)
def analyze_scan(directory, out):
    """
    Scan a directory of firmware files and build a format/entropy inventory.
    Good for surveying a full partition dump before starting work.
    """
    scan_dir = Path(directory)
    if not scan_dir.is_dir():
        console.print(f"[red]✗ Not a directory: {directory}[/red]")
        return

    files = sorted(scan_dir.glob("*"))
    console.print(f"\n[bold cyan]Firmware Scan: {scan_dir}[/bold cyan]\n")

    from rich.table import Table
    from rich import box as rbox
    t = Table(box=rbox.SIMPLE, border_style="cyan", show_header=True)
    t.add_column("File",    style="cyan",   width=22)
    t.add_column("Size",    style="green",  width=10)
    t.add_column("Format",  style="yellow", width=28)
    t.add_column("Entropy", style="white",  width=8)
    t.add_column("SHA256",  style="dim",    width=14)

    report = []
    for f in files:
        if not f.is_file() or f.stat().st_size == 0:
            continue
        try:
            with open(f, "rb") as fh:
                data = fh.read(65536)
        except (PermissionError, OSError):
            continue
        fmt  = detect_format(data)
        entr = f"{block_entropy(data):.2f}"
        chk  = sha256_file(f)[:12]
        size = f"{file_size_mb(f):.1f} MB"
        t.add_row(f.name[:22], size, fmt[:28], entr, chk)
        report.append({"file": f.name, "size_mb": round(file_size_mb(f),2),
                        "format": fmt, "entropy": entr, "sha256": sha256_file(f)})

    console.print(t)

    if out:
        import json
        Path(out).write_text(json.dumps(report, indent=2))
        console.print(f"\n[green]✓ Scan report: {out}[/green]")
