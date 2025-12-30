"""
ColdStartup performance comparison notebook generation.

This module executes analysis template notebooks and generates HTML reports.
"""

from pathlib import Path
import re
from bs4 import BeautifulSoup
from .trace_processor import process_base_and_test_traces


def combine_reports_with_tabs(
    batch_html_path: Path,
    blocked_html_path: Path,
    output_path: Path,
    base_name: str,
    test_name: str,
    device_pool: str,
    test_type: str
) -> Path:
    """
    Combine two HTML reports into a single HTML with tabs.

    Args:
        batch_html_path: Path to batch aggregation HTML
        blocked_html_path: Path to blocked bootstrap HTML
        output_path: Path for combined HTML output
        base_name: Base run name
        test_name: Test run name
        device_pool: Device pool name
        test_type: Test type name

    Returns:
        Path to combined HTML file
    """
    # Read both HTML files
    with open(batch_html_path, 'r', encoding='utf-8') as f:
        batch_html = f.read()

    with open(blocked_html_path, 'r', encoding='utf-8') as f:
        blocked_html = f.read()

    # Parse HTML to extract content and styles
    batch_soup = BeautifulSoup(batch_html, 'html.parser')
    blocked_soup = BeautifulSoup(blocked_html, 'html.parser')

    # Extract the body content from each report
    batch_body = batch_soup.find('body')
    blocked_body = blocked_soup.find('body')

    # Extract styles from first report (both should be similar)
    batch_styles = batch_soup.find_all('style')

    # Create combined HTML with CSS-only tabs (no JavaScript needed)
    combined_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Performance Analysis: {base_name} vs {test_name}</title>

    <!-- Include original notebook styles -->
    {''.join(str(style) for style in batch_styles)}

    <!-- Tab styling -->
    <style>
        body {{
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .header h1 {{
            margin: 0 0 0.5rem 0;
            font-size: 1.75rem;
            font-weight: 600;
        }}

        .header-info {{
            font-size: 0.9rem;
            opacity: 0.95;
        }}

        .header-info span {{
            margin-right: 1.5rem;
            display: inline-block;
        }}

        /* Hide radio buttons */
        input[type="radio"][name="tabs"] {{
            position: absolute;
            opacity: 0;
            pointer-events: none;
        }}

        .tabs {{
            display: flex;
            background: #f8f9fa;
            border-bottom: 2px solid #dee2e6;
            padding: 0 2rem;
            position: sticky;
            top: 0;
            z-index: 1000;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}

        label.tab {{
            padding: 1rem 2rem;
            cursor: pointer;
            border: none;
            background: none;
            font-size: 1rem;
            font-weight: 500;
            color: #6c757d;
            transition: all 0.2s;
            border-bottom: 3px solid transparent;
            position: relative;
            display: inline-block;
        }}

        label.tab:hover {{
            color: #495057;
            background: rgba(0,0,0,0.02);
        }}

        /* Tab content hidden by default */
        .tab-content {{
            display: none !important;
            padding: 2rem;
        }}

        /* Show content when corresponding radio is checked */
        #tab-batch:checked ~ #batch-aggregation {{
            display: block !important;
        }}

        #tab-blocked:checked ~ #blocked-bootstrap {{
            display: block !important;
        }}

        /* Style active tab */
        #tab-batch:checked ~ .tabs label[for="tab-batch"],
        #tab-blocked:checked ~ .tabs label[for="tab-blocked"] {{
            color: #667eea;
            border-bottom-color: #667eea;
            background: white;
        }}

        /* Override notebook container width for better layout */
        #notebook-container {{
            max-width: 100% !important;
            padding: 0 !important;
        }}

        .container {{
            max-width: 1400px !important;
            margin: 0 auto !important;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Performance Analysis Report</h1>
        <div class="header-info">
            <span><strong>Base:</strong> {base_name}</span>
            <span><strong>Test:</strong> {test_name}</span>
            <span><strong>Device:</strong> {device_pool}</span>
            <span><strong>Test Type:</strong> {test_type}</span>
        </div>
    </div>

    <!-- Radio buttons for CSS-only tab switching -->
    <input type="radio" id="tab-batch" name="tabs" checked>
    <input type="radio" id="tab-blocked" name="tabs">

    <div class="tabs">
        <label for="tab-batch" class="tab">Batch Aggregation Analysis</label>
        <label for="tab-blocked" class="tab">Blocked Bootstrap Analysis</label>
    </div>

    <div id="batch-aggregation" class="tab-content">
        {batch_body.decode_contents() if hasattr(batch_body, 'decode_contents') else ''}
    </div>

    <div id="blocked-bootstrap" class="tab-content">
        {blocked_body.decode_contents() if hasattr(blocked_body, 'decode_contents') else ''}
    </div>
</body>
</html>
"""

    # Write combined HTML
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(combined_html)

    return output_path


def create_batch_aware_analysis(
    base_traces_dir: Path,
    test_traces_dir: Path,
    device_pool: str,
    test_name_str: str,
    output_dir: Path
) -> tuple[Path, Path]:
    """
    Execute analysis templates and generate HTML reports.

    Args:
        base_traces_dir: Path to base traces directory
        test_traces_dir: Path to test traces directory
        device_pool: Device pool name
        test_name_str: Test name (e.g., "coldStartup")
        output_dir: Output directory for analysis files

    Returns:
        Path to combined HTML report with tabs
    """
    import papermill as pm
    import subprocess
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Extract run names from trace directories
    # Path format: .../output/{run_name}/traces/{device_pool}/{test_name}
    base_name = base_traces_dir.parent.parent.parent.name
    test_name = test_traces_dir.parent.parent.parent.name

    # Create analysis folder with proper naming
    folder_name = f"{base_name}_vs_{test_name}_{device_pool}_{test_name_str}"
    analysis_folder = output_dir / folder_name
    analysis_folder.mkdir(parents=True, exist_ok=True)

    # Process traces once with optimized parallel processing
    print(f"Processing traces with parallel extraction and caching...")
    base_df, test_df = process_base_and_test_traces(
        base_traces_dir,
        test_traces_dir,
        max_workers=None,  # Use CPU count
        use_cache=True
    )
    print(f"✓ Processed {len(base_df)} base traces and {len(test_df)} test traces")

    # Save processed data to CSV for notebooks to use
    base_csv = analysis_folder / "base_metrics.csv"
    test_csv = analysis_folder / "test_metrics.csv"
    base_df.to_csv(base_csv, index=False)
    test_df.to_csv(test_csv, index=False)

    # Get template paths
    template_dir = Path(__file__).parent / "templates"
    batch_template = template_dir / "batch_aggregation_template.ipynb"
    blocked_template = template_dir / "blocked_bootstrap_template.ipynb"

    # Parameters to inject - now using pre-processed CSV files
    parameters = {
        'base_csv_path': str(base_csv.absolute()),
        'test_csv_path': str(test_csv.absolute()),
        'base_name': base_name,
        'test_name': test_name,
        'device_pool': device_pool,
        'test_type': test_name_str
    }

    # Define functions for parallel execution
    def execute_batch_aggregation():
        batch_executed = analysis_folder / "batch_aggregation_executed.ipynb"
        batch_html = analysis_folder / "batch_aggregation.html"

        try:
            pm.execute_notebook(
                str(batch_template),
                str(batch_executed),
                parameters=parameters,
                kernel_name='python3'
            )

            # Convert to HTML (hide code cells, show only outputs)
            subprocess.run([
                'python3', '-m', 'nbconvert',
                '--to', 'html',
                '--no-input',
                '--output', str(batch_html),
                str(batch_executed)
            ], check=True)

            # Clean up executed notebook only on success
            batch_executed.unlink()
            return batch_html
        except Exception as e:
            print(f"\nERROR: Batch aggregation notebook failed!")
            print(f"Executed notebook saved at: {batch_executed}")
            print(f"Check the notebook for diagnostic output.")
            raise

    def execute_blocked_bootstrap():
        blocked_executed = analysis_folder / "blocked_bootstrap_executed.ipynb"
        blocked_html = analysis_folder / "blocked_bootstrap.html"

        try:
            pm.execute_notebook(
                str(blocked_template),
                str(blocked_executed),
                parameters=parameters,
                kernel_name='python3'
            )

            # Convert to HTML (hide code cells, show only outputs)
            subprocess.run([
                'python3', '-m', 'nbconvert',
                '--to', 'html',
                '--no-input',
                '--output', str(blocked_html),
                str(blocked_executed)
            ], check=True)

            # Clean up executed notebook only on success
            blocked_executed.unlink()
            return blocked_html
        except Exception as e:
            print(f"\nERROR: Blocked bootstrap notebook failed!")
            print(f"Executed notebook saved at: {blocked_executed}")
            print(f"Check the notebook for diagnostic output.")
            raise

    # Execute both notebooks in parallel
    print(f"Executing notebooks in parallel...")
    batch_html = None
    blocked_html = None

    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both tasks
        batch_future = executor.submit(execute_batch_aggregation)
        blocked_future = executor.submit(execute_blocked_bootstrap)

        # Wait for both to complete and handle results
        futures = {
            batch_future: 'batch aggregation',
            blocked_future: 'blocked bootstrap'
        }

        for future in as_completed(futures):
            notebook_name = futures[future]
            try:
                result = future.result()
                if notebook_name == 'batch aggregation':
                    batch_html = result
                    print(f"✓ Batch aggregation completed")
                else:
                    blocked_html = result
                    print(f"✓ Blocked bootstrap completed")
            except Exception as e:
                print(f"✗ {notebook_name.capitalize()} failed: {e}")
                raise

    # Combine both reports into a single HTML with tabs
    print(f"Combining reports into tabbed HTML...")
    combined_html = analysis_folder / "analysis_report.html"
    combine_reports_with_tabs(
        batch_html,
        blocked_html,
        combined_html,
        base_name,
        test_name,
        device_pool,
        test_name_str
    )

    # Clean up individual HTML files (keep only combined version)
    batch_html.unlink()
    blocked_html.unlink()

    # Clean up temporary CSV files
    base_csv.unlink()
    test_csv.unlink()

    return combined_html
