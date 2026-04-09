"""Baseline profile merging for Android baseline profiles."""

import re
from pathlib import Path
from typing import List

from perftest.logger import get_logger

logger = get_logger(__name__)

# Flags in canonical output order
_FLAG_ORDER = ['H', 'S', 'P']


def _parse_line(line: str):
    """
    Parse a baseline profile line into (flags, entry).

    Baseline profile lines have the format:
        [HSP]*L<class/method path>

    Where H (hot), S (startup), P (post-startup) are optional method flags
    and the entry begins with L (the JVM class type prefix).

    Returns:
        Tuple of (set of flag characters, entry string), or (None, None) for
        blank lines and comments.
    """
    line = line.strip()
    if not line or line.startswith('#'):
        return None, None

    match = re.match(r'^([HSP]*)(.+)$', line)
    if match:
        return set(match.group(1)), match.group(2)

    return None, None


def merge_baseline_profiles(profile_files: List[Path], output_path: Path) -> Path:
    """
    Merge multiple baseline profile files into a single deduplicated file.

    For entries that appear across multiple files with different flags, the
    flags are unioned so no coverage information is lost. Entries with
    identical flags and paths are deduplicated.

    Args:
        profile_files: List of paths to individual baseline profile files
        output_path: Path to write the merged profile

    Returns:
        Path to the merged profile file
    """
    merged: dict[str, set[str]] = {}  # entry -> union of flags across all files

    for profile_file in profile_files:
        logger.info(f"Reading: {profile_file.name}")
        with open(profile_file, 'r') as f:
            for line in f:
                flags, entry = _parse_line(line)
                if entry is None:
                    continue
                if entry not in merged:
                    merged[entry] = set()
                merged[entry].update(flags)

    lines = []
    for entry in sorted(merged.keys()):
        flag_str = ''.join(f for f in _FLAG_ORDER if f in merged[entry])
        lines.append(f"{flag_str}{entry}\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.writelines(lines)

    logger.info(
        f"Merged {len(profile_files)} file(s) → {len(lines)} unique entries"
    )
    return output_path
