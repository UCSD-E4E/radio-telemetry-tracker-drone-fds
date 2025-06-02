"""GPS interface classes."""

from __future__ import annotations

import datetime as dt
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import TYPE_CHECKING

import pynmea2

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)


class GPSInterface(ABC):
    """Abstract base class for GPS communication interfaces."""

    @abstractmethod
    def read_gps_data(self, total_length: int = 32) -> list[int] | None:
        """Read GPS data from the interface."""


class I2CGPSInterface(GPSInterface):
    """GPS interface using I2C communication."""

    def __init__(self, bus_number: int, address: int) -> None:
        """Initialize I2C GPS interface."""
        import smbus2

        self._bus = smbus2.SMBus(bus_number)
        self._address = address

    def read_gps_data(self, total_length: int = 32) -> list[int] | None:
        """Read GPS data from I2C interface."""
        try:
            return self._bus.read_i2c_block_data(self._address, 0xFF, total_length)
        except OSError:
            logger.exception("Error reading GPS data over I2C")
            return None


class SerialGPSInterface(GPSInterface):
    """GPS interface using Serial communication."""

    def __init__(self, port: str, baudrate: int) -> None:
        """Initialize Serial GPS interface."""
        import serial

        self._serial_port = serial.Serial(port, baudrate, timeout=1)

    def read_gps_data(self, total_length: int = 32) -> list[int] | None:
        """Read GPS data from Serial interface."""
        import serial

        try:
            data = self._serial_port.read(total_length)
            return list(data)
        except serial.SerialException:
            logger.exception("Error reading GPS data over Serial")
            return None


class SimulatedGPSInterface(GPSInterface):
    """GPS interface using simulated data."""

    def __init__(self, simulation_speed: float = 1.0) -> None:
        """Initialize Simulated GPS interface."""
        self._simulation_speed = simulation_speed
        self._start_time = time.time()
        self._data_generator = self._generate_simulated_data()
        self._logger = logging.getLogger(__name__)

    def _generate_simulated_data(self) -> Generator[list[int]]:
        """Generate simulated GPS data."""
        lat = 32.7157  # Starting latitude (e.g., San Diego, CA)
        lon = -117.1611  # Starting longitude
        altitude = 20

        while True:
            sentences = None
            # Try to generate sentences, if it fails, log and continue
            try:
                sentences = self._generate_sentences(lat, lon, altitude)
            except Exception:
                self._logger.exception("Error generating simulated GPS data")
                time.sleep(1)
                continue

            # Only proceed if we have valid sentences
            if sentences:
                data = [ord(c) for c in sentences]
                yield data
                time.sleep(1 / self._simulation_speed)

    def _generate_sentences(self, lat: float, lon: float, altitude: float) -> str:
        """Generate NMEA sentences for simulated GPS data."""
        elapsed_time = (time.time() - self._start_time) * self._simulation_speed
        current_lat = lat + 0.0001 * elapsed_time
        current_lon = lon + 0.0001 * elapsed_time
        current_alt = altitude + 0.01 * elapsed_time  # Ascend at 0.1m/s

        # Time in HHMMSS format
        now = dt.datetime.now(tz=dt.UTC)
        time_str = now.strftime("%H%M%S.%f")[:-3]

        # Date in ddmmyy format
        date_str = now.strftime("%d%m%y")

        # Speed over ground in knots (we can set to a fixed value or calculate)
        speed_over_ground = "0.5"  # knots

        # Track angle in degrees
        track_angle = "054.7"

        # Create NMEA sentences using pynmea2
        gga_msg = pynmea2.GGA(
            "GP",
            "GGA",
            (
                time_str,
                self._format_nmea_lat_lon(current_lat, "lat"), self._lat_dir(current_lat),
                self._format_nmea_lat_lon(current_lon, "lon"), self._lon_dir(current_lon),
                "1",  # GPS quality indicator
                "08",  # Number of satellites in use
                "0.9",  # Horizontal dilution of precision
                f"{current_alt:.1f}", "M",  # Altitude above mean sea level
                "0.0", "M",  # Height of geoid above WGS84 ellipsoid
                "",  # Time since last DGPS update
                "",   # DGPS reference station id
            ),
        )
        gga_sentence = gga_msg.render()

        rmc_msg = pynmea2.RMC(
            "GP",
            "RMC",
            (
                time_str,
                "A",  # Status
                self._format_nmea_lat_lon(current_lat, "lat"), self._lat_dir(current_lat),
                self._format_nmea_lat_lon(current_lon, "lon"), self._lon_dir(current_lon),
                speed_over_ground,  # Speed over ground in knots
                track_angle,  # Track angle in degrees
                date_str,  # Date in ddmmyy format
                "",  # Magnetic variation
                "",   # Magnetic variation direction
            ),
        )
        rmc_sentence = rmc_msg.render()

        return gga_sentence + "\r\n" + rmc_sentence + "\r\n"

    def _format_nmea_lat_lon(self, coord: float, coord_type: str) -> str:
        """Format latitude or longitude in NMEA format."""
        if coord_type == "lat":
            degrees = int(abs(coord))
            minutes = (abs(coord) - degrees) * 60
            return f"{degrees:02d}{minutes:07.4f}"
        if coord_type == "lon":
            degrees = int(abs(coord))
            minutes = (abs(coord) - degrees) * 60
            return f"{degrees:03d}{minutes:07.4f}"
        msg = "coord_type must be 'lat' or 'lon'"
        self._logger.error(msg)
        raise ValueError(msg)

    def _lat_dir(self, lat: float) -> str:
        return "N" if lat >= 0 else "S"

    def _lon_dir(self, lon: float) -> str:
        return "E" if lon >= 0 else "W"

    def read_gps_data(self, _: int = 128) -> list[int] | None:
        """Read simulated GPS data."""
        try:
            return next(self._data_generator)
        except StopIteration:
            return None
