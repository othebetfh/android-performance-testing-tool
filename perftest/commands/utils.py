"""Utility functions for perftest commands."""

import os
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()


def prompt_aws_credentials() -> dict[str, str]:
    """Load AWS credentials from environment variables."""
    console.print("\n[bold cyan]Loading AWS Credentials[/bold cyan]")
    console.print("─" * 50)

    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token = os.getenv("AWS_SESSION_TOKEN")

    # Check for placeholder or missing values
    placeholders = ['placeholder', 'your_key_here', 'your_secret_here', '']

    if not aws_access_key or aws_access_key.lower() in placeholders:
        console.print("[red]Error: AWS_ACCESS_KEY_ID not set or is a placeholder[/red]")
        console.print("\nPlease set your AWS credentials in the .env file:")
        console.print("  AWS_ACCESS_KEY_ID=your_access_key")
        console.print("  AWS_SECRET_ACCESS_KEY=your_secret_key")
        raise ValueError("AWS credentials not configured")

    if not aws_secret_key or aws_secret_key.lower() in placeholders:
        console.print("[red]Error: AWS_SECRET_ACCESS_KEY not set or is a placeholder[/red]")
        console.print("\nPlease set your AWS credentials in the .env file:")
        console.print("  AWS_ACCESS_KEY_ID=your_access_key")
        console.print("  AWS_SECRET_ACCESS_KEY=your_secret_key")
        raise ValueError("AWS credentials not configured")

    # Strip whitespace from credentials
    aws_access_key = aws_access_key.strip()
    aws_secret_key = aws_secret_key.strip()
    if aws_session_token:
        aws_session_token = aws_session_token.strip()

    console.print("[green]✓[/green] AWS credentials loaded from environment")

    result = {
        "access_key": aws_access_key,
        "secret_key": aws_secret_key
    }
    if aws_session_token and aws_session_token.lower() not in placeholders:
        result["session_token"] = aws_session_token

    return result


def check_properties_files(product_flavor: str) -> bool:
    """Check if required properties files exist."""
    properties_file = Path(f"/workspace/config/properties/{product_flavor}.properties")
    google_services_file = Path("/workspace/config/properties/google-services.json")

    if not properties_file.exists():
        console.print(f"\n[red]Error: {product_flavor}.properties not found in /workspace/config/properties/[/red]")
        console.print(f"Please copy it to the config directory on your host machine")
        return False

    if not google_services_file.exists():
        console.print(f"\n[red]Error: google-services.json not found in /workspace/config/properties/[/red]")
        console.print(f"Please copy it to the config directory on your host machine")
        return False

    return True


def get_output_directory() -> Path:
    """
    Get the output directory, checking multiple possible locations.

    Returns:
        Path to output directory, or None if not found
    """
    possible_dirs = [
        Path("/workspace/output"),  # Docker/mounted workspace
        Path("./output"),  # Relative to current directory
        Path(__file__).parent.parent / "output",  # Relative to perftest package
    ]

    for dir_path in possible_dirs:
        if dir_path.exists():
            return dir_path

    # Default to ./output if none exist (will be created if needed)
    return Path("./output")


def get_display_path(path: Path) -> str:
    """
    Convert a path to a display-friendly format.

    Returns the absolute path, which works correctly both locally and in Docker.
    """
    return str(path.absolute())


def find_available_builds() -> list[dict]:
    """
    Find all available builds in the output directory.

    Returns:
        List of dicts with keys: 'path', 'name', 'apks_dir'
    """
    output_dir = get_output_directory()
    builds = []

    if not output_dir or not output_dir.exists():
        return builds

    # Look for directories containing apks subdirectory
    for item in output_dir.iterdir():
        if item.is_dir():
            apks_dir = item / "apks"
            if apks_dir.exists() and list(apks_dir.glob("*.apk")):
                builds.append({
                    'path': item,
                    'name': item.name,
                    'apks_dir': apks_dir
                })

    return sorted(builds, key=lambda b: b['name'], reverse=True)


def detect_apk_pairs(apks_dir: Path) -> list[dict]:
    """
    Detect matching app and test APK pairs in the directory.

    Returns:
        List of dicts with keys: 'app', 'test', 'flavor', 'build_type', 'display'
    """
    if not apks_dir.exists():
        return []

    # Get all APK files
    apk_files = list(apks_dir.glob("*.apk"))
    if not apk_files:
        return []

    # Separate app APKs from test APKs
    app_apks = []
    test_apks = []

    for apk in apk_files:
        name_lower = apk.name.lower()
        # Test APKs come from benchmark module
        if 'benchmark' in name_lower:
            test_apks.append(apk)
        else:
            app_apks.append(apk)

    # Try to pair them based on flavor and build type
    pairs = []
    for app_apk in app_apks:
        app_name = app_apk.stem.lower()

        # Extract potential flavor and build type from app APK name
        # Expected format: app-{flavor}-{buildType}.apk or similar
        for test_apk in test_apks:
            test_name = test_apk.stem.lower()

            # Check if they share common flavor/build type indicators
            # Look for common substrings (e.g., "dev", "perf", "debug")
            common_parts = []
            app_parts = app_name.replace('-', ' ').replace('_', ' ').split()
            test_parts = test_name.replace('-', ' ').replace('_', ' ').split()

            for part in app_parts:
                if part in test_parts and part not in ['app', 'benchmark']:
                    common_parts.append(part)

            if common_parts:
                # Found a potential match
                flavor = common_parts[0] if len(common_parts) > 0 else "unknown"
                build_type = common_parts[1] if len(common_parts) > 1 else "unknown"

                pairs.append({
                    'app': app_apk,
                    'test': test_apk,
                    'flavor': flavor,
                    'build_type': build_type,
                    'display': f"{app_apk.name} + {test_apk.name}"
                })

    # Sort by modification time (most recent first)
    pairs.sort(key=lambda p: p['app'].stat().st_mtime, reverse=True)

    return pairs


def get_apks_from_config() -> tuple[list[Path], list[Path]]:
    """
    Get APKs from config folder.

    Returns:
        Tuple of (app_apks, test_apks) lists
    """
    config_dir = Path("/workspace/config")
    if not config_dir.exists():
        return [], []

    apk_files = list(config_dir.glob("*.apk"))
    if not apk_files:
        return [], []

    app_apks = []
    test_apks = []

    for apk in apk_files:
        name_lower = apk.name.lower()
        # Test APKs come from benchmark module
        if 'benchmark' in name_lower:
            test_apks.append(apk)
        else:
            app_apks.append(apk)

    # Sort by name
    app_apks.sort(key=lambda p: p.name)
    test_apks.sort(key=lambda p: p.name)

    return app_apks, test_apks


def find_available_test_runs() -> list[dict]:
    """
    Find all available test runs with traces in the output directory.

    Returns:
        List of dicts with keys: 'path', 'name', 'device_pools' (dict mapping pool name to list of tests)
    """
    output_dir = get_output_directory()
    test_runs = []

    if not output_dir or not output_dir.exists():
        return test_runs

    # Look for directories containing traces subdirectory
    for item in output_dir.iterdir():
        if item.is_dir():
            traces_dir = item / "traces"
            if traces_dir.exists() and traces_dir.is_dir():
                # Find device pool subdirectories
                device_pools = {}
                for pool_dir in traces_dir.iterdir():
                    if pool_dir.is_dir() and not pool_dir.name.startswith('.'):
                        # Find test subdirectories within each device pool
                        test_names = []
                        for test_dir in pool_dir.iterdir():
                            if test_dir.is_dir() and not test_dir.name.startswith('.'):
                                # Check for traces recursively (traces may be in run ARN subdirectories)
                                # Exclude hidden directories from trace search
                                traces = [
                                    p for p in test_dir.rglob("*.perfetto-trace")
                                    if not any(part.startswith('.') for part in p.parts)
                                ]
                                if traces:
                                    test_names.append(test_dir.name)

                        if test_names:
                            device_pools[pool_dir.name] = sorted(test_names)

                if device_pools:
                    test_runs.append({
                        'path': item,
                        'name': item.name,
                        'device_pools': device_pools
                    })

    return sorted(test_runs, key=lambda r: r['name'], reverse=True)
