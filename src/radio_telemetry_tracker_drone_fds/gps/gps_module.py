"""Module for handling GPS data acquisition and processing."""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

import pynmea2
import pyproj

from radio_telemetry_tracker_drone_fds.state import GPSData
from radio_telemetry_tracker_drone_fds.state.state_manager import GPSState

if TYPE_CHECKING:
    from radio_telemetry_tracker_drone_fds.gps.gps_interface import GPSInterface
    from radio_telemetry_tracker_drone_fds.state import StateManager

logger = logging.getLogger(__name__)


class GPSModule:
    """Handles GPS data acquisition and processing using a GPS interface."""

    GPS_DATA_TIMEOUT = 5  # seconds
    GPS_RETRY_INTERVAL = 1  # seconds

    def __init__(self, gps_interface: GPSInterface, epsg_code: int, state_manager: StateManager) -> None:
        """Initialize the GPS module with a GPS interface."""
        self._gps_interface = gps_interface
        self._state_manager = state_manager
        self._buffer = ""
        self._running = threading.Event()
        self._error_count = 0
        self._max_errors = 5
        self._epsg_code = epsg_code
        self._transformer = pyproj.Transformer.from_crs("epsg:4326", f"epsg:{self._epsg_code}", always_xy=True)
        self._last_update_time = time.time()

        # Set to IDLE after initialization
        self._state_manager.set_gps_state(GPSState.IDLE)

    def _read_gps_data(self, total_length: int = 32) -> list[int] | None:
        data = self._gps_interface.read_gps_data(total_length)
        if data is None:
            self._error_count += 1
            if self._error_count >= self._max_errors:
                self._state_manager.set_gps_state(GPSState.ERROR)
                logger.error("Maximum error count reached in GPS data reading.")
        else:
            self._error_count = 0  # Reset error count on successful read
        return data

    def _process_buffer(self) -> None:
        """Process the current buffer to extract and parse NMEA sentences."""
        sentences = self._buffer.split("\n")
        self._buffer = sentences[-1]  # Keep the incomplete sentence
        sentences = sentences[:-1]  # Process complete sentences

        data_updated, new_gps_data = self._process_sentences(sentences)

        if data_updated and new_gps_data:
            self._update_gps_data(new_gps_data)
        elif (time.time() - self._last_update_time > self.GPS_DATA_TIMEOUT and
              self._state_manager.get_gps_state() == GPSState.RUNNING.value):
            # If we timeout waiting for data, stay in INITIALIZING state
            self._state_manager.set_gps_state(GPSState.INITIALIZING)

    def _process_sentences(self, sentences: list[str]) -> tuple[bool, GPSData | None]:
        """Parse and process a list of NMEA sentences."""
        data_updated = False
        new_gps_data = GPSData()
        for sentence in sentences:
            stripped_sentence = sentence.strip()
            if not stripped_sentence:
                continue
            try:
                msg = pynmea2.parse(stripped_sentence)
                if isinstance(msg, pynmea2.types.talker.GGA):
                    new_gps_data.altitude = float(msg.altitude) if msg.altitude else None
                elif isinstance(msg, pynmea2.types.talker.RMC):
                    new_gps_data.latitude = msg.latitude if msg.latitude else None
                    new_gps_data.longitude = msg.longitude if msg.longitude else None
                    new_gps_data.heading = float(msg.true_course) if msg.true_course else None
                data_updated = True
            except pynmea2.ParseError:
                logger.warning("Failed to parse NMEA sentence: %s", sentence)
                continue
        return data_updated, new_gps_data if data_updated else None

    def _latlon_to_utm(self, latitude: float, longitude: float) -> tuple[float, float]:
        easting, northing = self._transformer.transform(longitude, latitude)
        return easting, northing

    def _update_gps_data(self, new_gps_data: GPSData) -> None:
        """Update the current GPS data and state."""
        if new_gps_data.latitude is not None and new_gps_data.longitude is not None:
            easting, northing = self._latlon_to_utm(new_gps_data.latitude, new_gps_data.longitude)
            new_gps_data.easting = easting
            new_gps_data.northing = northing
            new_gps_data.epsg_code = self._epsg_code

        self._state_manager.update_gps_data(new_gps_data)
        self._last_update_time = time.time()

        # Only update to RUNNING if we have valid coordinates and in INITIALIZING state
        if new_gps_data.latitude is not None and new_gps_data.longitude is not None:
            current_state = self._state_manager.get_gps_state()
            if current_state == GPSState.INITIALIZING.value:
                self._state_manager.set_gps_state(GPSState.RUNNING)

    def run(self) -> None:
        """Continuously read and process GPS data."""
        # Set to INITIALIZING when starting to wait for lock
        self._state_manager.set_gps_state(GPSState.INITIALIZING)
        self._running.set()

        while self._running.is_set():
            data = self._read_gps_data(32)
            if data:
                try:
                    incoming_data = "".join(chr(c) for c in data)
                    self._buffer += incoming_data
                    self._process_buffer()
                except UnicodeDecodeError:
                    logger.warning("Received non-UTF8 data from GPS interface")
            else:
                time.sleep(self.GPS_RETRY_INTERVAL)

    def stop(self) -> None:
        """Stop the GPS module's data acquisition loop."""
        self._running.clear()
        self._state_manager.set_gps_state(GPSState.IDLE)
