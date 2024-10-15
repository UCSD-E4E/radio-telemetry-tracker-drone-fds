"""Main module for the Radio Telemetry Tracker Drone FDS."""

import json
import logging
import os
import sys
import threading
import time

from radio_telemetry_tracker_drone_fds.config import config
from radio_telemetry_tracker_drone_fds.gps_module import GPSModule
from radio_telemetry_tracker_drone_fds.ping_finder_module import PingFinderModule

logger = logging.getLogger(__name__)

def setup_logging() -> None:
    """Configure basic logging settings."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

def check_sudo():
    if os.geteuid() != 0:
        logger.error("This program must be run with sudo privileges.")
        sys.exit(1)

def wait_for_gps_ready(gps_module: GPSModule, timeout: int = 300) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        if gps_module.is_ready():
            logger.info("GPS is ready.")
            return True
        time.sleep(1)
    logger.warning("GPS not ready after %d seconds.", timeout)
    return False

def print_heartbeat(gps_module: GPSModule, ping_finder_module: PingFinderModule):
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

        time.sleep(5)

def run():
    setup_logging()
    check_sudo()

    logger.info("Starting run function")
    logger.info("Configuration: %s", json.dumps(config.to_dict(), indent=2))

    logger.info("Initializing GPS module")
    gps_module = GPSModule()
    logger.info("Initializing PingFinder module")
    ping_finder_module = PingFinderModule(gps_module)

    logger.info("Starting GPS thread")
    gps_thread = threading.Thread(target=gps_module.run, daemon=True)
    gps_thread.start()

    logger.info("Waiting for GPS to be ready")
    if not wait_for_gps_ready(gps_module):
        logger.error("GPS not ready. Exiting the program.")
        sys.exit(1)

    logger.info("Waiting %d seconds before starting PingFinder", config.WAIT_TO_START_TIMER)
    time.sleep(config.WAIT_TO_START_TIMER)

    logger.info("Starting PingFinder thread")
    ping_finder_thread = threading.Thread(target=ping_finder_module.start, daemon=True)
    ping_finder_thread.start()

    logger.info("Starting heartbeat")
    heartbeat_thread = threading.Thread(target=print_heartbeat, args=(gps_module, ping_finder_module), daemon=True)
    heartbeat_thread.start()

    try:
        logger.info("Running for %s seconds", config.RUN_TIMER)
        time.sleep(config.RUN_TIMER)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        logger.info("Stopping all modules")
        gps_module.stop()
        ping_finder_module.stop()
        gps_thread.join(timeout=5)
        ping_finder_thread.join(timeout=5)

def main():
    run()

if __name__ == "__main__":
    main()
