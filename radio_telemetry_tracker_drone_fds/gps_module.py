"""GPS module for handling GPS data acquisition and processing."""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import NamedTuple

import smbus2

from radio_telemetry_tracker_drone_fds.config import GPS_ADDRESS, GPS_I2C_BUS


class GPSData(NamedTuple):
    """Represents GPS data with latitude, longitude, altitude, and heading."""

    latitude: float | None
    longitude: float | None
    altitude: float | None
    heading: float | None


class GPSState(Enum):
    """Represents the current state of the GPS module."""

    NOT_READY = "Not Ready"
    WAITING = "Waiting"
    PARTIAL = "Partial"
    READY = "Ready"
    ERRORED = "Errored"


class GPSModule:
    """Handles GPS data acquisition and processing using I2C communication."""

    GPS_DATA_TIMEOUT = 5  # seconds
    GNRMC_MIN_PARTS = 8
    GNGGA_MIN_PARTS = 10

    def __init__(self) -> None:
        """Initialize the GPS module with I2C bus and device address."""
        logging.basicConfig(level=logging.INFO)
        self._logger = logging.getLogger(__name__)
        self._logger.debug("Initializing GPSModule")
        self._i2c_bus = GPS_I2C_BUS
        self._neo_m9n_address = GPS_ADDRESS
        self._bus = smbus2.SMBus(self._i2c_bus)
        self._buffer = ""
        self._gps_data = GPSData(None, None, None, None)
        self._lock = threading.Lock()
        self._running = True
        self._state = GPSState.NOT_READY
        self._last_update_time = 0

    def _read_gps_data(self, total_length: int = 32) -> list[int] | None:
        try:
            return self._bus.read_i2c_block_data(
                self._neo_m9n_address,
                0xFF,
                total_length,
            )
        except OSError:
            logging.exception("Error reading GPS data")
            self._state = GPSState.ERRORED
            return None

    def _process_buffer(self) -> str:
        sentences = self._buffer.split("\n")
        data_updated, new_gps_data = self._process_sentences(sentences[:-1])

        if data_updated and new_gps_data:
            self._update_gps_data(new_gps_data)
        elif time.time() - self._last_update_time > self.GPS_DATA_TIMEOUT:
            self._state = GPSState.WAITING

        return sentences[-1]

    def _process_sentences(self, sentences: list[str]) -> tuple[bool, GPSData | None]:
        data_updated = False
        new_gps_data = None
        for sentence in sentences:
            if sentence.startswith("$GNRMC"):
                new_gps_data = self._process_gnrmc(sentence, new_gps_data)
                data_updated = True
            elif sentence.startswith("$GNGGA"):
                new_gps_data = self._process_gngga(sentence, new_gps_data)
                data_updated = True
        return data_updated, new_gps_data

    def _process_gnrmc(
        self,
        sentence: str,
        current_data: GPSData | None,
    ) -> GPSData | None:
        parts = sentence.split(",")
        if len(parts) >= self.GNRMC_MIN_PARTS:
            lat = self._convert_to_degrees(parts[3], parts[4], is_latitude=True)
            lon = self._convert_to_degrees(parts[5], parts[6], is_latitude=False)
            heading = float(parts[8]) if parts[8] else None
            return GPSData(
                lat,
                lon,
                current_data.altitude if current_data else None,
                heading,
            )
        return current_data

    def _process_gngga(
        self,
        sentence: str,
        current_data: GPSData | None,
    ) -> GPSData | None:
        parts = sentence.split(",")
        if len(parts) >= self.GNGGA_MIN_PARTS:
            altitude = float(parts[9]) if parts[9] else None
            if current_data:
                return GPSData(
                    current_data.latitude,
                    current_data.longitude,
                    altitude,
                    current_data.heading,
                )
            return GPSData(
                self._gps_data.latitude,
                self._gps_data.longitude,
                altitude,
                self._gps_data.heading,
            )
        return current_data

    def _update_gps_data(self, new_gps_data: GPSData) -> None:
        with self._lock:
            old_data = self._gps_data
            self._gps_data = GPSData(
                new_gps_data.latitude or old_data.latitude,
                new_gps_data.longitude or old_data.longitude,
                new_gps_data.altitude or old_data.altitude,
                new_gps_data.heading or old_data.heading,
            )

        self._last_update_time = time.time()

        # Check if any of the critical values (lat, lon, alt) are zero or None
        critical_values = [
            self._gps_data.latitude,
            self._gps_data.longitude,
            self._gps_data.altitude,
        ]
        zero_values = [v for v in critical_values if v == 0 or v is None]

        if len(zero_values) == len(critical_values):
            self._state = GPSState.WAITING
        elif len(zero_values) > 0:
            self._state = GPSState.PARTIAL
        else:
            self._state = GPSState.READY

    def _convert_to_degrees(
        self,
        value: str,
        direction: str,
        *,
        is_latitude: bool,
    ) -> float:
        if not value or not direction:
            return 0.0
        degrees = float(value[: 2 if is_latitude else 3])
        minutes = float(value[2 if is_latitude else 3 :])
        decimal_degrees = degrees + minutes / 60
        return -decimal_degrees if direction in ["S", "W"] else decimal_degrees

    def run(self) -> None:
        """Continuously read and process GPS data."""
        self._logger.info("Starting GPS data acquisition loop")
        self._state = GPSState.WAITING
        while self._running:
            data = self._read_gps_data(32)
            if data:
                self._buffer += "".join(chr(c) for c in data)
                self._buffer = self._process_buffer()
            else:
                self._logger.debug("No GPS data received")
            time.sleep(0.1)

    def get_gps_data(self) -> tuple[GPSData, GPSState]:
        """Return the current GPS data and state."""
        with self._lock:
            return self._gps_data, self._state

    def stop(self) -> None:
        """Stop the GPS module's data acquisition loop."""
        self.running = False

    def is_ready(self) -> bool:
        """Check if the GPS module is in READY state."""
        _, state = self.get_gps_data()
        return state == GPSState.READY
