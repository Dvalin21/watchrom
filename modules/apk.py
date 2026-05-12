"""
apk.py — APK decompilation, editing, recompilation, and signing
Tools: apktool (smali), jadx (Java decompile), apksigner / jarsigner
"""
import click
import shutil
import subprocess
from pathlib import Path
from modules import (
    run, run_adb, adb_devices, OUTPUT_DIR, WORKSPACE, KEYS_DIR,
    sha256_file, file_size_mb, console, require_tool, tool_available
)


# ─── Helper: jadx decompile ───────────────────────────────────────────────────

def jadx_decompile(apk_path: Path, out_dir: Path):
    """Decompile APK to Java source via jadx."""
    require_tool("jadx")
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "jadx",
        "--output-dir", str(out_dir),
        "--deobf",
        "--show-bad-code",
        "--threads-count", "4",
        str(apk_path)
    ]
    console.print(f"[cyan]→ jadx: decompiling to Java source...[/cyan]")
    rc, out, err = run(cmd, check=False, timeout=300)
    if rc == 0:
        java_files = list(out_dir.rglob("*.java"))
        console.print(f"[green]✓ jadx: {len(java_files)} Java source files[/green]")
    else:
        console.print(f"[yellow]! jadx exited {rc} (may still have output)[/yellow]")
        console.print(f"[dim]{err[:400]}[/dim]")


def apktool_decode(apk_path: Path, out_dir: Path, no_res=False, no_src=False):
    """Decode APK to smali + resources via apktool."""
    require_tool("apktool")
    cmd = [
        "apktool", "d",
        "-f",                         # Force overwrite
        "-o", str(out_dir),
        str(apk_path),
    ]
    if no_res: cmd.append("-r")
    if no_src: cmd.append("-s")
    console.print(f"[cyan]→ apktool: decoding APK (smali + resources)...[/cyan]")
    rc, out, err = run(cmd, check=False, timeout=300)
    if rc == 0:
        smali_files = list(out_dir.rglob("*.smali"))
        xml_files   = list(out_dir.rglob("*.xml"))
        console.print(f"[green]✓ apktool: {len(smali_files)} smali | {len(xml_files)} XML[/green]")
    else:
        console.print(f"[red]✗ apktool decode failed:[/red]\n{err[:400]}")
        raise RuntimeError("apktool decode failed")


def apktool_build(project_dir: Path, out_apk: Path):
    """Rebuild APK from smali/resource project."""
    require_tool("apktool")
    cmd = [
        "apktool", "b",
        str(project_dir),
        "-o", str(out_apk),
    ]
    console.print(f"[cyan]→ apktool: rebuilding APK...[/cyan]")
    rc, out, err = run(cmd, check=False, timeout=300)
    if rc != 0:
        raise RuntimeError(f"apktool build failed:\n{err[:400]}")
    console.print(f"[green]✓ Rebuilt: {out_apk} ({file_size_mb(out_apk):.1f} MB)[/green]")


# ─── Signing ──────────────────────────────────────────────────────────────────

def sign_apk_apksigner(apk_path: Path, ks_path: Path, ks_pass="watchrom",
                        key_alias="key0", out_path: Path = None) -> Path:
    """Sign APK with apksigner (SDK build-tools)."""
    if not tool_available("apksigner"):
        # Try Android SDK paths
        import os
        sdk = os.environ.get("ANDROID_HOME", os.path.expanduser("~/Android/Sdk"))
        for bt in Path(sdk).glob("build-tools/*/apksigner"):
            shutil.copy(bt, "/usr/local/bin/apksigner")
            break
        if not tool_available("apksigner"):
            raise FileNotFoundError(
                "apksigner not found.\n"
                "  Install Android SDK Build Tools OR:\n"
                "  sudo apt install apksigner"
            )

    out = out_path or apk_path.parent / (apk_path.stem + "_signed.apk")
    cmd = [
        "apksigner", "sign",
        "--ks", str(ks_path),
        "--ks-pass", f"pass:{ks_pass}",
        "--ks-key-alias", key_alias,
        "--out", str(out),
        str(apk_path),
    ]
    run(cmd, timeout=60)
    return out


def sign_apk_jarsigner(apk_path: Path, ks_path: Path, ks_pass="watchrom",
                         key_alias="key0", out_path: Path = None) -> Path:
    """Fallback sign with jarsigner (older method)."""
    require_tool("jarsigner")
    out = out_path or apk_path.parent / (apk_path.stem + "_signed.apk")
    shutil.copy(apk_path, out)
    cmd = [
        "jarsigner",
        "-verbose",
        "-sigalg",   "SHA1withRSA",
        "-digestalg", "SHA1",
        "-keystore",  str(ks_path),
        "-storepass", ks_pass,
        str(out),
        key_alias,
    ]
    run(cmd, timeout=60)
    # zipalign
    if tool_available("zipalign"):
        aligned = out.parent / (out.stem + "_aligned.apk")
        run(["zipalign", "-v", "4", str(out), str(aligned)], check=False)
        if aligned.exists():
            out.unlink()
            aligned.rename(out)
    return out


def create_debug_keystore(ks_path: Path, alias="key0", pass_="watchrom"):
    """Generate a debug keystore for signing."""
    require_tool("keytool")
    cmd = [
        "keytool", "-genkey", "-v",
        "-keystore", str(ks_path),
        "-alias",    alias,
        "-keyalg",   "RSA",
        "-keysize",  "2048",
        "-validity", "10000",
        "-storepass", pass_,
        "-keypass",   pass_,
        "-dname",    "CN=WatchROM,OU=ROM,O=Dev,L=Local,ST=Local,C=US",
        "-noprompt",
    ]
    run(cmd, timeout=30)


# ─── CLI ──────────────────────────────────────────────────────────────────────

@click.group()
def apk():
    """APK decompilation, editing, recompilation, and signing."""
    pass


@apk.command("pull")
@click.argument("package")
@click.option("--serial", "-s", default=None)
@click.option("--out",    "-o", default=None)
def apk_pull(package, serial, out):
    """Pull an APK from device by package name."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device online.[/red]")
        return
    target = serial or online[0]

    _, pm_out, _ = run_adb(["shell", f"pm path {package}"], serial=target, check=False)
    if "package:" not in pm_out:
        console.print(f"[red]✗ Package not found: {package}[/red]")
        return

    remote_apk = pm_out.strip().replace("package:", "")
    out_path   = Path(out) if out else (OUTPUT_DIR / f"{package}.apk")
    console.print(f"[cyan]Pulling {remote_apk}...[/cyan]")
    rc, _, err = run_adb(["pull", remote_apk, str(out_path)], serial=target, check=False)
    if rc == 0:
        console.print(f"[green]✓ Saved: {out_path} ({file_size_mb(out_path):.1f} MB)[/green]")
    else:
        console.print(f"[red]✗ Pull failed: {err}[/red]")


@apk.command("decompile")
@click.argument("apk_path")
@click.option("--out",    "-o", default=None, help="Output directory")
@click.option("--jadx",   "-j", "use_jadx", is_flag=True, default=True,
              help="Also run jadx for Java source (default: on)")
@click.option("--smali",  "-s", "use_smali", is_flag=True, default=True,
              help="Run apktool for smali+resources (default: on)")
@click.option("--no-res", is_flag=True, help="Skip resource decoding")
def apk_decompile(apk_path, out, use_jadx, use_smali, no_res):
    """
    Fully decompile an APK using apktool (smali) and jadx (Java).

    Output structure:
      out/smali/     — apktool decode (editable smali + resources)
      out/java/      — jadx Java source (read-only reference)
      out/apk_info.txt
    """
    src = Path(apk_path)
    if not src.exists():
        console.print(f"[red]✗ APK not found: {apk_path}[/red]")
        return

    base = Path(out) if out else (OUTPUT_DIR / "decompiled" / src.stem)
    smali_dir = base / "smali"
    java_dir  = base / "java"
    base.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold cyan]APK Decompiler[/bold cyan]")
    console.print(f"  APK   : {src.name} ({file_size_mb(src):.1f} MB)")
    console.print(f"  Output: {base}\n")

    # Write info
    with open(base / "apk_info.txt", "w") as f:
        f.write(f"APK: {src.name}\nSize: {file_size_mb(src):.2f} MB\nSHA256: {sha256_file(src)}\n")

    errors = []

    if use_smali:
        try:
            apktool_decode(src, smali_dir, no_res=no_res)
        except Exception as e:
            errors.append(f"apktool: {e}")

    if use_jadx:
        try:
            jadx_decompile(src, java_dir)
        except FileNotFoundError as e:
            console.print(f"[yellow]! jadx not found — skipping Java decompile[/yellow]")
        except Exception as e:
            errors.append(f"jadx: {e}")

    if errors:
        for err in errors:
            console.print(f"[red]✗ {err}[/red]")
    else:
        console.print(f"\n[bold green]✓ Decompile complete → {base}[/bold green]")
        console.print(f"  Edit smali in: [cyan]{smali_dir}[/cyan]")
        console.print(f"  Reference Java: [cyan]{java_dir}[/cyan]")
        console.print(f"\n  Rebuild with: [bold]watchrom apk recompile {smali_dir}[/bold]")


@apk.command("recompile")
@click.argument("project_dir")
@click.option("--out",    "-o", default=None, help="Output APK path")
@click.option("--keystore","-k", default=None,
              help="Keystore for signing (auto-generates debug ks if omitted)")
@click.option("--ks-pass",  default="watchrom", help="Keystore password")
@click.option("--ks-alias", default="key0",     help="Key alias")
@click.option("--no-sign",  is_flag=True, help="Skip signing")
def apk_recompile(project_dir, out, keystore, ks_pass, ks_alias, no_sign):
    """
    Rebuild an edited apktool project and sign the APK.

    Steps:
      1. apktool build → unsigned APK
      2. Sign with keystore (or auto-generate debug keystore)
    """
    proj = Path(project_dir)
    if not proj.is_dir():
        console.print(f"[red]✗ Not a directory: {project_dir}[/red]")
        return

    out_unsigned = WORKSPACE / f"{proj.name}_unsigned.apk"
    console.print(f"\n[bold cyan]APK Recompiler[/bold cyan]")

    try:
        apktool_build(proj, out_unsigned)
    except Exception as e:
        console.print(f"[red]✗ Build failed: {e}[/red]")
        return

    if no_sign:
        dst = Path(out) if out else (OUTPUT_DIR / f"{proj.name}.apk")
        shutil.copy(out_unsigned, dst)
        console.print(f"[green]✓ Unsigned APK: {dst}[/green]")
        return

    # Keystore
    ks_path = Path(keystore) if keystore else (KEYS_DIR / "debug.keystore")
    if not ks_path.exists():
        console.print(f"[cyan]→ Generating debug keystore: {ks_path}[/cyan]")
        try:
            create_debug_keystore(ks_path, alias=ks_alias, pass_=ks_pass)
        except FileNotFoundError:
            console.print("[yellow]! keytool not found. Install JDK.[/yellow]")
            return

    out_signed = Path(out) if out else (OUTPUT_DIR / f"{proj.name}_signed.apk")

    # Try apksigner first, fall back to jarsigner
    try:
        signed = sign_apk_apksigner(out_unsigned, ks_path, ks_pass, ks_alias, out_signed)
    except FileNotFoundError:
        console.print("[yellow]apksigner not found, trying jarsigner...[/yellow]")
        try:
            signed = sign_apk_jarsigner(out_unsigned, ks_path, ks_pass, ks_alias, out_signed)
        except Exception as e:
            console.print(f"[red]✗ Signing failed: {e}[/red]")
            return

    console.print(f"[bold green]✓ Signed APK: {signed}[/bold green]")
    console.print(f"  SHA256: {sha256_file(signed)[:32]}…")
    console.print(f"\n  Install: [bold]adb install -r {signed}[/bold]")


@apk.command("list")
@click.option("--serial", "-s", default=None)
@click.option("--system", "-S", is_flag=True, help="Include system apps")
@click.option("--filter", "-f", "pkg_filter", default="")
def apk_list(serial, system, pkg_filter):
    """List installed packages on device."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device online.[/red]")
        return
    target = serial or online[0]

    flags = "" if system else "-3"
    _, out, _ = run_adb(["shell", f"pm list packages {flags}"], serial=target, check=False)

    packages = sorted([l.replace("package:", "").strip() for l in out.splitlines() if "package:" in l])
    if pkg_filter:
        packages = [p for p in packages if pkg_filter.lower() in p.lower()]

    console.print(f"\n[bold]{len(packages)} packages[/bold] on {target}:\n")
    for pkg in packages:
        console.print(f"  [cyan]{pkg}[/cyan]")
