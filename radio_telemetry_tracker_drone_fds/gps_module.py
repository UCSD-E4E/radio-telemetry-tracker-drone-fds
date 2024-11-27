"""Module for handling GPS data acquisition and processing."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

import serial

from radio_telemetry_tracker_drone_fds.drone_state import (
    GPSData,
    GPSState,
    update_gps_data,
    update_gps_state,
)

if TYPE_CHECKING:
    from collections.abc import Generator


class CoordinateType(Enum):
    """Type of GPS coordinate."""
    LATITUDE = "latitude"
    LONGITUDE = "longitude"


class GPSInterface(ABC):
    """Abstract base class for GPS communication interfaces."""

    @abstractmethod
    def read_gps_data(self, total_length: int = 32) -> list[int] | None:
        """Read GPS data from the interface.

        Args:
            total_length: Number of bytes to read.

        Returns:
            List of integers representing the GPS data, or None if read failed.
        """


class I2CGPSInterface(GPSInterface):
    """GPS interface using I2C communication."""

    def __init__(self, bus_number: int, address: int) -> None:
        """Initialize I2C GPS interface.

        Args:
            bus_number: I2C bus number.
            address: I2C device address.
        """
        import smbus2

        self._bus = smbus2.SMBus(bus_number)
        self._address = address

    def read_gps_data(self, total_length: int = 32) -> list[int] | None:
        """Read GPS data from I2C interface.

        Args:
            total_length: Number of bytes to read.

        Returns:
            List of integers representing the GPS data, or None if read failed.
        """
        try:
            return self._bus.read_i2c_block_data(self._address, 0xFF, total_length)
        except OSError:
            logging.exception("Error reading GPS data over I2C")
            return None


class SerialGPSInterface(GPSInterface):
    """GPS interface using Serial communication."""

    def __init__(self, port: str, baudrate: int) -> None:
        """Initialize Serial GPS interface.

        Args:
            port: Serial port name.
            baudrate: Serial communication speed.
        """
        import serial

        self._serial_port = serial.Serial(port, baudrate, timeout=1)

    def read_gps_data(self, total_length: int = 32) -> list[int] | None:
        """Read GPS data from Serial interface.

        Args:
            total_length: Number of bytes to read.

        Returns:
            List of integers representing the GPS data, or None if read failed.
        """
        try:
            data = self._serial_port.read(total_length)
            return list(data)
        except serial.SerialException:
            logging.exception("Error reading GPS data over Serial")
            return None

class SimulatedGPSInterface(GPSInterface):
    """GPS interface using simulated data."""

    def __init__(self, simulation_speed: float = 1.0) -> None:
        """Initialize Simulated GPS interface.

        Args:
            simulation_speed: Speed multiplier for simulation.
        """
        self._simulation_speed = simulation_speed
        self._start_time = time.time()
        self._data_generator = self._generate_simulated_data()

    def _generate_simulated_data(self) -> Generator[list[int], None, None]:
        """Generate simulated GPS data.

        Yields:
            Lists of integers representing the GPS data.
        """
        lat = 32.7157  # Starting latitude (e.g., San Diego, CA)
        lon = -117.1611  # Starting longitude
        altitude = 20  # Starting altitude
        while True:
            elapsed_time = (time.time() - self._start_time) * self._simulation_speed
            current_lat = lat + 0.0001 * elapsed_time
            current_lon = lon + 0.0001 * elapsed_time
            current_alt = altitude + 0.01 * elapsed_time  # Ascend at 0.1m/s

            # Create NMEA sentences
            gngga = (
                f"$GNGGA,123519,{self._format_coordinate(current_lat, CoordinateType.LATITUDE)},N,"
                f"{self._format_coordinate(current_lon, CoordinateType.LONGITUDE)},W,"
                f"1,08,0.9,{current_alt},M,0.0,M,,*47"
            )
            gnrmc = (
                f"$GNRMC,123519,A,{self._format_coordinate(current_lat, CoordinateType.LATITUDE)},N,"
                f"{self._format_coordinate(current_lon, CoordinateType.LONGITUDE)},W,"
                f"0.5,054.7,181194,020.3,E*68"
            )

            sentences = gngga + "\n" + gnrmc + "\n"
            yield [ord(c) for c in sentences]
            time.sleep(1 / self._simulation_speed)

    def _format_coordinate(self, value: float, coordinate_type: CoordinateType) -> str:
        """Format coordinate value into NMEA format.

        Args:
            value: The coordinate value in decimal degrees.
            coordinate_type: Type of coordinate (latitude or longitude).

        Returns:
            Formatted coordinate string in NMEA format.
        """
        # Handle negative values properly
        abs_value = abs(value)

        degrees = int(abs_value)
        minutes = (abs_value - degrees) * 60

        if coordinate_type == CoordinateType.LATITUDE:
            return f"{degrees:02d}{minutes:07.4f}"
        return f"{degrees:03d}{minutes:07.4f}"

    def read_gps_data(self, _: int = 128) -> list[int] | None:
        """Read simulated GPS data.

        Args:
            _: Unused parameter for interface compatibility.

        Returns:
            List of integers representing the GPS data, or None if generation failed.
        """
        try:
            return next(self._data_generator)
        except StopIteration:
            return None


class GPSModule:
    """Handles GPS data acquisition and processing using a GPS interface."""

    GPS_DATA_TIMEOUT = 5  # seconds
    GPS_RETRY_INTERVAL = 1  # seconds
    GNRMC_MIN_PARTS = 8
    GNGGA_MIN_PARTS = 10

    def __init__(self, gps_interface: GPSInterface) -> None:
        """Initialize the GPS module with a GPS interface."""
        logging.basicConfig(level=logging.INFO)
        self._logger = logging.getLogger(__name__)
        self._logger.debug("Initializing GPSModule")
        self._gps_interface = gps_interface
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
        data = self._gps_interface.read_gps_data(total_length)
        if data is None:
            self._logger.debug("No GPS data received")
            self._error_count += 1
            if self._error_count >= self._max_errors:
                self._update_gps_state(GPSState.ERRORED)
        return data

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
            data = self._read_gps_data(32)
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
