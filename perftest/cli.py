"""Command-line interface for perftest."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from perftest.config import ConfigManager
from perftest.logger import setup_logging, get_logger, console

logger = get_logger(__name__)


@click.group()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file"
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    help="Output directory for artifacts"
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging (DEBUG level)"
)
@click.pass_context
def cli(ctx: click.Context, config: Optional[Path], output_dir: Optional[Path], verbose: bool):
    """Android Performance Testing Tool - Build, test, and analyze Android app performance."""
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Load configuration
    try:
        config_manager = ConfigManager(config_path=config)
        ctx.obj["config"] = config_manager
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        ctx.exit(1)

    # Override output directory if provided
    if output_dir:
        config_manager.config.output.base_dir = str(output_dir)

    # Setup logging
    log_level = "DEBUG" if verbose else config_manager.config.logging.level
    log_file = None
    if config_manager.config.logging.file_enabled:
        log_file = Path(config_manager.config.logging.file_path)
    setup_logging(level=log_level, log_file=log_file)

    # Ensure output directories exist
    config_manager.ensure_output_dirs()

    ctx.obj["console"] = console
    logger.debug("CLI initialized successfully")


@cli.command()
@click.option(
    "--commit",
    required=True,
    help="Git commit hash to build"
)
@click.option(
    "--github-token",
    envvar="GITHUB_PAT",
    help="GitHub Personal Access Token (or set GITHUB_PAT env var)"
)
@click.option(
    "--build-type",
    type=click.Choice(["debug", "release"]),
    default="debug",
    help="Build type"
)
@click.pass_context
def build(ctx: click.Context, commit: str, github_token: Optional[str], build_type: str):
    """Build APKs from source repository."""
    console.print(f"[bold blue]Building APKs for commit {commit}[/bold blue]")

    if not github_token:
        console.print("[red]Error: GitHub token required. Set GITHUB_PAT environment variable or use --github-token[/red]")
        ctx.exit(1)

    config_manager = ctx.obj["config"]

    # TODO: Implement build workflow
    console.print("[yellow]Build command not yet implemented[/yellow]")
    logger.info(f"Build command called with commit={commit}, build_type={build_type}")


@cli.command()
@click.option(
    "--app-apk",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to app APK file"
)
@click.option(
    "--test-apk",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to test APK file"
)
@click.option(
    "--device-pool",
    help="Device pool name or ARN"
)
@click.option(
    "--project-arn",
    envvar="AWS_DEVICEFARM_PROJECT_ARN",
    help="Device Farm project ARN"
)
@click.option(
    "--run-name",
    help="Test run name"
)
@click.option(
    "--timeout",
    type=int,
    default=3600,
    help="Test timeout in seconds"
)
@click.option(
    "--download-traces/--no-download-traces",
    default=True,
    help="Download Perfetto traces"
)
@click.option(
    "--download-artifacts/--no-download-artifacts",
    default=True,
    help="Download test artifacts"
)
@click.option(
    "--wait/--no-wait",
    default=True,
    help="Wait for test completion"
)
@click.pass_context
def test(
    ctx: click.Context,
    app_apk: Path,
    test_apk: Path,
    device_pool: Optional[str],
    project_arn: Optional[str],
    run_name: Optional[str],
    timeout: int,
    download_traces: bool,
    download_artifacts: bool,
    wait: bool
):
    """Run tests on AWS Device Farm."""
    console.print("[bold blue]Starting Device Farm test run[/bold blue]")

    if not project_arn:
        console.print("[red]Error: Device Farm project ARN required. Set AWS_DEVICEFARM_PROJECT_ARN env var or use --project-arn[/red]")
        ctx.exit(1)

    config_manager = ctx.obj["config"]

    # TODO: Implement test workflow
    console.print("[yellow]Test command not yet implemented[/yellow]")
    logger.info(f"Test command called with app_apk={app_apk}, test_apk={test_apk}")


@cli.command()
@click.option(
    "--trace-file",
    type=click.Path(exists=True, path_type=Path),
    help="Single trace file to analyze"
)
@click.option(
    "--trace-dir",
    type=click.Path(exists=True, path_type=Path),
    help="Directory containing trace files"
)
@click.option(
    "--query",
    multiple=True,
    help="Named query to run (can specify multiple)"
)
@click.option(
    "--custom-query",
    type=click.Path(exists=True, path_type=Path),
    help="Path to custom SQL query file"
)
@click.option(
    "--output-format",
    type=click.Choice(["csv", "json", "html"]),
    default="csv",
    help="Output format"
)
@click.pass_context
def analyze(
    ctx: click.Context,
    trace_file: Optional[Path],
    trace_dir: Optional[Path],
    query: tuple[str, ...],
    custom_query: Optional[Path],
    output_format: str
):
    """Analyze Perfetto trace files."""
    console.print("[bold blue]Analyzing Perfetto traces[/bold blue]")

    if not trace_file and not trace_dir:
        console.print("[red]Error: Must specify either --trace-file or --trace-dir[/red]")
        ctx.exit(1)

    config_manager = ctx.obj["config"]

    # TODO: Implement analysis workflow
    console.print("[yellow]Analyze command not yet implemented[/yellow]")
    logger.info(f"Analyze command called with trace_file={trace_file}, trace_dir={trace_dir}")


@cli.command()
@click.option(
    "--commit",
    required=True,
    help="Git commit hash to test"
)
@click.option(
    "--github-token",
    envvar="GITHUB_PAT",
    help="GitHub Personal Access Token"
)
@click.option(
    "--device-pool",
    help="Device pool name or ARN"
)
@click.option(
    "--project-arn",
    envvar="AWS_DEVICEFARM_PROJECT_ARN",
    help="Device Farm project ARN"
)
@click.option(
    "--run-name",
    help="Test run identifier"
)
@click.option(
    "--skip-build",
    is_flag=True,
    help="Skip build step (use existing APKs)"
)
@click.option(
    "--skip-analysis",
    is_flag=True,
    help="Skip analysis step"
)
@click.pass_context
def full_run(
    ctx: click.Context,
    commit: str,
    github_token: Optional[str],
    device_pool: Optional[str],
    project_arn: Optional[str],
    run_name: Optional[str],
    skip_build: bool,
    skip_analysis: bool
):
    """Execute complete test pipeline: build → test → analyze."""
    console.print("[bold blue]Starting full test pipeline[/bold blue]")

    if not github_token and not skip_build:
        console.print("[red]Error: GitHub token required for build. Set GITHUB_PAT env var or use --github-token[/red]")
        ctx.exit(1)

    if not project_arn:
        console.print("[red]Error: Device Farm project ARN required. Set AWS_DEVICEFARM_PROJECT_ARN env var[/red]")
        ctx.exit(1)

    config_manager = ctx.obj["config"]

    # TODO: Implement full pipeline
    console.print("[yellow]Full-run command not yet implemented[/yellow]")
    logger.info(f"Full-run command called with commit={commit}, skip_build={skip_build}, skip_analysis={skip_analysis}")


@cli.command()
@click.pass_context
def validate(ctx: click.Context):
    """Validate environment and configuration."""
    console.print("[bold blue]Validating environment[/bold blue]")

    config_manager = ctx.obj["config"]
    checks_passed = 0
    checks_failed = 0

    # Check 1: Configuration
    console.print("\n[bold]1. Configuration[/bold]")
    try:
        console.print(f"  ✓ Configuration loaded successfully")
        console.print(f"    - Output dir: {config_manager.config.output.base_dir}")
        console.print(f"    - Log level: {config_manager.config.logging.level}")
        checks_passed += 1
    except Exception as e:
        console.print(f"  ✗ Configuration error: {e}")
        checks_failed += 1

    # Check 2: Output directories
    console.print("\n[bold]2. Output Directories[/bold]")
    try:
        for subdir in ["apks", "traces", "artifacts", "reports"]:
            path = config_manager.get_output_dir(subdir)
            if path.exists():
                console.print(f"  ✓ {subdir}: {path}")
            else:
                console.print(f"  ✗ {subdir}: {path} (does not exist)")
        checks_passed += 1
    except Exception as e:
        console.print(f"  ✗ Output directory error: {e}")
        checks_failed += 1

    # Check 3: Environment variables
    console.print("\n[bold]3. Environment Variables[/bold]")
    import os
    env_vars = {
        "GITHUB_PAT": "GitHub access token",
        "AWS_ACCESS_KEY_ID": "AWS access key",
        "AWS_SECRET_ACCESS_KEY": "AWS secret key",
        "AWS_DEVICEFARM_PROJECT_ARN": "Device Farm project ARN",
    }
    for var, description in env_vars.items():
        if os.getenv(var):
            console.print(f"  ✓ {var}: Set")
        else:
            console.print(f"  ⚠ {var}: Not set ({description})")

    # Check 4: Android SDK (if in Docker)
    console.print("\n[bold]4. Android SDK[/bold]")
    import os
    android_home = os.getenv("ANDROID_HOME")
    if android_home and Path(android_home).exists():
        console.print(f"  ✓ ANDROID_HOME: {android_home}")
        checks_passed += 1
    else:
        console.print(f"  ⚠ ANDROID_HOME not set or path doesn't exist")
        console.print(f"    (Expected in Docker environment)")

    # Check 5: Perfetto tools
    console.print("\n[bold]5. Perfetto Tools[/bold]")
    perfetto_path = Path(config_manager.config.analysis.trace_processor_path)
    if perfetto_path.exists():
        console.print(f"  ✓ trace_processor_shell: {perfetto_path}")
        checks_passed += 1
    else:
        console.print(f"  ⚠ trace_processor_shell not found at: {perfetto_path}")
        console.print(f"    (Expected in Docker environment)")

    # Summary
    console.print(f"\n[bold]Summary[/bold]")
    console.print(f"  Passed: {checks_passed}")
    console.print(f"  Failed: {checks_failed}")

    if checks_failed > 0:
        console.print("\n[yellow]Some checks failed. Please review the issues above.[/yellow]")
    else:
        console.print("\n[green]All checks passed![/green]")


if __name__ == "__main__":
    cli()
