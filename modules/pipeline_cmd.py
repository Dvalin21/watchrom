"""
pipeline_cmd.py — CLI wrapper for the pipeline system
watchrom pipeline <name> [options]
"""
import click
import sys
from pathlib import Path
from modules import console


@click.group()
def pipeline():
    """
    Run automated multi-step workflows.

    Pipelines chain tasks with automatic backup, rollback on failure,
    progress display, and state persistence for resuming interrupted runs.

    Each step shows:   ✓ done   ✗ failed   — skipped   → running

    Available pipelines:
    \b
      root-device      Detect → backup → Magisk patch → flash → verify
      full-backup      Detect → dump all partitions → backup apps → manifest
      avb-disable      Detect → backup vbmeta → blank vbmeta → flash
      flash-rom        Validate → backup → disable AVB → flash all → reboot
      wearos-setup     Detect → root check → build module → install → verify
      configure-bands  Detect → backup bands → apply carrier → reboot
    """
    pass


def _run_pipeline(name: str, ctx: dict, dry: bool, resume: str,
                  state_file: Path = None):
    """Shared pipeline runner used by all subcommands."""
    from core.pipeline import get_pipeline
    p = get_pipeline(name)
    if not p:
        console.print(f"[red]✗ Unknown pipeline: {name}[/red]")
        sys.exit(1)

    console.print(f"\n[bold cyan]Pipeline: {p.name}[/bold cyan]")
    console.print(f"[dim]{p.description}[/dim]\n")
    console.print(f"  {'─'*50}")

    if dry:
        plan = p.dry_run(ctx)
        console.print(f"  [bold yellow]Dry run — {len(plan)} steps:[/bold yellow]\n")
        for step in plan:
            req  = "[bold]*[/bold]" if step["required"] else " "
            run  = "[green]would run[/green]" if step["would_run"] else "[dim]would skip[/dim]"
            console.print(f"    {req} {step['name']:28s} {run}  [dim]{step['description'][:40]}[/dim]")
        console.print(f"\n  [dim]* = required step[/dim]")
        return

    console.print()
    result = p.run(ctx, resume_from=resume,
                   state_file=state_file)

    console.print(f"\n  {'─'*50}")
    if result.success:
        console.print(f"[bold green]  ✓ Pipeline complete[/bold green]  {result.summary}")
    else:
        console.print(f"[bold red]  ✗ Pipeline failed[/bold red]  {result.summary}")
        for rec in result.failed_tasks:
            err = rec.result.error if rec.result else "unknown error"
            console.print(f"    [red]✗ {rec.name}: {err}[/red]")
        sys.exit(1)


@pipeline.command("root-device")
@click.option("--serial",  "-s", default=None, help="ADB device serial")
@click.option("--dry-run", is_flag=True, help="Show steps without executing")
@click.option("--resume",  default=None, help="Resume from step name")
@click.option("--state",   default=None, help="State file for resume support")
def pl_root_device(serial, dry_run, resume, state):
    """
    Root a device via Magisk boot.img patching.

    Steps:
    \b
      detect       — Identify device, chipset, ADB serial
      backup       — Dump stock boot.img to output/backups/
      check-magisk — Verify Magisk APK is installed on device
      patch-boot   — Patch boot.img using Magisk on-device
      disable-avb  — Create blank vbmeta (prevents AVB rejection)
      flash-boot   — Flash patched boot via fastboot, reboot
      verify       — Confirm uid=0 after boot

    Requires: Magisk installed on device, USB debugging enabled.
    """
    ctx = {}
    if serial:
        ctx["serial"] = serial
    _run_pipeline("root-device", ctx, dry_run, resume,
                  Path(state) if state else None)


@pipeline.command("full-backup")
@click.option("--serial",  "-s", default=None)
@click.option("--dry-run", is_flag=True)
@click.option("--out",     "-o", default=None, help="Output directory")
def pl_full_backup(serial, dry_run, out):
    """
    Complete device backup — all partitions + apps + manifest.

    Steps:
    \b
      detect          — Identify chipset and partition layout
      dump-partitions — Dump every partition to output/backups/<serial>/
      backup-apps     — ADB backup of all user apps and data
      write-manifest  — Write JSON manifest with checksums

    Safe to run any time — read-only, no changes to device.
    """
    ctx = {}
    if serial: ctx["serial"] = serial
    if out:    ctx["backup_root"] = out
    _run_pipeline("full-backup", ctx, dry_run, None)


@pipeline.command("avb-disable")
@click.option("--serial",  "-s", default=None)
@click.option("--dry-run", is_flag=True)
def pl_avb_disable(serial, dry_run):
    """
    Disable Android Verified Boot (AVB) verification.

    Steps:
    \b
      detect        — Identify device
      backup-vbmeta — Dump stock vbmeta.img to backup
      create-blank  — Generate a blank vbmeta (flags=3, verification disabled)
      flash-vbmeta  — Flash via fastboot --disable-verity --disable-verification

    Run this before flashing custom system images or ROMs.
    """
    ctx = {}
    if serial: ctx["serial"] = serial
    _run_pipeline("avb-disable", ctx, dry_run, None)


@pipeline.command("flash-rom")
@click.option("--parts-dir", "-p", required=True,
              help="Directory containing partition .img files")
@click.option("--serial",    "-s", default=None)
@click.option("--dry-run",   is_flag=True)
@click.option("--resume",    default=None,
              help="Resume from step name (e.g. 'flash-all')")
@click.option("--state",     default=None)
def pl_flash_rom(parts_dir, serial, dry_run, resume, state):
    """
    Flash a complete ROM package to device.

    Steps:
    \b
      validate    — Check all .img files exist and are valid
      backup      — Full device backup before any changes
      disable-avb — Disable AVB so custom images boot
      flash-all   — Flash partitions in safe order via fastboot

    Flash order: vbmeta → dtbo → persist → modem → vendor →
                 system → product → odm → recovery → boot

    Use --resume flash-all to skip straight to flashing (if backup already done).
    """
    ctx = {"parts_dir": parts_dir}
    if serial: ctx["serial"] = serial
    _run_pipeline("flash-rom", ctx, dry_run, resume,
                  Path(state) if state else None)


@pipeline.command("wearos-setup")
@click.option("--serial",   "-s", default=None)
@click.option("--density",  "-d", default=240, type=int,
              help="Screen DPI for watch (default 240)")
@click.option("--dry-run",  is_flag=True)
def pl_wearos_setup(serial, density, dry_run):
    """
    Set up WearOS app compatibility on a full Android watch.

    Steps:
    \b
      detect         — Identify device chipset
      check-root     — Verify Magisk root is active
      backup-props   — Save current system properties
      build-module   — Build WearOS systemless Magisk module
      install-module — Push and install via Magisk
      verify         — Check ro.build.characteristics=watch

    Requires root. Run 'watchrom pipeline root-device' first if not rooted.
    """
    ctx = {"screen_density": density}
    if serial: ctx["serial"] = serial
    _run_pipeline("wearos-setup", ctx, dry_run, None)


@pipeline.command("configure-bands")
@click.option("--carrier",  "-c", required=True,
              type=click.Choice([
                  "verizon","tmobile","att","firstnet","dish_boost","cbrs",
                  "uk_vodafone","uk_ee","eu_generic","canada_rogers",
                  "australia_telstra","japan_docomo","korea_skt","india_jio",
                  "china_telecom","latam_full","global_roaming",
              ]),
              help="Carrier profile to apply")
@click.option("--serial",   "-s", default=None)
@click.option("--dry-run",  is_flag=True)
def pl_configure_bands(carrier, serial, dry_run):
    """
    Configure LTE/5G band preferences for a carrier.

    Steps:
    \b
      detect         — Identify chipset vendor (MTK/Unisoc/Qualcomm/etc.)
      backup-bands   — Save current band config before changes
      apply-bands    — Write carrier band profile to modem
      reboot-verify  — Reboot and confirm signal

    Works on all vendors. Uses EFS (Qualcomm), AT+EPBSE (MTK/Unisoc),
    or generic AT commands for other vendors.

    Examples:
    \b
      watchrom pipeline configure-bands --carrier verizon
      watchrom pipeline configure-bands --carrier tmobile
      watchrom pipeline configure-bands --carrier global_roaming
    """
    ctx = {"carrier": carrier}
    if serial: ctx["serial"] = serial
    _run_pipeline("configure-bands", ctx, dry_run, None)


@pipeline.command("list")
def pl_list():
    """List all registered pipelines with their steps."""
    from core.pipeline import list_pipelines
    from rich.table import Table
    from rich import box as rbox

    pipelines = list_pipelines()
    console.print(f"\n[bold cyan]Available Pipelines ({len(pipelines)})[/bold cyan]\n")

    for name, p in pipelines.items():
        t = Table(
            title=f"[bold green]{name}[/bold green]  [dim]{p.description}[/dim]",
            box=rbox.SIMPLE, show_header=True,
            header_style="bold cyan", border_style="dim",
            title_justify="left",
        )
        t.add_column("Step",        style="cyan",  width=22)
        t.add_column("Description", style="white", width=40)
        t.add_column("Required",    style="dim",   width=10)
        t.add_column("Retries",     style="dim",   width=8)
        for task in p.tasks:
            t.add_row(
                task.name,
                task.description,
                "[bold]*[/bold]" if task.required else "optional",
                str(task.retries) if task.retries else "—",
            )
        console.print(t)
        console.print()

    console.print("[dim]Usage: watchrom pipeline <name> [--dry-run] [--resume <step>][/dim]\n")


@pipeline.command("custom")
@click.argument("steps", nargs=-1)
@click.option("--serial", "-s", default=None)
@click.option("--dry-run", is_flag=True)
def pl_custom(steps, serial, dry_run):
    """
    Run a custom pipeline from named built-in steps.

    Chain specific steps from any pipeline by name.
    Steps run in the order given.

    Example — backup then root without verify:
    \b
      watchrom pipeline custom detect backup check-magisk patch-boot flash-boot

    Available step names: detect, backup, check-magisk, patch-boot,
    disable-avb, flash-boot, verify, dump-partitions, backup-apps,
    backup-vbmeta, create-blank, flash-vbmeta, validate, flash-all,
    check-root, backup-props, build-module, install-module,
    backup-bands, apply-bands, reboot-verify
    """
    if not steps:
        console.print("[red]✗ Specify at least one step name.[/red]")
        console.print("  Run [bold]watchrom pipeline list[/bold] to see available steps.")
        return

    from core.pipeline import list_pipelines, Pipeline, Task

    # Collect all tasks from all pipelines
    all_tasks = {}
    for p in list_pipelines().values():
        for task in p.tasks:
            all_tasks[task.name] = task

    # Build custom pipeline
    custom = Pipeline("custom", f"Custom: {' → '.join(steps)}")
    not_found = []
    for step_name in steps:
        if step_name in all_tasks:
            custom.add(all_tasks[step_name])
        else:
            not_found.append(step_name)

    if not_found:
        console.print(f"[red]✗ Unknown steps: {', '.join(not_found)}[/red]")
        console.print(f"  Available: {', '.join(sorted(all_tasks.keys()))}")
        return

    ctx = {}
    if serial: ctx["serial"] = serial
    _run_pipeline_obj(custom, ctx, dry_run)


def _run_pipeline_obj(p, ctx: dict, dry: bool):
    """Run a Pipeline object directly."""
    console.print(f"\n[bold cyan]Pipeline: {p.name}[/bold cyan]")
    console.print(f"[dim]{p.description}[/dim]\n")

    if dry:
        plan = p.dry_run(ctx)
        for step in plan:
            marker = "✓" if step["would_run"] else "—"
            console.print(f"  {marker} {step['name']}")
        return

    result = p.run(ctx)
    if result.success:
        console.print(f"\n[bold green]✓ Complete[/bold green]  {result.summary}")
    else:
        console.print(f"\n[bold red]✗ Failed[/bold red]  {result.summary}")
        for rec in result.failed_tasks:
            err = rec.result.error if rec.result else "?"
            console.print(f"  [red]✗ {rec.name}: {err}[/red]")
