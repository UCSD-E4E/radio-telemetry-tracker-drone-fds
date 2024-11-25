# Radio Telemetry Tracker Drone FDS

The **Radio Telemetry Tracker Drone FDS** is a Python-based application designed to track and record radio telemetry data from drone transmitters. It leverages various hardware components for efficient data collection and processing.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Hardware Configuration](#hardware-configuration)
  - [PingFinder Configuration via USB](#pingfinder-configuration-via-usb)
- [Usage](#usage)
- [Automatic Startup](#automatic-startup)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Prerequisites
- **Operating System:** Ubuntu 24.04 or later (24.04.1 tested)
- **Python:** 3.12 or later (3.12.7 tested)
- **Poetry:** 1.8 or later (1.8.4 tested)
- **Dependencies:** 
  - `fftw-dev`
  - `libboost-all-dev`
  - `libuhd-dev`
  - `uhd-host`
  - `libairspy-dev`
  - `libhackrf-dev`
  - `cmake`
  - `build-essential`

## Installation

1. **Install System Dependencies:**
    ```bash
    sudo add-apt-repository ppa:ettusresearch/uhd
    sudo apt update
    sudo apt install -y fftw-dev libboost-all-dev libuhd-dev uhd-host libairspy-dev libhackrf-dev cmake build-essential
    sudo uhd_images_downloader
    ```

2. **Set Up Hardware Permissions:**
    ```bash
    # Add user to i2c group
    getent group i2c || sudo groupadd i2c
    sudo usermod -aG i2c $USER

    # Create udev rules
    sudo tee /etc/udev/rules.d/99-i2c.rules <<EOF
    KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660"
    EOF

    sudo udevadm control --reload-rules
    sudo udevadm trigger

    # Re-login for changes to take effect
    ```

3. **Clone Repository and Install Python Dependencies:**
    ```bash
    git clone https://github.com/UCSD-E4E/radio-telemetry-tracker-drone-fds.git
    cd radio-telemetry-tracker-drone-fds
    poetry install
    ```

## Configuration

### Hardware Configuration
- **File:** `./config/hardware_config.json`
- **Example:**
    ```json
    {
        "GPS_I2C_BUS": 1,
        "GPS_ADDRESS": "0x42"
    }
    ```

### PingFinder Configuration via USB
Enable field modifications by using a `ping_finder_config.json` on a USB stick.

1. **Prepare USB Stick:**
    - Format as FAT32.
    - Create `ping_finder_config.json` at root:
        ```json
        {
          "gain": 56.0,
          "sampling_rate": 2500000,
          "center_frequency": 173500000,
          "run_num": 1,
          "enable_test_data": false,
          "output_dir": "./rtt_output/",
          "ping_width_ms": 25,
          "ping_min_snr": 25,
          "ping_max_len_mult": 1.5,
          "ping_min_len_mult": 0.5,
          "target_frequencies": [173043000]
        }
        ```

2. **Mount USB Stick:**
    - **Create Mount Point:**
        ```bash
        sudo mkdir -p /media/usbstick
        sudo chown $USER:$USER /media/usbstick
        ```
    - **Add to fstab:**
        ```bash
        # Get USB UUID
        sudo blkid

        # Add to /etc/fstab
        sudo tee -a /etc/fstab <<EOF
        UUID=XXXX-XXXX    /media/usbstick    vfat    rw,user,exec,umask=000,uid=1000,gid=1000    0    0
        EOF
        ```
    - **Mount USB:**
        ```bash
        sudo mount -a
        ```

3. **Using Multiple USB Sticks:**
    - Format each as FAT32 and label uniquely.
    - Add each UUID to `/etc/fstab` with `nofail` option.
    - Ensure all sticks contain `ping_finder_config.json`.

## Usage

1. **Run Application:**
    ```bash
    poetry run radio_telemetry_tracker_drone_fds
    ```

2. **Development with Poetry Shell:**
    ```bash
    poetry shell
    python -m radio_telemetry_tracker_drone_fds.main
    exit
    ```

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
