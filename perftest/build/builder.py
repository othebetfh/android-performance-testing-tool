"""Gradle build operations for Android projects."""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from perftest.logger import get_logger
from perftest.utils.exceptions import BuildError

logger = get_logger(__name__)


class GradleBuilder:
    """Handles Gradle build operations for Android projects."""

    def __init__(
        self,
        project_dir: Path,
        android_home: Optional[str] = None,
        java_home: Optional[str] = None,
        properties_file: Optional[Path] = None,
        google_services_file: Optional[Path] = None,
        github_user: Optional[str] = None,
        github_token: Optional[str] = None
    ):
        """
        Initialize Gradle builder.

        Args:
            project_dir: Path to Android project directory
            android_home: Path to Android SDK (defaults to ANDROID_HOME env var)
            java_home: Path to Java installation (defaults to JAVA_HOME env var)
            properties_file: Path to properties file to copy to project root
            google_services_file: Path to google-services.json file to copy to app folder
            github_user: GitHub username for Maven authentication
            github_token: GitHub token for Maven authentication
        """
        self.project_dir = project_dir
        self.android_home = android_home or os.getenv('ANDROID_HOME', '/opt/android-sdk')
        self.java_home = java_home or os.getenv('JAVA_HOME', '/usr/lib/jvm/java-17-openjdk')
        self.properties_file = properties_file
        self.google_services_file = google_services_file
        self.github_user = github_user
        self.github_token = github_token

        # Validate project directory
        if not self.project_dir.exists():
            raise BuildError(f"Project directory does not exist: {project_dir}")

        # Check for gradlew
        self.gradlew = self.project_dir / 'gradlew'
        if not self.gradlew.exists():
            raise BuildError(f"gradlew not found in {project_dir}")

        # Make gradlew executable
        self.gradlew.chmod(0o755)

        # Create local.properties with SDK path
        self._create_local_properties()

        # Create gradle.properties with memory settings
        self._create_gradle_properties()

        logger.debug(f"Gradle builder initialized")
        logger.debug(f"  Project dir: {project_dir}")
        logger.debug(f"  ANDROID_HOME: {self.android_home}")
        logger.debug(f"  JAVA_HOME: {self.java_home}")
        if self.properties_file:
            logger.debug(f"  Properties file: {self.properties_file}")

    def _create_local_properties(self) -> None:
        """
        Create local.properties file with Android SDK location.
        This file is required by Android Gradle Plugin.
        """
        local_props_path = self.project_dir / 'local.properties'

        # Always create/overwrite with SDK path
        logger.info(f"Creating local.properties with sdk.dir={self.android_home}")

        with open(local_props_path, 'w') as f:
            f.write(f"sdk.dir={self.android_home}\n")

        logger.debug(f"local.properties created at {local_props_path}")

    def _create_gradle_properties(self) -> None:
        """
        Create gradle.properties file with JVM memory settings.
        This prevents OOM errors during DEX merging and other memory-intensive tasks.
        """
        gradle_props_path = self.project_dir / 'gradle.properties'

        # Check if file already exists
        if gradle_props_path.exists():
            logger.debug("gradle.properties already exists, appending memory settings")
            with open(gradle_props_path, 'r') as f:
                existing_content = f.read()

            # Check if jvmargs already set
            if 'org.gradle.jvmargs' not in existing_content:
                with open(gradle_props_path, 'a') as f:
                    f.write("\n# JVM memory settings for build\n")
                    f.write("org.gradle.jvmargs=-Xmx4g -XX:MaxMetaspaceSize=512m -XX:+HeapDumpOnOutOfMemoryError\n")
                    f.write("\n# Kotlin daemon settings\n")
                    f.write("kotlin.daemon.jvm.options=-Xmx1g\n")
                    f.write("\n# Limit parallel workers for memory efficiency\n")
                    f.write("org.gradle.workers.max=2\n")
                logger.info("Added JVM memory settings to existing gradle.properties")
        else:
            logger.info("Creating gradle.properties with JVM memory settings")
            with open(gradle_props_path, 'w') as f:
                f.write("# JVM memory settings for build\n")
                f.write("org.gradle.jvmargs=-Xmx4g -XX:MaxMetaspaceSize=512m -XX:+HeapDumpOnOutOfMemoryError\n")
                f.write("\n# Gradle daemon settings\n")
                f.write("org.gradle.daemon=false\n")
                f.write("org.gradle.parallel=false\n")
                f.write("org.gradle.caching=true\n")
                f.write("org.gradle.vfs.watch=false\n")
                f.write("\n# Limit parallel workers for memory efficiency\n")
                f.write("org.gradle.workers.max=2\n")

        logger.debug(f"gradle.properties configured at {gradle_props_path}")

    def _copy_properties_file(self) -> None:
        """
        Copy properties file into project root.
        """
        if not self.properties_file:
            raise BuildError("Properties file is required but not provided")

        if not self.properties_file.exists():
            raise BuildError(f"Properties file not found: {self.properties_file}")

        # Copy to project root with the same filename
        dest = self.project_dir / self.properties_file.name
        logger.info(f"Copying {self.properties_file.name} to project root")

        import shutil
        shutil.copy2(self.properties_file, dest)

        logger.debug(f"Properties file copied: {dest}")

    def _copy_google_services_file(self) -> None:
        """
        Copy google-services.json file into app folder.
        """
        if not self.google_services_file:
            raise BuildError("Google services file is required but not provided")

        if not self.google_services_file.exists():
            raise BuildError(f"Google services file not found: {self.google_services_file}")

        # Copy to app folder
        app_dir = self.project_dir / 'app'
        if not app_dir.exists():
            raise BuildError(f"App directory not found: {app_dir}")

        dest = app_dir / 'google-services.json'
        logger.info(f"Copying google-services.json to app folder")

        import shutil
        shutil.copy2(self.google_services_file, dest)

        logger.debug(f"Google services file copied: {dest}")

    def build(
        self,
        product_flavor: str = "dev",
        build_type: str = "perf",
        gradle_options: Optional[List[str]] = None
    ) -> Dict[str, Path]:
        """
        Build Android APKs with specified product flavor and build type.

        Args:
            product_flavor: Product flavor (e.g., "dev", "prod")
            build_type: Build type (e.g., "debug", "release", "perf")
            gradle_options: Additional Gradle options

        Returns:
            Dict[str, Path]: Paths to built APKs (app and test)

        Raises:
            BuildError: If build fails
        """
        # Copy properties file to project root
        self._copy_properties_file()

        # Copy google-services.json to app folder
        self._copy_google_services_file()

        # Capitalize first letter for Gradle task names
        Flavor = product_flavor.capitalize()
        BuildType = build_type.capitalize()

        # Build task names
        # App APK from root project
        app_task = f"assemble{Flavor}{BuildType}"
        # Test APK from benchmark module
        test_task = f":benchmark:assemble{Flavor}{BuildType}"

        logger.info(f"Building APKs with flavor '{product_flavor}' and type '{build_type}'")
        logger.info(f"  App task: {app_task}")
        logger.info(f"  Test task: {test_task}")

        # Default Gradle options
        if gradle_options is None:
            gradle_options = [
                '--no-daemon',
                '--stacktrace',
            ]

        # Build app APK
        logger.info("Building application APK...")
        self._execute_gradle([app_task] + gradle_options)

        # Build test APK
        logger.info("Building instrumentation test APK...")
        self._execute_gradle([test_task] + gradle_options)

        # Locate built APKs
        logger.info("Locating built APKs...")
        apks = self._locate_apks(product_flavor, build_type)

        if not apks.get('app'):
            raise BuildError("Application APK not found after build")
        if not apks.get('test'):
            raise BuildError("Test APK not found after build")

        logger.info("Build completed successfully")
        logger.info(f"  App APK: {apks['app'].name}")
        logger.info(f"  Test APK: {apks['test'].name}")

        return apks

    def _execute_gradle(self, tasks: List[str]) -> None:
        """
        Execute Gradle command with given tasks.

        Args:
            tasks: List of Gradle tasks and options

        Raises:
            BuildError: If Gradle execution fails
        """
        # Set up environment
        env = os.environ.copy()
        env['ANDROID_HOME'] = self.android_home
        env['ANDROID_SDK_ROOT'] = self.android_home
        env['JAVA_HOME'] = self.java_home
        env['PATH'] = f"{self.android_home}/cmdline-tools/latest/bin:{self.android_home}/platform-tools:{env.get('PATH', '')}"

        # Set GitHub Maven authentication if provided
        if self.github_user:
            env['GITHUB_USER'] = self.github_user
        if self.github_token:
            env['GITHUB_TOKEN'] = self.github_token

        # Build command
        cmd = [str(self.gradlew)] + tasks

        logger.debug(f"Executing: {' '.join(cmd)}")
        logger.debug(f"Working directory: {self.project_dir}")

        # Execute Gradle with real-time output
        try:
            process = subprocess.Popen(
                cmd,
                cwd=self.project_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            # Stream output line by line
            if process.stdout:
                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        # Always print to stdout so user sees it in real-time
                        print(f"  {line}")

                        # Also log at appropriate level for log files
                        if 'error' in line.lower() or 'failed' in line.lower():
                            logger.error(f"  {line}")
                        elif 'warning' in line.lower():
                            logger.warning(f"  {line}")
                        else:
                            logger.debug(f"  {line}")

            # Wait for process to complete
            return_code = process.wait()

            if return_code != 0:
                raise BuildError(
                    f"Gradle build failed with exit code {return_code}. "
                    f"Check logs for details."
                )

        except subprocess.SubprocessError as e:
            raise BuildError(f"Failed to execute Gradle: {e}")
        except Exception as e:
            raise BuildError(f"Unexpected error during Gradle execution: {e}")

    def _locate_apks(self, product_flavor: str, build_type: str) -> Dict[str, Path]:
        """
        Locate built APK files in the project directory.

        Args:
            product_flavor: Product flavor used in build
            build_type: Build type used in build

        Returns:
            Dict[str, Path]: Paths to app and test APKs
        """
        apks = {}

        # Common APK output directories in Android projects
        output_dirs = [
            self.project_dir / "app" / "build" / "outputs" / "apk",
            self.project_dir / "benchmark" / "build" / "outputs" / "apk",
            self.project_dir / "build" / "outputs" / "apk",
        ]

        # Search for app APK
        # Pattern: app-{flavor}-{buildType}.apk or similar
        for output_dir in output_dirs:
            if not output_dir.exists():
                continue

            # Search recursively for APKs
            for apk_file in output_dir.rglob("*.apk"):
                apk_name_lower = apk_file.name.lower()

                # Skip test APKs in this pass
                if 'androidtest' in apk_name_lower or '-test' in apk_name_lower:
                    continue

                # Check if this APK matches our flavor and type
                if product_flavor.lower() in apk_name_lower and build_type.lower() in apk_name_lower:
                    if not apks.get('app'):
                        apks['app'] = apk_file
                        logger.debug(f"Found app APK: {apk_file}")

        # Search for test APK from benchmark module
        # Pattern: benchmark-{flavor}-{buildType}.apk
        benchmark_dir = self.project_dir / "benchmark" / "build" / "outputs" / "apk"
        if benchmark_dir.exists():
            for apk_file in benchmark_dir.rglob("*.apk"):
                apk_name_lower = apk_file.name.lower()

                # Look for benchmark APKs matching our flavor and type
                if 'benchmark' in apk_name_lower:
                    if product_flavor.lower() in apk_name_lower and build_type.lower() in apk_name_lower:
                        if not apks.get('test'):
                            apks['test'] = apk_file
                            logger.debug(f"Found test APK: {apk_file}")

        return apks

    def clean(self) -> None:
        """
        Clean the Gradle build.

        Raises:
            BuildError: If clean fails
        """
        logger.info("Cleaning Gradle build...")
        self._execute_gradle(['clean'])
