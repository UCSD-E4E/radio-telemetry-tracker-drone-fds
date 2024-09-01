"""Main module for the Radio Telemetry Tracker Drone FDS."""

import logging
import threading

from radio_telemetry_tracker_drone_fds.data_processor import DataProcessor
from radio_telemetry_tracker_drone_fds.gps_module import GPSModule


def main() -> None:
    """Initialize and run the Radio Telemetry Tracker Drone FDS."""
    gps_module = GPSModule()
    data_processor = DataProcessor()

    gps_module.set_callback(data_processor.process_gps_data)

    gps_thread = threading.Thread(target=gps_module.run)
    gps_thread.start()

    try:
        while True:
            # Main loop
            pass
    except KeyboardInterrupt:
        logging.info("Stopping GPS module...")
        gps_module.stop()
        gps_thread.join()

if __name__ == "__main__":
    main()
