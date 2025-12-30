FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set up environment variables
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV PATH="${PATH}:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/build-tools/34.0.0:/usr/local/bin"

# Layer 1: Install system dependencies
RUN apt-get update && apt-get install -y \
    openjdk-17-jdk \
    git \
    curl \
    wget \
    unzip \
    python3.11 \
    python3.11-dev \
    python3-pip \
    build-essential \
    libstdc++6 \
    libc6 \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for python
RUN ln -sf /usr/bin/python3.11 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.11 /usr/bin/python

# Detect JAVA_HOME dynamically (works for both amd64 and arm64)
RUN DETECTED_JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java)))) && \
    echo "export JAVA_HOME=${DETECTED_JAVA_HOME}" >> /etc/profile && \
    ln -sf ${DETECTED_JAVA_HOME} /usr/lib/jvm/java-17-openjdk

# Set JAVA_HOME environment variable
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk

# Upgrade pip
RUN python3 -m pip install --upgrade pip setuptools wheel

# Layer 2: Install Android SDK
RUN mkdir -p ${ANDROID_HOME}/cmdline-tools && \
    cd ${ANDROID_HOME}/cmdline-tools && \
    wget -q https://dl.google.com/android/repository/commandlinetools-linux-10406996_latest.zip && \
    unzip commandlinetools-linux-10406996_latest.zip && \
    mv cmdline-tools latest && \
    rm commandlinetools-linux-10406996_latest.zip

# Accept licenses and install SDK packages
RUN yes | sdkmanager --licenses && \
    sdkmanager --install \
    "platforms;android-34" \
    "build-tools;34.0.0" \
    "platform-tools" \
    "cmdline-tools;latest"

# Layer 3: Prepare for Perfetto
# Note: Perfetto Python library will auto-download its trace processor binary
# We just ensure a proper cache directory exists
RUN mkdir -p /root/.local/share/perfetto && chmod -R 755 /root/.local

# Layer 4: Install Python dependencies
WORKDIR /app
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r requirements.txt

# Layer 5: Install application code
COPY perftest/ /app/perftest/
COPY setup.py /app/
COPY config/ /app/config/
COPY queries/ /app/queries/

# Install perftest package in editable mode
RUN pip3 install -e /app

# Layer 6: Runtime setup
# Create workspace directory for volume mounts
RUN mkdir -p /workspace/output
WORKDIR /workspace

# Set entry point
# When no arguments provided, runs in interactive mode
# When arguments provided, passes them to the CLI
ENTRYPOINT ["python3", "-m", "perftest"]
