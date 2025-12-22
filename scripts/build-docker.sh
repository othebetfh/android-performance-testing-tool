#!/usr/bin/env bash
#
# Build Docker image for perftest
#

set -e

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Default image name and tag
IMAGE_NAME="${IMAGE_NAME:-perftest}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "======================================"
echo "Building perftest Docker image"
echo "======================================"
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "Project directory: ${PROJECT_DIR}"
echo ""

# Build the Docker image
docker build \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    -f "${PROJECT_DIR}/Dockerfile" \
    "${PROJECT_DIR}"

echo ""
echo "======================================"
echo "Docker image built successfully!"
echo "======================================"
echo ""
echo "Run with:"
echo "  docker run --rm ${IMAGE_NAME}:${IMAGE_TAG} --help"
echo ""
echo "Or use scripts/run-docker.sh for easier usage"
