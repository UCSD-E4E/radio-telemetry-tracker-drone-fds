"""Main module for the Radio Telemetry Tracker Drone FDS."""

import logging
import os
import signal
import sys
import threading
import time
import types
from threading import Event

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


def print_heartbeat(
    gps_module: GPSModule,
    ping_finder_module: PingFinderModule,
    stop_event: Event,
) -> None:
    """Print periodic heartbeat messages with GPS and PingFinder status."""
    while not stop_event.is_set():
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

        stop_event.wait(5)


def main() -> None:
    """Initialize and run the Radio Telemetry Tracker Drone FDS."""
    setup_logging()
    check_sudo()

    gps_module = GPSModule()
    ping_finder_module = PingFinderModule(gps_module)

    gps_thread = threading.Thread(target=gps_module.run)
    gps_thread.start()

    wait_for_gps_ready(gps_module)

    ping_finder_module.start()

    stop_event = threading.Event()
    heartbeat_thread = threading.Thread(
        target=print_heartbeat,
        args=(gps_module, ping_finder_module, stop_event),
    )
    heartbeat_thread.start()

    def signal_handler(_signum: int, _frame: types.FrameType) -> None:
        logger.info("Stopping GPS module and ping finder module...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    signal.pause()


if __name__ == "__main__":
    main()
