"""Configuration management for perftest."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from perftest.utils.exceptions import ConfigurationError


# Load environment variables from .env file if it exists
load_dotenv()


class BuildConfig(BaseModel):
    """Build configuration."""
    repository_url: str = Field(description="GitHub repository URL (required)")
    default_branch: str = Field(default="main")
    gradle_options: list[str] = Field(default=["--no-daemon", "--stacktrace"])


class DeviceFarmConfig(BaseModel):
    """AWS Device Farm configuration."""
    project_arn: str = Field(default="")
    region: str = Field(default="us-west-2")
    test_timeout: int = Field(default=3600)
    test_type: str = Field(default="INSTRUMENTATION")
    traces_pattern: str = Field(default="*.perfetto-trace")


class AnalysisConfig(BaseModel):
    """Perfetto analysis configuration."""
    trace_processor_path: str = Field(default="/usr/local/bin/trace_processor_shell")


class OutputConfig(BaseModel):
    """Output configuration."""
    base_dir: str = Field(default="./output")
    cleanup_on_success: bool = Field(default=False)


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field(default="INFO")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_enabled: bool = Field(default=True)
    file_path: str = Field(default="./output/perftest.log")


class Config(BaseModel):
    """Main configuration model."""
    build: BuildConfig = Field(default_factory=BuildConfig)
    devicefarm: DeviceFarmConfig = Field(default_factory=DeviceFarmConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class ConfigManager:
    """Configuration manager with support for YAML files and environment variables."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Optional path to YAML configuration file.
                        If not provided, loads from config/default.yaml
        """
        # Use default.yaml if no config path provided
        if config_path is None:
            # Try container path first (mounted at /workspace/config)
            container_config = Path("/workspace/config/default.yaml")
            if container_config.exists():
                config_path = container_config
            else:
                # Fall back to relative path for local development
                local_config = Path(__file__).parent.parent / "config" / "default.yaml"
                if local_config.exists():
                    config_path = local_config

        self.config_path = config_path
        self._config: Optional[Config] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file and environment variables."""
        config_dict: Dict[str, Any] = {}

        # Load from YAML file if provided
        if self.config_path and self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    config_dict = yaml.safe_load(f) or {}
            except Exception as e:
                raise ConfigurationError(f"Failed to load config file {self.config_path}: {e}")

        # Override with environment variables
        config_dict = self._apply_env_overrides(config_dict)

        # Validate and create config object
        try:
            self._config = Config(**config_dict)
        except Exception as e:
            raise ConfigurationError(f"Invalid configuration: {e}")

    def _apply_env_overrides(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration."""
        # Device Farm overrides
        if "AWS_DEVICEFARM_PROJECT_ARN" in os.environ:
            config_dict.setdefault("devicefarm", {})["project_arn"] = os.environ["AWS_DEVICEFARM_PROJECT_ARN"]
        if "AWS_DEFAULT_REGION" in os.environ:
            config_dict.setdefault("devicefarm", {})["region"] = os.environ["AWS_DEFAULT_REGION"]

        # Analysis overrides
        if "PERFETTO_PATH" in os.environ:
            config_dict.setdefault("analysis", {})["trace_processor_path"] = os.environ["PERFETTO_PATH"]

        # Output overrides
        if "PERFTEST_OUTPUT_DIR" in os.environ:
            config_dict.setdefault("output", {})["base_dir"] = os.environ["PERFTEST_OUTPUT_DIR"]

        # Logging overrides
        if "PERFTEST_LOG_LEVEL" in os.environ:
            config_dict.setdefault("logging", {})["level"] = os.environ["PERFTEST_LOG_LEVEL"]

        return config_dict

    @property
    def config(self) -> Config:
        """Get the configuration object."""
        if self._config is None:
            raise ConfigurationError("Configuration not loaded")
        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by dot-separated key path.

        Args:
            key: Dot-separated key path (e.g., "build.repository_url")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        try:
            obj = self.config
            for part in key.split("."):
                obj = getattr(obj, part)
            return obj
        except (AttributeError, KeyError):
            return default

    def get_output_dir(self, subdir: Optional[str] = None) -> Path:
        """
        Get output directory path.

        Args:
            subdir: Optional subdirectory name

        Returns:
            Path: Full path to output directory
        """
        base = Path(self.config.output.base_dir)

        if subdir:
            return base / subdir

        return base

    def ensure_output_dirs(self) -> None:
        """Create base output directory if it doesn't exist."""
        self.get_output_dir().mkdir(parents=True, exist_ok=True)
