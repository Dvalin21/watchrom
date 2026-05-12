"""
keys.py — AOSP signing key generation and management
Generates: platform, media, shared, releasekey, AVB keys
Matches AOSP build/target/product/security/ key set
"""
import click
from pathlib import Path
from modules import run, KEYS_DIR, console, tool_available, require_tool


# AOSP standard key names
AOSP_KEY_NAMES = ["platform", "media", "shared", "releasekey", "networkstack"]
AVB_KEY_NAME   = "avb"
APK_KEY_NAME   = "apk_debug"

SUBJECT_TEMPLATE = "/C=US/ST=California/L=Mountain View/O=Android/OU=Android/CN={name}/emailAddress=android@android.com"


def gen_rsa_key(key_path: Path, bits=2048):
    """Generate RSA private key."""
    require_tool("openssl")
    run(["openssl", "genrsa", "-out", str(key_path), str(bits)])


def gen_x509_cert(key_path: Path, cert_path: Path, subject: str, days=10000):
    """Generate self-signed X.509 certificate."""
    run([
        "openssl", "req",
        "-new", "-x509",
        "-key", str(key_path),
        "-out", str(cert_path),
        "-days", str(days),
        "-subj", subject,
        "-sha256",
    ])


def gen_pkcs8_key(key_path: Path, pk8_path: Path):
    """Convert PEM private key to PKCS#8 DER (needed by AOSP signapk)."""
    run([
        "openssl", "pkcs8",
        "-in", str(key_path),
        "-topk8", "-nocrypt",
        "-outform", "DER",
        "-out", str(pk8_path),
    ])


def gen_keystore(ks_path: Path, alias: str, password: str, dname: str):
    """Generate a JKS keystore with keytool."""
    require_tool("keytool")
    run([
        "keytool", "-genkey", "-v",
        "-keystore", str(ks_path),
        "-alias", alias,
        "-keyalg", "RSA", "-keysize", "4096",
        "-validity", "10000",
        "-storepass", password,
        "-keypass",   password,
        "-dname", dname,
        "-noprompt",
    ])


def gen_avb_key(key_path: Path, bits=2048):
    """Generate AVB signing key (RSA PEM, used by avbtool)."""
    gen_rsa_key(key_path, bits)


def extract_avb_pubkey(key_path: Path, pubkey_path: Path):
    """Extract AVB public key in avbtool format."""
    if tool_available("avbtool"):
        run(["avbtool", "extract_public_key",
             "--key", str(key_path),
             "--output", str(pubkey_path)], check=False)
    else:
        run(["openssl", "rsa",
             "-in", str(key_path),
             "-pubout", "-out", str(pubkey_path)])


@click.group()
def keys():
    """Generate and manage AOSP signing keys (platform, media, AVB, APK)."""
    pass


@keys.command("generate")
@click.option("--out",     "-o", default=None, help="Output directory (default: keys/)")
@click.option("--bits",    "-b", default=2048, type=int, help="RSA key size")
@click.option("--avb",     is_flag=True, default=True,  help="Generate AVB key (default: on)")
@click.option("--apk",     is_flag=True, default=True,  help="Generate APK debug keystore")
@click.option("--ks-pass", default="watchrom", help="Keystore password")
def keys_generate(out, bits, avb, apk, ks_pass):
    """
    Generate a full AOSP signing key set:

      platform.pk8 / platform.x509.pem  — System app signing
      media.pk8    / media.x509.pem      — Media framework
      shared.pk8   / shared.x509.pem     — Shared user
      releasekey.pk8 / releasekey.x509   — Release key
      avb.pem                            — AVB boot/vbmeta signing
      debug.keystore                     — APK debug signing keystore
    """
    key_dir = Path(out) if out else KEYS_DIR
    key_dir.mkdir(parents=True, exist_ok=True)

    if not tool_available("openssl"):
        console.print("[red]✗ openssl not found. Install: sudo apt install openssl[/red]")
        return

    console.print(f"\n[bold cyan]AOSP Key Generator[/bold cyan]")
    console.print(f"  Output : {key_dir}")
    console.print(f"  RSA    : {bits}-bit\n")

    # AOSP standard keys
    for name in AOSP_KEY_NAMES:
        pem_path  = key_dir / f"{name}.pem"
        pk8_path  = key_dir / f"{name}.pk8"
        cert_path = key_dir / f"{name}.x509.pem"
        subject   = SUBJECT_TEMPLATE.format(name=name)

        console.print(f"  Generating [cyan]{name}[/cyan]...", end="")
        gen_rsa_key(pem_path, bits)
        gen_x509_cert(pem_path, cert_path, subject)
        gen_pkcs8_key(pem_path, pk8_path)
        size = pk8_path.stat().st_size
        console.print(f" [green]✓[/green] ({size} bytes)")

    # AVB key
    if avb:
        avb_key  = key_dir / "avb.pem"
        avb_pub  = key_dir / "avb_pubkey.bin"
        console.print(f"  Generating [cyan]AVB key[/cyan]...", end="")
        gen_avb_key(avb_key, bits)
        extract_avb_pubkey(avb_key, avb_pub)
        console.print(f" [green]✓[/green]")

    # APK debug keystore
    if apk:
        ks_path = key_dir / "debug.keystore"
        console.print(f"  Generating [cyan]APK debug keystore[/cyan]...", end="")
        if tool_available("keytool"):
            gen_keystore(
                ks_path, alias="key0", password=ks_pass,
                dname="CN=WatchROM Debug,OU=WatchROM,O=WatchROM,L=Local,ST=CA,C=US"
            )
            console.print(f" [green]✓[/green]")
        else:
            console.print(f" [yellow]skipped (keytool not found)[/yellow]")

    # Write index
    index = key_dir / "KEY_INDEX.txt"
    with open(index, "w") as f:
        f.write("WatchROM Signing Key Index\n")
        f.write(f"Generated: RSA-{bits}\n\n")
        f.write("AOSP Keys (signapk usage):\n")
        for name in AOSP_KEY_NAMES:
            f.write(f"  {name:15s}  {name}.pk8  +  {name}.x509.pem\n")
        f.write(f"\nAVB:       avb.pem  (avbtool --key avb.pem)\n")
        f.write(f"APK:       debug.keystore  (pass: {ks_pass})\n\n")
        f.write("Signing examples:\n")
        f.write(f"  APK:     apksigner sign --ks debug.keystore --ks-pass pass:{ks_pass} app.apk\n")
        f.write(f"  System:  java -jar signapk.jar platform.x509.pem platform.pk8 in.apk out.apk\n")
        f.write(f"  vbmeta:  avbtool make_vbmeta_image --key avb.pem --algorithm SHA256_RSA2048 ...\n")

    console.print(f"\n[bold green]✓ Key set complete → {key_dir}[/bold green]")
    console.print(f"  [dim]Index: {index}[/dim]")


@keys.command("list")
@click.option("--dir", "-d", "key_dir", default=None)
def keys_list(key_dir):
    """List available signing keys."""
    kd = Path(key_dir) if key_dir else KEYS_DIR
    if not kd.exists():
        console.print(f"[yellow]No keys directory found at {kd}[/yellow]")
        console.print("  Generate with: [bold]watchrom keys generate[/bold]")
        return

    from rich.table import Table
    from rich import box as rbox
    t = Table(title=f"Keys in {kd}", box=rbox.SIMPLE, border_style="cyan")
    t.add_column("Name", style="green")
    t.add_column("Type", style="yellow")
    t.add_column("Size")

    for f in sorted(kd.iterdir()):
        if f.suffix in (".pem",".pk8",".keystore",".bin",".p12"):
            ftype = {"pem":"RSA/X509 PEM","pk8":"PKCS8 DER","keystore":"JKS Keystore",
                     "bin":"Binary Pubkey","p12":"PKCS12"}.get(f.suffix.lstrip("."),"Key File")
            t.add_row(f.name, ftype, f"{f.stat().st_size} B")

    console.print(t)
