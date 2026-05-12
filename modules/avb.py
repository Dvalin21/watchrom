"""
avb.py — Android Verified Boot (AVB) / vbmeta manipulation
Handles: disabling verification, patching flags, re-signing with custom keys
"""
import click
import struct
import shutil
from pathlib import Path
from modules import (
    run, run_adb, run_fastboot, adb_devices, OUTPUT_DIR, WORKSPACE,
    KEYS_DIR, sha256_file, file_size_mb, console, tool_available
)

# ─── AVB constants ─────────────────────────────────────────────────────────────

AVB_MAGIC           = b"AVB0"
AVB_HASHTREE_FLAGS  = 0x00000001   # HASHTREE_DISABLED
AVB_VERIFICATION_FLAGS = 0x00000002  # VERIFICATION_DISABLED

EMPTY_VBMETA_FLAGS  = 0x00000003   # Both disabled

# ─── Low-level vbmeta binary patching ─────────────────────────────────────────

class VBMetaHeader:
    """
    Minimal AVB vbmeta header parser/writer.
    Ref: external/avb/libavb/avb_vbmeta_image.h
    """
    FORMAT = ">4sI I I I I I I I I I I I I 64s 32s 32s 48s 256s"
    SIZE    = struct.calcsize(FORMAT)

    def __init__(self, data: bytes):
        fields = struct.unpack(self.FORMAT, data[:self.SIZE])
        (self.magic, self.required_libavb_version_major,
         self.required_libavb_version_minor, self.authentication_data_block_size,
         self.auxiliary_data_block_size, self.algorithm_type,
         self.hash_offset, self.hash_size, self.signature_offset,
         self.signature_size, self.public_key_offset, self.public_key_size,
         self.public_key_metadata_offset, self.public_key_metadata_size,
         self.descriptor_end_offset, self.rollback_index, self.flags,
         self.rollback_index_location, self.release_string,
         self.reserved) = fields[:20]
        self.raw = bytearray(data)

    @property
    def flags_offset(self):
        return struct.calcsize(">4sI I I I I I I I I I I I I 64s 32s")

    def set_flags(self, flags: int):
        struct.pack_into(">I", self.raw, self.flags_offset, flags)

    def to_bytes(self) -> bytes:
        return bytes(self.raw)

    def is_valid(self) -> bool:
        return self.magic == AVB_MAGIC


def read_vbmeta(path: Path) -> VBMetaHeader:
    with open(path, "rb") as f:
        data = f.read()
    hdr = VBMetaHeader(data)
    if not hdr.is_valid():
        raise ValueError(f"Not a valid vbmeta image: {path}")
    return hdr


def patch_vbmeta_flags(vbmeta_path: Path, out_path: Path, flags: int = EMPTY_VBMETA_FLAGS):
    """Patch vbmeta flags to disable verification and hashtree checks."""
    hdr = read_vbmeta(vbmeta_path)
    old_flags = hdr.flags
    hdr.set_flags(flags)
    with open(out_path, "wb") as f:
        f.write(hdr.to_bytes())
    console.print(f"  [dim]vbmeta flags: 0x{old_flags:08x} → 0x{flags:08x}[/dim]")
    return hdr


def create_blank_vbmeta(out_path: Path):
    """Create a minimal vbmeta.img with verification fully disabled."""
    # Craft minimal header — 4096 bytes, magic + flags=3
    buf = bytearray(4096)
    buf[0:4] = AVB_MAGIC
    struct.pack_into(">I", buf, 4,  1)   # major
    struct.pack_into(">I", buf, 8,  0)   # minor
    # flags at offset = struct.calcsize(">4sI I I I I I I I I I I I I 64s 32s")
    flag_off = 4 + 4 + 4 + 4 + 4 + 4 + 4 + 4 + 4 + 4 + 4 + 4 + 4 + 4 + 64 + 32
    struct.pack_into(">I", buf, flag_off, EMPTY_VBMETA_FLAGS)
    with open(out_path, "wb") as f:
        f.write(bytes(buf))
    console.print(f"  [green]✓ Blank vbmeta created: {out_path}[/green]")


# ─── avbtool wrapper ──────────────────────────────────────────────────────────

def avbtool_sign(image_path: Path, key_path: Path, algorithm="SHA256_RSA2048",
                 rollback_index=0, out_path: Path = None) -> Path:
    """Sign a partition image using avbtool."""
    if not tool_available("avbtool"):
        raise FileNotFoundError(
            "avbtool not found.\n"
            "  Install: pip install avbtool  OR  build from AOSP external/avb/"
        )
    out = out_path or image_path.parent / (image_path.stem + "_signed.img")
    shutil.copy(image_path, out)
    cmd = [
        "avbtool", "add_hashtree_footer",
        "--image", str(out),
        "--key", str(key_path),
        "--algorithm", algorithm,
        "--rollback_index", str(rollback_index),
    ]
    run(cmd)
    return out


def avbtool_make_vbmeta(images: dict, key_path: Path, out_path: Path,
                         algorithm="SHA256_RSA2048"):
    """
    Generate vbmeta.img that chains to signed partition images.
    images = {"boot": Path(...), "system": Path(...), ...}
    """
    if not tool_available("avbtool"):
        raise FileNotFoundError("avbtool not found.")

    cmd = [
        "avbtool", "make_vbmeta_image",
        "--output", str(out_path),
        "--key", str(key_path),
        "--algorithm", algorithm,
    ]
    for part_name, img_path in images.items():
        cmd += ["--include_descriptors_from_image", str(img_path)]

    run(cmd)
    return out_path


# ─── CLI ──────────────────────────────────────────────────────────────────────

@click.group()
def avb():
    """AVB (Android Verified Boot) vbmeta manipulation and signing."""
    pass


@avb.command("patch")
@click.argument("vbmeta_img", required=False)
@click.option("--serial",  "-s", default=None)
@click.option("--out",     "-o", default=None)
@click.option("--blank",   "-b", is_flag=True,
              help="Create a blank vbmeta (verification fully disabled)")
@click.option("--flash",   "-f", "do_flash", is_flag=True,
              help="Flash patched vbmeta to device immediately")
def avb_patch(vbmeta_img, serial, out, blank, do_flash):
    """
    Patch vbmeta to disable AVB verification and dm-verity.

    This allows booting modified system/vendor/boot images
    without signature failures. Two modes:

      --blank    : Replace with a minimal empty vbmeta (most compatible)
      (default)  : Patch flags in existing vbmeta image
    """
    console.print("\n[bold cyan]AVB vbmeta Patcher[/bold cyan]")

    if blank:
        out_path = Path(out) if out else (OUTPUT_DIR / "vbmeta_blank.img")
        create_blank_vbmeta(out_path)
    else:
        if not vbmeta_img:
            # Try to dump from device
            devs = adb_devices()
            online = [s for s, st in devs if st == "device"]
            if not online:
                console.print("[red]✗ No device and no vbmeta image specified.[/red]")
                return
            target = serial or online[0]
            console.print("[cyan]→ Dumping vbmeta from device...[/cyan]")
            from modules.partition import dump_partition_adb
            vbmeta_path = WORKSPACE / "vbmeta_stock.img"
            if not dump_partition_adb("vbmeta", vbmeta_path, serial=target):
                console.print("[red]✗ Could not dump vbmeta.[/red]")
                return
        else:
            vbmeta_path = Path(vbmeta_img)

        out_path = Path(out) if out else (vbmeta_path.parent / "vbmeta_patched.img")

        try:
            hdr = patch_vbmeta_flags(vbmeta_path, out_path)
            console.print(f"[green]✓ Patched vbmeta: {out_path}[/green]")
            console.print(f"  Size: {file_size_mb(out_path):.2f} MB | SHA256: {sha256_file(out_path)[:24]}…")
        except Exception as e:
            console.print(f"[red]✗ Patch failed: {e}[/red]")
            return

    if do_flash or click.confirm("\nFlash patched vbmeta to device?", default=False):
        target = serial
        if not target:
            from modules import fastboot_devices
            fb = fastboot_devices()
            target = fb[0] if fb else None
        if not target:
            console.print("[yellow]! No fastboot device. Reboot to bootloader first.[/yellow]")
        else:
            rc, _, err = run_fastboot(
                ["flash", "vbmeta", str(out_path)],
                serial=target, check=False
            )
            if rc == 0:
                console.print("[green]✓ vbmeta flashed.[/green]")
            else:
                console.print(f"[red]✗ Flash failed: {err}[/red]")


@avb.command("sign")
@click.argument("image")
@click.option("--key",  "-k", required=True, help="Private key (.pem)")
@click.option("--algo", "-a", default="SHA256_RSA2048",
              type=click.Choice(["SHA256_RSA2048","SHA256_RSA4096","SHA512_RSA4096"]))
@click.option("--rollback", "-r", default=0, type=int)
@click.option("--out",  "-o", default=None)
def avb_sign(image, key, algo, rollback, out):
    """Re-sign a partition image with a custom AVB key using avbtool."""
    img_path = Path(image)
    key_path = Path(key)
    if not img_path.exists():
        console.print(f"[red]✗ Image not found: {image}[/red]")
        return
    if not key_path.exists():
        console.print(f"[red]✗ Key not found: {key}[/red]")
        return

    try:
        signed = avbtool_sign(img_path, key_path, algo, rollback,
                              Path(out) if out else None)
        console.print(f"[green]✓ Signed image: {signed}[/green]")
    except Exception as e:
        console.print(f"[red]✗ {e}[/red]")


@avb.command("info")
@click.argument("image")
def avb_info(image):
    """Show AVB metadata for a partition image or vbmeta."""
    img_path = Path(image)
    if not img_path.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return

    if tool_available("avbtool"):
        rc, out, _ = run(["avbtool", "info_image", "--image", str(img_path)], check=False)
        console.print(out)
    else:
        # Fallback: manual parse
        try:
            hdr = read_vbmeta(img_path)
            console.print(f"[bold]AVB Header Info[/bold]")
            console.print(f"  Magic      : {hdr.magic}")
            console.print(f"  Flags      : 0x{hdr.flags:08x}")
            console.print(f"  Algo type  : {hdr.algorithm_type}")
            console.print(f"  Pubkey size: {hdr.public_key_size}")
            console.print(f"  Auth block : {hdr.authentication_data_block_size}")
            console.print(f"  Aux block  : {hdr.auxiliary_data_block_size}")
        except Exception as e:
            console.print(f"[red]Not a vbmeta image or parse error: {e}[/red]")
