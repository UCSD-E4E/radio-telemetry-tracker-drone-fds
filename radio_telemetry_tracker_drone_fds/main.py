"""Main entry point for the Radio Telemetry Tracker Drone FDS application."""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path

from radio_telemetry_tracker_drone_fds.config import HardwareConfig, PingFinderConfig
from radio_telemetry_tracker_drone_fds.gps import GPSInterface, GPSModule
from radio_telemetry_tracker_drone_fds.gps.gps_interface import (
    I2CGPSInterface,
    SerialGPSInterface,
    SimulatedGPSInterface,
)
from radio_telemetry_tracker_drone_fds.ping_finder import PingFinderModule
from radio_telemetry_tracker_drone_fds.state.state_manager import StateManager
from radio_telemetry_tracker_drone_fds.utils.logging_helper import log_heartbeat
from radio_telemetry_tracker_drone_fds.utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)


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


def find_ping_finder_config() -> Path | None:
    """Search for ping_finder_config.json on mounted USB directories.

    Returns:
        Path | None: Path to the configuration file if found, else None.
    """
    usb_media_path = Path("/media") / os.getenv("USER", "")
    if not usb_media_path.exists():
        logger.error("USB media path %s does not exist.", usb_media_path)
        return None

    for device in usb_media_path.iterdir():
        config_path = device / "ping_finder_config.json"
        if config_path.exists():
            logger.info("Found ping_finder_config.json at %s", config_path)
            return config_path

    logger.error("No ping_finder_config.json found on any USB devices.")
    return None


def main() -> None:
    """Main function to initialize and start modules."""
    setup_logging()

    try:
        # Load hardware configuration
        hardware_config = HardwareConfig.load_from_file(Path("./config/hardware_config.json"))

        # Initialize StateManager
        state_manager = StateManager()

        # Initialize GPS module
        gps_interface = initialize_gps_interface(hardware_config)

        # Initialize GPS module
        gps_module = GPSModule(gps_interface, hardware_config.EPSG_CODE, state_manager)

        # Start GPS module in a separate thread
        gps_thread = threading.Thread(target=gps_module.run, daemon=True)
        gps_thread.start()

        # Wait for GPS to be ready
        if not wait_for_gps_ready(state_manager):
            logger.error("GPS failed to initialize within the timeout period.")
            sys.exit(1)

        # Find PingFinder configuration based on CHECK_USB_FOR_CONFIG
        if hardware_config.CHECK_USB_FOR_CONFIG:
            ping_finder_config_path = find_ping_finder_config()
            if not ping_finder_config_path:
                logger.error("PingFinder configuration not found on USB stick.")
                sys.exit(1)
        else:
            ping_finder_config_path = Path("./config/ping_finder_config.json")
            if not ping_finder_config_path.exists():
                logger.error("PingFinder configuration not found at ./config/ping_finder_config.json.")
                sys.exit(1)

        # Load PingFinder configuration
        ping_finder_config = PingFinderConfig.load_from_file(ping_finder_config_path)

        # Initialize and start PingFinder module
        ping_finder_module = PingFinderModule(
            gps_module, ping_finder_config, state_manager, hardware_config.SDR_TYPE,
        )
        ping_finder_module.start()

        # Start heartbeat thread
        heartbeat_thread = threading.Thread(
            target=print_heartbeat,
            args=(state_manager, ping_finder_module),
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
        if "gps_module" in locals():
            gps_module.stop()
        if "ping_finder_module" in locals():
            ping_finder_module.stop()


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
        gps_data = state_manager.get_current_gps_data()
        gps_state = state_manager.get_gps_state()
        ping_finder_state = (
            state_manager.get_ping_finder_state() if ping_finder_module else "Not Available"
        )

        # Use logging helper to log heartbeat
        log_heartbeat(gps_state, ping_finder_state, gps_data)

        time.sleep(5)


if __name__ == "__main__":
    main()
