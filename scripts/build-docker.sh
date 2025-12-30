#!/usr/bin/env bash
#
# Build Docker image for perftest
#
# Automatically detects the host architecture and builds for the appropriate platform:
#   - arm64/aarch64 → linux/arm64 (Apple Silicon, AWS Graviton)
#   - x86_64/amd64  → linux/amd64 (Intel/AMD, standard EC2)
#

set -e

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Default image name and tag
IMAGE_NAME="${IMAGE_NAME:-perftest}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Detect host architecture
HOST_ARCH="$(uname -m)"
case "${HOST_ARCH}" in
    arm64|aarch64)
        DOCKER_PLATFORM="linux/arm64"
        ARCH_NAME="ARM64 (Apple Silicon / AWS Graviton)"
        ;;
    x86_64|amd64)
        DOCKER_PLATFORM="linux/amd64"
        ARCH_NAME="x86_64 (Intel/AMD / Standard EC2)"
        ;;
    *)
        echo "Error: Unsupported architecture: ${HOST_ARCH}"
        echo "Supported: arm64, aarch64, x86_64, amd64"
        exit 1
        ;;
esac

# Allow manual override via environment variable
if [ -n "${DOCKER_PLATFORM_OVERRIDE}" ]; then
    echo "Platform override detected: ${DOCKER_PLATFORM_OVERRIDE}"
    DOCKER_PLATFORM="${DOCKER_PLATFORM_OVERRIDE}"
fi

echo "======================================"
echo "Building perftest Docker image"
echo "======================================"
echo "Host architecture: ${HOST_ARCH}"
echo "Docker platform: ${DOCKER_PLATFORM}"
echo "Architecture: ${ARCH_NAME}"
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "Project directory: ${PROJECT_DIR}"
echo ""

# Build the Docker image
docker build \
    --platform "${DOCKER_PLATFORM}" \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    -f "${PROJECT_DIR}/Dockerfile" \
    "${PROJECT_DIR}"

echo ""
echo "======================================"
echo "Docker image built successfully!"
echo "======================================"
echo ""
echo "Run with:"
echo "  ./scripts/perftest --help"
echo ""
echo "For interactive mode:"
echo "  ./scripts/perftest"
