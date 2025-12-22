"""Custom exceptions for the perftest package."""


class PerfTestError(Exception):
    """Base exception for all perftest errors."""
    pass


class BuildError(PerfTestError):
    """Raised when APK build fails."""
    pass


class CloneError(PerfTestError):
    """Raised when git clone/checkout fails."""
    pass


class ValidationError(PerfTestError):
    """Raised when APK validation fails."""
    pass


class DeviceFarmError(PerfTestError):
    """Raised for AWS Device Farm related issues."""
    pass


class UploadError(DeviceFarmError):
    """Raised when APK upload to Device Farm fails."""
    pass


class TestRunError(DeviceFarmError):
    """Raised when Device Farm test run fails."""
    pass


class DownloadError(DeviceFarmError):
    """Raised when artifact download fails."""
    pass


class PerfettoError(PerfTestError):
    """Raised for Perfetto trace processor issues."""
    pass


class QueryError(PerfettoError):
    """Raised when Perfetto query execution fails."""
    pass


class AnalysisError(PerfettoError):
    """Raised when trace analysis fails."""
    pass


class ConfigurationError(PerfTestError):
    """Raised when configuration is invalid or missing."""
    pass
