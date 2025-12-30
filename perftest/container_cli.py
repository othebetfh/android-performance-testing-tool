"""CLI entry point for perftest Docker container."""

import argparse
import sys

from rich.console import Console

# Import all command functions from commands module
from perftest.commands import (
    non_interactive_build,
    non_interactive_upload_and_test,
    non_interactive_analyze,
    non_interactive_full_pipeline
)

console = Console()


def main():
    """
    Android Performance Testing Tool container CLI.

    Execute commands with required arguments. For interactive mode, use scripts/perftest.
    """
    parser = argparse.ArgumentParser(
        description="Android Performance Testing Tool Container CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # build-apk command
    build_parser = subparsers.add_parser(
        'build-apk',
        help='Build APK from source'
    )
    build_parser.add_argument('--branch', required=True, help='Git branch name')
    build_parser.add_argument('--commit', required=True, help='Git commit hash')
    build_parser.add_argument('--product-flavor', default='dev', help='Product flavor (default: dev)')
    build_parser.add_argument('--build-type', default='perf', help='Build type (default: perf)')

    # upload-and-test command
    upload_parser = subparsers.add_parser(
        'upload-and-test',
        help='Upload APK and run test on Device Farm'
    )
    upload_parser.add_argument('--branch', required=True, help='Git branch name')
    upload_parser.add_argument('--commit', required=True, help='Git commit hash')
    upload_parser.add_argument('--project-arn', required=True, help='AWS Device Farm project ARN')
    upload_parser.add_argument('--device-pool-arn', required=True, help='AWS Device Farm device pool ARN')
    upload_parser.add_argument('--test-name', required=True, help='Test name from benchmark_tests.yml')
    upload_parser.add_argument('--run-name', help='Optional test run name')
    upload_parser.add_argument('--num-iterations', type=int, required=True, help='Number of test iterations')

    # analyze command
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='Analyze and compare performance results'
    )
    analyze_parser.add_argument('--base-branch', required=True, help='Base branch name')
    analyze_parser.add_argument('--base-commit', required=True, help='Base commit hash')
    analyze_parser.add_argument('--test-branch', required=True, help='Test branch name')
    analyze_parser.add_argument('--test-commit', required=True, help='Test commit hash')
    analyze_parser.add_argument('--device-pool', required=True, help='Device pool name')
    analyze_parser.add_argument('--test-name', required=True, help='Test name')

    # full-pipeline command
    pipeline_parser = subparsers.add_parser(
        'full-pipeline',
        help='Run complete pipeline: build → test → analyze'
    )
    pipeline_parser.add_argument('--base-branch', required=True, help='Base branch name')
    pipeline_parser.add_argument('--base-commit', required=True, help='Base commit hash')
    pipeline_parser.add_argument('--test-branch', required=True, help='Test branch name')
    pipeline_parser.add_argument('--test-commit', required=True, help='Test commit hash')
    pipeline_parser.add_argument('--project-arn', required=True, help='AWS Device Farm project ARN')
    pipeline_parser.add_argument('--device-pool-arn', required=True, help='AWS Device Farm device pool ARN')
    pipeline_parser.add_argument('--test-name', required=True, help='Test name from benchmark_tests.yml')
    pipeline_parser.add_argument('--product-flavor', default='dev', help='Product flavor (default: dev)')
    pipeline_parser.add_argument('--build-type', default='perf', help='Build type (default: perf)')
    pipeline_parser.add_argument('--run-name', help='Optional test run name')
    pipeline_parser.add_argument('--num-iterations', type=int, required=True, help='Number of test iterations')

    # Interactive mode commands (module-specific)
    subparsers.add_parser(
        'build-interactive',
        help='Interactive build workflow'
    )
    subparsers.add_parser(
        'test-interactive',
        help='Interactive test workflow'
    )
    subparsers.add_parser(
        'analyze-interactive',
        help='Interactive analysis workflow'
    )
    subparsers.add_parser(
        'full-pipeline-interactive',
        help='Interactive full pipeline workflow'
    )

    # Parse arguments
    args = parser.parse_args()

    if args.command == 'build-apk':
        # Non-interactive build
        non_interactive_build(
            branch=args.branch,
            commit=args.commit,
            product_flavor=args.product_flavor,
            build_type=args.build_type
        )
    elif args.command == 'upload-and-test':
        # Non-interactive upload and test
        non_interactive_upload_and_test(
            branch=args.branch,
            commit=args.commit,
            project_arn=args.project_arn,
            device_pool_arn=args.device_pool_arn,
            test_name=args.test_name,
            run_name=args.run_name,
            num_iterations=args.num_iterations
        )
    elif args.command == 'analyze':
        # Non-interactive analyze
        non_interactive_analyze(
            base_branch=args.base_branch,
            base_commit=args.base_commit,
            test_branch=args.test_branch,
            test_commit=args.test_commit,
            device_pool=args.device_pool,
            test_name=args.test_name
        )
    elif args.command == 'full-pipeline':
        # Execute full pipeline
        non_interactive_full_pipeline(
            base_branch=args.base_branch,
            base_commit=args.base_commit,
            test_branch=args.test_branch,
            test_commit=args.test_commit,
            project_arn=args.project_arn,
            device_pool_arn=args.device_pool_arn,
            test_name=args.test_name,
            product_flavor=args.product_flavor,
            build_type=args.build_type,
            run_name=args.run_name,
            num_iterations=args.num_iterations
        )
    elif args.command == 'build-interactive':
        # Interactive build workflow
        from perftest.interactive import build_apk_interactive
        build_apk_interactive()
    elif args.command == 'test-interactive':
        # Interactive test workflow
        from perftest.interactive import run_test_interactive
        run_test_interactive()
    elif args.command == 'analyze-interactive':
        # Interactive analysis workflow
        from perftest.interactive import analyze_interactive
        analyze_interactive()
    elif args.command == 'full-pipeline-interactive':
        # Interactive full pipeline workflow
        from perftest.interactive import full_pipeline_interactive
        full_pipeline_interactive()
    else:
        # No command provided
        console.print("[red]Error: A command is required[/red]")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
