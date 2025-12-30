# Builder image (x86_64 for Android SDK compatibility)
FROM --platform=linux/amd64 ubuntu:22.04 AS builder

# ... (keep all Android SDK and build setup)

# Analysis image (native ARM64 for fast Perfetto)
FROM --platform=linux/arm64 ubuntu:22.04 AS analyzer

# ... (only Python and Perfetto, no Android SDK)
