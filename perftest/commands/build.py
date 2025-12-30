"""Build command functions for perftest."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from perftest.build import GradleBuilder, clone_repository, validate_apk_pair
from perftest.config import ConfigManager
from .utils import check_properties_files

console = Console()


def build_apk_for_pipeline(
    branch: str,
    commit: str,
    github_token: str,
    product_flavor: str = "dev",
    build_type: str = "perf"
) -> Optional[Path]:
    """
    Build APK for pipeline use.

    Args:
        branch: Git branch name
        commit: Git commit hash
        github_token: GitHub token for authentication
        product_flavor: Product flavor (default: "dev")
        build_type: Build type (default: "perf")

    Returns:
        Path to output directory containing the APK, or None if build fails
    """
    # Get GitHub user from environment
    github_user = os.getenv("GITHUB_USER")
    if not github_user:
        console.print("[red]Error: GITHUB_USER environment variable not set[/red]")
        return None

    # Check properties files
    if not check_properties_files(product_flavor):
        console.print(f"[red]Properties files not found for flavor: {product_flavor}[/red]")
        return None

    properties_file = Path(f"/workspace/config/properties/{product_flavor}.properties")
    google_services_file = Path("/workspace/config/properties/google-services.json")

    # Create output directory based on branch and commit
    branch_sanitized = branch.replace('/', '-').replace('\\', '-')
    commit_short = commit[:8] if len(commit) >= 8 else commit
    output_base = Path(f"/workspace/output/{branch_sanitized}_{commit_short}")

    # Check if APKs already exist (cache check)
    apk_dir = output_base / "apks"

    if apk_dir.exists():
        # Look for app and test/benchmark APKs
        apk_files = list(apk_dir.glob("*.apk"))
        app_apks = [f for f in apk_files if f.name.startswith("app-")]
        test_apks = [f for f in apk_files if not f.name.startswith("app-")]

        if app_apks and test_apks:
            console.print(f"[green]✓[/green] Using cached build: {branch}@{commit_short}")
            return output_base

    # Build the APK
    console.print(f"[bold]Building APK: {branch}@{commit_short}[/bold]")

    # Create temporary directory for cloning
    temp_dir = Path(tempfile.mkdtemp(prefix=f"perftest-build-{branch_sanitized}-{commit_short}-"))
    clone_dir = temp_dir / "repo"

    try:
        # Clone repository
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task(description="Cloning repository...", total=None)

            # Get repo URL from config
            config = ConfigManager()
            repo_url = config.config.build.repository_url

            clone_repository(
                repo_url=repo_url,
                token=github_token,
                target_dir=clone_dir,
                commit=commit,
                branch=branch
            )

        console.print("[green]✓[/green] Repository cloned successfully")

        # Build APKs
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task(description="Building APKs with Gradle...", total=None)

            builder = GradleBuilder(
                clone_dir,
                properties_file=properties_file,
                google_services_file=google_services_file,
                github_user=github_user,
                github_token=github_token
            )
            apks = builder.build(
                product_flavor=product_flavor,
                build_type=build_type,
                gradle_options=[]
            )

        console.print("[green]✓[/green] APKs built successfully")

        # Validate APKs
        console.print("Validating APKs...")
        validate_apk_pair(apks['app'], apks['test'])
        console.print("[green]✓[/green] APK validation passed")

        # Copy APKs to output directory
        apk_dir.mkdir(parents=True, exist_ok=True)
        app_output = apk_dir / apks['app'].name
        test_output = apk_dir / apks['test'].name

        shutil.copy2(apks['app'], app_output)
        shutil.copy2(apks['test'], test_output)

        console.print(f"[green]✓[/green] Build completed: {branch}@{commit_short}")
        console.print(f"  App APK:  {app_output.name}")
        console.print(f"  Test APK: {test_output.name}")

        return output_base

    except Exception as e:
        console.print(f"[red]Build failed: {e}[/red]")
        return None
    finally:
        # Cleanup temporary directory
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to cleanup temp directory: {e}[/yellow]")
