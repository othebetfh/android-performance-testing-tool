# Android Performance Testing Tool

A Docker-based tool for automated Android app performance testing using AWS Device Farm and Perfetto trace analysis.

### Container Architecture

**Docker Images** (pre-built templates):
- `perftest:amd64` - For APK building (AAPT2 requires x86_64)
- `perftest:arm64` - For Perfetto analysis (optimized for ARM64)
- `perftest:latest` - Defaults to ARM64

### Platform Selection Logic

| Operation | On ARM64 Host (Apple Silicon) | On x86_64 Host |
|-----------|-------------------------------|----------------|
| Build APK | AMD64 (required for AAPT2) | AMD64 |
| Run Tests | ARM64 (faster) | AMD64 |
| Analyze | ARM64 (optimized) | AMD64 |
| Full Pipeline | ARM64 | AMD64 |

The system automatically detects your host architecture and selects the optimal container platform.

## Prerequisites

- Docker installed and running
- GitHub Personal Access Token with repository access
- AWS credentials with Device Farm permissions
- Property files and google-services.json for your Android app

## Setup

### 1. Configure Credentials

Create a `.env` file with your credentials:

```bash
# Copy template
cp .env.example .env

# Edit .env and add:
# AWS Credentials
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_SESSION_TOKEN=your_session_token  # Optional
AWS_REGION=us-west-2

# GitHub Credentials
GITHUB_TOKEN=your_github_token
GITHUB_USER=your_github_username
```

### 2. Add Property Files

Place your Android app property files in `config/properties/`:

```bash
config/properties/
├── dev.properties
├── prod.properties
└── google-services.json
```

### 3. Build Docker Images

Build both AMD64 and ARM64 images:

```bash
./scripts/build-all-platforms.sh
```

This creates:
- `perftest:amd64` - For APK building
- `perftest:arm64` - For Perfetto analysis
- `perftest:latest` - Defaults to ARM64

## Usage

### Interactive Mode

Launch the interactive menu (runs on host, launches containers per operation):

```bash
./scripts/perftest-interactive
```

**Menu options:**
1. **Build APK from source** - Always uses AMD64 container
2. **Run performance test on Device Farm** - Uses host-appropriate container
3. **Analyze performance test runs** - Uses host-appropriate container
4. **Full pipeline** (build → test → analyze) - Uses host-appropriate container
5. **Exit**

**How it works:**
- Menu runs on your host machine
- Each option launches the appropriate Docker container
- Container executes the operation and stops
- You return to the menu for the next operation

### Command-Line Mode

Run commands directly with automatic platform selection:

#### Build APK

```bash
./scripts/perftest build-apk \
  --branch main \
  --commit abc123 \
  --product-flavor dev \
  --build-type perf
```

#### Upload and Test

```bash
./scripts/perftest upload-and-test \
  --branch main \
  --commit abc123 \
  --project-arn arn:aws:devicefarm:us-west-2:xxx:project:xxx \
  --device-pool-arn arn:aws:devicefarm:us-west-2:xxx:devicepool:xxx \
  --test-name coldStartup \
  --num-iterations 50
```

#### Analyze Results

```bash
./scripts/perftest analyze \
  --base-branch main \
  --base-commit abc123 \
  --test-branch feature \
  --test-commit def456 \
  --device-pool "Samsung Galaxy S22 - OS13" \
  --test-name coldStartup
```

#### Full Pipeline

```bash
./scripts/perftest full-pipeline \
  --base-branch main \
  --base-commit abc123 \
  --test-branch feature \
  --test-commit def456 \
  --project-arn arn:aws:devicefarm:us-west-2:xxx:project:xxx \
  --device-pool-arn arn:aws:devicefarm:us-west-2:xxx:devicepool:xxx \
  --test-name coldStartup \
  --num-iterations 50
```

## Environment Variables

All credentials are automatically loaded from the `.env` file. Required variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `AWS_ACCESS_KEY_ID` | AWS access key | Yes |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | Yes |
| `AWS_SESSION_TOKEN` | AWS session token | No |
| `AWS_REGION` | AWS region (e.g., us-west-2) | Yes |
| `GITHUB_TOKEN` | GitHub personal access token | Yes |
| `GITHUB_USER` | GitHub username | Yes |

## Project Structure

```
performance-testing-app/
├── config/
│   ├── default.yaml           # Default configuration
│   └── properties/             # Android properties and configuration files
├── output/                     # Test results and analysis (git-ignored)
├── perftest/                   # Python package
│   ├── analysis/              # Trace analysis modules
│   ├── build/                 # APK building modules
│   ├── commands/              # Command implementations
│   ├── interactive.py         # Interactive mode functions
│   ├── container_cli.py       # Container entry point
│   └── config.py              # Configuration management
├── scripts/
│   ├── build-all-platforms.sh    # Build both Docker images
│   ├── build-docker.sh           # Build single platform
│   ├── perftest                  # Command-line entry point
│   └── perftest-interactive      # Interactive menu (host-based)
├── queries/                    # SQL queries for Perfetto analysis
├── .env                       # Credentials (create from .env.example)
├── .env.example              # Template for .env
├── Dockerfile                # Docker image definition
└── README.md                # This file
```

## Development

### Building Images

```bash
# Build both platforms
./scripts/build-all-platforms.sh

# Build single platform
DOCKER_PLATFORM_OVERRIDE=linux/amd64 ./scripts/build-docker.sh
DOCKER_PLATFORM_OVERRIDE=linux/arm64 ./scripts/build-docker.sh
```

### Testing in Containers

```bash
# Run ARM64 container with shell
docker run --rm -it \
  -v "$(pwd)/output:/workspace/output" \
  -v "$(pwd)/config:/workspace/config" \
  perftest:arm64 bash

# Run AMD64 container with shell
docker run --rm -it \
  -v "$(pwd)/output:/workspace/output" \
  -v "$(pwd)/config:/workspace/config" \
  perftest:amd64 bash
```

### Rebuilding After Code Changes

After modifying Python code:

```bash
# Rebuild both images
./scripts/build-all-platforms.sh

# Or rebuild single platform
DOCKER_PLATFORM_OVERRIDE=linux/amd64 ./scripts/build-docker.sh
```

## Advanced Usage

### Custom Configuration

Override default configuration by setting environment variables:

```bash
# Set custom output directory
export PERFTEST_OUTPUT_DIR=/custom/output

# Set log level
export PERFTEST_LOG_LEVEL=DEBUG

# Set custom Perfetto path (in container)
export PERFETTO_PATH=/custom/trace_processor_shell
```

### Cached Builds

The tool caches built APKs per commit. If APKs exist for a branch/commit combination, they're reused instead of rebuilding:

```
✓ Using cached build: feature-branch@abc12345
```

To force rebuild, delete the cached directory:

```bash
rm -rf output/<branch>_<commit>/apks/
```

## License

[Your License]

## Contributing

[Your Contributing Guidelines]
