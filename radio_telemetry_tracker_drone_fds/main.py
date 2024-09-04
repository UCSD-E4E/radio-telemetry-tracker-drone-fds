"""Main module for the Radio Telemetry Tracker Drone FDS."""

import asyncio
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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


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


async def print_heartbeat(
    gps_module: GPSModule,
    ping_finder_module: PingFinderModule,
) -> None:
    """Print periodic heartbeat messages with GPS and PingFinder status."""
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

        await asyncio.sleep(5)  # Non-blocking sleep


def run_gps_module(gps_module: GPSModule) -> None:
    """Run the GPS module."""
    gps_module.run()


def run_ping_finder(ping_finder_module: PingFinderModule) -> None:
    """Start the PingFinder module."""
    ping_finder_module.start()


async def run() -> None:
    """Initialize and run the Radio Telemetry Tracker Drone FDS."""
    setup_logging()
    check_sudo()

    gps_module = GPSModule()
    ping_finder_module = PingFinderModule(gps_module)

    gps_thread = threading.Thread(target=run_gps_module, args=(gps_module,))
    gps_thread.start()

    # Wait for GPS to be ready
    wait_for_gps_ready(gps_module)

    # Start ping finder only after GPS is ready
    ping_finder_thread = threading.Thread(
        target=run_ping_finder,
        args=(ping_finder_module,),
    )
    ping_finder_thread.start()

    await print_heartbeat(gps_module, ping_finder_module)


def main() -> None:
    """Entry point for the Radio Telemetry Tracker Drone FDS."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
