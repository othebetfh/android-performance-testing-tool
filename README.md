# Android Performance Testing Tool (perftest)

A Docker-based tool for automated Android app performance testing using AWS Device Farm and Perfetto trace analysis.

## Features

- **Automated APK Building**: Clone and build APKs from specific commits of private GitHub repositories
- **AWS Device Farm Integration**: Upload APKs, run instrumentation tests, and download results
- **Perfetto Trace Analysis**: Analyze performance traces with SQL queries and pandas
- **Docker-based**: Fully containerized with Android SDK, Python 3.11, and Perfetto tools
- **CLI Interface**: Easy-to-use command-line interface with rich output

## Quick Start

### Prerequisites

- Docker installed
- GitHub Personal Access Token with access to worldcoin/wld-android repo
- AWS credentials with Device Farm permissions
- AWS Device Farm project ARN

### 1. Clone and Setup

```bash
git clone <your-repo>
cd performance-testing-app

# Copy environment template and fill in your credentials
cp .env.example .env
# Edit .env and add your credentials
```

### 2. Build Docker Image

```bash
./scripts/build-docker.sh
```

This will create a Docker image with:
- Ubuntu 22.04
- Android SDK (API 34, Build Tools 34.0.0)
- Java 17
- Python 3.11
- Perfetto trace processor
- perftest CLI tool

### 3. Validate Environment

```bash
./scripts/run-docker.sh validate
```

This checks that all dependencies and environment variables are configured correctly.

### 4. Run Tests

```bash
# Build APKs from a commit
./scripts/run-docker.sh build --commit <commit-hash>

# Run tests on Device Farm (using pre-built APKs)
./scripts/run-docker.sh test \
  --app-apk /workspace/output/apks/app-debug.apk \
  --test-apk /workspace/output/apks/app-debug-androidTest.apk

# Analyze Perfetto traces
./scripts/run-docker.sh analyze --trace-dir /workspace/output/traces

# Run complete pipeline
./scripts/run-docker.sh full-run --commit <commit-hash>
```

## CLI Commands

### `perftest build`
Build APKs from source repository.

```bash
perftest build --commit <hash> [--build-type debug|release]
```

**Options:**
- `--commit`: Git commit hash to build (required)
- `--github-token`: GitHub PAT (or set GITHUB_PAT env var)
- `--build-type`: Build type - debug or release (default: debug)

**Outputs:**
- `output/apks/app-debug.apk`
- `output/apks/app-debug-androidTest.apk`

### `perftest test`
Run tests on AWS Device Farm.

```bash
perftest test \
  --app-apk <path> \
  --test-apk <path> \
  [--device-pool <name>] \
  [--run-name <name>]
```

**Options:**
- `--app-apk`: Path to app APK (required)
- `--test-apk`: Path to test APK (required)
- `--device-pool`: Device pool name or ARN
- `--project-arn`: Device Farm project ARN (or set AWS_DEVICEFARM_PROJECT_ARN env var)
- `--run-name`: Test run identifier
- `--timeout`: Test timeout in seconds (default: 3600)
- `--download-traces/--no-download-traces`: Download Perfetto traces (default: true)
- `--download-artifacts/--no-download-artifacts`: Download test artifacts (default: true)

**Outputs:**
- Test run results
- `output/traces/*.perfetto-trace`
- `output/artifacts/` (logs, videos, screenshots)

### `perftest analyze`
Analyze Perfetto trace files.

```bash
perftest analyze \
  --trace-file <path> \
  [--query <name>] \
  [--output-format csv|json|html]
```

**Options:**
- `--trace-file`: Single trace file to analyze
- `--trace-dir`: Directory containing trace files
- `--query`: Named query to run (can specify multiple)
- `--custom-query`: Path to custom SQL query file
- `--output-format`: Output format - csv, json, or html (default: csv)

**Available Queries:**
- `frame_metrics`: Frame rendering metrics (frame time, jank)
- `cpu_usage`: CPU usage by thread
- `memory_usage`: Memory allocation events
- `startup_time`: App startup metrics

**Outputs:**
- `output/reports/*.csv` or `*.json`
- Analysis summary

### `perftest full-run`
Execute complete pipeline: build → test → analyze.

```bash
perftest full-run --commit <hash> [options]
```

**Options:**
- `--commit`: Git commit to test (required)
- `--github-token`: GitHub PAT
- `--device-pool`: Device pool name
- `--project-arn`: Device Farm project ARN
- `--run-name`: Test run identifier
- `--skip-build`: Skip build step (use existing APKs)
- `--skip-analysis`: Skip analysis step

### `perftest validate`
Validate environment and configuration.

```bash
perftest validate
```

Checks:
- Configuration loading
- Output directories
- Environment variables
- Android SDK (in Docker)
- Perfetto tools

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# GitHub Authentication
GITHUB_PAT=ghp_xxxxxxxxxxxxx

# AWS Credentials
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_DEFAULT_REGION=us-west-2

# AWS Device Farm
AWS_DEVICEFARM_PROJECT_ARN=arn:aws:devicefarm:us-west-2:123456789:project/abc-def
DEVICEFARM_DEVICE_POOL=Top Devices
```

### Configuration File

Customize behavior with `config/default.yaml` or provide your own:

```bash
perftest --config /path/to/config.yaml <command>
```

See `config/default.yaml` for all available options.

## Docker Usage

### Build Image

```bash
docker build -t perftest:latest .
```

### Run Container

```bash
docker run --rm -it \
  -v $(pwd)/output:/workspace/output \
  -e GITHUB_PAT=$GITHUB_PAT \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  -e AWS_DEVICEFARM_PROJECT_ARN=$AWS_DEVICEFARM_PROJECT_ARN \
  perftest:latest \
  <command>
```

Or use the helper script:

```bash
./scripts/run-docker.sh <command>
```

## Project Structure

```
performance-testing-app/
├── Dockerfile                    # Docker image definition
├── requirements.txt              # Python dependencies
├── setup.py                      # Package setup
├── .env.example                  # Environment template
├── config/
│   └── default.yaml             # Default configuration
├── scripts/
│   ├── build-docker.sh          # Build Docker image
│   └── run-docker.sh            # Run Docker container
├── perftest/                    # Main Python package
│   ├── cli.py                   # CLI commands
│   ├── config.py                # Configuration management
│   ├── logger.py                # Logging setup
│   ├── build/                   # APK build component
│   ├── devicefarm/              # AWS Device Farm integration
│   ├── analysis/                # Perfetto analysis
│   └── utils/                   # Utilities
├── queries/                     # SQL query templates
└── output/                      # Runtime output
    ├── apks/                    # Built APKs
    ├── traces/                  # Perfetto traces
    ├── artifacts/               # Device Farm artifacts
    └── reports/                 # Analysis reports
```

## Development

### Local Setup (without Docker)

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install package in editable mode
pip install -e .

# Run CLI
perftest --help
```

### Requirements

- Python 3.11+
- Android SDK (for local development)
- Perfetto trace_processor_shell

## Implementation Status

### ✅ Phase 1: Foundation (Completed)
- [x] Project structure
- [x] Configuration management
- [x] CLI skeleton with Click
- [x] Logging with Rich
- [x] Dockerfile with Android SDK + Python
- [x] Helper scripts

### 🚧 Phase 2: Build Component (In Progress)
- [ ] Git cloning with GitHub authentication
- [ ] Gradle build execution
- [ ] APK validation

### 📋 Phase 3: Device Farm Component (Pending)
- [ ] Boto3 client wrapper
- [ ] APK upload
- [ ] Test run creation and monitoring
- [ ] Artifact download

### 📋 Phase 4: Analysis Component (Pending)
- [ ] Perfetto trace processor wrapper
- [ ] SQL query library
- [ ] Data analysis with pandas
- [ ] Report generation

### 📋 Phase 5: Integration (Pending)
- [ ] Full-run command implementation
- [ ] Error handling and retry logic
- [ ] Progress indicators

### 📋 Phase 6: Polish (Pending)
- [ ] Comprehensive testing
- [ ] Documentation
- [ ] Performance optimization

## Troubleshooting

### Docker build fails

```bash
# Clean build
docker build --no-cache -t perftest:latest .
```

### Missing environment variables

```bash
# Check .env file
cat .env

# Or export manually
export GITHUB_PAT=your_token
export AWS_ACCESS_KEY_ID=your_key
```

### Android SDK issues (in Docker)

```bash
# Check SDK installation
docker run --rm perftest:latest bash -c "ls -la $ANDROID_HOME"
```

### Perfetto not found

```bash
# Check Perfetto installation
docker run --rm perftest:latest bash -c "which trace_processor_shell"
```

## License

[Your License Here]

## Contributing

[Contributing guidelines]

## Contact

[Contact information]
