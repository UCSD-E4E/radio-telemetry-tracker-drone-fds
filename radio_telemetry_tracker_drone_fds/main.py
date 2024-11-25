"""Main module for the Radio Telemetry Tracker Drone FDS."""
from __future__ import annotations

import json
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Any

from radio_telemetry_tracker_drone_fds.drone_state import PingFinderState
from radio_telemetry_tracker_drone_fds.gps_module import GPSModule
from radio_telemetry_tracker_drone_fds.ping_finder_module import PingFinderModule

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure basic logging settings with console handler."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def wait_for_gps_ready(gps_module: GPSModule, timeout: int = 300) -> bool:
    """Wait for GPS module to be ready within the specified timeout.

    Args:
        gps_module (GPSModule): The GPS module to check.
        timeout (int, optional): Maximum wait time in seconds. Defaults to 300.

    Returns:
        bool: True if GPS is ready, False if timeout occurred.

    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if gps_module.is_ready():
            logger.info("GPS is ready.")
            return True
        time.sleep(1)
    logger.warning("GPS not ready after %d seconds.", timeout)
    return False


def print_heartbeat(
    gps_module: GPSModule,
    ping_finder_module: PingFinderModule | None,
) -> None:
    """Continuously print GPS and PingFinder status information."""
    while True:
        gps_data, gps_state = gps_module.get_gps_data()
        ping_finder_state = ping_finder_module.get_state() if ping_finder_module else "Not Available"

        logger.info("GPS State: %s", gps_state.value)
        state_str = ping_finder_state.value if isinstance(ping_finder_state, PingFinderState) else ping_finder_state
        logger.info("PingFinder State: %s", state_str)
        logger.info(
            "GPS Data: Lat: %s, Lon: %s, Alt: %s",
            gps_data.latitude,
            gps_data.longitude,
            gps_data.altitude,
        )
        logger.info("-" * 40)

        time.sleep(5)


class PingFinderManager:
    """Handles PingFinder configuration and operation."""

    def __init__(self, config_path: Path, gps_module: GPSModule) -> None:
        """Initialize the manager.

        Args:
            config_path (Path): The path to the ping_finder_config.json file.
            gps_module (GPSModule): The GPS module instance.
        """
        self.config_path = config_path
        self.gps_module = gps_module
        self.ping_finder_module: PingFinderModule | None = None
        self.file_handler: logging.Handler | None = None

    def start(self) -> None:
        """Load configuration and start PingFinder module."""
        try:
            config_data = self._read_config_file()
            self._setup_logging_file(config_data.get("output_dir"))
            self._validate_config_data(config_data)
            self.ping_finder_module = PingFinderModule(self.gps_module, config_data)
            self.ping_finder_module.start()
            logger.info("PingFinderModule started with configuration")
        except Exception:
            logger.exception("Failed to start PingFinder")
            raise

    def stop(self) -> None:
        """Stop the PingFinder module and cleanup."""
        if self.ping_finder_module is not None:
            logger.info("Stopping PingFinderModule.")
            self.ping_finder_module.stop()
            self.ping_finder_module = None

        if self.file_handler:
            logger.removeHandler(self.file_handler)
            self.file_handler.close()
            self.file_handler = None

    def _read_config_file(self) -> dict[str, Any]:
        """Read and parse configuration file."""
        with self.config_path.open() as f:
            config = json.load(f)
        
        # Add output directory based on config file location
        config["output_dir"] = str(self.config_path.parent / "rtt_output")
        return config

    def _setup_logging_file(self, output_dir: str | None) -> None:
        """Set up or update the file handler for logging based on output_dir.

        Args:
            output_dir (str | None): The directory where logs should be saved.
        """
        root_logger = logging.getLogger()  # Get the root logger first

        if output_dir is None:
            root_logger.warning("output_dir is not specified in the configuration.")
            return

        # Ensure the output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        log_file_path = Path(output_dir) / "radio_telemetry_tracker_drone_fds.log"

        # Remove the old file handler if it exists
        if self.file_handler:
            root_logger.removeHandler(self.file_handler)
            self.file_handler.close()
            self.file_handler = None

        # Create a new file handler
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        self.file_handler = file_handler

        root_logger.info("Logging to file: %s", log_file_path)

    def _validate_config_data(self, config_data: dict[str, Any]) -> None:
        """Validate configuration data.

        Args:
            config_data: Configuration dictionary to validate
        """
        required_fields = {
            "gain": float,
            "sampling_rate": int,
            "center_frequency": int,
            "run_num": int,
            "enable_test_data": bool,
            "ping_width_ms": int,
            "ping_min_snr": int,
            "ping_max_len_mult": float,
            "ping_min_len_mult": float,
            "target_frequencies": list,
        }

        def validate_field(field: str, expected_type: type) -> None:
            if field not in config_data:
                msg = f"Missing required field: {field}"
                raise KeyError(msg)
            if not isinstance(config_data[field], expected_type):
                msg = f"Field {field} must be of type {expected_type.__name__}, got {type(config_data[field]).__name__}"
                raise TypeError(msg)

        for field, expected_type in required_fields.items():
            validate_field(field, expected_type)

        if not config_data["target_frequencies"]:
            msg = "target_frequencies list cannot be empty"
            raise ValueError(msg)
        if not all(isinstance(freq, int) for freq in config_data["target_frequencies"]):
            msg = "All target_frequencies must be integers"
            raise ValueError(msg)


def find_ping_finder_config() -> Path | None:
    """Search for ping_finder_config.json on mounted USB directories.

    Returns:
        Path | None: Path to the configuration file if found, else None.
    """
    for mount_point in [Path("/media"), Path("/mnt")]:
        if not mount_point.exists():
            continue
        for usb_dir in mount_point.iterdir():
            if usb_dir.is_dir():
                config_file = usb_dir / "ping_finder_config.json"
                if config_file.exists():
                    return config_file
    return None


def run() -> None:
    """Initialize and run the main components of Radio Telemetry Tracker Drone FDS.

    Raises:
        SystemExit: If GPS is not ready or configuration is invalid
    """
    setup_logging()
    logger.info("Starting run function")

    # Initialize GPS module
    logger.info("Initializing GPS module")
    gps_module = GPSModule()

    logger.info("Starting GPS thread")
    gps_thread = threading.Thread(target=gps_module.run, daemon=True)
    gps_thread.start()

    logger.info("Waiting for GPS to be ready")
    if not wait_for_gps_ready(gps_module):
        logger.error("GPS not ready. Exiting the program.")
        sys.exit(1)

    # Find PingFinder configuration
    initial_config_path = find_ping_finder_config()
    if not initial_config_path:
        logger.error("No ping_finder_config.json found on any USB device")
        sys.exit(1)

    # Initialize and start PingFinder
    manager = PingFinderManager(initial_config_path, gps_module)
    try:
        manager.start()
    except Exception:
        logger.exception("Failed to start PingFinder")
        sys.exit(1)

    try:
        # Start the heartbeat in a separate thread
        heartbeat_thread = threading.Thread(
            target=print_heartbeat,
            args=(gps_module, manager.ping_finder_module),
            daemon=True,
        )
        heartbeat_thread.start()

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt. Shutting down.")
    finally:
        manager.stop()
        gps_module.stop()


def main() -> None:
    """Entry point for the Radio Telemetry Tracker Drone FDS application."""
    run()


if __name__ == "__main__":
    main()
