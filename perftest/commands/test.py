"""Test command functions for perftest."""

import math
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Prompt

from .utils import (
    find_available_builds,
    detect_apk_pairs
)
from .devicefarm import (
    get_projects,
    get_device_pools,
    get_available_tests,
    upload_apk,
    schedule_test_run,
    monitor_runs_parallel_with_retry,
    load_test_execution_config
)

console = Console()


def schedule_test_for_pipeline(
    branch: str,
    commit: str,
    project_arn: str,
    device_pool_arn: str,
    test_name: str,
    num_iterations: int = 150
) -> Optional[dict]:
    """
    Helper function to schedule test run(s) without monitoring (for parallel execution).
    Supports batching for iterations > 50.

    Args:
        branch: Git branch name
        commit: Git commit hash
        project_arn: AWS Device Farm project ARN
        device_pool_arn: AWS Device Farm device pool ARN
        test_name: Test name from benchmark_tests.yml
        num_iterations: Number of test iterations (default: 150)

    Returns:
        Dictionary with scheduling info if successful, None otherwise:
        {
            'run_arns': List[str],
            'app_arn': str,
            'test_package_arn': str,
            'test_spec_arns': List[str],
            'test_class': str,
            'run_names': List[str]
        }
    """
    # Construct build directory path
    branch_sanitized = branch.replace('/', '-').replace('\\', '-')
    commit_short = commit[:8] if len(commit) >= 8 else commit
    build_output_dir = Path(f"/workspace/output/{branch_sanitized}_{commit_short}")

    # Find APK files
    apk_dir = build_output_dir / "apks"
    if not apk_dir.exists():
        console.print(f"[red]Error: APKs directory not found at {apk_dir}[/red]")
        return None

    apk_files = list(apk_dir.glob("*.apk"))
    app_apks = [f for f in apk_files if f.name.startswith("app-")]
    test_apks = [f for f in apk_files if not f.name.startswith("app-")]

    if not app_apks or not test_apks:
        console.print(f"[red]Error: APKs not found in {apk_dir}[/red]")
        return None

    app_apk_path = app_apks[0]
    test_apk_path = test_apks[0]

    # Load and validate test
    available_tests = get_available_tests()
    selected_test = None
    for test in available_tests:
        if test['name'] == test_name:
            selected_test = test
            break

    if not selected_test:
        console.print(f"[red]Error: Test '{test_name}' not found[/red]")
        return None

    # Load test execution config
    exec_config = load_test_execution_config()
    batch_size = exec_config['batch_size']

    # Calculate batches
    num_batches = math.ceil(num_iterations / batch_size)
    batches = []
    for i in range(num_batches):
        batch_iterations = min(batch_size, num_iterations - i * batch_size)
        batches.append(batch_iterations)

    if num_batches > 1:
        console.print(f"  Batching: {num_iterations} iterations → {num_batches} runs")

    # Upload APKs once (reused for all batches)
    console.print(f"  Uploading app APK ({app_apk_path.name})...")
    app_arn = upload_apk(project_arn, str(app_apk_path), 'ANDROID_APP')
    if not app_arn:
        console.print("[red]Failed to upload app APK[/red]")
        return None

    console.print(f"  Uploading test APK ({test_apk_path.name})...")
    test_package_arn = upload_apk(project_arn, str(test_apk_path), 'INSTRUMENTATION_TEST_PACKAGE')
    if not test_package_arn:
        console.print("[red]Failed to upload test APK[/red]")
        return None

    # Schedule test runs for all batches
    test_selector = f"-e class {selected_test['full_name']}"
    template_path = Path("/workspace/config/custom_test_spec.yml.template")

    if not template_path.exists():
        console.print(f"[red]Test spec template not found[/red]")
        return None

    with open(template_path, 'r') as f:
        template_content = f.read()

    run_arns = []
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
        test_spec_arn = upload_apk(project_arn, str(test_spec_path), 'INSTRUMENTATION_TEST_SPEC')
        if not test_spec_arn:
            console.print(f"[red]Failed to upload test spec for batch {batch_idx}[/red]")
            test_spec_path.unlink(missing_ok=True)
            return None

        # Clean up temp test spec file
        test_spec_path.unlink(missing_ok=True)

        # Schedule test run (without monitoring)
        if num_batches > 1:
            batch_run_name = f"{branch_sanitized}_{commit_short} [{batch_idx} / {num_batches}]"
        else:
            batch_run_name = f"{branch_sanitized}_{commit_short}"
        run_arn = schedule_test_run(
            project_arn=project_arn,
            device_pool_arn=device_pool_arn,
            app_arn=app_arn,
            test_package_arn=test_package_arn,
            test_spec_arn=test_spec_arn,
            test_class=selected_test['full_name'],
            run_name=batch_run_name
        )

        if not run_arn:
            console.print(f"[red]Failed to schedule run for batch {batch_idx}[/red]")
            return None

        run_arns.append(run_arn)
        test_spec_arns.append(test_spec_arn)
        run_names.append(batch_run_name)

    if num_batches > 1:
        console.print(f"  [green]✓[/green] Scheduled {num_batches} runs for {branch_sanitized}_{commit_short}")
    else:
        console.print(f"  [green]✓[/green] Scheduled: {branch_sanitized}_{commit_short}")

    return {
        'run_arns': run_arns,
        'app_arn': app_arn,
        'test_package_arn': test_package_arn,
        'test_spec_arns': test_spec_arns,
        'test_class': selected_test['full_name'],
        'run_names': run_names
    }
