"""Analyze command functions for perftest."""

from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

from .utils import find_available_test_runs, get_output_directory, get_display_path

console = Console()


def analyze_command():
    """Interactive analyze command."""
    console.print("\n[bold blue]Analyze performance test runs[/bold blue]")
    console.print("─" * 50)

    # Find available test runs
    test_runs = find_available_test_runs()

    if not test_runs:
        console.print("\n[yellow]No test runs with traces found in output directory[/yellow]")
        return

    # Select base run
    console.print("\n[bold]Available test runs:[/bold]")
    for idx, run in enumerate(test_runs, 1):
        pools_str = ", ".join(run['device_pools'].keys())
        console.print(f"  {idx}) {run['name']} (device pools: {pools_str})")

    while True:
        base_choice = Prompt.ask("\nSelect base run")
        try:
            base_idx = int(base_choice) - 1
            if 0 <= base_idx < len(test_runs):
                break
            console.print(f"[red]Please enter a number between 1 and {len(test_runs)}[/red]")
        except ValueError:
            console.print("[red]Please enter a valid number[/red]")

    base_run = test_runs[base_idx]
    console.print(f"\n[green]✓[/green] Selected base run: {base_run['name']}")

    # Select test run
    console.print("\n[bold]Select test run to compare:[/bold]")
    for idx, run in enumerate(test_runs, 1):
        pools_str = ", ".join(run['device_pools'].keys())
        console.print(f"  {idx}) {run['name']} (device pools: {pools_str})")

    while True:
        test_choice = Prompt.ask("\nSelect test run")
        try:
            test_idx = int(test_choice) - 1
            if 0 <= test_idx < len(test_runs):
                break
            console.print(f"[red]Please enter a number between 1 and {len(test_runs)}[/red]")
        except ValueError:
            console.print("[red]Please enter a valid number[/red]")

    test_run = test_runs[test_idx]
    console.print(f"\n[green]✓[/green] Selected test run: {test_run['name']}")

    # Find common device pools between base and test runs
    common_pools = sorted(set(base_run['device_pools'].keys()) & set(test_run['device_pools'].keys()))

    if not common_pools:
        console.print("\n[yellow]No common device pools found between the selected runs[/yellow]")
        return

    # Select device pool
    console.print("\n[bold]Device pools available in both runs:[/bold]")
    for idx, pool_name in enumerate(common_pools, 1):
        base_tests = ", ".join(base_run['device_pools'][pool_name])
        test_tests = ", ".join(test_run['device_pools'][pool_name])
        console.print(f"  {idx}) {pool_name}")
        console.print(f"      Base tests: {base_tests}")
        console.print(f"      Test tests: {test_tests}")

    selected_pool = None
    if len(common_pools) == 1:
        # Auto-select if only one pool
        selected_pool = common_pools[0]
        console.print(f"\n[green]✓[/green] Auto-selected device pool: {selected_pool}")
    else:
        # Let user choose
        while True:
            pool_choice = Prompt.ask("\nSelect device pool")
            try:
                pool_idx = int(pool_choice) - 1
                if 0 <= pool_idx < len(common_pools):
                    break
                console.print(f"[red]Please enter a number between 1 and {len(common_pools)}[/red]")
            except ValueError:
                console.print("[red]Please enter a valid number[/red]")

        selected_pool = common_pools[pool_idx]
        console.print(f"\n[green]✓[/green] Selected device pool: {selected_pool}")

    # Find common tests within selected device pool
    base_tests_in_pool = set(base_run['device_pools'][selected_pool])
    test_tests_in_pool = set(test_run['device_pools'][selected_pool])
    common_tests = sorted(base_tests_in_pool & test_tests_in_pool)

    if not common_tests:
        console.print(f"\n[yellow]No comparable tests found in device pool '{selected_pool}'[/yellow]")
        return

    # Select test to compare
    console.print(f"\n[bold]Tests available in both runs (device pool: {selected_pool}):[/bold]")
    for idx, test_name in enumerate(common_tests, 1):
        console.print(f"  {idx}) {test_name}")

    while True:
        test_choice = Prompt.ask("\nSelect test to compare")
        try:
            test_idx = int(test_choice) - 1
            if 0 <= test_idx < len(common_tests):
                break
            console.print(f"[red]Please enter a number between 1 and {len(common_tests)}[/red]")
        except ValueError:
            console.print("[red]Please enter a valid number[/red]")

    selected_test = common_tests[test_idx]
    console.print(f"\n[green]✓[/green] Selected test: {selected_test}")

    # Generate comparison notebook
    base_traces_dir = base_run['path'] / "traces" / selected_pool / selected_test
    test_traces_dir = test_run['path'] / "traces" / selected_pool / selected_test

    console.print("\n[bold]Generating comparison notebook...[/bold]")

    # Select appropriate notebook generator based on test type
    if selected_test == "coldStartup":
        from perftest.analysis.coldstartup import create_batch_aware_analysis

        analysis_dir = get_output_directory() / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)

        report_path = create_batch_aware_analysis(
            base_traces_dir,
            test_traces_dir,
            selected_pool,
            selected_test,
            analysis_dir
        )
    else:
        console.print(f"[red]Error: No notebook generator available for test type '{selected_test}'[/red]")
        console.print("[yellow]Currently only 'coldStartup' is supported[/yellow]")
        return

    console.print(f"\n[green]✓[/green] Analysis report generated successfully!")
    console.print(f"\n[bold]Combined Analysis Report:[/bold]")
    console.print(f"  {get_display_path(report_path)}")
