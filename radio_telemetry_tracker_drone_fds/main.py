"""Main module for the Radio Telemetry Tracker Drone FDS."""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path

from radio_telemetry_tracker_drone_fds.config import HardwareConfig, PingFinderConfig
from radio_telemetry_tracker_drone_fds.gps_module import (
    GPSInterface,
    GPSModule,
    I2CGPSInterface,
    SerialGPSInterface,
    SimulatedGPSInterface,
)
from radio_telemetry_tracker_drone_fds.ping_finder_module import PingFinderModule
from radio_telemetry_tracker_drone_fds.state_manager import StateManager

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


def wait_for_gps_ready(state_manager: StateManager, timeout: int = 300) -> bool:
    """Wait for GPS module to be ready within the specified timeout."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if state_manager.get_gps_state() == "Locked":
            logger.info("GPS is ready.")
            return True
        time.sleep(1)
    logger.warning("GPS not ready after %d seconds.", timeout)
    return False


def print_heartbeat(
    state_manager: StateManager,
    ping_finder_module: PingFinderModule | None,
) -> None:
    """Continuously print GPS and PingFinder status information."""
    while True:
        gps_data = state_manager.get_gps_data()
        gps_state = state_manager.get_gps_state()
        ping_finder_state = (
            state_manager.get_ping_finder_state() if ping_finder_module else "Not Available"
        )

        logger.info("GPS State: %s", gps_state)
        logger.info("PingFinder State: %s", ping_finder_state)
        logger.info(
            "GPS Data: Easting: %s, Northing: %s, Altitude: %s, Heading: %s, EPSG Code: %s",
            f"{gps_data.easting:.3f}" if gps_data.easting is not None else "N/A",
            f"{gps_data.northing:.3f}" if gps_data.northing is not None else "N/A",
            gps_data.altitude if gps_data.altitude is not None else "N/A",
            gps_data.heading if gps_data.heading is not None else "N/A",
            gps_data.epsg_code if gps_data.epsg_code is not None else "N/A",
        )
        logger.info("-" * 40)

        time.sleep(5)


class PingFinderManager:
    """Handles PingFinder configuration and operation."""

    def __init__(self, config_path: Path, gps_module: GPSModule, state_manager: StateManager) -> None:
        """Initialize the manager."""
        self.config_path = config_path
        self.gps_module = gps_module
        self.state_manager = state_manager
        self.ping_finder_module: PingFinderModule | None = None
        self.file_handler: logging.Handler | None = None

    def start(self) -> None:
        """Load configuration and start PingFinder module."""
        try:
            config_data = self._read_config_file()
            self._setup_logging_file(config_data.output_dir)
            self.ping_finder_module = PingFinderModule(self.gps_module, config_data, self.state_manager)
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

    def _read_config_file(self) -> PingFinderConfig:
        """Read and parse configuration file."""
        return PingFinderConfig.load_from_file(self.config_path)

    def _setup_logging_file(self, output_dir: str | None) -> None:
        """Set up or update the file handler for logging based on output_dir."""
        root_logger = logging.getLogger()

        if output_dir is None:
            root_logger.warning("output_dir is not specified in the configuration.")
            return

        # Ensure the output directory exists
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        log_file_path = output_path / "radio_telemetry_tracker_drone_fds.log"

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


def find_ping_finder_config() -> Path | None:
    """Search for ping_finder_config.json on mounted USB directory.

    Returns:
        Path | None: Path to the configuration file if found, else None.
    """
    config_path = Path(f"/media/{os.getenv('USER')}/usb/ping_finder_config.json")
    if config_path.exists():
        return config_path
    return None


def load_hardware_config() -> HardwareConfig:
    """Load hardware configuration from a JSON file."""
    config_path = Path("./config/hardware_config.json")
    return HardwareConfig.load_from_file(config_path)


def initialize_gps_interface(hardware_config: HardwareConfig) -> GPSInterface:
    """Initialize and return appropriate GPS interface based on configuration."""
    gps_interface_type = hardware_config.GPS_INTERFACE.upper()
    if gps_interface_type == "I2C":
        return I2CGPSInterface(
            hardware_config.GPS_I2C_BUS, hardware_config.GPS_ADDRESS,
        )
    if gps_interface_type == "SERIAL":
        return SerialGPSInterface(
            hardware_config.GPS_SERIAL_PORT, hardware_config.GPS_SERIAL_BAUDRATE,
        )
    if gps_interface_type == "SIMULATED":
        return SimulatedGPSInterface(hardware_config.GPS_SIMULATION_SPEED)

    logger.error("Unsupported GPS interface: %s", hardware_config.GPS_INTERFACE)
    sys.exit(1)


def initialize_gps_module(hardware_config: HardwareConfig, state_manager: StateManager) -> GPSModule:
    """Initialize and start GPS module."""
    gps_interface = initialize_gps_interface(hardware_config)
    logger.info("Initializing GPS module")
    gps_module = GPSModule(gps_interface, hardware_config.EPSG_CODE, state_manager)

    logger.info("Starting GPS thread")
    gps_thread = threading.Thread(target=gps_module.run, daemon=True)
    gps_thread.start()

    logger.info("Waiting for GPS to be ready")
    if not wait_for_gps_ready(state_manager):
        logger.error("GPS not ready. Exiting the program.")
        sys.exit(1)

    return gps_module


def initialize_ping_finder(state_manager: StateManager, gps_module: GPSModule) -> PingFinderManager:
    """Initialize and start PingFinder."""
    initial_config_path = find_ping_finder_config()
    if not initial_config_path:
        logger.error("No ping_finder_config.json found")
        sys.exit(1)

    manager = PingFinderManager(initial_config_path, gps_module, state_manager)
    try:
        manager.start()
    except Exception:
        logger.exception("Failed to start PingFinder")
        sys.exit(1)

    return manager


def run() -> None:
    """Initialize and run the main components of Radio Telemetry Tracker Drone FDS."""
    setup_logging()
    logger.info("Starting run function")

    try:
        # Load hardware configuration
        hardware_config = load_hardware_config()

        # Initialize StateManager
        state_manager = StateManager()

        # Initialize GPS module
        gps_module = initialize_gps_module(hardware_config, state_manager)

        # Initialize and start PingFinder
        manager = initialize_ping_finder(state_manager, gps_module)

        # Start the heartbeat in a separate thread
        heartbeat_thread = threading.Thread(
            target=print_heartbeat,
            args=(state_manager, manager.ping_finder_module),
            daemon=True,
        )
        heartbeat_thread.start()

        # Main loop
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt. Shutting down.")
    except Exception:
        logger.exception("An unexpected error occurred.")
    finally:
        if "manager" in locals():
            manager.stop()
        if "gps_module" in locals():
            gps_module.stop()


def main() -> None:
    """Entry point for the Radio Telemetry Tracker Drone FDS application."""
    run()


if __name__ == "__main__":
    main()
