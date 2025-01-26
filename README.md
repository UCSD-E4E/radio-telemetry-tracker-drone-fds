# Radio Telemetry Tracker Drone Field Device Software (FDS)

The **Radio Telemetry Tracker Drone FDS** is a Python-based system designed to track and locate wildlife radio transmitters using a drone-mounted payload. It integrates GPS, software-defined radio (SDR), and signal processing to detect and record telemetry signals, aiding in wildlife monitoring and conservation efforts.

## Table of Contents
- [Prerequisites](#prerequisites)
  - [Hardware Requirements](#hardware-requirements)
  - [System Requirements](#system-requirements)
  - [System Dependencies](#system-dependencies)
- [Operation Modes](#operation-modes)
  - [Online Mode](#online-mode)
  - [Offline Mode](#offline-mode)
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
  - Required for high-bandwidth data transfer
  - Compatible with USRP, HackRF, and AirSpy devices
  - Hot-pluggable, but requires system restart after connection

- **GPS Connection:**
  1. **I2C GPS Module Example:**
     - Connect to I2C Bus 1
     - Pin Connections:
       - SDA: Pin 3 (I2C1_SDA)
       - SCL: Pin 5 (I2C1_SCL)
       - VCC: Pin 1 (3.3V)
       - GND: Pin 6 (Ground)
     - Default I2C Address: 0x42
     - Recommended: Sparkfun NEO-M9N

  2. **Serial GPS Module Example:**
     - Connect to available serial port (e.g., /dev/ttyUSB0)
     - Default Baud Rate: 9600
     - Supports NMEA 0183 protocol
     - USB-to-Serial adapter recommended

  3. **Simulated GPS Example:**
     - No physical connections required
     - Used for testing and development
     - Configurable simulation speed

- **Radio Connection (Online Mode):**
  1. **Serial Radio Example:**
     - Connect to USB port (e.g., /dev/ttyUSB0)
     - Default Baud Rate: 57600
     - Recommended: RFD900x Telemetry Modem


  2. **Simulated Radio Example:**
     - No physical connections required
     - Uses TCP/IP for communication
     - Default port: 50000
     - Useful for local testing

- **USB Storage:**
  - Any available USB 2.0/3.0 port
  - FAT32 formatted drive required
  - Minimum recommended size: 8GB
  - Automounted to /media/\<USER\>/usb/

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

## Operation Modes

The system primarily operates in Online Mode with Ground Control Station (GCS) integration, while also supporting an Offline Mode for autonomous operations.

### Online Mode
- Requires communication with the [Ground Control Station (GCS)](https://github.com/UCSD-E4E/radio-telemetry-tracker-drone-gcs)
- Configuration and commands received remotely
- Real-time data transmission and stored locally on the drone
- Provides real-time location estimation but requires laptop with GCS to be present and connected to the drone

#### Communication Options
1. **Serial Interface**
   - Direct radio modem connection to GCS
   - Configuration parameters:
     ```yaml
     RADIO_INTERFACE: SERIAL
     RADIO_PORT: /dev/ttyUSB0
     RADIO_BAUDRATE: 57600
     ```

2. **Simulated Interface**
   - TCP/IP-based communication with GCS
   - Useful for testing and development
   - Configuration parameters:
     ```yaml
     RADIO_INTERFACE: SIMULATED
     RADIO_HOST: localhost
     RADIO_TCP_PORT: 50000
     RADIO_SERVER_MODE: true
     ```

### Offline Mode
- Operates independently without GCS
- Configuration loaded from local files
- Data stored locally for later retrieval

#### Configuration Sources
1. **USB Storage** (if `USE_USB_STORAGE: true`)
   - Searches for `ping_finder_config.json` on USB drive
   - Creates output directory: `/media/<USER>/usb/rtt_output/`

2. **Local Storage** (if `USE_USB_STORAGE: false`)
   - Uses `./config/ping_finder_config.json`
   - Creates output directory: `./rtt_output/`

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
```yaml
GPS_INTERFACE: SIMULATED
GPS_I2C_BUS: 1
GPS_ADDRESS: "0x42"
GPS_SERIAL_PORT: /dev/ttyUSB0
GPS_SERIAL_BAUDRATE: 9600
GPS_SIMULATION_SPEED: 1.0
USE_USB_STORAGE: true
SDR_TYPE: USRP
RADIO_INTERFACE: SERIAL
RADIO_PORT: /dev/ttyUSB1
RADIO_BAUDRATE: 57600
RADIO_HOST: localhost
RADIO_TCP_PORT: 50000
RADIO_SERVER_MODE: true
```

#### Explanation of Parameters:
- **GPS_INTERFACE:** "SIMULATED", "I2C", or "SERIAL". Selects the GPS interface type.
- **EPSG_CODE:** EPSG code for the UTM zone (e.g., `32611` for UTM zone 11N).
- **GPS_I2C_BUS:** (For I2C interface) I2C bus number (e.g., `1`).
- **GPS_ADDRESS:** (For I2C interface) I2C address of the GPS module (e.g., `"0x42"`).
- **GPS_SERIAL_PORT:** (For Serial interface) Serial port for the GPS module (e.g., `"/dev/ttyS0"`).
- **GPS_SERIAL_BAUDRATE:** (For Serial interface) Serial baud rate for the GPS module (e.g., `9600`).
- **GPS_SIMULATION_SPEED:** (For Simulated interface) Speed multiplier for simulated GPS data (e.g., `1.0`).
- **USE_USB_STORAGE:** `true` or `false`. Whether to use USB storage for configuration (only if `OPERATION_MODE` is `"OFFLINE"`) and output.
- **SDR_TYPE:** `"USRP"`, `"HACKRF"`, or `"AIRSPY"`. Selects the SDR type.
- **OPERATION_MODE:** `"ONLINE"` or `"OFFLINE"`. Selects the operation mode.
- **RADIO_INTERFACE:** (For Online mode) `"SERIAL"` or `"SIMULATED"`. Selects the radio communication interface.
- **RADIO_PORT:** (For Serial interface) Serial port for radio communication (e.g., `"/dev/ttyUSB0"`).
- **RADIO_BAUDRATE:** (For Serial interface) Baud rate for radio communication (e.g., `57600`).
- **RADIO_HOST:** (For Simulated interface) Host address for simulated radio (e.g., `"localhost"`).
- **RADIO_TCP_PORT:** (For Simulated interface) TCP port for simulated radio (e.g., `50000`).
- **RADIO_SERVER_MODE:** (For Simulated interface) `true` or `false`. Whether to run radio as the server.

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
- Create `ping_finder_config.json` in the root directory (for offline mode):
```yaml
EPSG_CODE: 32611
OPERATION_MODE: ONLINE
gain: 56.0
sampling_rate: 2500000
center_frequency: 173500000
run_num: 1
enable_test_data: false
ping_width_ms: 25
ping_min_snr: 25
ping_max_len_mult: 1.5
ping_min_len_mult: 0.5
target_frequencies:
  - 173043000
```

## Usage

### Online Mode Usage
1. **Start the Ground Control Station**
   - Follow GCS setup instructions
   - Ensure radio communication is configured

2. **Launch FDS**
    ```bash
    poetry run radio_telemetry_tracker_drone_fds
    ```

3. **Operation**
   - Wait for GCS connection
   - Follow GCS interface for configuration and control
   - Monitor real-time data through GCS

## Automatic Startup

To ensure the application runs automatically on system startup, you can create a **systemd** service. This is useful so when the microprocessor is powered on by the drone and the application can run without the need to manually start it. The configuration is also only loaded in offline mode when the program is started.

1. **Create a systemd Service File:**

    Create a file named `radio_telemetry_tracker.service` in `/etc/systemd/system/`:

    ```bash
    sudo tee /etc/systemd/system/radio_telemetry_tracker.service <<EOF
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
    EOF
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

## Troubleshooting

### Online Mode Issues
- **Communication Failures**
  ```bash
  # Test serial connection
  minicom -D /dev/ttyUSB0 -b 57600
  
  # Check TCP connection
  netstat -an | grep 50000
  
  # Monitor radio logs
  journalctl -u radio_telemetry_tracker.service | grep "Radio"
  ```

- **Configuration Issues**
  - Verify radio interface settings
  - Check port permissions
  - Confirm baudrate matches base station
  - Test network connectivity for simulated mode

### General Issues
- **Data Storage**
  - Monitor available space
  - Check write permissions
  - Verify USB mount status
  - Review output directory structure

## License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.
