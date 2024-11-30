"""Module for handling GPS data acquisition and processing."""

from __future__ import annotations

import datetime as dt
import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

import pynmea2
import pyproj

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
        import serial

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
        self._logger = logging.getLogger(__name__)

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

            # Time in HHMMSS format
            now = dt.datetime.now(tz=dt.timezone.utc)
            time_str = now.strftime("%H%M%S.%f")[:-3]

            # Date in ddmmyy format
            date_str = now.strftime("%d%m%y")

            # Speed over ground in knots (we can set to a fixed value or calculate)
            speed_over_ground = "0.5"  # knots

            # Track angle in degrees
            track_angle = "054.7"

            # Create NMEA sentences using pynmea2
            try:
                gga_msg = pynmea2.GGA(
                    "GP", "GGA", (
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
            except Exception:
                self._logger.exception("Error creating GGA message")
                continue

            try:
                rmc_msg = pynmea2.RMC(
                    "GP", "RMC", (
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
            except Exception:
                self._logger.exception("Error creating RMC message")
                continue

            sentences = gga_sentence + "\r\n" + rmc_sentence + "\r\n"
            yield [ord(c) for c in sentences]
            time.sleep(1 / self._simulation_speed)

    def _format_nmea_lat_lon(self, coord: float, coord_type: str) -> str:
        """Format latitude or longitude in NMEA format.

        Args:
            coord: Coordinate in decimal degrees.
            coord_type: 'lat' for latitude, 'lon' for longitude.

        Returns:
            Formatted coordinate string.
        """
        if coord_type == "lat":
            degrees = int(abs(coord))
            minutes = (abs(coord) - degrees) * 60
            return f"{degrees:02d}{minutes:07.4f}"
        if coord_type == "lon":
            degrees = int(abs(coord))
            minutes = (abs(coord) - degrees) * 60
            return f"{degrees:03d}{minutes:07.4f}"
        msg = "coord_type must be 'lat' or 'lon'"
        raise ValueError(msg)

    def _lat_dir(self, lat: float) -> str:
        return "N" if lat >= 0 else "S"

    def _lon_dir(self, lon: float) -> str:
        return "E" if lon >= 0 else "W"

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

    def __init__(self, gps_interface: GPSInterface, epsg_code: int) -> None:
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
        self._epsg_code = epsg_code
        self._transformer = pyproj.Transformer.from_crs("epsg:4326", f"epsg:{self._epsg_code}", always_xy=True)
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
        """Process the current buffer to extract and parse NMEA sentences."""
        sentences = self._buffer.split("\n")
        self._buffer = sentences[-1]  # Keep the incomplete sentence
        sentences = sentences[:-1]  # Process complete sentences

        data_updated, new_gps_data = self._process_sentences(sentences)

        if data_updated and new_gps_data:
            self._update_gps_data(new_gps_data)
            self._error_count = 0  # Reset error count on successful update
        elif time.time() - self._last_update_time > self.GPS_DATA_TIMEOUT:
            self._update_gps_state(GPSState.WAITING)

        return self._buffer

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
                self._logger.warning("Failed to parse NMEA sentence: %s", sentence)
                continue
        return data_updated, new_gps_data if data_updated else None

    def _latlon_to_utm(self, latitude: float, longitude: float) -> tuple[float, float]:
        easting, northing = self._transformer.transform(longitude, latitude)
        return easting, northing

    def _update_gps_data(self, new_gps_data: GPSData) -> None:
        """Update the current GPS data and state."""
        if new_gps_data.latitude and new_gps_data.longitude is not None:
            easting, northing = self._latlon_to_utm(new_gps_data.latitude, new_gps_data.longitude)
            new_gps_data.easting = easting
            new_gps_data.northing = northing
            new_gps_data.epsg_code = self._epsg_code

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

    def run(self) -> None:
        """Continuously read and process GPS data."""
        self._logger.info("Starting GPS data acquisition loop")
        self._update_gps_state(GPSState.WAITING)

        while self._running:
            data = self._read_gps_data(32)
            if data:
                try:
                    # Convert list of integers to string
                    incoming_data = "".join(chr(c) for c in data)
                    self._buffer += incoming_data
                    self._buffer = self._process_buffer()
                except UnicodeDecodeError:
                    self._logger.warning("Received non-UTF8 data from GPS interface")
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
