"""AWS Device Farm functions for perftest."""

import os
import time
from pathlib import Path
from typing import Optional, List, Tuple

import boto3
import requests
import yaml
from rich.console import Console

console = Console()


def create_devicefarm_client():
    """Create AWS Device Farm client with credentials from environment."""
    access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    session_token = os.environ.get('AWS_SESSION_TOKEN')

    session_kwargs = {
        'aws_access_key_id': access_key,
        'aws_secret_access_key': secret_key,
        'region_name': 'us-west-2'
    }
    if session_token:
        session_kwargs['aws_session_token'] = session_token

    session = boto3.Session(**session_kwargs)
    return session.client('devicefarm')


def get_projects() -> list[dict]:
    """
    Get list of projects from AWS Device Farm.

    Returns:
        List of projects with 'name' and 'arn' keys
    """
    try:
        client = create_devicefarm_client()

        # List all projects
        response = client.list_projects()

        projects = []
        for project in response.get('projects', []):
            projects.append({
                'name': project['name'],
                'arn': project['arn']
            })

        # Sort by name
        projects.sort(key=lambda p: p['name'])

        return projects
    except Exception as e:
        console.print(f"[yellow]Warning: Could not fetch projects: {e}[/yellow]")
        # Show more details for authentication errors
        if 'UnrecognizedClientException' in str(e) or 'security token' in str(e).lower():
            console.print("[yellow]Hint: This usually means invalid AWS credentials or insufficient permissions[/yellow]")
            console.print("[yellow]Required permissions: devicefarm:ListProjects[/yellow]")
        return []


def get_device_pools(project_arn: str) -> list[dict]:
    """
    Get list of device pools from AWS Device Farm.

    Args:
        project_arn: AWS Device Farm project ARN

    Returns:
        List of device pools with 'name' and 'arn' keys
    """
    try:
        session_kwargs = {
            'aws_access_key_id': os.environ.get('AWS_ACCESS_KEY_ID'),
            'aws_secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
            'region_name': 'us-west-2'
        }
        session_token = os.environ.get('AWS_SESSION_TOKEN')
        if session_token:
            session_kwargs['aws_session_token'] = session_token

        session = boto3.Session(**session_kwargs)
        client = session.client('devicefarm')

        # List all device pools for the project
        response = client.list_device_pools(arn=project_arn)

        device_pools = []
        for pool in response.get('devicePools', []):
            device_pools.append({
                'name': pool['name'],
                'arn': pool['arn'],
                'type': pool.get('type', 'PRIVATE')
            })

        # Sort by name
        device_pools.sort(key=lambda p: p['name'])

        return device_pools
    except Exception as e:
        console.print(f"[yellow]Warning: Could not fetch device pools: {e}[/yellow]")
        return []


def upload_apk(project_arn: str, apk_path: str, upload_type: str = 'ANDROID_APP') -> Optional[str]:
    """
    Upload APK file to AWS Device Farm.

    Args:
        project_arn: AWS Device Farm project ARN
        apk_path: Path to APK file
        upload_type: Type of upload (ANDROID_APP or INSTRUMENTATION_TEST_PACKAGE)

    Returns:
        Upload ARN if successful, None otherwise
    """
    try:
        session_kwargs = {
            'aws_access_key_id': os.environ.get('AWS_ACCESS_KEY_ID'),
            'aws_secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
            'region_name': 'us-west-2'
        }
        session_token = os.environ.get('AWS_SESSION_TOKEN')
        if session_token:
            session_kwargs['aws_session_token'] = session_token

        session = boto3.Session(**session_kwargs)
        client = session.client('devicefarm')
        apk_file = Path(apk_path)

        # Create upload
        console.print(f"  Creating upload request for {apk_file.name}...")
        create_response = client.create_upload(
            projectArn=project_arn,
            name=apk_file.name,
            type=upload_type
        )

        upload_arn = create_response['upload']['arn']
        presigned_url = create_response['upload']['url']

        # Upload file to presigned URL
        console.print(f"  Uploading {apk_file.name}...")
        with open(apk_path, 'rb') as f:
            response = requests.put(presigned_url, data=f, headers={'Content-Type': 'application/octet-stream'})
            response.raise_for_status()

        console.print(f"  Waiting for upload to be processed...")
        # Wait for upload to be processed
        max_wait = 300  # 5 minutes
        start_time = time.time()
        while time.time() - start_time < max_wait:
            get_response = client.get_upload(arn=upload_arn)
            status = get_response['upload']['status']

            if status == 'SUCCEEDED':
                console.print(f"  [green]✓[/green] Upload completed: {apk_file.name}")
                return upload_arn
            elif status == 'FAILED':
                error_msg = get_response['upload'].get('metadata', 'Unknown error')
                console.print(f"  [red]✗[/red] Upload failed: {error_msg}")
                return None

            time.sleep(2)

        console.print(f"  [yellow]⚠[/yellow] Upload timed out after {max_wait}s")
        return None

    except Exception as e:
        console.print(f"[red]Error uploading APK: {e}[/red]")
        return None


def load_test_execution_config() -> dict:
    """
    Load test execution configuration from default.yaml.

    Returns:
        Dictionary with 'max_retries' and 'batch_size' keys
    """
    config_path = Path("/workspace/config/default.yaml")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    test_exec_config = config['test_execution']
    return {
        'max_retries': test_exec_config['max_retries'],
        'batch_size': test_exec_config['batch_size']
    }


def get_available_tests() -> list[dict]:
    """
    Get list of available benchmark tests from config.

    Returns:
        List of tests with 'class', 'name', 'full_name', and 'description' keys
    """
    tests_config_path = Path("/workspace/config/benchmark_tests.yml")

    if not tests_config_path.exists():
        console.print(f"[yellow]Warning: Tests config not found at {tests_config_path}[/yellow]")
        return []

    try:
        with open(tests_config_path, 'r') as f:
            config = yaml.safe_load(f)

        tests = []
        for test_class in config.get('test_classes', []):
            class_name = test_class['class']
            for test in test_class.get('tests', []):
                tests.append({
                    'class': class_name,
                    'name': test['name'],
                    'full_name': f"{class_name}#{test['name']}",
                    'description': test.get('description', '')
                })

        return tests
    except Exception as e:
        console.print(f"[yellow]Warning: Could not read tests config: {e}[/yellow]")
        return []


def schedule_test_run(
    project_arn: str,
    device_pool_arn: str,
    app_arn: str,
    test_package_arn: str,
    test_spec_arn: str,
    test_class: str,
    run_name: Optional[str] = None
) -> Optional[str]:
    """
    Schedule a test run on AWS Device Farm.

    Args:
        project_arn: Project ARN
        device_pool_arn: Device pool ARN
        app_arn: Uploaded app APK ARN
        test_package_arn: Uploaded test APK ARN
        test_spec_arn: Uploaded test spec ARN
        test_class: Test class to run (e.g., com.worldcoin.benchmark.PerformanceBenchmark#coldStartup)
        run_name: Optional name for the test run

    Returns:
        Test run ARN if successful, None otherwise
    """
    try:
        session_kwargs = {
            'aws_access_key_id': os.environ.get('AWS_ACCESS_KEY_ID'),
            'aws_secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
            'region_name': 'us-west-2'
        }
        session_token = os.environ.get('AWS_SESSION_TOKEN')
        if session_token:
            session_kwargs['aws_session_token'] = session_token

        session = boto3.Session(**session_kwargs)
        client = session.client('devicefarm')

        # Generate run name if not provided
        if not run_name:
            from datetime import datetime
            run_name = f"Performance Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        console.print(f"  Scheduling test run: {run_name}")

        # Build test configuration
        test_config = {
            'type': 'INSTRUMENTATION',
            'testPackageArn': test_package_arn,
            'parameters': {
                'TEST_CLASS': test_class
            }
        }
        # Only add testSpecArn if provided
        if test_spec_arn:
            test_config['testSpecArn'] = test_spec_arn

        # Schedule the run
        response = client.schedule_run(
            projectArn=project_arn,
            appArn=app_arn,
            devicePoolArn=device_pool_arn,
            name=run_name,
            test=test_config,
            configuration={
                'locale': 'en_US',
                'location': {
                    'latitude': 37.7749,
                    'longitude': -122.4194
                },
                'radios': {
                    'wifi': True,
                    'bluetooth': False,
                    'nfc': False,
                    'gps': True
                }
            },
            executionConfiguration={
                'jobTimeoutMinutes': 60,
                'accountsCleanup': True,
                'appPackagesCleanup': True
            }
        )

        run_arn = response['run']['arn']
        run_status = response['run']['status']

        console.print(f"  [green]✓[/green] Test run scheduled")
        console.print(f"  Run ARN: {run_arn}")
        console.print(f"  Status: {run_status}")

        return run_arn

    except Exception as e:
        console.print(f"[red]Error scheduling test run: {e}[/red]")
        return None


def monitor_test_run(run_arn: str) -> dict:
    """
    Monitor a test run until completion.

    Args:
        run_arn: Test run ARN to monitor

    Returns:
        Final run details
    """
    try:
        session_kwargs = {
            'aws_access_key_id': os.environ.get('AWS_ACCESS_KEY_ID'),
            'aws_secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
            'region_name': 'us-west-2'
        }
        session_token = os.environ.get('AWS_SESSION_TOKEN')
        if session_token:
            session_kwargs['aws_session_token'] = session_token

        session = boto3.Session(**session_kwargs)
        client = session.client('devicefarm')

        console.print("\n[bold]Monitoring test run...[/bold]")
        console.print("This may take several minutes. Press Ctrl+C to stop monitoring (test will continue running)\n")

        last_status = None
        start_time = time.time()

        while True:
            try:
                response = client.get_run(arn=run_arn)
                run = response['run']

                status = run['status']
                result = run.get('result', 'N/A')

                # Show status update if changed
                if status != last_status:
                    elapsed = int(time.time() - start_time)
                    console.print(f"[{elapsed}s] Status: {status}")
                    last_status = status

                # Check if run is complete
                if status in ['COMPLETED', 'STOPPED']:
                    console.print(f"\n[bold]Test run finished![/bold]")
                    console.print(f"  Final status: {status}")
                    console.print(f"  Result: {result}")

                    # Show counters
                    counters = run.get('counters', {})
                    if counters:
                        console.print(f"\n[bold]Test Results:[/bold]")
                        console.print(f"  Total: {counters.get('total', 0)}")
                        console.print(f"  Passed: [green]{counters.get('passed', 0)}[/green]")
                        console.print(f"  Failed: [red]{counters.get('failed', 0)}[/red]")
                        console.print(f"  Warned: [yellow]{counters.get('warned', 0)}[/yellow]")
                        console.print(f"  Errored: [red]{counters.get('errored', 0)}[/red]")
                        console.print(f"  Stopped: {counters.get('stopped', 0)}")
                        console.print(f"  Skipped: {counters.get('skipped', 0)}")

                    # Show device minutes
                    device_minutes = run.get('deviceMinutes', {})
                    if device_minutes:
                        total_minutes = device_minutes.get('total', 0)
                        console.print(f"\n[bold]Device Time:[/bold]")
                        console.print(f"  Total: {total_minutes:.2f} minutes")
                        console.print(f"  Metered: {device_minutes.get('metered', 0):.2f} minutes")
                        console.print(f"  Unmetered: {device_minutes.get('unmetered', 0):.2f} minutes")

                    return run

                # Wait before next poll
                time.sleep(10)

            except KeyboardInterrupt:
                console.print("\n\n[yellow]Monitoring stopped by user[/yellow]")
                console.print(f"Test run is still active. Check status in AWS Device Farm console.")
                console.print(f"Run ARN: {run_arn}")
                return None

    except Exception as e:
        console.print(f"\n[red]Error monitoring test run: {e}[/red]")
        return None


def monitor_runs_parallel_with_retry(
    project_arn: str,
    device_pool_arn: str,
    app_arn: str,
    test_package_arn: str,
    test_spec_arns: List[str],
    test_class: str,
    run_names: List[str],
    initial_run_arns: List[str],
    output_dir: Path,
    max_retries: int = 3
) -> Tuple[bool, List[Path]]:
    """
    Monitor multiple test runs in parallel, evaluating failures immediately and retrying.

    Args:
        project_arn: AWS Device Farm project ARN
        device_pool_arn: Device pool ARN
        app_arn: Uploaded app ARN
        test_package_arn: Uploaded test package ARN
        test_spec_arns: List of test spec ARNs (one per batch)
        test_class: Test class name
        run_names: List of run names (one per batch)
        initial_run_arns: List of initially scheduled run ARNs
        output_dir: Directory to save traces
        max_retries: Maximum retry attempts per run

    Returns:
        Tuple of (success: bool, downloaded_traces: List[Path])
    """
    try:
        session_kwargs = {
            'aws_access_key_id': os.environ.get('AWS_ACCESS_KEY_ID'),
            'aws_secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
            'region_name': 'us-west-2'
        }
        session_token = os.environ.get('AWS_SESSION_TOKEN')
        if session_token:
            session_kwargs['aws_session_token'] = session_token

        session = boto3.Session(**session_kwargs)
        client = session.client('devicefarm')

        # Track each run: {run_arn: {'batch_idx': int, 'attempt': int, 'status': str, 'last_status': str, 'completed': bool}}
        runs = {}
        for idx, run_arn in enumerate(initial_run_arns):
            runs[run_arn] = {
                'batch_idx': idx,
                'attempt': 1,
                'status': 'PENDING',
                'last_status': None,
                'completed': False
            }

        all_traces = []
        start_time = time.time()

        console.print(f"\n[bold]Monitoring {len(runs)} run(s) in parallel...[/bold]")
        console.print("Press Ctrl+C to stop monitoring (tests will continue running)\n")

        try:
            while True:
                # Check if all runs completed successfully
                if all(run_info['completed'] for run_info in runs.values()):
                    console.print(f"\n[green]✓[/green] All runs completed successfully!")
                    return True, all_traces

                # Poll each incomplete run
                for run_arn in list(runs.keys()):
                    run_info = runs[run_arn]

                    if run_info['completed']:
                        continue

                    try:
                        # Get run status
                        response = client.get_run(arn=run_arn)
                        run = response['run']
                        status = run['status']
                        run_info['status'] = status

                        # Show status update if changed
                        if status != run_info['last_status']:
                            elapsed = int(time.time() - start_time)
                            batch_idx = run_info['batch_idx']
                            attempt = run_info['attempt']
                            console.print(f"[{elapsed}s] Batch {batch_idx + 1} (attempt {attempt}): {status}")
                            run_info['last_status'] = status

                        # Check if run completed
                        if status in ['COMPLETED', 'STOPPED']:
                            elapsed = int(time.time() - start_time)
                            batch_idx = run_info['batch_idx']
                            attempt = run_info['attempt']

                            # Attempt to download traces
                            console.print(f"[{elapsed}s] Batch {batch_idx + 1} (attempt {attempt}): Downloading traces...")
                            downloaded = download_artifacts(run_arn, output_dir)

                            if downloaded:
                                # Success!
                                all_traces.extend(downloaded)
                                run_info['completed'] = True
                                console.print(f"[{elapsed}s] Batch {batch_idx + 1} (attempt {attempt}): [green]✓[/green] Downloaded {len(downloaded)} trace(s)")
                            else:
                                # No traces - check if we can retry
                                if attempt < max_retries + 1:
                                    # Schedule retry
                                    console.print(f"[{elapsed}s] Batch {batch_idx + 1} (attempt {attempt}): [yellow]No traces, scheduling retry {attempt}/{max_retries}...[/yellow]")

                                    # Schedule new run with same parameters
                                    retry_run_arn = schedule_test_run(
                                        project_arn=project_arn,
                                        device_pool_arn=device_pool_arn,
                                        app_arn=app_arn,
                                        test_package_arn=test_package_arn,
                                        test_spec_arn=test_spec_arns[batch_idx],
                                        test_class=test_class,
                                        run_name=run_names[batch_idx]
                                    )

                                    if retry_run_arn:
                                        # Remove old run, add retry run
                                        del runs[run_arn]
                                        runs[retry_run_arn] = {
                                            'batch_idx': batch_idx,
                                            'attempt': attempt + 1,
                                            'status': 'PENDING',
                                            'last_status': None,
                                            'completed': False
                                        }
                                        console.print(f"[{elapsed}s] Batch {batch_idx + 1}: [green]✓[/green] Retry scheduled")
                                    else:
                                        console.print(f"[red]Failed to schedule retry for batch {batch_idx + 1}[/red]")
                                        return False, all_traces
                                else:
                                    # Max retries exceeded
                                    console.print(f"[{elapsed}s] Batch {batch_idx + 1}: [red]Failed after {max_retries} retries (no traces)[/red]")
                                    return False, all_traces

                    except Exception as e:
                        console.print(f"[yellow]Warning: Error checking run {run_arn[-8:]}: {e}[/yellow]")

                # Wait before next poll
                time.sleep(10)

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Monitoring stopped by user[/yellow]")
            console.print("Test runs are still active. Check AWS Device Farm console for status.")
            return False, all_traces

    except Exception as e:
        console.print(f"[red]Error in parallel monitoring: {e}[/red]")
        return False, all_traces


def download_artifacts(run_arn: str, output_dir: Path) -> list[Path]:
    """
    Download artifacts (Perfetto traces) from a completed test run.

    Args:
        run_arn: Test run ARN
        output_dir: Directory to save artifacts

    Returns:
        List of downloaded file paths
    """
    try:
        session_kwargs = {
            'aws_access_key_id': os.environ.get('AWS_ACCESS_KEY_ID'),
            'aws_secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
            'region_name': 'us-west-2'
        }
        session_token = os.environ.get('AWS_SESSION_TOKEN')
        if session_token:
            session_kwargs['aws_session_token'] = session_token

        session = boto3.Session(**session_kwargs)
        client = session.client('devicefarm')

        # Create run-specific subdirectory using run ARN as folder name
        # Replace problematic characters for filesystem compatibility
        run_folder_name = run_arn.replace(':', '_').replace('/', '_')
        run_output_dir = output_dir / run_folder_name
        run_output_dir.mkdir(parents=True, exist_ok=True)

        downloaded_files = []

        # List all jobs in the run
        jobs_response = client.list_jobs(arn=run_arn)
        jobs = jobs_response.get('jobs', [])

        for job in jobs:
            job_arn = job['arn']

            # Download job-level artifacts (customer artifacts from $DEVICEFARM_LOG_DIR)
            try:
                job_artifacts_response = client.list_artifacts(
                    arn=job_arn,
                    type='FILE'
                )
                job_artifacts = job_artifacts_response.get('artifacts', [])

                console.print(f"  Found {len(job_artifacts)} job-level artifact(s)")

                for artifact in job_artifacts:
                    artifact_name = artifact.get('name', '')
                    artifact_extension = artifact.get('extension', '')
                    artifact_url = artifact.get('url', '')
                    artifact_type = artifact.get('type', '')

                    # Look for Customer Artifacts zip (contains traces from $DEVICEFARM_LOG_DIR)
                    if artifact_type == 'CUSTOMER_ARTIFACT' and artifact_extension == 'zip':
                        console.print(f"  Downloading and extracting: {artifact_name}")

                        # Download the zip file
                        response = requests.get(artifact_url)
                        response.raise_for_status()

                        # Save zip temporarily
                        import zipfile
                        import tarfile
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
                            temp_zip.write(response.content)
                            temp_zip_path = temp_zip.name

                        # Extract and look for trace files or compressed archives
                        try:
                            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                                for zip_info in zip_ref.namelist():
                                    # Look for compressed traces archive
                                    if zip_info.endswith('traces.tar.gz'):
                                        console.print(f"    Found compressed traces: {zip_info}")

                                        # Extract the tar.gz to a temp location
                                        tar_data = zip_ref.read(zip_info)
                                        with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as temp_tar:
                                            temp_tar.write(tar_data)
                                            temp_tar_path = temp_tar.name

                                        try:
                                            # Extract traces from tar.gz
                                            with tarfile.open(temp_tar_path, 'r:gz') as tar_ref:
                                                for tar_member in tar_ref.getmembers():
                                                    if '.perfetto-trace' in tar_member.name or tar_member.name.endswith('.trace'):
                                                        console.print(f"    Found trace: {tar_member.name}")

                                                        # Extract trace file
                                                        trace_file = tar_ref.extractfile(tar_member)
                                                        if trace_file:
                                                            trace_filename = Path(tar_member.name).name
                                                            output_file = run_output_dir / trace_filename
                                                            with open(output_file, 'wb') as f:
                                                                f.write(trace_file.read())

                                                            downloaded_files.append(output_file)
                                                            console.print(f"    [green]✓[/green] Extracted: {output_file}")
                                        finally:
                                            Path(temp_tar_path).unlink(missing_ok=True)

                                    # Also look for uncompressed perfetto trace files (fallback)
                                    elif '.perfetto-trace' in zip_info or zip_info.endswith('.trace'):
                                        console.print(f"    Found trace: {zip_info}")

                                        # Extract just the trace file
                                        trace_data = zip_ref.read(zip_info)

                                        # Save to run-specific directory with just the filename (remove path)
                                        trace_filename = Path(zip_info).name
                                        output_file = run_output_dir / trace_filename
                                        with open(output_file, 'wb') as f:
                                            f.write(trace_data)

                                        downloaded_files.append(output_file)
                                        console.print(f"    [green]✓[/green] Extracted: {output_file}")
                        finally:
                            # Clean up temp zip
                            Path(temp_zip_path).unlink(missing_ok=True)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not list job artifacts: {e}[/yellow]")

            # List all suites in the job
            suites_response = client.list_suites(arn=job_arn)
            suites = suites_response.get('suites', [])

            for suite in suites:
                suite_arn = suite['arn']

                # List all tests in the suite
                tests_response = client.list_tests(arn=suite_arn)
                tests = tests_response.get('tests', [])

                for test in tests:
                    test_arn = test['arn']

                    # List artifacts for this test
                    artifacts_response = client.list_artifacts(
                        arn=test_arn,
                        type='FILE'
                    )

                    artifacts = artifacts_response.get('artifacts', [])

                    # Filter for Perfetto trace files
                    for artifact in artifacts:
                        artifact_name = artifact.get('name', '')
                        artifact_extension = artifact.get('extension', '')
                        artifact_url = artifact.get('url', '')

                        # Look for Perfetto traces
                        if '.perfetto-trace' in artifact_name or artifact_extension == '.perfetto-trace':
                            console.print(f"  Downloading: {artifact_name}")

                            # Download the file
                            response = requests.get(artifact_url)
                            response.raise_for_status()

                            # Save to run-specific directory
                            output_file = run_output_dir / artifact_name
                            with open(output_file, 'wb') as f:
                                f.write(response.content)

                            downloaded_files.append(output_file)
                            console.print(f"  [green]✓[/green] Saved: {output_file}")

        if downloaded_files:
            console.print(f"\n[green]✓[/green] Downloaded {len(downloaded_files)} Perfetto trace file(s)")
        else:
            console.print(f"\n[yellow]No Perfetto trace files found[/yellow]")
            # Remove empty run folder if no traces were downloaded
            if run_output_dir.exists() and not any(run_output_dir.iterdir()):
                run_output_dir.rmdir()

        return downloaded_files

    except Exception as e:
        console.print(f"\n[red]Error downloading artifacts: {e}[/red]")
        # Clean up empty run folder on error
        try:
            if run_output_dir.exists() and not any(run_output_dir.iterdir()):
                run_output_dir.rmdir()
        except:
            pass
        return []
