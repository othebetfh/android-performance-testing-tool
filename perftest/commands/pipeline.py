"""Pipeline command functions for perftest."""

import os
import sys
from pathlib import Path
from typing import Optional

import boto3
from rich.console import Console
from rich.prompt import Prompt

from .utils import (
    get_output_directory,
    get_display_path,
    check_properties_files
)
from .devicefarm import (
    get_projects,
    get_device_pools,
    get_available_tests,
    load_test_execution_config,
    monitor_runs_parallel_with_retry,
    download_artifacts
)
from .test import schedule_test_for_pipeline
from .build import build_apk_for_pipeline

console = Console()


def non_interactive_analyze(
    base_branch: str,
    base_commit: str,
    test_branch: str,
    test_commit: str,
    device_pool: str,
    test_name: str
):
    """
    Analyze command.

    Args:
        base_branch: Base branch name
        base_commit: Base commit hash
        test_branch: Test branch name
        test_commit: Test commit hash
        device_pool: Device pool name
        test_name: Test name
    """
    console.print("\n[bold blue]Analyze performance results[/bold blue]")
    console.print("─" * 50)

    # Get output directory
    output_dir = get_output_directory()

    # Construct base run path
    base_branch_sanitized = base_branch.replace('/', '-').replace('\\', '-')
    base_commit_short = base_commit[:8] if len(base_commit) >= 8 else base_commit
    base_run_name = f"{base_branch_sanitized}_{base_commit_short}"
    base_build_dir = output_dir / base_run_name

    # Construct test run path
    test_branch_sanitized = test_branch.replace('/', '-').replace('\\', '-')
    test_commit_short = test_commit[:8] if len(test_commit) >= 8 else test_commit
    test_run_name = f"{test_branch_sanitized}_{test_commit_short}"
    test_build_dir = output_dir / test_run_name

    console.print(f"\n[bold]Configuration:[/bold]")
    console.print(f"  Base: {base_run_name}")
    console.print(f"  Test: {test_run_name}")
    console.print(f"  Device Pool: {device_pool}")
    console.print(f"  Test: {test_name}")

    # Validate base run exists
    if not base_build_dir.exists():
        console.print(f"\n[red]Error: Base run not found at {base_build_dir}[/red]")
        console.print(f"[yellow]Please run tests for base branch '{base_branch}' and commit '{base_commit}' first[/yellow]")
        sys.exit(1)

    # Validate test run exists
    if not test_build_dir.exists():
        console.print(f"\n[red]Error: Test run not found at {test_build_dir}[/red]")
        console.print(f"[yellow]Please run tests for test branch '{test_branch}' and commit '{test_commit}' first[/yellow]")
        sys.exit(1)

    # Construct trace directory paths
    base_traces_dir = base_build_dir / "traces" / device_pool / test_name
    test_traces_dir = test_build_dir / "traces" / device_pool / test_name

    # Validate base traces exist
    if not base_traces_dir.exists():
        console.print(f"\n[red]Error: Base traces not found at {base_traces_dir}[/red]")
        console.print(f"[yellow]Available device pools/tests:[/yellow]")
        traces_base = base_build_dir / "traces"
        if traces_base.exists():
            for pool in traces_base.iterdir():
                if pool.is_dir():
                    tests = [t.name for t in pool.iterdir() if t.is_dir()]
                    console.print(f"  Pool: {pool.name}, Tests: {', '.join(tests)}")
        sys.exit(1)

    # Validate test traces exist
    if not test_traces_dir.exists():
        console.print(f"\n[red]Error: Test traces not found at {test_traces_dir}[/red]")
        console.print(f"[yellow]Available device pools/tests:[/yellow]")
        traces_base = test_build_dir / "traces"
        if traces_base.exists():
            for pool in traces_base.iterdir():
                if pool.is_dir():
                    tests = [t.name for t in pool.iterdir() if t.is_dir()]
                    console.print(f"  Pool: {pool.name}, Tests: {', '.join(tests)}")
        sys.exit(1)

    # Check for trace files (use rglob to find traces in run ARN subdirectories)
    base_trace_files = list(base_traces_dir.rglob("*.perfetto-trace"))
    test_trace_files = list(test_traces_dir.rglob("*.perfetto-trace"))

    if not base_trace_files:
        console.print(f"\n[red]Error: No trace files found in {base_traces_dir}[/red]")
        sys.exit(1)

    if not test_trace_files:
        console.print(f"\n[red]Error: No trace files found in {test_traces_dir}[/red]")
        sys.exit(1)

    console.print(f"\n[bold]Trace files:[/bold]")
    console.print(f"  Base: {len(base_trace_files)} trace(s)")
    console.print(f"  Test: {len(test_trace_files)} trace(s)")

    # Generate comparison notebook
    console.print(f"\n[bold]Generating comparison notebooks...[/bold]")

    if test_name == "coldStartup":
        from perftest.analysis.coldstartup import create_batch_aware_analysis

        analysis_dir = get_output_directory() / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)

        report_path = create_batch_aware_analysis(
            base_traces_dir,
            test_traces_dir,
            device_pool,
            test_name,
            analysis_dir
        )
    else:
        console.print(f"[red]Error: No notebook generator available for test type '{test_name}'[/red]")
        console.print(f"[yellow]Currently only 'coldStartup' is supported[/yellow]")
        sys.exit(1)

    console.print(f"\n[bold green]Analysis completed successfully![/bold green]")
    console.print(f"\n[bold]Combined Analysis Report:[/bold]")
    console.print(f"  {get_display_path(report_path)}")


def non_interactive_upload_and_test(
    branch: str,
    commit: str,
    project_arn: str,
    device_pool_arn: str,
    test_name: str,
    run_name: Optional[str] = None,
    num_iterations: int = 150
):
    """
    Upload and test command.

    Args:
        branch: Git branch name
        commit: Git commit hash
        project_arn: AWS Device Farm project ARN
        device_pool_arn: AWS Device Farm device pool ARN
        test_name: Test name from benchmark_tests.yml
        run_name: Optional test run name
        num_iterations: Number of test iterations (default: 150)
    """
    from datetime import datetime
    from .devicefarm import upload_apk, schedule_test_run, monitor_runs_parallel_with_retry
    import math

    console.print("\n[bold blue]Upload and run test[/bold blue]")
    console.print("─" * 50)

    # Construct build directory path
    branch_sanitized = branch.replace('/', '-').replace('\\', '-')
    commit_short = commit[:8] if len(commit) >= 8 else commit
    build_output_dir = Path(f"/workspace/output/{branch_sanitized}_{commit_short}")

    # Check if build exists
    if not build_output_dir.exists():
        console.print(f"[red]Error: Build not found at {build_output_dir}[/red]")
        console.print(f"[yellow]Please run build-apk first for branch '{branch}' and commit '{commit}'[/yellow]")
        sys.exit(1)

    # Find APK files
    apk_dir = build_output_dir / "apks"
    if not apk_dir.exists():
        console.print(f"[red]Error: APKs directory not found at {apk_dir}[/red]")
        sys.exit(1)

    apk_files = list(apk_dir.glob("*.apk"))
    app_apks = [f for f in apk_files if f.name.startswith("app-")]
    test_apks = [f for f in apk_files if not f.name.startswith("app-")]

    if not app_apks:
        console.print(f"[red]Error: App APK not found in {apk_dir}[/red]")
        sys.exit(1)

    if not test_apks:
        console.print(f"[red]Error: Test APK not found in {apk_dir}[/red]")
        sys.exit(1)

    app_apk_path = app_apks[0]
    test_apk_path = test_apks[0]

    console.print(f"\n[bold]Configuration:[/bold]")
    console.print(f"  Build: {build_output_dir.name}")
    console.print(f"  App APK: {app_apk_path.name}")
    console.print(f"  Test APK: {test_apk_path.name}")
    console.print(f"  Project ARN: {project_arn}")
    console.print(f"  Device Pool ARN: {device_pool_arn}")
    console.print(f"  Test: {test_name}")
    if run_name:
        console.print(f"  Run Name: {run_name}")

    # Load and validate test
    available_tests = get_available_tests()
    selected_test = None
    for test in available_tests:
        if test['name'] == test_name:
            selected_test = test
            break

    if not selected_test:
        console.print(f"\n[red]Error: Test '{test_name}' not found in benchmark_tests.yml[/red]")
        console.print(f"[yellow]Available tests: {', '.join([t['name'] for t in available_tests])}[/yellow]")
        sys.exit(1)

    # Get device pool name from ARN
    try:
        session_kwargs = {
            'aws_access_key_id': os.environ.get('AWS_ACCESS_KEY_ID'),
            'aws_secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
            'region_name': os.environ.get('AWS_DEFAULT_REGION', 'us-west-2')
        }
        session_token = os.environ.get('AWS_SESSION_TOKEN')
        if session_token:
            session_kwargs['aws_session_token'] = session_token

        session = boto3.Session(**session_kwargs)
        devicefarm = session.client('devicefarm')
        pool_response = devicefarm.get_device_pool(arn=device_pool_arn)
        device_pool = pool_response['devicePool']['name']
    except Exception as e:
        console.print(f"[yellow]Warning: Could not fetch device pool name: {e}[/yellow]")
        console.print("[yellow]Using pool ID from ARN instead[/yellow]")
        device_pool = device_pool_arn.split('/')[-1] if '/' in device_pool_arn else device_pool_arn

    # Load test execution config
    exec_config = load_test_execution_config()
    batch_size = exec_config['batch_size']
    max_retries = exec_config['max_retries']

    # Calculate batches
    num_batches = math.ceil(num_iterations / batch_size)
    batches = []
    for i in range(num_batches):
        batch_iterations = min(batch_size, num_iterations - i * batch_size)
        batches.append(batch_iterations)

    if num_batches > 1:
        console.print(f"\n[bold]Batching:[/bold] {num_iterations} iterations split into {num_batches} runs")
        for i, batch_iters in enumerate(batches, 1):
            console.print(f"  Run {i}: {batch_iters} iterations")

    # Upload APKs once (reused for all batches)
    console.print(f"\n[bold]Uploading APKs...[/bold]")

    console.print("\n[bold]Uploading app APK...[/bold]")
    app_arn = upload_apk(project_arn, str(app_apk_path), 'ANDROID_APP')
    if not app_arn:
        console.print("[red]Failed to upload app APK[/red]")
        sys.exit(1)

    console.print("\n[bold]Uploading test APK...[/bold]")
    test_package_arn = upload_apk(project_arn, str(test_apk_path), 'INSTRUMENTATION_TEST_PACKAGE')
    if not test_package_arn:
        console.print("[red]Failed to upload test APK[/red]")
        sys.exit(1)

    # Schedule test runs for all batches
    test_selector = f"-e class {selected_test['full_name']}"
    template_path = Path("/workspace/config/custom_test_spec.yml.template")

    if not template_path.exists():
        console.print(f"[red]Test spec template not found: {template_path}[/red]")
        sys.exit(1)

    with open(template_path, 'r') as f:
        template_content = f.read()

    # Prepare test specs and schedule all batches in parallel
    console.print(f"\n[bold]Preparing and scheduling {num_batches} test batch(es) in parallel...[/bold]")

    traces_dir = build_output_dir / "traces" / device_pool / test_name
    traces_dir.mkdir(parents=True, exist_ok=True)

    # Generate base run name
    if not run_name:
        base_name = f"Performance Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    else:
        base_name = run_name

    # Prepare test specs for all batches
    test_spec_arns = []
    run_names = []

    for batch_idx, batch_iterations in enumerate(batches, 1):
        # Generate test spec for this batch
        spec_contents = template_content.replace("{{TEST_SELECTOR}}", test_selector)
        spec_contents = spec_contents.replace("{{NUM_ITERATIONS}}", str(batch_iterations))
        test_spec_path = Path(f"/tmp/{branch_sanitized}_{commit_short}_{test_name}_batch{batch_idx}_testspec.yml")

        with open(test_spec_path, 'w') as f:
            f.write(spec_contents)

        # Upload test spec for this batch
        console.print(f"  Uploading test spec for batch {batch_idx}/{num_batches}...")
        test_spec_arn = upload_apk(project_arn, str(test_spec_path), 'INSTRUMENTATION_TEST_SPEC')
        if not test_spec_arn:
            console.print(f"[red]Failed to upload test spec for batch {batch_idx}[/red]")
            test_spec_path.unlink(missing_ok=True)
            sys.exit(1)

        test_spec_arns.append(test_spec_arn)

        # Generate run name
        if num_batches > 1:
            batch_run_name = f"{base_name} [{batch_idx} / {num_batches}]"
        else:
            batch_run_name = base_name
        run_names.append(batch_run_name)

        # Clean up temp test spec file
        test_spec_path.unlink(missing_ok=True)

    # Schedule all test runs in parallel
    console.print(f"\n[bold]Scheduling all {num_batches} batch(es)...[/bold]")
    initial_run_arns = []

    for batch_idx in range(num_batches):
        console.print(f"  Scheduling batch {batch_idx + 1}/{num_batches}...")
        run_arn = schedule_test_run(
            project_arn=project_arn,
            device_pool_arn=device_pool_arn,
            app_arn=app_arn,
            test_package_arn=test_package_arn,
            test_spec_arn=test_spec_arns[batch_idx],
            test_class=selected_test['full_name'],
            run_name=run_names[batch_idx]
        )

        if not run_arn:
            console.print(f"[red]Failed to schedule batch {batch_idx + 1}[/red]")
            sys.exit(1)

        initial_run_arns.append(run_arn)
        console.print(f"  [green]✓[/green] Batch {batch_idx + 1} scheduled: {run_arn}")

    # Monitor all runs in parallel with automatic retry
    console.print(f"\n[bold cyan]Monitoring all {num_batches} batch(es) in parallel...[/bold cyan]")
    success, all_downloaded_traces = monitor_runs_parallel_with_retry(
        project_arn=project_arn,
        device_pool_arn=device_pool_arn,
        app_arn=app_arn,
        test_package_arn=test_package_arn,
        test_spec_arns=test_spec_arns,
        test_class=selected_test['full_name'],
        run_names=run_names,
        initial_run_arns=initial_run_arns,
        output_dir=traces_dir,
        max_retries=max_retries
    )

    if not success:
        console.print("\n[red]Test execution failed[/red]")
        sys.exit(1)

    if all_downloaded_traces:
        console.print(f"\n[bold green]All tests completed successfully![/bold green]")
        console.print(f"\n[bold]Traces saved to:[/bold]")
        console.print(f"  {get_display_path(traces_dir)}")
        console.print(f"  {len(all_downloaded_traces)} trace(s) downloaded from {num_batches} run(s)")
    else:
        console.print("\n[yellow]Tests completed but no traces were downloaded[/yellow]")


def non_interactive_build(
    branch: str,
    commit: str,
    product_flavor: str = "dev",
    build_type: str = "perf"
):
    """
    Build command.

    Args:
        branch: Git branch name
        commit: Git commit hash
        product_flavor: Product flavor (default: "dev")
        build_type: Build type (default: "perf")
    """
    console.print("\n[bold blue]Building APK from source[/bold blue]")
    console.print("─" * 50)

    # Get credentials from environment variables only
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        console.print("[red]Error: GITHUB_TOKEN environment variable not set[/red]")
        sys.exit(1)

    github_user = os.getenv("GITHUB_USER")
    if not github_user:
        console.print("[red]Error: GITHUB_USER environment variable not set[/red]")
        sys.exit(1)

    console.print(f"\n[bold]Build configuration:[/bold]")
    console.print(f"  Branch: {branch}")
    console.print(f"  Commit: {commit}")
    console.print(f"  Product flavor: {product_flavor}")
    console.print(f"  Build type: {build_type}")

    # Check properties files
    if not check_properties_files(product_flavor):
        sys.exit(1)

    # Build the APK
    output_dir = build_apk_for_pipeline(
        branch=branch,
        commit=commit,
        github_token=github_token,
        product_flavor=product_flavor,
        build_type=build_type
    )

    if not output_dir:
        console.print("\n[red]Build failed[/red]")
        sys.exit(1)

    # Display APK locations
    apk_dir = output_dir / "apks"
    if apk_dir.exists():
        apk_files = list(apk_dir.glob("*.apk"))
        if apk_files:
            console.print("\n[bold green]Build completed successfully![/bold green]")
            console.print(f"\n[bold]APK locations:[/bold]")
            for apk in apk_files:
                apk_type = "App" if apk.name.startswith("app-") else "Test"
                size_mb = apk.stat().st_size / (1024 * 1024)
                console.print(f"  {apk_type:5}: {get_display_path(apk)} ({size_mb:.1f} MB)")
    else:
        console.print("\n[yellow]Build completed but APKs not found[/yellow]")


def non_interactive_full_pipeline(
    base_branch: str,
    base_commit: str,
    test_branch: str,
    test_commit: str,
    project_arn: str,
    device_pool_arn: str,
    test_name: str,
    product_flavor: str = "dev",
    build_type: str = "perf",
    run_name: Optional[str] = None,
    num_iterations: int = 150
):
    """
    Full pipeline command.

    Args:
        base_branch: Base branch name
        base_commit: Base commit hash
        test_branch: Test branch name
        test_commit: Test commit hash
        project_arn: AWS Device Farm project ARN
        device_pool_arn: AWS Device Farm device pool ARN
        test_name: Test name from benchmark_tests.yml
        product_flavor: Product flavor (default: dev)
        build_type: Build type (default: perf)
        run_name: Optional test run name
        num_iterations: Number of test iterations (default: 150)
    """
    console.print("\n[bold blue]Full pipeline[/bold blue]")
    console.print("─" * 50)

    console.print(f"\n[bold]Configuration:[/bold]")
    console.print(f"  Base: {base_branch} @ {base_commit[:8]}")
    console.print(f"  Test: {test_branch} @ {test_commit[:8]}")
    console.print(f"  Product Flavor: {product_flavor}")
    console.print(f"  Build Type: {build_type}")
    console.print(f"  Test: {test_name}")

    # Step 1: Build base version
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]Step 1/5: Building BASE version[/bold cyan]")
    console.print("=" * 60)

    try:
        non_interactive_build(
            branch=base_branch,
            commit=base_commit,
            product_flavor=product_flavor,
            build_type=build_type
        )
    except SystemExit as e:
        console.print("[red]Base build failed[/red]")
        sys.exit(1)

    # Step 2: Build test version
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]Step 2/5: Building TEST version[/bold cyan]")
    console.print("=" * 60)

    try:
        non_interactive_build(
            branch=test_branch,
            commit=test_commit,
            product_flavor=product_flavor,
            build_type=build_type
        )
    except SystemExit as e:
        console.print("[red]Test build failed[/red]")
        sys.exit(1)

    # Step 3: Upload and test base version
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]Step 3/5: Testing BASE version[/bold cyan]")
    console.print("=" * 60)

    try:
        non_interactive_upload_and_test(
            branch=base_branch,
            commit=base_commit,
            project_arn=project_arn,
            device_pool_arn=device_pool_arn,
            test_name=test_name,
            run_name=run_name,
            num_iterations=num_iterations
        )
    except SystemExit as e:
        console.print("[red]Base test failed[/red]")
        sys.exit(1)

    # Step 4: Upload and test test version
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]Step 4/5: Testing TEST version[/bold cyan]")
    console.print("=" * 60)

    try:
        non_interactive_upload_and_test(
            branch=test_branch,
            commit=test_commit,
            project_arn=project_arn,
            device_pool_arn=device_pool_arn,
            test_name=test_name,
            run_name=run_name,
            num_iterations=num_iterations
        )
    except SystemExit as e:
        console.print("[red]Test test failed[/red]")
        sys.exit(1)

    # Step 5: Generate comparison analysis
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]Step 5/5: Generating comparison analysis[/bold cyan]")
    console.print("=" * 60)

    # Get device pool name from ARN for analysis
    # ARN format: arn:aws:devicefarm:region:account:devicepool:project-id/pool-id
    # We need to fetch the device pool name from Device Farm
    try:
        devicefarm = boto3.client('devicefarm', region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-west-2'))
        pool_response = devicefarm.get_device_pool(arn=device_pool_arn)
        device_pool_name = pool_response['devicePool']['name']
    except Exception as e:
        console.print(f"[yellow]Warning: Could not fetch device pool name: {e}[/yellow]")
        console.print("[yellow]Using 'Unknown Pool' for analysis[/yellow]")
        device_pool_name = "Unknown Pool"

    try:
        non_interactive_analyze(
            base_branch=base_branch,
            base_commit=base_commit,
            test_branch=test_branch,
            test_commit=test_commit,
            device_pool=device_pool_name,
            test_name=test_name
        )
    except SystemExit as e:
        console.print("[red]Analysis failed[/red]")
        sys.exit(1)

    console.print("\n[bold green]Full pipeline completed successfully![/bold green]")
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  ✓ Built base version: {base_branch} @ {base_commit[:8]}")
    console.print(f"  ✓ Built test version: {test_branch} @ {test_commit[:8]}")
    console.print(f"  ✓ Tested both versions on Device Farm")
    console.print(f"  ✓ Generated comparison notebook")
