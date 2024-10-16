# Radio Telemetry Tracker Drone FDS

The Radio Telemetry Tracker Drone FDS is a software program designed to track and record radio telemetry data from a drone. It is built using Python and utilizes various hardware components to collect and process telemetry data from a drone's radio transmitter.

## Installation and Setup

### Prerequisites

- Ubuntu 24.04 or later
- Docker
- Docker Compose

### Installation Steps

1. Clone the repository:
   ```
   git clone https://github.com/your-username/radio-telemetry-tracker-drone-fds.git
   cd radio-telemetry-tracker-drone-fds
   ```

2. Build the Docker image:
   ```
   docker-compose build
   ```

   This command will build the Docker image.

### Setting Up Automatic Start on Boot

To configure the Docker container to start automatically when your Ubuntu computer boots up, follow these steps:

1. Create a systemd service file:
   ```
   sudo nano /etc/systemd/system/rtt-drone-fds.service
   ```

2. Add the following content to the file:
   ```
   [Unit]
   Description=Radio Telemetry Tracker Drone FDS
   Requires=docker.service
   After=docker.service

   [Service]
   WorkingDirectory=/path/to/radio-telemetry-tracker-drone-fds
   ExecStart=/usr/bin/docker-compose up
   ExecStop=/usr/bin/docker-compose down
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   Replace `/path/to/radio-telemetry-tracker-drone-fds` with the actual path to your project directory.

3. Save the file and exit the editor.

4. Reload the systemd daemon:
   ```
   sudo systemctl daemon-reload
   ```

5. Enable the service to start on boot:
   ```
   sudo systemctl enable rtt-drone-fds.service
   ```

6. Start the service:
   ```
   sudo systemctl start rtt-drone-fds.service
   ```

Now, the Radio Telemetry Tracker Drone FDS container will automatically start when your Ubuntu computer boots up.

## Configuration

The project uses environment variables for configuration. You can modify these in the `docker-compose.yml` file:

```yaml:docker-compose.yml
services:
  rtt-drone-fds:
    environment:
      - PYTHONUNBUFFERED=1
      - GPS_I2C_BUS=1
      - GPS_ADDRESS=0x42
      - PING_FINDER_CONFIG='{}'
      - WAIT_TO_START_TIMER=300
      - RUN_TIMER=1800
```

## Usage

Once the container is running, the Radio Telemetry Tracker Drone FDS will automatically start its operations. The system will:

1. Initialize the GPS module
2. Wait for a GPS fix
3. Start the PingFinder module to detect and log radio signals
4. Continuously log GPS and signal data

Data will be saved to the mounted USB drive specified in the Docker Compose file.

## Troubleshooting

- If the container doesn't start, check the systemd service logs:
  ```
  sudo journalctl -u rtt-drone-fds.service
  ```

- Ensure that the USB devices (GPS and SDR) are properly connected and recognized by the system.

- If you encounter permission issues, make sure the container has the necessary privileges to access the required devices.

## License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.
