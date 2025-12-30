"""Commands module for perftest interactive client."""

# Import utility functions
from .utils import (
    prompt_aws_credentials,
    check_properties_files,
    get_output_directory,
    get_display_path,
    find_available_builds,
    detect_apk_pairs,
    get_apks_from_config,
    find_available_test_runs
)

# Import Device Farm functions
from .devicefarm import (
    create_devicefarm_client,
    get_projects,
    get_device_pools,
    upload_apk,
    load_test_execution_config,
    get_available_tests,
    schedule_test_run,
    monitor_test_run,
    monitor_runs_parallel_with_retry,
    download_artifacts
)

# Import build functions
from .build import build_apk_for_pipeline

# Import test functions
from .test import schedule_test_for_pipeline

# Import analyze functions
from .analyze import (
    analyze_command
)

# Import pipeline functions
from .pipeline import (
    non_interactive_analyze,
    non_interactive_upload_and_test,
    non_interactive_build,
    non_interactive_full_pipeline
)

__all__ = [
    # Utils
    'prompt_aws_credentials',
    'check_properties_files',
    'get_output_directory',
    'get_display_path',
    'find_available_builds',
    'detect_apk_pairs',
    'get_apks_from_config',
    'find_available_test_runs',
    # Device Farm
    'create_devicefarm_client',
    'get_projects',
    'get_device_pools',
    'upload_apk',
    'load_test_execution_config',
    'get_available_tests',
    'schedule_test_run',
    'monitor_test_run',
    'monitor_runs_parallel_with_retry',
    'download_artifacts',
    # Build
    'build_apk_for_pipeline',
    # Test
    'schedule_test_for_pipeline',
    # Analyze
    'analyze_command',
    # Pipeline
    'non_interactive_analyze',
    'non_interactive_upload_and_test',
    'non_interactive_build',
    'non_interactive_full_pipeline'
]
