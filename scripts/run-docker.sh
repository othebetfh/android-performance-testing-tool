#!/usr/bin/env bash
#
# Run perftest Docker container
#

set -e

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Default image name and tag
IMAGE_NAME="${IMAGE_NAME:-perftest}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Output directory
OUTPUT_DIR="${PROJECT_DIR}/output"
mkdir -p "${OUTPUT_DIR}"

# Check if .env file exists
ENV_FILE="${PROJECT_DIR}/.env"
if [ ! -f "${ENV_FILE}" ]; then
    echo "Warning: .env file not found at ${ENV_FILE}"
    echo "Please create one from .env.example and set your credentials"
    echo ""
fi

# Load .env file if it exists
if [ -f "${ENV_FILE}" ]; then
    set -a
    source "${ENV_FILE}"
    set +a
fi

# Check required environment variables
REQUIRED_VARS=("GITHUB_PAT" "AWS_ACCESS_KEY_ID" "AWS_SECRET_ACCESS_KEY" "AWS_DEVICEFARM_PROJECT_ARN")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("${var}")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo "Error: Missing required environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - ${var}"
    done
    echo ""
    echo "Please set them in .env file or export them in your shell"
    exit 1
fi

echo "======================================"
echo "Running perftest Docker container"
echo "======================================"
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "Output dir: ${OUTPUT_DIR}"
echo ""

# Run Docker container
docker run --rm -it \
    -v "${OUTPUT_DIR}:/workspace/output" \
    -e GITHUB_PAT="${GITHUB_PAT}" \
    -e AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
    -e AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
    -e AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}" \
    -e AWS_DEVICEFARM_PROJECT_ARN="${AWS_DEVICEFARM_PROJECT_ARN}" \
    -e DEVICEFARM_DEVICE_POOL="${DEVICEFARM_DEVICE_POOL:-Top Devices}" \
    "${IMAGE_NAME}:${IMAGE_TAG}" \
    "$@"
