"""
Optimized trace processing using parallel extraction with Perfetto's Python API.

This module uses multiprocessing to process multiple trace files concurrently
with optimized SQL queries and result caching.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, asdict
import pandas as pd


# SQL query to extract startup metrics from traces
# This query uses CTEs for efficiency and extracts the first occurrence of each marker
STARTUP_METRICS_QUERY = """
WITH markers AS (
    SELECT
        name,
        ts,
        ROW_NUMBER() OVER (PARTITION BY name ORDER BY ts) as rn
    FROM slice
    WHERE name IN (
        'android_platform_page_load_complete',
        'bindApplication',
        'android_apps_tab_screen_render_begin'
    )
),
timestamps AS (
    SELECT
        MAX(CASE WHEN name = 'android_platform_page_load_complete' THEN ts END) AS page_load_ts,
        MAX(CASE WHEN name = 'bindApplication' THEN ts END) AS bind_app_ts,
        MAX(CASE WHEN name = 'android_apps_tab_screen_render_begin' THEN ts END) AS render_ts
    FROM markers
    WHERE rn = 1
)
SELECT
    (page_load_ts - bind_app_ts) / 1000000.0 AS startup_latency_ms,
    (render_ts - bind_app_ts) / 1000000.0 AS render_latency_ms
FROM timestamps
WHERE page_load_ts IS NOT NULL
  AND bind_app_ts IS NOT NULL
  AND render_ts IS NOT NULL;
"""


@dataclass
class TraceMetrics:
    """Metrics extracted from a single trace."""
    trace_file: str
    iteration: int
    startup_latency_ms: float
    render_latency_ms: float
    batch: int
    run_arn: str


def extract_startup_metrics_from_trace(trace_path: Path) -> Optional[Tuple[float, float]]:
    """
    Extract startup metrics from a single trace file using optimized SQL query.

    Args:
        trace_path: Path to the perfetto trace file

    Returns:
        Tuple of (startup_latency_ms, render_latency_ms) or None if extraction fails
    """
    try:
        from perfetto.trace_processor import TraceProcessor

        tp = TraceProcessor(trace=str(trace_path))
        result = tp.query(STARTUP_METRICS_QUERY).as_pandas_dataframe()
        tp.close()

        if len(result) > 0 and pd.notna(result.iloc[0]['startup_latency_ms']):
            startup_ms = result.iloc[0]['startup_latency_ms']
            render_ms = result.iloc[0]['render_latency_ms']
            return startup_ms, render_ms
    except Exception:
        # Silent failure - let the caller handle missing data
        pass

    return None


def process_single_trace(args: Tuple[Path, int, str]) -> Optional[TraceMetrics]:
    """
    Process a single trace file and extract metrics.

    This function is designed to be called in parallel via multiprocessing.

    Args:
        args: Tuple of (trace_path, batch_id, run_arn)

    Returns:
        TraceMetrics object or None if processing fails
    """
    trace_path, batch_id, run_arn = args

    # Extract iteration number from filename
    iter_match = re.search(r'iter(\d+)', trace_path.name)
    if not iter_match:
        return None

    iter_num = int(iter_match.group(1))

    # Extract metrics using optimized query
    result = extract_startup_metrics_from_trace(trace_path)
    if result is None:
        return None

    startup_ms, render_ms = result

    return TraceMetrics(
        trace_file=str(trace_path),
        iteration=iter_num,
        startup_latency_ms=startup_ms,
        render_latency_ms=render_ms,
        batch=batch_id,
        run_arn=run_arn
    )


def load_traces_with_batches_parallel(
    base_dir: Path,
    max_workers: Optional[int] = None,
    use_cache: bool = True
) -> pd.DataFrame:
    """
    Load traces using parallel processing with optional caching.

    Args:
        base_dir: Directory containing trace files
        max_workers: Maximum number of parallel workers (default: CPU count)
        use_cache: Whether to use cached metrics if available

    Returns:
        DataFrame with extracted metrics

    Raises:
        ValueError: If no valid traces found or directory doesn't exist
    """
    base_path = Path(base_dir)

    if not base_path.exists():
        raise ValueError(f'Directory does not exist: {base_path}')

    # Check for cached metrics
    cache_file = base_path / '.metrics_cache.json'
    if use_cache and cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
            print(f"Using cached metrics from {cache_file.name}")
            return pd.DataFrame(cached_data)
        except Exception:
            # If cache is corrupted, proceed with processing
            pass

    # Find all run folders (batches)
    run_folders = sorted([d for d in base_path.iterdir() if d.is_dir() and d.name.startswith('arn')])

    if not run_folders:
        run_folders = [base_path]

    # Collect all traces with their batch information
    trace_tasks = []
    for batch_id, run_folder in enumerate(run_folders):
        # Find traces, excluding hidden directories (e.g., .backup_traces)
        all_traces = run_folder.rglob('*.perfetto-trace')
        traces = sorted([
            t for t in all_traces
            if not any(part.startswith('.') for part in t.parts)
        ])
        for trace in traces:
            trace_tasks.append((trace, batch_id, run_folder.name))

    if not trace_tasks:
        raise ValueError(f'No trace files found in {base_path}')

    print(f"Processing {len(trace_tasks)} traces in parallel with {max_workers or 'auto'} workers...")

    # Process traces in parallel
    metrics_list = []
    failed_count = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {executor.submit(process_single_trace, task): task for task in trace_tasks}

        # Collect results as they complete
        for future in as_completed(futures):
            try:
                result = future.result()
                if result is not None:
                    metrics_list.append(asdict(result))
                else:
                    failed_count += 1
            except Exception:
                failed_count += 1

    if not metrics_list:
        raise ValueError(
            f'No valid trace data loaded from {base_path}. '
            f'{failed_count} traces failed processing. '
            'Check that traces contain required slices: '
            'android_platform_page_load_complete, bindApplication, android_apps_tab_screen_render_begin'
        )

    if failed_count > 0:
        print(f"Warning: {failed_count} traces failed to process or had missing metrics")

    print(f"✓ Successfully processed {len(metrics_list)} traces")

    # Create DataFrame
    df = pd.DataFrame(metrics_list)

    # Cache the results
    if use_cache:
        try:
            with open(cache_file, 'w') as f:
                json.dump(metrics_list, f)
            print(f"Cached results to {cache_file.name}")
        except Exception:
            # If caching fails, just continue
            pass

    return df


def clear_cache(directory: Path) -> bool:
    """
    Clear cached metrics for a directory.

    Args:
        directory: Directory containing cached metrics

    Returns:
        True if cache was cleared, False if no cache existed
    """
    cache_file = Path(directory) / '.metrics_cache.json'
    if cache_file.exists():
        cache_file.unlink()
        return True
    return False


def process_base_and_test_traces(
    base_traces_dir: Path,
    test_traces_dir: Path,
    max_workers: Optional[int] = None,
    use_cache: bool = True
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Process both base and test traces.

    Args:
        base_traces_dir: Directory containing base traces
        test_traces_dir: Directory containing test traces
        max_workers: Maximum number of parallel workers per trace set
        use_cache: Whether to use cached metrics if available

    Returns:
        Tuple of (base_df, test_df) DataFrames
    """
    print("=" * 80)
    print("PROCESSING BASE TRACES")
    print("=" * 80)
    base_df = load_traces_with_batches_parallel(
        base_traces_dir,
        max_workers,
        use_cache
    )

    print("\n" + "=" * 80)
    print("PROCESSING TEST TRACES")
    print("=" * 80)
    test_df = load_traces_with_batches_parallel(
        test_traces_dir,
        max_workers,
        use_cache
    )

    return base_df, test_df
