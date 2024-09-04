# Radio Telemetry Tracker Drone FDS

## Table of Contents
1. [Overview](#overview)
2. [Hardware Requirements](#hardware-requirements)
3. [Getting Started](#getting-started)
4. [Configuration](#configuration)
5. [Troubleshooting](#troubleshooting)

## Overview
Brief description of the project (to be added)

## Hardware Requirements

### Single-Board Computer
- [UP 7000](https://up-shop.org/default/up-7000-series.html)
- Specifications: Intel N100, 8GB RAM, 64GB eMMC

### GPS Module
- Model: Sparkfun Neo M9N
- Default I2C bus: i2c-1
- Default I2C address: 0x42

### Software-Defined Radio (SDR)
- Model: USRP B200mini
- Recommended USB port: Above the HDMI port on UP 7000
- Note: Any available USB port can be used with correct configuration

## Getting Started

1. Install Docker on your system.

2. Pull the latest Docker image: 

```bash
docker pull ghcr.io/ucsd-e4e/radio-telemetry-tracker-drone-fds:latest
```

3. Run the Docker container:

a. Run the container via `docker run`:

```bash
docker run -d --name rtt-drone-fds-release \
--privileged \
--device=/dev/i2c-1:/dev/i2c-1 \
--device=/dev/bus/usb/001/006:/dev/bus/usb/001/006 \
-e GPS_I2C_BUS=1 \
-e GPS_ADDRESS=0x42 \
-e PING_FINDER_CONFIG='{"gain": 56.0, "sampling_rate": 2500000, "center_frequency": 173500000, "run_num": 1, "enable_test_data": false, "output_dir": "./deleteme/", "ping_width_ms": 25, "ping_min_snr": 25, "ping_max_len_mult": 1.5, "ping_min_len_mult": 0.5, "target_frequencies": [173043000]}' \
-e WAIT_TIME=60 \
ghcr.io/ucsd-e4e/radio-telemetry-tracker-drone-fds:latest
```

b. Run the container via `docker compose` (make sure you have a `docker-compose.yml` file from the Release page and edit variables as needed):

```bash
docker compose up -d rtt-drone-fds-release
```

4. View logs:

```bash
docker logs rtt-drone-fds-release
```

5. Stop the container:

```bash
docker stop rtt-drone-fds-release
```

**Note:** This program is intended to run on computer startup. To achieve this, you can set up the Docker container to start automatically when the system boots. One way to do this is by using Docker's `--restart always` option when running the container, or by creating a systemd service that starts the Docker container on boot.

## Configuration

### Environment Variables
- `GPS_I2C_BUS`: I2C bus for GPS module (default: 1)
- `GPS_ADDRESS`: I2C address for GPS module (default: 0x42)
- `PING_FINDER_CONFIG`: JSON string for PingFinder configuration

### Device Mappings
- I2C bus (GPS): `/dev/i2c-1` (default, adjustable)
- USB device (SDR): `/dev/bus/usb/001/006` (default, adjustable)

Adjust these in the Docker run command or `docker-compose.yml` as needed.

For detailed options, see `config.py` in the source code.

## Troubleshooting

### Checking Device Mappings
1. For I2C devices:
   ```bash
   ls /dev/i2c*
   ```

2. For USB devices:
   ```bash
   lsusb
   ```

### Privileged Mode
The Docker container runs in privileged mode to access hardware devices.

## Development

For Engineers for Exploration Radio Telemetry Tracker project members:

1. Contact the project lead to be added to the UP 7000 device that hosts this code.

2. Once granted access, you can SSH into the device using VS Code Remote-SSH:

3. The project code is located in the `/workspace/radio-telemetry-tracker-drone-fds` directory.

4. To set up the development environment open the Command Palette (F1) and select `Remote-Containers: Reopen in Container`. This will open the project in a Docker container. 

5. To run the program run the following command in the container:

```bash
poetry run rttDroneFDS
```

6. For code formatting and linting, we use `ruff` and `black`. These are configured in the `pyproject.toml` file:

```pyproject.toml
[tool.poetry.dev-dependencies]
ruff = "^0.6.3"
black = "^24.8.0"
```

7. VS Code should automatically install and run `ruff` and `black` when you open the project. The code will be formatted automatically on save.

8. When making changes, please refer to the Engineers for Exploration Radio Telemetry Tracker Code Style Guidelines.





