"""Main entry point for the Radio Telemetry Tracker Drone FDS application."""
from __future__ import annotations

import yaml
import logging
import os
import sys
import threading
import time
from pathlib import Path

from radio_telemetry_tracker_drone_comms_package import (
    DroneComms,
    RadioConfig,
)

from radio_telemetry_tracker_drone_fds.config import HardwareConfig, PingFinderConfig
from radio_telemetry_tracker_drone_fds.gps import GPSInterface, GPSModule
from radio_telemetry_tracker_drone_fds.gps.gps_interface import (
    I2CGPSInterface,
    SerialGPSInterface,
    SimulatedGPSInterface,
)
from radio_telemetry_tracker_drone_fds.ping_finder import PingFinderModule
from radio_telemetry_tracker_drone_fds.ping_finder.online_ping_finder_manager import OnlinePingFinderManager
from radio_telemetry_tracker_drone_fds.state.state_manager import StateManager
from radio_telemetry_tracker_drone_fds.utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)

# Global reference to prevent garbage collection
_online_manager = None


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
    """Search for ping_finder_config.yaml on first mounted USB directory.

    Returns:
        Path | None: Path to the configuration file if found, else None.
    """
    usb_media_path = Path("/media") / os.getenv("USER", "")
    if not usb_media_path.exists():
        logger.error("USB media path %s does not exist.", usb_media_path)
        return None

    # Only check first device
    for device in usb_media_path.iterdir():
        config_path = device / "ping_finder_config.yaml"
        if config_path.exists():
            logger.info("Found ping_finder_config.yaml at %s", config_path)
            return config_path
        logger.error("ping_finder_config.yaml not found on USB device %s", device)
        return None

    logger.error("No USB devices found.")
    return None


def initialize_drone_comms(hardware_config: HardwareConfig) -> DroneComms | None:
    """Initialize DroneComms if in ONLINE mode.

    Args:
        hardware_config: Hardware configuration object

    Returns:
        DroneComms instance if in ONLINE mode, None otherwise
    """
    if PingFinderConfig.OPERATION_MODE != "ONLINE":
        return None

    radio_config = RadioConfig(
        interface_type=hardware_config.RADIO_INTERFACE.lower(),
        port=hardware_config.RADIO_PORT,
        baudrate=hardware_config.RADIO_BAUDRATE,
        host=hardware_config.RADIO_HOST,
        tcp_port=hardware_config.RADIO_TCP_PORT,
        server_mode=hardware_config.RADIO_SERVER_MODE,
    )

    try:
        return DroneComms(radio_config=radio_config)
    except Exception:
        logger.exception("Failed to initialize DroneComms")
        raise


def wait_for_gps_ready(state_manager: StateManager, timeout: int = 300) -> bool:
    """Wait for GPS module to be ready within the specified timeout."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if state_manager.get_gps_state() == "Running":
            logger.info("GPS is ready.")
            return True
        time.sleep(1)
    logger.warning("GPS not ready after %d seconds.", timeout)
    return False


def get_output_directory(hardware_config: HardwareConfig) -> Path:
    """Determine the output directory based on hardware configuration.

    Args:
        hardware_config: Hardware configuration object

    Returns:
        Path to the output directory
    """
    if hardware_config.USE_USB_STORAGE:
        usb_media_path = Path("/media") / os.getenv("USER", "")
        if not usb_media_path.exists():
            logger.error("USB media path %s does not exist.", usb_media_path)
            msg = f"USB media path {usb_media_path} does not exist"
            raise FileNotFoundError(msg)

        # Find first mounted USB device
        for device in usb_media_path.iterdir():
            return device / "rtt_output"

        msg = "No USB storage device found"
        logger.error(msg)
        raise FileNotFoundError(msg)

    # If not using USB storage, use project root
    return Path.cwd() / "rtt_output"


def initialize_modules(hardware_config: HardwareConfig) -> tuple[DroneComms | None, StateManager, GPSModule]:
    """Initialize all required modules.

    Args:
        hardware_config: Hardware configuration object

    Returns:
        Tuple of (DroneComms | None, StateManager, GPSModule)
    """
    # Initialize DroneComms if in ONLINE mode
    drone_comms = initialize_drone_comms(hardware_config)
    if PingFinderConfig.OPERATION_MODE == "ONLINE" and drone_comms is None:
        logger.error("Failed to initialize DroneComms in ONLINE mode")
        sys.exit(1)

    # Initialize StateManager
    state_manager = StateManager()

    # Initialize GPS module
    gps_interface = initialize_gps_interface(hardware_config)
    gps_module = GPSModule(gps_interface, PingFinderConfig.EPSG_CODE, state_manager)

    return drone_comms, state_manager, gps_module


def run_online_mode(
    gps_module: GPSModule,
    state_manager: StateManager,
    drone_comms: DroneComms,
    hardware_config: HardwareConfig,
) -> None:
    """Run the application in online mode.

    Args:
        gps_module: Initialized GPS module
        state_manager: State manager instance
        drone_comms: DroneComms instance
        hardware_config: Hardware configuration
    """
    OnlinePingFinderManager(
        gps_module=gps_module,
        state_manager=state_manager,
        drone_comms=drone_comms,
        hardware_config=hardware_config,
    )
    logger.info("Waiting for configuration from base station...")

    # Main loop - keep program running
    while True:
        time.sleep(1)


def run_offline_mode(
    gps_module: GPSModule,
    state_manager: StateManager,
    hardware_config: HardwareConfig,
) -> PingFinderModule:
    """Run the application in offline mode.

    Args:
        gps_module: Initialized GPS module
        state_manager: State manager instance
        hardware_config: Hardware configuration

    Returns:
        Initialized and started PingFinderModule
    """
    # Load config from file
    config_path = get_config_path(hardware_config)
    if not config_path:
        logger.error("PingFinder configuration not found.")
        sys.exit(1)

    # Load base config from file
    config_data = yaml.loads(config_path.read_text())
    # Update output directory
    config_data["output_dir"] = str(get_output_directory(hardware_config))
    ping_finder_config = PingFinderConfig.from_dict(config_data)

    # Initialize and start PingFinder module
    ping_finder_module = PingFinderModule(
        gps_module=gps_module,
        config=ping_finder_config,
        state_manager=state_manager,
        sdr_type=hardware_config.SDR_TYPE,
        drone_comms=None,
    )
    ping_finder_module.start()

    return ping_finder_module


def get_config_path(hardware_config: HardwareConfig) -> Path | None:
    """Get the path to the ping finder configuration file.

    Args:
        hardware_config: Hardware configuration object

    Returns:
        Path to the configuration file if found, else None
    """
    if hardware_config.USE_USB_STORAGE:
        return find_ping_finder_config()

    config_path = Path("./config/ping_finder_config.yaml")
    return config_path if config_path.exists() else None


def main() -> None:
    """Main function to initialize and start modules."""
    setup_logging()

    try:
        # Load hardware configuration
        hardware_config = HardwareConfig.load_from_file(Path("./config/hardware_config.yaml"))

        # Initialize modules
        drone_comms, state_manager, gps_module = initialize_modules(hardware_config)

        # Start GPS module in a separate thread
        gps_thread = threading.Thread(target=gps_module.run, daemon=True)
        gps_thread.start()

        # Wait for GPS to be ready
        if not wait_for_gps_ready(state_manager):
            logger.error("GPS failed to initialize within the timeout period.")
            sys.exit(1)

        # Run in appropriate mode
        ping_finder_module = None
        if PingFinderConfig.OPERATION_MODE == "ONLINE":
            run_online_mode(gps_module, state_manager, drone_comms, hardware_config)
        else:
            ping_finder_module = run_offline_mode(gps_module, state_manager, hardware_config)
            # Main loop - keep program running
            while True:
                time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt. Shutting down.")
    except Exception:
        logger.exception("An unexpected error occurred.")
    finally:
        if "gps_module" in locals():
            gps_module.stop()
        if ping_finder_module is not None:
            ping_finder_module.stop()


if __name__ == "__main__":
    main()
