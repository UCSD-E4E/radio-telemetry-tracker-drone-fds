"""Main entry point for the Radio Telemetry Tracker Drone FDS application."""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Callable
import json

from radio_telemetry_tracker_drone_comms_package import (
    ConfigRequestData,
    ConfigResponseData,
    DroneComms,
    GPSData,
    RadioConfig,
    SyncRequestData,
    SyncResponseData,
    StartRequestData,
    StartResponseData,
)

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
    """Search for ping_finder_config.json on first mounted USB directory.

    Returns:
        Path | None: Path to the configuration file if found, else None.
    """
    usb_media_path = Path("/media") / os.getenv("USER", "")
    if not usb_media_path.exists():
        logger.error("USB media path %s does not exist.", usb_media_path)
        return None

    # Only check first device
    for device in usb_media_path.iterdir():
        config_path = device / "ping_finder_config.json"
        if config_path.exists():
            logger.info("Found ping_finder_config.json at %s", config_path)
            return config_path
        else:
            logger.error("ping_finder_config.json not found on USB device %s", device)
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
    if hardware_config.OPERATION_MODE != "ONLINE":
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


def create_sync_request_handler(
    state_manager: StateManager,
    drone_comms: DroneComms,
) -> Callable[[SyncRequestData], None]:
    """Create a sync request handler with access to state_manager and drone_comms.

    Args:
        state_manager: State manager instance to check GPS state
        drone_comms: DroneComms instance to send response

    Returns:
        Callback function that handles sync requests
    """
    def handle_sync_request(data: SyncRequestData) -> None:
        gps_state = state_manager.get_gps_state()
        success = gps_state == "Locked"
        drone_comms.send_sync_response(SyncResponseData(success=success))

    return handle_sync_request


def send_gps_data_loop(state_manager: StateManager, drone_comms: DroneComms) -> None:
    """Continuously send GPS data when GPS is locked.

    Args:
        state_manager: State manager instance to check GPS state and get data
        drone_comms: DroneComms instance to send GPS data
    """
    while True:
        if state_manager.get_gps_state() == "Locked":
            gps_data = state_manager.get_current_gps_data()
            drone_comms.send_gps_data(GPSData(easting=gps_data.easting, northing=gps_data.northing, altitude=gps_data.altitude, heading=gps_data.heading, epsg_code=gps_data.epsg_code))
        time.sleep(1)  # Send GPS data every second when locked


def create_start_request_handler(
    ping_finder_module: PingFinderModule,
    drone_comms: DroneComms,
) -> Callable[[StartRequestData], None]:
    """Create a start request handler for the ping finder module.

    Args:
        ping_finder_module: PingFinder module instance to start
        drone_comms: DroneComms instance to send response

    Returns:
        Callback function that handles start requests
    """
    def handle_start_request(data: StartRequestData) -> None:
        try:
            ping_finder_module.start()
            drone_comms.send_start_response(StartResponseData(success=True))
        except Exception:
            logger.exception("Failed to start ping finder")
            drone_comms.send_start_response(StartResponseData(success=False))

    return handle_start_request


def main() -> None:
    """Main function to initialize and start modules."""
    setup_logging()

    try:
        # Load hardware configuration
        hardware_config = HardwareConfig.load_from_file(Path("./config/hardware_config.json"))

        # Initialize DroneComms if in ONLINE mode
        drone_comms = initialize_drone_comms(hardware_config)
        if hardware_config.OPERATION_MODE == "ONLINE" and drone_comms is None:
            logger.error("Failed to initialize DroneComms in ONLINE mode")
            sys.exit(1)

        # Initialize StateManager
        state_manager = StateManager()

        # Register sync request handler if in ONLINE mode
        if drone_comms is not None:
            sync_handler = create_sync_request_handler(state_manager, drone_comms)
            drone_comms.register_sync_request_handler(sync_handler)
            drone_comms.start()

            # Start GPS data sending thread
            gps_sender_thread = threading.Thread(
                target=send_gps_data_loop,
                args=(state_manager, drone_comms),
                daemon=True,
            )
            gps_sender_thread.start()

        # Initialize GPS module
        gps_interface = initialize_gps_interface(hardware_config)
        gps_module = GPSModule(gps_interface, hardware_config.EPSG_CODE, state_manager)

        # Start GPS module in a separate thread
        gps_thread = threading.Thread(target=gps_module.run, daemon=True)
        gps_thread.start()

        # Wait for GPS to be ready
        if not wait_for_gps_ready(state_manager):
            logger.error("GPS failed to initialize within the timeout period.")
            sys.exit(1)

        # Get PingFinder configuration based on operation mode
        if hardware_config.OPERATION_MODE == "ONLINE":
            # Wait for config from base station
            ping_finder_config = wait_for_config_data(state_manager, drone_comms, hardware_config)
            if ping_finder_config is None:
                logger.error("Failed to receive configuration data from base station")
                sys.exit(1)
        else:
            # OFFLINE mode - load from file
            if hardware_config.USE_USB_STORAGE:
                config_path = find_ping_finder_config()
                if not config_path:
                    logger.error("PingFinder configuration not found on USB stick.")
                    sys.exit(1)
            else:
                config_path = Path("./config/ping_finder_config.json")
                if not config_path.exists():
                    logger.error("PingFinder configuration not found at ./config/ping_finder_config.json")
                    sys.exit(1)
            
            # Load base config from file
            config_data = json.loads(config_path.read_text())
            # Update output directory
            config_data["output_dir"] = str(get_output_directory(hardware_config))
            ping_finder_config = PingFinderConfig.from_dict(config_data)

        # Initialize PingFinder module
        ping_finder_module = PingFinderModule(
            gps_module=gps_module,
            config=ping_finder_config,
            state_manager=state_manager,
            sdr_type=hardware_config.SDR_TYPE,
            drone_comms=drone_comms,
        )

        if hardware_config.OPERATION_MODE == "ONLINE":
            # Register start request handler and wait for start command
            start_handler = create_start_request_handler(ping_finder_module, drone_comms)
            drone_comms.register_start_request_handler(start_handler)
            logger.info("Waiting for start command from base station...")
        else:
            # In OFFLINE mode, start immediately
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


def wait_for_config_data(
    state_manager: StateManager, 
    drone_comms: DroneComms, 
    hardware_config: HardwareConfig,
    timeout: int = 300,
) -> PingFinderConfig | None:
    """Wait for configuration data from base station within timeout period."""
    config_received = threading.Event()
    config_data = None

    def config_handler(data: ConfigRequestData) -> None:
        nonlocal config_data
        # Create PingFinderConfig from received data
        config_dict = {
            "gain": data.gain,
            "sampling_rate": data.sampling_rate,
            "center_frequency": data.center_frequency,
            "run_num": data.run_num,
            "enable_test_data": data.enable_test_data,
            "ping_width_ms": data.ping_width_ms,
            "ping_min_snr": data.ping_min_snr,
            "ping_max_len_mult": data.ping_max_len_mult,
            "ping_min_len_mult": data.ping_min_len_mult,
            "target_frequencies": data.target_frequencies,
            "output_dir": str(get_output_directory(hardware_config))
        }
        config_data = PingFinderConfig.from_dict(config_dict)
        config_received.set()
        # Send success response
        drone_comms.send_config_response(ConfigResponseData(success=True))

    # Register config handler
    drone_comms.register_config_request_handler(config_handler)

    # Wait for config data
    if config_received.wait(timeout):
        drone_comms.unregister_config_request_handler(config_handler)
        return config_data
    
    drone_comms.unregister_config_request_handler(config_handler)
    return None


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
            raise FileNotFoundError(f"USB media path {usb_media_path} does not exist")
        
        # Find first mounted USB device
        for device in usb_media_path.iterdir():
            return device / "rtt_output"
        
        msg = "No USB storage device found"
        logger.error(msg)
        raise FileNotFoundError(msg)
    
    # If not using USB storage, use project root
    return Path.cwd() / "rtt_output"


if __name__ == "__main__":
    main()
