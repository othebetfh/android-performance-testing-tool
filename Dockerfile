FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set up environment variables
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
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
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for python
RUN ln -sf /usr/bin/python3.11 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.11 /usr/bin/python

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

# Layer 3: Install Perfetto trace processor
RUN mkdir -p /usr/local/bin && \
    cd /usr/local/bin && \
    wget -q https://get.perfetto.dev/trace_processor && \
    mv trace_processor trace_processor_shell && \
    chmod +x trace_processor_shell

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
RUN mkdir -p /workspace/output/{apks,traces,artifacts,reports}
WORKDIR /workspace

# Set entry point
ENTRYPOINT ["python3", "-m", "perftest"]
CMD ["--help"]
