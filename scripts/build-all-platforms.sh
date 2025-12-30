#!/usr/bin/env bash
#
# Build Docker images for both platforms
# - amd64: For APK building (AAPT2 compatibility)
# - arm64: For Perfetto analysis (native performance)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "======================================"
echo "Building Multi-Platform Docker Images"
echo "======================================"
echo ""

# Build AMD64 image for APK building
echo "Building AMD64 image for APK builds..."
DOCKER_PLATFORM_OVERRIDE=linux/amd64 "${SCRIPT_DIR}/build-docker.sh"
docker tag perftest:latest perftest:amd64
echo "✓ Tagged as perftest:amd64"
echo ""

# Build ARM64 image for analysis
echo "Building ARM64 image for Perfetto analysis..."
DOCKER_PLATFORM_OVERRIDE=linux/arm64 "${SCRIPT_DIR}/build-docker.sh"
docker tag perftest:latest perftest:arm64
echo "✓ Tagged as perftest:arm64"
echo ""

# Tag latest as arm64 (most common use case)
docker tag perftest:arm64 perftest:latest
echo "✓ perftest:latest → perftest:arm64 (default)"
echo ""

echo "======================================"
echo "Build Complete!"
echo "======================================"
echo ""
echo "Available images:"
echo "  perftest:amd64  - Use for APK builds"
echo "  perftest:arm64  - Use for analysis"
echo "  perftest:latest - Defaults to arm64"
echo ""
echo "Verify with:"
echo "  docker images | grep perftest"
