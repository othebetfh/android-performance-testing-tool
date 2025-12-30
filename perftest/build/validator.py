"""APK validation utilities."""

import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

from perftest.logger import get_logger
from perftest.utils.exceptions import ValidationError

logger = get_logger(__name__)


def validate_apk(apk_path: Path, android_home: Optional[str] = None) -> Dict[str, any]:
    """
    Validate an APK file.

    Args:
        apk_path: Path to APK file
        android_home: Path to Android SDK (defaults to ANDROID_HOME env var)

    Returns:
        Dict containing APK information

    Raises:
        ValidationError: If APK is invalid
    """
    logger.debug(f"Validating APK: {apk_path}")

    # Check file exists
    if not apk_path.exists():
        raise ValidationError(f"APK file not found: {apk_path}")

    # Check file is readable
    if not os.access(apk_path, os.R_OK):
        raise ValidationError(f"APK file is not readable: {apk_path}")

    # Check file size
    file_size = apk_path.stat().st_size
    if file_size == 0:
        raise ValidationError(f"APK file is empty: {apk_path}")

    logger.debug(f"  File size: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")

    # Try to get APK info using aapt if available
    apk_info = {
        'path': str(apk_path),
        'name': apk_path.name,
        'size_bytes': file_size,
        'size_mb': round(file_size / (1024 * 1024), 2),
    }

    # Try to use aapt to get more info
    try:
        android_home = android_home or os.getenv('ANDROID_HOME', '/opt/android-sdk')
        aapt_path = Path(android_home) / 'build-tools'

        # Find aapt in build-tools (try multiple versions)
        aapt_binary = None
        if aapt_path.exists():
            for build_tools_dir in sorted(aapt_path.iterdir(), reverse=True):
                potential_aapt = build_tools_dir / 'aapt'
                if potential_aapt.exists():
                    aapt_binary = potential_aapt
                    break

        if aapt_binary and aapt_binary.exists():
            logger.debug(f"Using aapt: {aapt_binary}")
            result = subprocess.run(
                [str(aapt_binary), 'dump', 'badging', str(apk_path)],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Parse aapt output
                output = result.stdout
                apk_info.update(_parse_aapt_output(output))
                logger.debug(f"  Package: {apk_info.get('package_name', 'unknown')}")
                logger.debug(f"  Version: {apk_info.get('version_name', 'unknown')} ({apk_info.get('version_code', 'unknown')})")
            else:
                logger.warning(f"aapt failed: {result.stderr}")
        else:
            logger.debug("aapt not found, skipping detailed APK info")

    except Exception as e:
        logger.debug(f"Could not get detailed APK info: {e}")

    logger.info(f"APK validation passed: {apk_path.name}")
    return apk_info


def _parse_aapt_output(output: str) -> Dict[str, str]:
    """
    Parse aapt dump badging output.

    Args:
        output: aapt command output

    Returns:
        Dict containing parsed information
    """
    info = {}

    for line in output.splitlines():
        line = line.strip()

        if line.startswith('package:'):
            # Extract package info
            # Format: package: name='com.example.app' versionCode='1' versionName='1.0'
            parts = line.split()
            for part in parts:
                if part.startswith("name='"):
                    info['package_name'] = part.split("'")[1]
                elif part.startswith("versionCode='"):
                    info['version_code'] = part.split("'")[1]
                elif part.startswith("versionName='"):
                    info['version_name'] = part.split("'")[1]

        elif line.startswith('application-label:'):
            # Extract app name
            # Format: application-label:'App Name'
            if ':' in line:
                app_name = line.split(':', 1)[1].strip().strip("'")
                info['app_name'] = app_name

        elif line.startswith('sdkVersion:'):
            # Extract min SDK version
            # Format: sdkVersion:'21'
            if ':' in line:
                sdk_version = line.split(':', 1)[1].strip().strip("'")
                info['min_sdk'] = sdk_version

        elif line.startswith('targetSdkVersion:'):
            # Extract target SDK version
            # Format: targetSdkVersion:'34'
            if ':' in line:
                sdk_version = line.split(':', 1)[1].strip().strip("'")
                info['target_sdk'] = sdk_version

    return info


def validate_apk_pair(app_apk: Path, test_apk: Path, android_home: Optional[str] = None) -> Dict[str, Dict]:
    """
    Validate a pair of app and test APKs.

    Args:
        app_apk: Path to application APK
        test_apk: Path to instrumentation test APK
        android_home: Path to Android SDK

    Returns:
        Dict containing validation results for both APKs

    Raises:
        ValidationError: If either APK is invalid
    """
    logger.info("Validating APK pair...")

    # Validate app APK
    app_info = validate_apk(app_apk, android_home)

    # Validate test APK
    test_info = validate_apk(test_apk, android_home)

    # Check that test APK package matches app APK (with .test suffix)
    app_package = app_info.get('package_name')
    test_package = test_info.get('package_name')

    if app_package and test_package:
        expected_test_package = f"{app_package}.test"
        if test_package != expected_test_package:
            logger.warning(
                f"Test APK package name '{test_package}' does not match "
                f"expected '{expected_test_package}' (based on app package '{app_package}')"
            )

    logger.info("APK pair validation passed")

    return {
        'app': app_info,
        'test': test_info
    }
