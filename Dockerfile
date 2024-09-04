FROM ubuntu:24.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    software-properties-common \
    git \
    curl \
    && add-apt-repository ppa:ettusresearch/uhd \
    && apt-get update \
    && apt-get install -y \
    fftw-dev \
    libboost-all-dev \
    libuhd-dev \
    uhd-host \
    libairspy-dev \
    libhackrf-dev \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    cmake \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Run UHD images downloader
RUN uhd_images_downloader

# Clone rct_dsp2
RUN git clone --branch v1.1.1 https://github.com/UCSD-E4E/radio_collar_tracker_dsp2.git /workspace/radio_collar_tracker_dsp2
WORKDIR /workspace/radio_collar_tracker_dsp2

# Create and activate virtual environment
RUN python3 -m venv .venv
ENV PATH="/workspace/radio_collar_tracker_dsp2/.venv/bin:$PATH"

# Install rct_dsp2
RUN pip install .

# Create a temporary wrapper script to remove sudo from install.sh
RUN if [ -f install.sh ]; then \
       sed 's/sudo //g' install.sh > temp_install.sh && \
       chmod +x temp_install.sh && \
       ./temp_install.sh && \
       rm temp_install.sh; \
    else \
       echo "install.sh not found!"; \
    fi

# Set working directory back to the project
WORKDIR /workspace/radio-telemetry-tracker-drone-fds

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Add user to dialout group
RUN groupadd -f dialout && usermod -aG dialout root
