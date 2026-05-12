"""
sepolicy.py — SELinux policy extraction, auditing, and patching
Handles: policy.33, plat_sepolicy.cil, audit2allow, permissive mode injection
"""
import click
import re
import shutil
from pathlib import Path
from modules import run, run_adb, adb_devices, OUTPUT_DIR, WORKSPACE, console, tool_available


# ── Helpers ───────────────────────────────────────────────────────────────────

def find_policy_on_device(serial=None) -> str:
    """Find the SELinux policy file on device."""
    candidates = [
        "/sys/fs/selinux/policy",
        "/vendor/etc/selinux/precompiled_sepolicy",
        "/system/etc/selinux/plat_sepolicy.cil",
        "/odm/etc/selinux/precompiled_sepolicy",
    ]
    for path in candidates:
        _, out, _ = run_adb(["shell", f"ls {path} 2>/dev/null"], serial=serial, check=False)
        if out.strip() == path:
            return path
    return ""


def pull_policy(serial=None, out_path: Path = None) -> Path:
    """Pull SELinux policy from device."""
    remote = find_policy_on_device(serial)
    if not remote:
        raise FileNotFoundError("SELinux policy not found on device")
    out = out_path or (WORKSPACE / "sepolicy.bin")
    run_adb(["pull", remote, str(out)], serial=serial)
    return out


def audit2allow_rules(log_lines: list) -> list:
    """
    Parse AVC denied lines from logcat and generate allow rules.
    Returns list of allow rule strings.
    """
    rules = []
    seen  = set()
    avc_pattern = re.compile(
        r"avc:\s+denied\s+\{([^}]+)\}\s+for\s+.*?scontext=(\S+)\s+tcontext=(\S+)\s+tclass=(\S+)"
    )
    for line in log_lines:
        m = avc_pattern.search(line)
        if m:
            perms   = m.group(1).strip().split()
            sctx    = m.group(2).split(":")[2] if ":" in m.group(2) else m.group(2)
            tctx    = m.group(3).split(":")[2] if ":" in m.group(3) else m.group(3)
            tclass  = m.group(4)
            rule = f"allow {sctx} {tctx}:{tclass} {{{' '.join(perms)}}};"
            if rule not in seen:
                seen.add(rule)
                rules.append(rule)
    return rules


# ── CLI ───────────────────────────────────────────────────────────────────────

@click.group()
def sepolicy():
    """SELinux policy extraction, auditing, and patching."""
    pass


@sepolicy.command("pull")
@click.option("--serial", "-s", default=None)
@click.option("--out",    "-o", default=None)
def sepolicy_pull(serial, out):
    """Pull SELinux policy binary from connected device."""
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    out_path = Path(out) if out else (OUTPUT_DIR / "sepolicy.bin")
    try:
        policy = pull_policy(target, out_path)
        console.print(f"[green]✓ Policy pulled: {policy}[/green]")
        console.print(f"  Decompile: [bold]watchrom sepolicy decompile {policy}[/bold]")
    except Exception as e:
        console.print(f"[red]✗ {e}[/red]")


@sepolicy.command("decompile")
@click.argument("policy_bin")
@click.option("--out", "-o", default=None)
def sepolicy_decompile(policy_bin, out):
    """
    Decompile binary SELinux policy to CIL or readable text.
    Requires: seinfo, sesearch, or apol (setools package)
    """
    pol = Path(policy_bin)
    if not pol.exists():
        console.print(f"[red]✗ Not found: {policy_bin}[/red]")
        return

    out_path = Path(out) if out else (OUTPUT_DIR / "sepolicy_decompiled.txt")

    if tool_available("sedump"):
        rc, out_text, _ = run(["sedump", str(pol)], check=False)
        out_path.write_text(out_text)
        console.print(f"[green]✓ Decompiled → {out_path}[/green]")
    elif tool_available("seinfo"):
        rc, out_text, _ = run(["seinfo", str(pol), "--all"], check=False)
        out_path.write_text(out_text)
        console.print(f"[green]✓ Policy info → {out_path}[/green]")
        # Also dump all allow rules
        rules_path = out_path.parent / "sepolicy_allow_rules.txt"
        rc2, out2, _ = run(["sesearch", str(pol), "--allow"], check=False)
        rules_path.write_text(out2)
        console.print(f"[green]✓ Allow rules → {rules_path}[/green]")
    else:
        console.print("[yellow]! setools not installed.[/yellow]")
        console.print("  Install: sudo apt install setools")
        console.print("  OR: pip install setools")
        # Show raw stats at least
        size = pol.stat().st_size
        console.print(f"\n  Policy file: {pol}  ({size//1024} KB)")
        console.print("  Binary SELinux policy — setools needed to read.")


@sepolicy.command("audit")
@click.option("--serial",  "-s", default=None)
@click.option("--lines",   "-n", default=500, type=int,
              help="Number of logcat lines to scan (default 500)")
@click.option("--out",     "-o", default=None,
              help="Write allow rules to file")
@click.option("--live",    "-l", is_flag=True,
              help="Stream live logcat (Ctrl+C to stop and generate rules)")
def sepolicy_audit(serial, lines, out, live):
    """
    Parse AVC denials from device logcat and generate allow rules (audit2allow).

    Output is ready-to-add SELinux allow rules for your policy.
    """
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    console.print(f"\n[bold cyan]SELinux AVC Audit — {target}[/bold cyan]\n")

    if live:
        console.print("[cyan]Streaming logcat (Ctrl+C to stop)...[/cyan]")
        import subprocess, signal
        log_lines = []
        try:
            proc = subprocess.Popen(
                ["adb", "-s", target, "logcat", "-s", "auditd", "avc"],
                stdout=subprocess.PIPE, text=True
            )
            for line in proc.stdout:
                log_lines.append(line)
                if "avc: denied" in line:
                    console.print(f"  [yellow]AVC[/yellow] {line.strip()[:100]}")
        except KeyboardInterrupt:
            proc.terminate()
    else:
        _, out_log, _ = run_adb(
            ["logcat", "-d", "-s", "auditd,avc", f"-T", str(lines)],
            serial=target, check=False
        )
        log_lines = out_log.splitlines()

    avc_lines = [l for l in log_lines if "avc: denied" in l]
    console.print(f"\n[bold]Found {len(avc_lines)} AVC denial(s)[/bold]")

    if not avc_lines:
        console.print("[green]✓ No AVC denials found in log.[/green]")
        return

    rules = audit2allow_rules(avc_lines)
    console.print(f"[bold]Generated {len(rules)} allow rule(s):[/bold]\n")

    for rule in rules:
        console.print(f"  [green]{rule}[/green]")

    if out or click.confirm("\nSave rules to file?", default=True):
        out_file = Path(out) if out else (OUTPUT_DIR / "avc_allow_rules.te")
        with open(out_file, "w") as f:
            f.write("# Auto-generated by WatchROM audit2allow\n")
            f.write("# Add to your device sepolicy/\n\n")
            for rule in rules:
                f.write(rule + "\n")
        console.print(f"\n[green]✓ Rules saved: {out_file}[/green]")


@sepolicy.command("permissive")
@click.option("--serial",  "-s", default=None,
              help="Apply permissive to live device (requires root)")
@click.option("--domain",  "-d", default=None,
              help="Domain to make permissive (e.g. untrusted_app). Leave blank for global.")
def sepolicy_permissive(serial, domain):
    """
    Set SELinux to permissive mode on a live device (requires root).
    Global permissive disables all enforcement — useful for debugging denials.
    """
    devs = adb_devices()
    online = [s for s, st in devs if st == "device"]
    if not online:
        console.print("[red]✗ No ADB device.[/red]")
        return
    target = serial or online[0]

    console.print(f"\n[bold cyan]SELinux Permissive — {target}[/bold cyan]")

    if domain:
        # Per-domain permissive via supolicy/magiskpolicy
        for tool in ["supolicy", "magiskpolicy"]:
            _, loc, _ = run_adb(["shell", f"which {tool} 2>/dev/null"],
                                 serial=target, check=False)
            if loc.strip():
                cmd = f"su -c '{loc.strip()} --live \"permissive {domain}\"'"
                _, out, _ = run_adb(["shell", cmd], serial=target, check=False)
                console.print(f"[green]✓ Domain '{domain}' set permissive[/green]")
                return

        # Try setenforce + sepolicy-inject
        _, out, _ = run_adb(
            ["shell", f"su -c 'setenforce 0 && echo ok'"],
            serial=target, check=False
        )
        if "ok" in out:
            console.print("[green]✓ Global SELinux set to Permissive[/green]")
        else:
            console.print("[yellow]! Could not set permissive. Root required.[/yellow]")
    else:
        _, out, _ = run_adb(
            ["shell", "su -c 'setenforce 0 && getenforce'"],
            serial=target, check=False
        )
        console.print(f"[{'green' if 'Permissive' in out else 'red'}]{out.strip()}[/{'green' if 'Permissive' in out else 'red'}]")

    # Check current state
    _, state, _ = run_adb(["shell", "getenforce"], serial=target, check=False)
    console.print(f"  Current SELinux: [bold]{state.strip()}[/bold]")
