FROM ubuntu:24.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    software-properties-common \
    git \
    curl \
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
    python3-psutil \
    && add-apt-repository ppa:ettusresearch/uhd \
    && apt-get update \
    && apt-get install -y uhd-host \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Run UHD images downloader
RUN uhd_images_downloader

# Clone rct_dsp2 and install
WORKDIR /workspace
RUN git clone --branch v1.1.1 https://github.com/UCSD-E4E/radio_collar_tracker_dsp2.git \
    && cd radio_collar_tracker_dsp2 \
    && python3 -m venv .venv \
    && . .venv/bin/activate \
    && pip install . \
    && if [ -f install.sh ]; then \
         sed 's/sudo //g' install.sh > temp_install.sh \
         && chmod +x temp_install.sh \
         && ./temp_install.sh \
         && rm temp_install.sh; \
       else \
         echo "install.sh not found!"; \
       fi

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && echo 'export PATH="/root/.local/bin:$PATH"' >> ~/.bashrc

# Add user to dialout group
RUN groupadd -f dialout && usermod -aG dialout root

# Set working directory for the project
WORKDIR /workspace/radio-telemetry-tracker-drone-fds

# Copy the project files
COPY . .

# Install the project dependencies
RUN poetry install --no-dev

# Set the command to run the main script
CMD ["poetry", "run", "rttDroneFDS"]
