# Radio Telemetry Tracker Drone Field Device Software (FDS)

The **Radio Telemetry Tracker Drone FDS** is a Python-based system designed to track and locate wildlife radio transmitters using a drone-mounted payload. It integrates GPS, software-defined radio (SDR), and signal processing to detect and record telemetry signals, aiding in wildlife monitoring and conservation efforts.

## Table of Contents
- [Prerequisites](#prerequisites)
  - [Hardware Requirements](#hardware-requirements)
  - [System Requirements](#system-requirements)
  - [System Dependencies](#system-dependencies)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Hardware Configuration](#hardware-configuration)
  - [USB Configuration](#usb-configuration)
- [Usage](#usage)
- [Automatic Startup](#automatic-startup)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Prerequisites

### Hardware Requirements

#### Required Components
- **Single Board Computer:** Intel-based SBC (tested with UP 7000)
- **Software Defined Radio (SDR):** Supported SDR types:
  - **USRP** (e.g., USRP B200mini-i)
  - **HackRF** (e.g., HackRF One)
  - **AirSpy** (e.g., AirSpy R2)
- **GPS Module:** Supported GPS modules:
  - **I2C GPS Module:** e.g., Sparkfun NEO-M9N (connected via I2C bus)
  - **Serial GPS Module:** (connected via serial port)
  - **Simulated GPS:** (for testing)
- **Storage:** USB Flash Drive (FAT32 formatted)

#### Connection Details
- **SDR Connection:** USB 3.0 port
- **GPS Connection:**
  - **I2C GPS Module:** I2C Bus 1
    - SDA: Pin XX
    - SCL: Pin XX
    - VCC: 3.3V
    - GND: Ground
  - **Serial GPS Module:** Serial port (e.g., /dev/ttyUSB0)
- **USB Storage:** Any available USB port

### System Requirements
- **Operating System:** Ubuntu 24.04 or later
- **Python:** 3.12 or later
- **Poetry:** 1.8 or later

### System Dependencies
```bash
sudo add-apt-repository ppa:ettusresearch/uhd
sudo apt update
sudo apt install -y \
    fftw-dev \
    libboost-all-dev \
    libuhd-dev \
    uhd-host \
    libairspy-dev \
    libhackrf-dev \
    cmake \
    build-essential \
    udisks2  # Required for USB automounting
sudo uhd_images_downloader
```

## Installation

### 1. Hardware Setup
#### GPS Permissions (if using I2C GPS)

```bash
# Add user to i2c group for GPS access
sudo groupadd -f i2c
sudo usermod -aG i2c $USER

# Create udev rules for I2C permissions
sudo tee /etc/udev/rules.d/99-i2c.rules <<EOF
KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660"
EOF

# Apply changes
sudo udevadm control --reload-rules
sudo udevadm trigger

# Note: Log out and back in for group changes to take effect
```

### 2. Software Installation
```bash
# Clone and install
git clone https://github.com/UCSD-E4E/radio-telemetry-tracker-drone-fds.git
cd radio-telemetry-tracker-drone-fds
poetry install
```

## Configuration

### Hardware Configuration
Create or modify `./config/hardware_config.json`:
```json
{
  "GPS_INTERFACE": "SIMULATED",
  "EPSG_CODE": 32611,
  "GPS_I2C_BUS": 1,
  "GPS_ADDRESS": "0x42",
  "GPS_SERIAL_PORT": "/dev/ttyS0",
  "GPS_SERIAL_BAUDRATE": 9600,
  "GPS_SIMULATION_SPEED": 1.0,
  "CHECK_USB_FOR_CONFIG": true,
  "SDR_TYPE": "USRP"
}
```

#### Explanation of Parameters:
- **GPS_INTERFACE:** "SIMULATED", "I2C", or "SERIAL". Selects the GPS interface type.
- **EPSG_CODE:** EPSG code for the UTM zone (e.g., `32611` for UTM zone 11N).
- **GPS_I2C_BUS:** (For I2C interface) I2C bus number (e.g., `1`).
- **GPS_ADDRESS:** (For I2C interface) I2C address of the GPS module (e.g., `"0x42"`).
- **GPS_SERIAL_PORT:** (For Serial interface) Serial port for the GPS module (e.g., `"/dev/ttyS0"`).
- **GPS_SERIAL_BAUDRATE:** (For Serial interface) Serial baud rate for the GPS module (e.g., `9600`).
- **GPS_SIMULATION_SPEED:** (For Simulated interface) Speed multiplier for simulated GPS data (e.g., `1.0`).
- **CHECK_USB_FOR_CONFIG:** `true` or `false`. Whether to check USB storage for configuration.
- **SDR_TYPE:** `"USRP"`, `"HACKRF"`, or `"AIRSPY"`. Selects the SDR type.

### USB Configuration
1. **Create Automount Service:**
```bash
sudo tee /etc/systemd/system/usb-automount.service <<EOF
[Unit]
Description=USB Automount Service
After=udisks2.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'for dev in /dev/sd*1; do mkdir -p /media/$USER/usb && mount -t auto "\$dev" /media/$USER/usb -o "rw,umask=000" || true; done'
ExecStop=/bin/sh -c 'for dev in /dev/sd*1; do umount /media/$USER/usb || true; done'
User=root

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable usb-automount
sudo systemctl start usb-automount
```

2. **Prepare USB Configuration:**
- Format USB drive as FAT32
- Create `ping_finder_config.json` in the root directory:
```json
{
    "gain": 56.0,
    "sampling_rate": 2500000,
    "center_frequency": 173500000,
    "run_num": 1,
    "enable_test_data": false,
    "ping_width_ms": 25,
    "ping_min_snr": 25,
    "ping_max_len_mult": 1.5,
    "ping_min_len_mult": 0.5,
    "target_frequencies": [173043000]
}
```
**Note:** The application will check for `ping_finder_config.json` on the USB drive if `CHECK_USB_FOR_CONFIG` is `true` in `hardware_config.json`. If `false`, the application will check for `./config/ping_finder_config.json`.

## Usage

1. **Run Application:**
    ```bash
    poetry run radio_telemetry_tracker_drone_fds
    ```

2. **Development with Poetry Shell:**
    ```bash
    # Enter poetry shell
    poetry shell
    # Install dependencies + dev tools
    poetry install --with dev
    # Run application
    radio_telemetry_tracker_drone_fds
    # Run tests
    pytest
    # Exit poetry shell
    exit
    ```

3. **Code Formatting with Ruff:**
    ```bash
    poetry run ruff check --unsafe-fixes --fix
    ```
    *Use this command to automatically fix code style issues.*

## Automatic Startup

To ensure the application runs automatically on system startup, you can create a **systemd** service.

1. **Create a systemd Service File:**

    Create a file named `radio_telemetry_tracker.service` in `/etc/systemd/system/`:

    ```bash: /etc/systemd/system/radio_telemetry_tracker.service
    [Unit]
    Description=Radio Telemetry Tracker Drone FDS Service
    After=network.target

    [Service]
    User=your_username
    WorkingDirectory=/path/to/radio-telemetry-tracker-drone-fds
    ExecStart=/usr/bin/poetry run radio_telemetry_tracker_drone_fds
    Restart=always
    Environment=PATH=/usr/bin:/usr/local/bin
    Environment=POETRY_VIRTUALENVS_IN_PROJECT=true

    [Install]
    WantedBy=multi-user.target
    ```

    **Replace the following placeholders:**
    - `your_username`: Your actual Linux username.
    - `/path/to/radio-telemetry-tracker-drone-fds`: The full path to your cloned repository.

2. **Reload systemd and Enable the Service:**
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable radio_telemetry_tracker.service
    sudo systemctl start radio_telemetry_tracker.service
    ```

3. **Check Service Status:**
    ```bash
    sudo systemctl status radio_telemetry_tracker.service
    ```

    You should see output indicating that the service is active and running. If there are issues, logs can be viewed using:
    ```bash
    sudo journalctl -u radio_telemetry_tracker.service -f
    ```

**Note:** Ensure that all paths and usernames are correctly specified. The `Restart=always` directive ensures that the service restarts automatically if it crashes.

## Troubleshooting

- **USB Issues:**
    - Verify USB is mounted: `mount | grep usbstick`
    - Check UUID: `sudo blkid`
    - Manual mount: `sudo mount -o uid=1000,gid=1000 /dev/sdX1 /media/usbstick`
    - Review logs: `dmesg | tail`

- **GPS Not Ready:**
    - Confirm GPS hardware connection.
    - Validate `hardware_config.json` settings.
    - Check system logs for GPS errors.

- **Permissions:**
    - Run application with necessary privileges.
    - Ensure user has read/write access to config and output directories.

- **Service Issues:**
    - Check service status: `sudo systemctl status radio_telemetry_tracker.service`
    - View logs: `sudo journalctl -u radio_telemetry_tracker.service -f`

## License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.
