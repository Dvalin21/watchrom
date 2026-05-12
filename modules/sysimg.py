"""
sysimg.py — system.img / vendor.img extraction, editing, and repacking
Supports: ext4 raw images, sparse images (simg2img), erofs (read-only extract)
"""
import click
import shutil
import subprocess
import os
from pathlib import Path
from modules import (
    run, OUTPUT_DIR, WORKSPACE, sha256_file, file_size_mb, console, tool_available
)

# ── Tool checks ────────────────────────────────────────────────────────────────

def need(tool, hint):
    if not tool_available(tool):
        console.print(f"[red]✗ '{tool}' not found.[/red]  Install: {hint}")
        return False
    return True


# ── Sparse ↔ raw conversion ───────────────────────────────────────────────────

def is_sparse(img: Path) -> bool:
    """Check for Android sparse image magic (3aff26ed)."""
    with open(img, "rb") as f:
        magic = f.read(4)
    return magic == b"\x3a\xff\x26\xed"


def sparse_to_raw(img: Path, out: Path) -> Path:
    """Convert sparse image to raw ext4 using simg2img."""
    if not need("simg2img", "sudo apt install android-sdk-libsparse-utils"):
        raise FileNotFoundError("simg2img")
    console.print(f"[cyan]→ Converting sparse → raw...[/cyan]")
    run(["simg2img", str(img), str(out)])
    return out


def raw_to_sparse(img: Path, out: Path) -> Path:
    """Convert raw ext4 back to sparse using img2simg."""
    if not need("img2simg", "sudo apt install android-sdk-libsparse-utils"):
        raise FileNotFoundError("img2simg")
    console.print(f"[cyan]→ Converting raw → sparse...[/cyan]")
    run(["img2simg", str(img), str(out)])
    return out


# ── ext4 mount / unmount ──────────────────────────────────────────────────────

def _sudo_or_root(cmd: list) -> tuple:
    """Try command with sudo, fall back to direct (works if already root)."""
    import shutil
    if shutil.which("sudo"):
        rc, out, err = run(["sudo"] + cmd, check=False)
        if rc == 0:
            return rc, out, err
    return run(cmd, check=False)


def mount_ext4(img: Path, mount_point: Path) -> bool:
    """Mount a raw ext4 image via loop device. Works with or without sudo."""
    mount_point.mkdir(parents=True, exist_ok=True)
    rc, _, err = _sudo_or_root(["mount", "-o", "loop,rw", str(img), str(mount_point)])
    if rc != 0:
        rc, _, err = _sudo_or_root(["mount", "-o", "loop,ro", str(img), str(mount_point)])
        if rc != 0:
            # Final fallback: debugfs (no mount needed)
            return False
        console.print(f"[yellow]! Mounted read-only[/yellow]")
    return True


def unmount(mount_point: Path):
    _sudo_or_root(["umount", str(mount_point)])
    _sudo_or_root(["umount", "-l", str(mount_point)])


# ── erofs extract ──────────────────────────────────────────────────────────────

def extract_erofs(img: Path, out_dir: Path):
    """Extract erofs image (Android 11+ read-only system) using fsck.erofs."""
    if tool_available("fsck.erofs"):
        run(["fsck.erofs", "--extract=" + str(out_dir), str(img)])
    elif tool_available("extract.erofs"):
        run(["extract.erofs", "-i", str(img), "-o", str(out_dir)])
    else:
        raise FileNotFoundError(
            "erofs extract tool not found.\n"
            "  Install: sudo apt install erofs-utils\n"
            "  OR build from: https://git.kernel.org/pub/scm/linux/kernel/git/xiang/erofs-utils.git"
        )


def pack_erofs(src_dir: Path, out_img: Path):
    """Repack a directory into an erofs image using mkfs.erofs."""
    if not need("mkfs.erofs", "sudo apt install erofs-utils"):
        raise FileNotFoundError("mkfs.erofs")
    run(["mkfs.erofs", str(out_img), str(src_dir)])


# ── ext4 repack ───────────────────────────────────────────────────────────────

def pack_ext4(src_dir: Path, out_img: Path, label="system", size_mb: int = None):
    """
    Repack a directory into an ext4 image.
    Uses make_ext4fs or mke2fs depending on availability.
    """
    # Calculate size if not specified
    if not size_mb:
        result = subprocess.run(["du", "-sm", str(src_dir)], capture_output=True, text=True)
        used_mb = int(result.stdout.split()[0]) if result.returncode == 0 else 512
        size_mb = int(used_mb * 1.15) + 64  # 15% overhead + 64MB buffer

    size_bytes = size_mb * 1024 * 1024

    if tool_available("make_ext4fs"):
        run([
            "make_ext4fs",
            "-l", str(size_bytes),
            "-a", f"/{label}",
            "-L", label,
            str(out_img), str(src_dir)
        ])
    elif tool_available("mke2fs"):
        # Create blank image then populate
        run(["dd", "if=/dev/zero", f"of={out_img}", "bs=1M", f"count={size_mb}"])
        run(["mke2fs", "-t", "ext4", "-L", label, str(out_img)])
        # Copy files with e2cp or mount
        if tool_available("debugfs"):
            console.print("[yellow]! Using debugfs to populate (slower)...[/yellow]")
            for f in src_dir.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(src_dir)
                    run(["debugfs", "-w", str(out_img), "-R",
                         f"write {f} {rel}"], check=False)
        else:
            # Fallback: mount and copy
            mp = WORKSPACE / "tmp_ext4_mount"
            if mount_ext4(out_img, mp):
                run(["cp", "-a", str(src_dir) + "/.", str(mp)])
                unmount(mp)
    else:
        raise FileNotFoundError(
            "No ext4 packing tool found.\n"
            "  Install: sudo apt install android-sdk-libsparse-utils e2fsprogs"
        )

    console.print(f"[green]✓ Packed: {out_img} ({file_size_mb(out_img):.1f} MB)[/green]")


# ── File-context and permissions fix ──────────────────────────────────────────

def fix_permissions(mount_point: Path, fs_config: Path = None):
    """Apply Android filesystem permissions (contexts + ownership)."""
    # Default contexts for common system paths
    default_contexts = {
        "system/app":      ("system", "system", "0755"),
        "system/priv-app": ("system", "system", "0755"),
        "system/bin":      ("root",   "shell",  "0755"),
        "system/lib":      ("root",   "system", "0755"),
        "system/lib64":    ("root",   "system", "0755"),
        "system/etc":      ("root",   "system", "0755"),
        "system/framework":("system", "system", "0755"),
    }
    console.print("[cyan]→ Fixing ownership/permissions...[/cyan]")
    for path, (user, group, mode) in default_contexts.items():
        target = mount_point / path.replace("system/", "")
        if target.exists():
            run(["chown", "-R", f"{user}:{group}", str(target)], check=False)
            run(["chmod", "-R", mode, str(target)], check=False)

    # selinux contexts
    fc_path = fs_config or (mount_point / "etc/selinux/plat_file_contexts")
    if fc_path.exists() and tool_available("restorecon"):
        run(["sudo", "restorecon", "-r", str(mount_point)], check=False)


# ── CLI ────────────────────────────────────────────────────────────────────────

@click.group()
def sysimg():
    """system.img / vendor.img extraction, editing, and repacking."""
    pass


@sysimg.command("extract")
@click.argument("image")
@click.option("--out",    "-o", default=None, help="Output directory")
@click.option("--format", "-f",
              type=click.Choice(["auto", "ext4", "erofs", "sparse"]),
              default="auto", help="Image format (auto-detect by default)")
def sysimg_extract(image, out, format):
    """
    Extract system.img or vendor.img to an editable directory.

    Supports ext4 (raw + sparse) and erofs images.
    Sparse images are automatically converted to raw ext4 first.

    Output directory can be freely edited, then repacked with:
      watchrom sysimg repack
    """
    img_path = Path(image)
    if not img_path.exists():
        console.print(f"[red]✗ Image not found: {image}[/red]")
        return

    label = img_path.stem
    out_dir = Path(out) if out else (OUTPUT_DIR / "sysimg_extracted" / label)
    out_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold cyan]System Image Extractor[/bold cyan]")
    console.print(f"  Image : {img_path.name} ({file_size_mb(img_path):.1f} MB)")
    console.print(f"  Out   : {out_dir}\n")

    # Auto-detect format
    if format == "auto":
        if is_sparse(img_path):
            format = "sparse"
        else:
            with open(img_path, "rb") as f:
                magic = f.read(4)
            if magic == b"\xe2\xe1\xf5\xe0":  # erofs magic
                format = "erofs"
            else:
                format = "ext4"

    console.print(f"  [dim]Detected format: {format}[/dim]\n")

    # Resolve to raw ext4 if sparse
    work_img = img_path
    if format == "sparse":
        raw_img = WORKSPACE / f"{label}_raw.img"
        work_img = sparse_to_raw(img_path, raw_img)
        format = "ext4"

    if format == "erofs":
        console.print("[cyan]→ Extracting erofs image...[/cyan]")
        try:
            extract_erofs(work_img, out_dir)
            console.print(f"[green]✓ Extracted to: {out_dir}[/green]")
        except Exception as e:
            console.print(f"[red]✗ erofs extract failed: {e}[/red]")
        return

    # ext4 — mount and copy
    mount_pt = WORKSPACE / f"{label}_mount"
    console.print(f"[cyan]→ Mounting ext4 image...[/cyan]")
    if not mount_ext4(work_img, mount_pt):
        # Fallback: debugfs
        console.print("[yellow]! Mount failed, trying debugfs extract...[/yellow]")
        if tool_available("debugfs"):
            run(["debugfs", "-R", f"rdump / {out_dir}", str(work_img)], check=False)
            console.print(f"[green]✓ Extracted via debugfs → {out_dir}[/green]")
        else:
            console.print("[red]✗ No extraction method available. Install: sudo apt install e2fsprogs[/red]")
        return

    console.print(f"[cyan]→ Copying files...[/cyan]")
    run(["cp", "-a", str(mount_pt) + "/.", str(out_dir)])
    unmount(mount_pt)

    # Fix ownership so user can edit
    run(["chown", "-R", f"{os.getuid()}:{os.getgid()}", str(out_dir)], check=False)

    file_count = sum(1 for _ in out_dir.rglob("*"))
    console.print(f"[green]✓ Extracted {file_count} items → {out_dir}[/green]")
    console.print(f"\n[dim]Edit freely, then repack with:[/dim]")
    console.print(f"  [bold]watchrom sysimg repack {out_dir} --label {label}[/bold]")


@sysimg.command("repack")
@click.argument("src_dir")
@click.option("--label",  "-l", default="system",
              type=click.Choice(["system","vendor","product","system_ext","odm"]))
@click.option("--out",    "-o", default=None, help="Output image path")
@click.option("--format", "-f",
              type=click.Choice(["ext4","erofs","sparse-ext4"]), default="ext4")
@click.option("--size",   "-s", default=None, type=int,
              help="Image size in MB (auto-calculated if omitted)")
@click.option("--no-sparse", is_flag=True,
              help="Keep as raw ext4 (don't convert to sparse)")
def sysimg_repack(src_dir, label, out, format, size, no_sparse):
    """
    Repack an edited directory back into a flashable system image.

    Produces raw ext4 or erofs, optionally converted to sparse
    (required by some fastboot implementations).
    """
    src = Path(src_dir)
    if not src.is_dir():
        console.print(f"[red]✗ Not a directory: {src_dir}[/red]")
        return

    out_path = Path(out) if out else (OUTPUT_DIR / f"{label}_repacked.img")

    console.print(f"\n[bold cyan]System Image Repacker[/bold cyan]")
    console.print(f"  Source : {src}")
    console.print(f"  Label  : {label}")
    console.print(f"  Format : {format}")
    console.print(f"  Output : {out_path}\n")

    try:
        if format == "erofs":
            console.print("[cyan]→ Packing erofs...[/cyan]")
            pack_erofs(src, out_path)
        else:
            console.print("[cyan]→ Packing ext4...[/cyan]")
            pack_ext4(src, out_path, label=label, size_mb=size)

            if format == "sparse-ext4" and not no_sparse:
                sparse_out = out_path.parent / (out_path.stem + "_sparse.img")
                console.print("[cyan]→ Converting to sparse...[/cyan]")
                raw_to_sparse(out_path, sparse_out)
                console.print(f"[green]✓ Sparse image: {sparse_out}[/green]")
                out_path = sparse_out

    except Exception as e:
        console.print(f"[red]✗ Repack failed: {e}[/red]")
        return

    console.print(f"\n[bold green]✓ Repacked: {out_path}[/bold green]")
    console.print(f"  Size  : {file_size_mb(out_path):.1f} MB")
    console.print(f"  SHA256: {sha256_file(out_path)[:32]}…")
    console.print(f"\n  Flash: [bold]watchrom flash {label} {out_path}[/bold]")


@sysimg.command("edit")
@click.argument("image")
@click.option("--out",   "-o", default=None, help="Output repacked image path")
@click.option("--label", "-l", default="system")
def sysimg_edit(image, out, label):
    """
    Interactive edit session: extract → open shell → repack.

    Extracts the image, opens a shell in the extracted directory
    so you can make changes, then repacks on exit.
    """
    img_path = Path(image)
    if not img_path.exists():
        console.print(f"[red]✗ Image not found: {image}[/red]")
        return

    edit_dir = WORKSPACE / f"{label}_edit"

    console.print(f"\n[bold cyan]Interactive System Image Editor[/bold cyan]")
    console.print(f"  Will extract → you edit → auto-repack on exit\n")

    # Extract
    from click.testing import CliRunner
    ctx = click.get_current_context()
    console.print("[cyan]Step 1/3: Extracting...[/cyan]")

    label_val = img_path.stem

    # Inline extraction
    if is_sparse(img_path):
        raw = WORKSPACE / f"{label_val}_raw.img"
        sparse_to_raw(img_path, raw)
        work = raw
    else:
        work = img_path

    edit_dir.mkdir(parents=True, exist_ok=True)
    mount_pt = WORKSPACE / f"{label_val}_mount_edit"

    if mount_ext4(work, mount_pt):
        run(["cp", "-a", str(mount_pt) + "/.", str(edit_dir)])
        unmount(mount_pt)
        run(["chown", "-R", f"{os.getuid()}:{os.getgid()}", str(edit_dir)], check=False)
    else:
        if tool_available("debugfs"):
            run(["debugfs", "-R", f"rdump / {edit_dir}", str(work)], check=False)
        else:
            console.print("[red]✗ Extraction failed.[/red]")
            return

    console.print(f"\n[bold green]Step 2/3: Edit your files in:[/bold green]")
    console.print(f"  [cyan]{edit_dir}[/cyan]")
    console.print(f"\n  Common edits:")
    console.print(f"    app/         — system APKs")
    console.print(f"    priv-app/    — privileged APKs (Settings, SystemUI, etc.)")
    console.print(f"    framework/   — framework JARs")
    console.print(f"    build.prop   — system properties")
    console.print(f"    etc/         — configs, hosts, permissions")
    console.print(f"\n  Press [Enter] when done editing to repack...")
    input()

    # Repack
    out_path = Path(out) if out else (OUTPUT_DIR / f"{label}_modified.img")
    console.print("\n[cyan]Step 3/3: Repacking...[/cyan]")
    try:
        pack_ext4(edit_dir, out_path, label=label)
        console.print(f"\n[bold green]✓ Done! Modified image: {out_path}[/bold green]")
        console.print(f"  Flash: [bold]watchrom flash {label} {out_path}[/bold]")
    except Exception as e:
        console.print(f"[red]✗ Repack failed: {e}[/red]")


@sysimg.command("ls")
@click.argument("image")
@click.argument("path", required=False, default="/")
def sysimg_ls(image, path):
    """List files inside a system image without fully extracting it."""
    img_path = Path(image)
    if not img_path.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return

    work = img_path
    if is_sparse(img_path):
        raw = WORKSPACE / f"{img_path.stem}_raw_ls.img"
        work = sparse_to_raw(img_path, raw)

    if tool_available("debugfs"):
        rc, out, _ = run(
            ["debugfs", "-R", f"ls -l {path}", str(work)],
            check=False
        )
        console.print(out)
    else:
        # Mount and ls
        mp = WORKSPACE / "sysimg_ls_mount"
        if mount_ext4(work, mp):
            target = mp / path.lstrip("/")
            if target.exists():
                for f in sorted(target.iterdir()):
                    icon = "📁" if f.is_dir() else "📄"
                    console.print(f"  {icon} {f.name}")
            unmount(mp)


@sysimg.command("cat")
@click.argument("image")
@click.argument("filepath")
def sysimg_cat(image, filepath):
    """Read a single file from inside a system image."""
    img_path = Path(image)
    if not img_path.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return

    work = img_path
    if is_sparse(img_path):
        raw = WORKSPACE / f"{img_path.stem}_raw_cat.img"
        work = sparse_to_raw(img_path, raw)

    if tool_available("debugfs"):
        rc, out, _ = run(
            ["debugfs", "-R", f"cat {filepath}", str(work)],
            check=False
        )
        console.print(out)
    else:
        mp = WORKSPACE / "sysimg_cat_mount"
        if mount_ext4(work, mp):
            target = mp / filepath.lstrip("/")
            if target.exists():
                console.print(target.read_text(errors="replace"))
            else:
                console.print(f"[red]Not found in image: {filepath}[/red]")
            unmount(mp)


@sysimg.command("patch-prop")
@click.argument("image")
@click.option("--key",   "-k", required=True, help="Property key (e.g. ro.debuggable)")
@click.option("--value", "-v", required=True, help="New value")
@click.option("--out",   "-o", default=None,  help="Output image path")
@click.option("--file",  "-f", default="build.prop",
              help="Prop file path inside image (default: build.prop)")
def sysimg_patch_prop(image, key, value, out, file):
    """
    Patch a single property in build.prop (or any .prop file) inside the image.

    Common uses:
      --key ro.debuggable       --value 1
      --key ro.secure           --value 0
      --key ro.adb.secure       --value 0
      --key persist.sys.usb.config --value mtp,adb
    """
    img_path = Path(image)
    if not img_path.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return

    work = img_path
    if is_sparse(img_path):
        raw = WORKSPACE / f"{img_path.stem}_raw_pp.img"
        work = sparse_to_raw(img_path, raw)

    out_path = Path(out) if out else (OUTPUT_DIR / f"{img_path.stem}_patched.img")

    # Mount, edit prop, unmount, repack
    mp = WORKSPACE / "prop_patch_mount"
    console.print(f"\n[cyan]→ Mounting {img_path.name}...[/cyan]")

    if not mount_ext4(work, mp):
        console.print("[red]✗ Mount failed.[/red]")
        return

    prop_file = mp / file
    if not prop_file.exists():
        # Try in /system/
        prop_file = mp / "system" / file
    if not prop_file.exists():
        unmount(mp)
        console.print(f"[red]✗ Property file not found: {file}[/red]")
        return

    content = prop_file.read_text(errors="replace")
    lines   = content.splitlines()
    found   = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            old_val = line.split("=", 1)[1]
            new_lines.append(f"{key}={value}")
            console.print(f"  [yellow]{key}[/yellow]: [red]{old_val}[/red] → [green]{value}[/green]")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{key}={value}")
        console.print(f"  [yellow]{key}[/yellow]: [dim](new)[/dim] → [green]{value}[/green]")

    run(["tee", str(prop_file)], check=False,
        capture=False)
    prop_file.write_text("\n".join(new_lines) + "\n")

    unmount(mp)

    # Copy to output
    shutil.copy(work, out_path)
    console.print(f"\n[green]✓ Patched image: {out_path}[/green]")
    console.print(f"  Flash: [bold]watchrom flash system {out_path}[/bold]")


@sysimg.command("info")
@click.argument("image")
def sysimg_info(image):
    """Show format, size, and filesystem info for a system image."""
    img_path = Path(image)
    if not img_path.exists():
        console.print(f"[red]✗ Not found: {image}[/red]")
        return

    console.print(f"\n[bold cyan]Image Info: {img_path.name}[/bold cyan]\n")
    console.print(f"  File size : {file_size_mb(img_path):.2f} MB")
    console.print(f"  SHA256    : {sha256_file(img_path)[:32]}…")

    with open(img_path, "rb") as f:
        magic = f.read(8)

    fmt = "unknown"
    if magic[:4] == b"\x3a\xff\x26\xed":
        fmt = "sparse ext4"
    elif magic[:4] == b"\xe2\xe1\xf5\xe0":
        fmt = "erofs"
    elif magic[:2] in (b"\x53\xef", b"\x53\xef"):
        fmt = "ext4 (raw)"
    elif magic[:4] == b"CrAU":
        fmt = "payload.bin / OTA"
    console.print(f"  Format    : [yellow]{fmt}[/yellow]")

    if tool_available("file"):
        rc, out, _ = run(["file", str(img_path)], check=False)
        console.print(f"  file(1)   : {out.strip()}")

    if tool_available("dumpe2fs") and "ext4" in fmt:
        rc, out, _ = run(["dumpe2fs", "-h", str(img_path)], check=False)
        for line in out.splitlines():
            if any(k in line for k in ("Block count","Block size","Inode count","Volume name","Last mount","Features")):
                console.print(f"  [dim]{line.strip()}[/dim]")
