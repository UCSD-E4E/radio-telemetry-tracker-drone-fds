"""Module for handling ping finding operations using SDR."""

import datetime as dt
import logging
import threading
from enum import Enum

from rct_dsp2 import PingFinder

from radio_telemetry_tracker_drone_fds.config import PING_FINDER_CONFIG
from radio_telemetry_tracker_drone_fds.gps_module import GPSModule


class PingFinderState(Enum):
    """Represents the current state of the PingFinderModule."""

    NOT_READY = "Not Ready"
    READY = "Ready"
    RUNNING = "Running"
    STOPPED = "Stopped"
    ERRORED = "Errored"


class PingFinderModule:
    """Handles ping finding operations using SDR."""

    def __init__(self, gps_module: GPSModule) -> None:
        """Initialize PingFinderModule with configured PingFinder and GPSModule."""
        self._ping_finder = PingFinder()
        self._configure_ping_finder()
        self._gps_module = gps_module
        self._state = PingFinderState.READY
        self._stop_event = threading.Event()

    def _configure_ping_finder(self) -> None:
        for key, value in PING_FINDER_CONFIG.items():
            setattr(self._ping_finder, key, value)
        self._ping_finder.register_callback(self._callback)
        self._state = PingFinderState.READY

    def _callback(self, now: dt.datetime, amplitude: float, frequency: int) -> None:
        gps_data, _ = self._gps_module.get_gps_data()
        logging.info("=" * 60)
        logging.info("Timestamp: %s", now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
        logging.info("Frequency: %d Hz", frequency)
        logging.info("Amplitude: %.2f", amplitude)
        logging.info("-" * 60)
        logging.info("GPS Data:")
        logging.info(
            f"  Latitude:  {gps_data.latitude:.6f}"
            if gps_data.latitude is not None
            else "  Latitude:  N/A",
        )
        logging.info(
            f"  Longitude: {gps_data.longitude:.6f}"
            if gps_data.longitude is not None
            else "  Longitude: N/A",
        )
        logging.info("=" * 60)

    def start(self) -> None:
        """Start the ping finding operation in a separate thread."""
        if self._state == PingFinderState.READY:
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run)
            self._thread.start()
            self._state = PingFinderState.RUNNING

    def stop(self) -> None:
        """Stop the ping finding operation."""
        if self._state == PingFinderState.RUNNING:
            self._stop_event.set()
            self._ping_finder.stop()
            if self._thread:
                self._thread.join()
            self._state = PingFinderState.STOPPED

    def _run(self) -> None:
        try:
            self._ping_finder.start()
            while not self._stop_event.is_set():
                # Add a small sleep to prevent busy-waiting
                self._stop_event.wait(0.1)
        except (OSError, RuntimeError):
            logging.exception("PingFinder error")
            self._state = PingFinderState.ERRORED
        finally:
            if self._state != PingFinderState.ERRORED:
                self._state = PingFinderState.STOPPED

    def get_state(self) -> PingFinderState:
        """Return the current state of the PingFinderModule."""
        return self._state
