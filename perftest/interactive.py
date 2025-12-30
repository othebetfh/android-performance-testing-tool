"""Interactive mode for Android Performance Testing Tool - full menu system."""

import os
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.panel import Panel

from perftest.commands import (
    find_available_builds,
    find_available_test_runs,
    detect_apk_pairs,
    non_interactive_build,
    non_interactive_upload_and_test,
    non_interactive_analyze,
    non_interactive_full_pipeline
)

console = Console()


def parse_build_name(name: str) -> tuple[str, str]:
    """
    Parse branch and commit from build directory name.
    Expected format: <branch>_<commit>

    Returns:
        Tuple of (branch, commit)
    """
    parts = name.rsplit('_', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return name, ""


def select_cached_build() -> dict | None:
    """
    Show available cached builds and allow user to select one.

    Returns:
        Dict with build info and selected APK pair, or None if skipped
    """
    builds = find_available_builds()

    if not builds:
        console.print("[yellow]No cached builds found in output directory[/yellow]")
        return None

    console.print("\n[cyan]Available Builds:[/cyan]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Build Name", style="cyan")
    table.add_column("APK Pairs", style="green")

    build_options = []
    for idx, build in enumerate(builds, 1):
        apk_pairs = detect_apk_pairs(build['apks_dir'])
        apk_info = f"{len(apk_pairs)} pair(s)" if apk_pairs else "No valid pairs"

        table.add_row(
            str(idx),
            build['name'],
            apk_info
        )
        build_options.append({
            'build': build,
            'apk_pairs': apk_pairs
        })

    console.print(table)
    console.print()

    choice = IntPrompt.ask(
        "Select build number (0 to skip)",
        default=0
    )

    if choice == 0 or choice > len(build_options):
        return None

    selected = build_options[choice - 1]

    # If multiple APK pairs, let user select one
    if len(selected['apk_pairs']) > 1:
        console.print("\n[cyan]Available APK Pairs:[/cyan]\n")

        pair_table = Table(show_header=True, header_style="bold magenta")
        pair_table.add_column("#", style="dim", width=4)
        pair_table.add_column("APK Pair", style="green")

        for idx, pair in enumerate(selected['apk_pairs'], 1):
            pair_table.add_row(
                str(idx),
                pair['display']
            )

        console.print(pair_table)
        console.print()

        pair_choice = IntPrompt.ask(
            "Select APK pair number"
        )

        if pair_choice < 1 or pair_choice > len(selected['apk_pairs']):
            pair_choice = 1

        selected['selected_pair'] = selected['apk_pairs'][pair_choice - 1]
    elif selected['apk_pairs']:
        selected['selected_pair'] = selected['apk_pairs'][0]
    else:
        console.print("[yellow]No valid APK pairs found[/yellow]")
        return None

    # Parse branch and commit
    branch, commit = parse_build_name(selected['build']['name'])
    selected['branch'] = branch
    selected['commit'] = commit

    return selected


def select_cached_test_run(label: str = "test run") -> dict | None:
    """
    Show available cached test runs and allow user to select one.

    Args:
        label: Label for the selection (e.g., "base run", "test run")

    Returns:
        Dict with test run info, or None if skipped
    """
    test_runs = find_available_test_runs()

    if not test_runs:
        console.print("[yellow]No cached test runs found in output directory[/yellow]")
        return None

    console.print(f"\n[cyan]Available Test Runs ({label}):[/cyan]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Build Name", style="cyan")
    table.add_column("Device Pools", style="green")
    table.add_column("Tests", style="yellow")

    run_options = []
    for idx, run in enumerate(test_runs, 1):
        device_pool_names = list(run['device_pools'].keys())
        all_test_names = set()
        for tests in run['device_pools'].values():
            all_test_names.update(tests)

        table.add_row(
            str(idx),
            run['name'],
            ", ".join(device_pool_names),
            ", ".join(sorted(all_test_names))
        )
        run_options.append(run)

    console.print(table)
    console.print()

    choice = IntPrompt.ask(
        "Select test run number (0 to skip)",
        default=0
    )

    if choice == 0 or choice > len(run_options):
        return None

    selected = run_options[choice - 1]

    # If multiple device pools, let user select one
    device_pool_names = list(selected['device_pools'].keys())
    if len(device_pool_names) > 1:
        console.print("\n[cyan]Available Device Pools:[/cyan]\n")

        pool_table = Table(show_header=True, header_style="bold magenta")
        pool_table.add_column("#", style="dim", width=4)
        pool_table.add_column("Device Pool", style="green")
        pool_table.add_column("Tests", style="yellow")

        for idx, pool_name in enumerate(device_pool_names, 1):
            tests = selected['device_pools'][pool_name]
            pool_table.add_row(
                str(idx),
                pool_name,
                ", ".join(tests)
            )

        console.print(pool_table)
        console.print()

        pool_choice = IntPrompt.ask(
            "Select device pool number"
        )

        if pool_choice < 1 or pool_choice > len(device_pool_names):
            pool_choice = 1

        selected['selected_pool'] = device_pool_names[pool_choice - 1]
    else:
        selected['selected_pool'] = device_pool_names[0]

    # If multiple tests, let user select one
    test_names = selected['device_pools'][selected['selected_pool']]
    if len(test_names) > 1:
        console.print("\n[cyan]Available Tests:[/cyan]\n")

        test_table = Table(show_header=True, header_style="bold magenta")
        test_table.add_column("#", style="dim", width=4)
        test_table.add_column("Test Name", style="yellow")

        for idx, test_name in enumerate(test_names, 1):
            test_table.add_row(
                str(idx),
                test_name
            )

        console.print(test_table)
        console.print()

        test_choice = IntPrompt.ask(
            "Select test number"
        )

        if test_choice < 1 or test_choice > len(test_names):
            test_choice = 1

        selected['selected_test'] = test_names[test_choice - 1]
    else:
        selected['selected_test'] = test_names[0]

    # Parse branch and commit
    branch, commit = parse_build_name(selected['name'])
    selected['branch'] = branch
    selected['commit'] = commit

    return selected


def build_apk_interactive():
    """Interactive workflow for building APK."""
    console.print("\n[cyan]Build APK from source[/cyan]\n")

    branch = Prompt.ask("Git branch name")
    commit = Prompt.ask("Git commit hash")
    flavor = Prompt.ask("Product flavor", default="dev")
    build_type = Prompt.ask("Build type", default="perf")

    console.print("\n[green]Building APK...[/green]\n")

    non_interactive_build(
        branch=branch,
        commit=commit,
        product_flavor=flavor,
        build_type=build_type
    )


def run_test_interactive():
    """Interactive workflow for running performance test."""
    console.print("\n[cyan]Run performance test on Device Farm[/cyan]\n")

    # Try to show cached builds
    console.print("[yellow]Checking for cached builds...[/yellow]")
    selected_build = select_cached_build()

    if selected_build:
        branch = selected_build['branch']
        commit = selected_build['commit']
        console.print(f"\n[green]✓ Using build:[/green] {selected_build['build']['name']}")
        console.print(f"  Branch: {branch}")
        console.print(f"  Commit: {commit}\n")
    else:
        console.print("\n[yellow]No cached build selected. Enter details manually:[/yellow]\n")
        branch = Prompt.ask("Git branch name")
        commit = Prompt.ask("Git commit hash")

    # Get AWS Device Farm projects
    from perftest.commands.devicefarm import get_projects, get_device_pools, get_available_tests

    console.print("\n[yellow]Fetching AWS Device Farm projects...[/yellow]")
    projects = get_projects()

    project_arn = None
    if projects:
        console.print("\n[cyan]Available Projects:[/cyan]\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Project Name", style="cyan")

        for idx, project in enumerate(projects, 1):
            table.add_row(str(idx), project['name'])

        console.print(table)
        console.print()

        choice = IntPrompt.ask(
            "Select project number (0 to enter ARN manually)",
            default=0
        )

        if choice > 0 and choice <= len(projects):
            project_arn = projects[choice - 1]['arn']
            console.print(f"\n[green]✓ Selected project:[/green] {projects[choice - 1]['name']}\n")

    if not project_arn:
        project_arn = Prompt.ask("AWS Device Farm project ARN")

    # Get device pools for selected project
    console.print("[yellow]Fetching device pools...[/yellow]")
    device_pools = get_device_pools(project_arn)

    device_pool_arn = None
    if device_pools:
        console.print("\n[cyan]Available Device Pools:[/cyan]\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Device Pool Name", style="green")
        table.add_column("Type", style="yellow")

        for idx, pool in enumerate(device_pools, 1):
            table.add_row(str(idx), pool['name'], pool.get('type', 'PRIVATE'))

        console.print(table)
        console.print()

        choice = IntPrompt.ask(
            "Select device pool number (0 to enter ARN manually)",
            default=0
        )

        if choice > 0 and choice <= len(device_pools):
            device_pool_arn = device_pools[choice - 1]['arn']
            console.print(f"\n[green]✓ Selected device pool:[/green] {device_pools[choice - 1]['name']}\n")

    if not device_pool_arn:
        device_pool_arn = Prompt.ask("AWS Device Farm device pool ARN")

    # Get available tests
    console.print("[yellow]Loading available tests...[/yellow]")
    tests = get_available_tests()

    test_name = None
    if tests:
        console.print("\n[cyan]Available Tests:[/cyan]\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Test Name", style="yellow")
        table.add_column("Description", style="white")

        for idx, test in enumerate(tests, 1):
            table.add_row(
                str(idx),
                test['name'],
                test.get('description', '')
            )

        console.print(table)
        console.print()

        choice = IntPrompt.ask(
            "Select test number (0 to enter test name manually)",
            default=0
        )

        if choice > 0 and choice <= len(tests):
            test_name = tests[choice - 1]['name']
            console.print(f"\n[green]✓ Selected test:[/green] {test_name}\n")

    if not test_name:
        test_name = Prompt.ask("Test name from benchmark_tests.yml")

    run_name = Prompt.ask("Optional test run name", default="")
    num_iterations = IntPrompt.ask("Number of test iterations")

    console.print("\n[green]Running test...[/green]\n")

    non_interactive_upload_and_test(
        branch=branch,
        commit=commit,
        project_arn=project_arn,
        device_pool_arn=device_pool_arn,
        test_name=test_name,
        run_name=run_name if run_name else None,
        num_iterations=num_iterations
    )


def analyze_interactive():
    """Interactive workflow for analyzing performance test runs."""
    console.print("\n[cyan]Analyze performance test runs[/cyan]\n")

    # Base run selection
    console.print("[yellow]Select BASE run (baseline):[/yellow]")
    base_run = select_cached_test_run("base")

    if base_run:
        base_branch = base_run['branch']
        base_commit = base_run['commit']
        device_pool = base_run['selected_pool']
        test_name = base_run['selected_test']
        console.print(f"\n[green]✓ Base run:[/green] {base_run['name']}")
        console.print(f"  Device Pool: {device_pool}")
        console.print(f"  Test: {test_name}")
    else:
        console.print("\n[yellow]No cached run selected. Enter BASE details manually:[/yellow]\n")
        base_branch = Prompt.ask("Base branch name")
        base_commit = Prompt.ask("Base commit hash")
        device_pool = Prompt.ask("Device pool name")
        test_name = Prompt.ask("Test name")

    # Test run selection
    console.print("\n[yellow]Select TEST run (comparison):[/yellow]")
    test_run = select_cached_test_run("test")

    if test_run:
        test_branch = test_run['branch']
        test_commit = test_run['commit']
        # Use device pool and test from test run if selected
        if test_run['selected_pool']:
            device_pool = test_run['selected_pool']
        if test_run['selected_test']:
            test_name = test_run['selected_test']
        console.print(f"\n[green]✓ Test run:[/green] {test_run['name']}")
        console.print(f"  Device Pool: {device_pool}")
        console.print(f"  Test: {test_name}")
    else:
        console.print("\n[yellow]No cached run selected. Enter TEST details manually:[/yellow]\n")
        test_branch = Prompt.ask("Test branch name")
        test_commit = Prompt.ask("Test commit hash")

    console.print("\n[green]Analyzing...[/green]\n")

    non_interactive_analyze(
        base_branch=base_branch,
        base_commit=base_commit,
        test_branch=test_branch,
        test_commit=test_commit,
        device_pool=device_pool,
        test_name=test_name
    )


def full_pipeline_interactive():
    """Interactive workflow for full pipeline."""
    import platform

    # Check architecture
    host_arch = platform.machine()
    if host_arch not in ["x86_64", "AMD64"]:
        console.print("\n[red]Full Pipeline - x86_64 Only[/red]\n")
        console.print(f"[yellow]The full pipeline only works on x86_64 architecture.[/yellow]")
        console.print(f"[yellow]Current architecture: {host_arch}[/yellow]\n")
        console.print("[yellow]On ARM64 (Apple Silicon), please run the steps separately:[/yellow]")
        console.print("[yellow]  1. Build APK[/yellow]")
        console.print("[yellow]  2. Run tests[/yellow]")
        console.print("[yellow]  3. Analyze results[/yellow]\n")
        Prompt.ask("Press Enter to return to menu")
        return

    console.print("\n[cyan]Full pipeline (build → test → analyze)[/cyan]\n")

    base_branch = Prompt.ask("Base branch name")
    base_commit = Prompt.ask("Base commit hash")
    test_branch = Prompt.ask("Test branch name")
    test_commit = Prompt.ask("Test commit hash")
    project_arn = Prompt.ask("AWS Device Farm project ARN")
    device_pool_arn = Prompt.ask("AWS Device Farm device pool ARN")
    test_name = Prompt.ask("Test name from benchmark_tests.yml")
    flavor = Prompt.ask("Product flavor", default="dev")
    build_type = Prompt.ask("Build type", default="perf")
    run_name = Prompt.ask("Optional test run name", default="")
    num_iterations = IntPrompt.ask("Number of test iterations")

    console.print()
    if not Confirm.ask("Continue with full pipeline?"):
        console.print("[yellow]Cancelled[/yellow]")
        return

    console.print("\n[green]Running full pipeline...[/green]\n")

    non_interactive_full_pipeline(
        base_branch=base_branch,
        base_commit=base_commit,
        test_branch=test_branch,
        test_commit=test_commit,
        project_arn=project_arn,
        device_pool_arn=device_pool_arn,
        test_name=test_name,
        product_flavor=flavor,
        build_type=build_type,
        run_name=run_name if run_name else None,
        num_iterations=num_iterations
    )


# Note: Main menu is now handled by scripts/perftest-interactive (bash)
# Each function above is called directly as a separate command:
#   - build-interactive
#   - test-interactive
#   - analyze-interactive
#   - full-pipeline-interactive
