"""
dtb.py — Device Tree Blob (DTB/DTBO) extraction, inspection, and patching
Used for: kernel hardware descriptions, panel configs, clock/GPIO tables
"""
import click
import struct
import shutil
from pathlib import Path
from modules import run, OUTPUT_DIR, WORKSPACE, sha256_file, console, tool_available

# FDT (Flattened Device Tree) magic
FDT_MAGIC = 0xD00DFEED

# DTBO image header magic (Android)
DTBO_MAGIC = 0xD7B7AB1E


def is_dtb(data: bytes) -> bool:
    if len(data) < 4:
        return False
    return struct.unpack(">I", data[:4])[0] == FDT_MAGIC


def is_dtbo(data: bytes) -> bool:
    if len(data) < 4:
        return False
    return struct.unpack(">I", data[:4])[0] == DTBO_MAGIC


# ── DTBO image parser ─────────────────────────────────────────────────────────

def parse_dtbo_header(data: bytes) -> dict:
    if len(data) < 32:
        raise ValueError("DTBO too small")
    magic, total_size, hdr_size, dt_entry_size, dt_entry_count, dt_entries_offset, \
        page_size, version = struct.unpack(">IIIIIIII", data[:32])
    return {
        "magic":            hex(magic),
        "total_size":       total_size,
        "header_size":      hdr_size,
        "dt_entry_size":    dt_entry_size,
        "dt_entry_count":   dt_entry_count,
        "dt_entries_offset": dt_entries_offset,
        "page_size":        page_size,
        "version":          version,
    }


def extract_dtbo_entries(dtbo_path: Path, out_dir: Path) -> list:
    """Extract individual DTB entries from a DTBO image."""
    out_dir.mkdir(parents=True, exist_ok=True)
    data = dtbo_path.read_bytes()
    hdr  = parse_dtbo_header(data)

    entries = []
    entry_off = hdr["dt_entries_offset"]
    entry_size = hdr["dt_entry_size"]

    for i in range(hdr["dt_entry_count"]):
        off = entry_off + i * entry_size
        if off + 24 > len(data):
            break
        dt_size, dt_offset, id_, rev, flags = struct.unpack(">IIIII", data[off:off+20])
        dt_data = data[dt_offset:dt_offset + dt_size]
        out_path = out_dir / f"dtb_{i:03d}.dtb"
        out_path.write_bytes(dt_data)
        entries.append({"index": i, "size": dt_size, "offset": dt_offset,
                        "id": id_, "rev": rev, "path": out_path})

    return entries


# ── dtc wrapper ───────────────────────────────────────────────────────────────

def dtb_to_dts(dtb_path: Path, dts_path: Path):
    """Decompile DTB binary to human-readable DTS source."""
    if not tool_available("dtc"):
        raise FileNotFoundError(
            "dtc not found.\n  Install: sudo apt install device-tree-compiler"
        )
    run(["dtc", "-I", "dtb", "-O", "dts", "-o", str(dts_path), str(dtb_path)])


def dts_to_dtb(dts_path: Path, dtb_path: Path):
    """Compile DTS source back to DTB binary."""
    if not tool_available("dtc"):
        raise FileNotFoundError("dtc not found. Install: sudo apt install device-tree-compiler")
    run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(dtb_path), str(dts_path)])


# ── CLI ───────────────────────────────────────────────────────────────────────

@click.group()
def dtb():
    """Device Tree Blob (DTB/DTBO) inspection, extraction, and patching."""
    pass


@dtb.command("info")
@click.argument("image")
def dtb_info(image):
    """Show DTB or DTBO image information."""
    img = Path(image)
    if not img.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return

    data = img.read_bytes()
    console.print(f"\n[bold cyan]DTB/DTBO Info: {img.name}[/bold cyan]\n")
    console.print(f"  Size  : {len(data)//1024} KB")
    console.print(f"  SHA256: {sha256_file(img)[:32]}…")

    if is_dtbo(data):
        console.print(f"  [bold]Format: DTBO (Android overlay image)[/bold]")
        hdr = parse_dtbo_header(data)
        for k, v in hdr.items():
            console.print(f"  [cyan]{k:25s}[/cyan] {v}")
    elif is_dtb(data):
        console.print(f"  [bold]Format: DTB (Flattened Device Tree)[/bold]")
        size = struct.unpack(">I", data[4:8])[0]
        str_off  = struct.unpack(">I", data[12:16])[0]
        str_size = struct.unpack(">I", data[20:24])[0]
        console.print(f"  [cyan]Total size   [/cyan] {size} bytes")
        console.print(f"  [cyan]String block [/cyan] offset={str_off} size={str_size}")
        if tool_available("dtc"):
            rc, out, _ = run(["dtc", "-I", "dtb", "-O", "dts", str(img)], check=False)
            root_nodes = [l.strip() for l in out.splitlines() if l.strip().endswith("{") and not l.startswith("\t\t")][:10]
            console.print(f"  [bold]Root nodes:[/bold]")
            for n in root_nodes:
                console.print(f"    [dim]{n}[/dim]")
    else:
        console.print(f"  [yellow]! Unknown format (magic: {data[:4].hex()})[/yellow]")


@dtb.command("extract")
@click.argument("dtbo_image")
@click.option("--out", "-o", default=None, help="Output directory for DTB entries")
def dtb_extract(dtbo_image, out):
    """Extract individual DTB entries from a DTBO image."""
    img = Path(dtbo_image)
    if not img.exists():
        console.print(f"[red]✗ Not found: {dtbo_image}[/red]")
        return

    out_dir = Path(out) if out else (OUTPUT_DIR / "dtbo_extracted" / img.stem)
    data = img.read_bytes()

    if not is_dtbo(data):
        console.print("[yellow]! Not a DTBO image. Treating as single DTB.[/yellow]")
        single_out = out_dir / f"{img.stem}.dtb"
        single_out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(img, single_out)
        console.print(f"[green]✓ Saved: {single_out}[/green]")
        return

    console.print(f"\n[bold cyan]DTBO Extractor[/bold cyan]")
    entries = extract_dtbo_entries(img, out_dir)
    console.print(f"[green]✓ Extracted {len(entries)} DTB entries → {out_dir}[/green]")
    for e in entries:
        console.print(f"  [dim]dtb_{e['index']:03d}.dtb  {e['size']//1024} KB  id={e['id']}[/dim]")


@dtb.command("decompile")
@click.argument("dtb_file")
@click.option("--out", "-o", default=None, help="Output .dts file")
def dtb_decompile(dtb_file, out):
    """Decompile a DTB binary to human-readable DTS source."""
    dtb_path = Path(dtb_file)
    if not dtb_path.exists():
        console.print(f"[red]✗ Not found: {dtb_file}[/red]")
        return

    dts_out = Path(out) if out else (OUTPUT_DIR / "dts" / (dtb_path.stem + ".dts"))
    dts_out.parent.mkdir(parents=True, exist_ok=True)

    try:
        dtb_to_dts(dtb_path, dts_out)
        console.print(f"[green]✓ Decompiled: {dts_out}[/green]")
        console.print(f"  Edit DTS then recompile: [bold]watchrom dtb compile {dts_out}[/bold]")
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")


@dtb.command("compile")
@click.argument("dts_file")
@click.option("--out", "-o", default=None, help="Output .dtb file")
def dtb_compile(dts_file, out):
    """Compile an edited DTS source back to DTB binary."""
    dts_path = Path(dts_file)
    if not dts_path.exists():
        console.print(f"[red]✗ Not found: {dts_file}[/red]")
        return

    dtb_out = Path(out) if out else (OUTPUT_DIR / "dtb" / (dts_path.stem + ".dtb"))
    dtb_out.parent.mkdir(parents=True, exist_ok=True)

    try:
        dts_to_dtb(dts_path, dtb_out)
        console.print(f"[green]✓ Compiled: {dtb_out}[/green]")
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")


@dtb.command("patch-prop")
@click.argument("dtb_file")
@click.option("--node",  "-n", required=True, help="DT node path (e.g. /chosen)")
@click.option("--prop",  "-p", required=True, help="Property name (e.g. bootargs)")
@click.option("--value", "-v", required=True, help="New value")
@click.option("--out",   "-o", default=None)
def dtb_patch_prop(dtb_file, node, prop, value, out):
    """
    Patch a property value in a DTB node using fdtput.

    Examples:
      --node /chosen --prop bootargs --value "console=ttyS1,115200 androidboot.selinux=permissive"
      --node /memory --prop reg --value "0x80000000 0x40000000"
    """
    if not tool_available("fdtput"):
        console.print("[red]✗ fdtput not found. Install: sudo apt install device-tree-compiler[/red]")
        return

    dtb_path = Path(dtb_file)
    out_path = Path(out) if out else (OUTPUT_DIR / f"{dtb_path.stem}_patched.dtb")
    shutil.copy(dtb_path, out_path)

    console.print(f"[cyan]→ Patching {node}:{prop} = {value}[/cyan]")
    rc, _, err = run(["fdtput", "-t", "s", str(out_path), node, prop, value], check=False)
    if rc == 0:
        console.print(f"[green]✓ Patched DTB: {out_path}[/green]")
    else:
        console.print(f"[red]✗ fdtput failed: {err}[/red]")
