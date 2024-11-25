"""GPS module for handling GPS data acquisition and processing."""

from __future__ import annotations

import logging
import time

import smbus2

from radio_telemetry_tracker_drone_fds.config import config
from radio_telemetry_tracker_drone_fds.drone_state import (
    GPSData,
    GPSState,
    update_gps_data,
    update_gps_state,
)


class GPSModule:
    """Handles GPS data acquisition and processing using I2C communication."""

    GPS_DATA_TIMEOUT = 5  # seconds
    GPS_RETRY_INTERVAL = 1  # seconds
    GNRMC_MIN_PARTS = 8
    GNGGA_MIN_PARTS = 10

    def __init__(self) -> None:
        """Initialize the GPS module with I2C bus and device address."""
        logging.basicConfig(level=logging.INFO)
        self._logger = logging.getLogger(__name__)
        self._logger.debug("Initializing GPSModule")
        self._i2c_bus = config.GPS_I2C_BUS
        self._neo_m9n_address = config.GPS_ADDRESS
        self._bus = smbus2.SMBus(self._i2c_bus)
        self._buffer = ""
        self._running = True
        self._last_update_time = 0
        self._error_count = 0
        self._max_errors = 5
        self._update_gps_state(GPSState.INITIALIZING)
        update_gps_data(GPSData())

    def _update_gps_state(self, new_state: GPSState) -> None:
        """Update the GPS state and log the change."""
        current_state = self.get_gps_data()[1]
        if new_state != current_state:
            self._logger.info(
                "GPS State changed from %s to %s",
                current_state,
                new_state,
            )
            update_gps_state(new_state)

    def _read_gps_data(self, total_length: int = 32) -> list[int] | None:
        try:
            return self._bus.read_i2c_block_data(
                self._neo_m9n_address,
                0xFF,
                total_length,
            )
        except OSError:
            self._logger.exception("Error reading GPS data")
            self._error_count += 1
            if self._error_count >= self._max_errors:
                self._update_gps_state(GPSState.ERRORED)
            return None

    def _process_buffer(self) -> str:
        sentences = self._buffer.split("\n")
        data_updated, new_gps_data = self._process_sentences(sentences[:-1])

        if data_updated and new_gps_data:
            self._update_gps_data(new_gps_data)
            self._error_count = 0  # Reset error count on successful update
        elif time.time() - self._last_update_time > self.GPS_DATA_TIMEOUT:
            self._update_gps_state(GPSState.WAITING)

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
            current_gps_data, _ = self.get_gps_data()
            return GPSData(
                current_gps_data.latitude,
                current_gps_data.longitude,
                altitude,
                current_gps_data.heading,
            )
        return current_data

    def _update_gps_data(self, new_gps_data: GPSData) -> None:
        update_gps_data(new_gps_data)
        self._last_update_time = time.time()

        if all(
            v is not None and v != 0
            for v in [
                new_gps_data.latitude,
                new_gps_data.longitude,
                new_gps_data.altitude,
            ]
        ):
            self._update_gps_state(GPSState.READY)
        elif any(
            v is not None and v != 0
            for v in [
                new_gps_data.latitude,
                new_gps_data.longitude,
                new_gps_data.altitude,
            ]
        ):
            self._update_gps_state(GPSState.PARTIAL)
        else:
            self._update_gps_state(GPSState.WAITING)

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
        self._update_gps_state(GPSState.WAITING)

        while self._running:
            data = None
            try:
                data = self._read_gps_data(32)
            except Exception:
                self._logger.exception("Unexpected error in GPS data acquisition")
                self._update_gps_state(GPSState.ERRORED)
                time.sleep(self.GPS_RETRY_INTERVAL)
                continue

            if data:
                self._buffer += "".join(chr(c) for c in data)
                self._buffer = self._process_buffer()
            else:
                self._logger.debug("No GPS data received")
                time.sleep(self.GPS_RETRY_INTERVAL)

    def get_gps_data(self) -> tuple[GPSData, GPSState]:
        """Return the current GPS data and state."""
        from radio_telemetry_tracker_drone_fds.drone_state import get_current_state

        current_state = get_current_state()
        return current_state.gps_data, current_state.gps_state

    def stop(self) -> None:
        """Stop the GPS module's data acquisition loop."""
        self._running = False
        self._update_gps_state(GPSState.STOPPED)

    def is_ready(self) -> bool:
        """Check if the GPS module is in READY state."""
        _, state = self.get_gps_data()
        return state == GPSState.READY
