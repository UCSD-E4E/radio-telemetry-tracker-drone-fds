"""Main module for the Radio Telemetry Tracker Drone FDS."""

import logging
import os
import sys
import threading
import time

from radio_telemetry_tracker_drone_fds.gps_module import GPSModule
from radio_telemetry_tracker_drone_fds.ping_finder_module import PingFinderModule

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure basic logging for the application."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove all existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def check_sudo() -> None:
    """Check if the program is running with sudo privileges."""
    if os.geteuid() != 0:
        logger.error("This program must be run with sudo privileges.")
        sys.exit(1)


def wait_for_gps_ready(gps_module: GPSModule) -> None:
    """Wait until the GPS module is ready."""
    logger.info("Waiting for GPS to be ready...")
    while not gps_module.is_ready():
        time.sleep(0.1)
    logger.info("GPS is ready.")


def print_heartbeat(
    gps_module: GPSModule,
    ping_finder_module: PingFinderModule,
) -> None:
    """Print periodic heartbeat messages with GPS and PingFinder status."""
    logger.debug("print_heartbeat called")
    while True:
        gps_data, gps_state = gps_module.get_gps_data()
        ping_finder_state = ping_finder_module.get_state()

        logger.info("GPS State: %s", gps_state.value)
        logger.info("PingFinder State: %s", ping_finder_state.value)
        logger.info(
            "GPS Data: Lat: %s, Lon: %s, Alt: %s",
            gps_data.latitude,
            gps_data.longitude,
            gps_data.altitude,
        )
        logger.info("-" * 40)

        time.sleep(5)  # Non-blocking sleep


def run_gps_module(gps_module: GPSModule) -> None:
    """Run the GPS module."""
    gps_module.run()


def run_ping_finder(ping_finder_module: PingFinderModule) -> None:
    """Start the PingFinder module."""
    ping_finder_module.start()


def run() -> None:
    """Initialize and run the Radio Telemetry Tracker Drone FDS."""
    setup_logging()
    check_sudo()

    logger.info("Starting run function")

    logger.info("Initializing GPS module")
    gps_module = GPSModule()
    logger.info("Initializing PingFinder module")
    ping_finder_module = PingFinderModule(gps_module)

    logger.info("Starting GPS thread")
    gps_thread = threading.Thread(target=run_gps_module, args=(gps_module,))
    gps_thread.start()

    logger.info("Waiting for GPS to be ready")
    wait_for_gps_ready(gps_module)
    logger.info("GPS is ready")

    logger.info("Starting PingFinder thread")
    ping_finder_thread = threading.Thread(
        target=run_ping_finder,
        args=(ping_finder_module,),
    )
    ping_finder_thread.start()

    logger.info("Starting heartbeat")
    print_heartbeat(gps_module, ping_finder_module)


def main() -> None:
    """Entry point for the Radio Telemetry Tracker Drone FDS."""
    run()


if __name__ == "__main__":
    main()
