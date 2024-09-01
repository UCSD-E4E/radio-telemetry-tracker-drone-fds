"""GPS module for handling GPS data acquisition and processing."""

from __future__ import annotations

import logging
import os
import threading
import time
from enum import Enum
from typing import Callable, NamedTuple

import smbus2


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
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Initializing GPSModule")
        self.i2c_bus = int(os.getenv("GPS_I2C_BUS"))
        self.neo_m9n_address = int(os.getenv("GPS_ADDRESS"), 16)
        self.bus = smbus2.SMBus(self.i2c_bus)
        self.buffer = ""
        self.gps_data = GPSData(None, None, None, None)
        self.lock = threading.Lock()
        self.running = True
        self.callback = None
        self.state = GPSState.NOT_READY
        self.last_update_time = 0

    def set_callback(self, callback: Callable[[GPSData, GPSState], None]) -> None:
        """Set the callback function for GPS data updates."""
        self.callback = callback

    def _read_gps_data(self, total_length: int = 32) -> list[int] | None:
        try:
            return self.bus.read_i2c_block_data(
                self.neo_m9n_address,
                0xFF,
                total_length,
            )
        except OSError:
            logging.exception("Error reading GPS data")
            self.state = GPSState.ERRORED
            return None

    def _process_buffer(self) -> str:
        sentences = self.buffer.split("\n")
        data_updated, new_gps_data = self._process_sentences(sentences[:-1])

        if data_updated and new_gps_data:
            self._update_gps_data(new_gps_data)
        elif time.time() - self.last_update_time > self.GPS_DATA_TIMEOUT:
            self.state = GPSState.WAITING

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
                self.gps_data.latitude,
                self.gps_data.longitude,
                altitude,
                self.gps_data.heading,
            )
        return current_data

    def _update_gps_data(self, new_gps_data: GPSData) -> None:
        with self.lock:
            if self.state == GPSState.READY:
                # If state is READY, only update non-None values
                self.gps_data = GPSData(
                    new_gps_data.latitude or self.gps_data.latitude,
                    new_gps_data.longitude or self.gps_data.longitude,
                    new_gps_data.altitude or self.gps_data.altitude,
                    new_gps_data.heading or self.gps_data.heading,
                )
            else:
                self.gps_data = new_gps_data

        self.last_update_time = time.time()
        self.state = (
            GPSState.READY
            if all(
                getattr(self.gps_data, attr) is not None
                for attr in ["latitude", "longitude", "altitude"]
            )
            else GPSState.WAITING
        )
        if self.callback:
            self.callback(self.gps_data, self.state)

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
        self.logger.info("Starting GPS data acquisition loop")
        self.state = GPSState.WAITING
        while self.running:
            data = self._read_gps_data(32)
            if data:
                self.buffer += "".join(chr(c) for c in data)
                self.buffer = self._process_buffer()
            else:
                self.logger.debug("No GPS data received")
            time.sleep(0.1)

    def _get_gps_data(self) -> tuple[GPSData, GPSState]:
        with self.lock:
            return self.gps_data, self.state

    def stop(self) -> None:
        """Stop the GPS module's data acquisition loop."""
        self.running = False
