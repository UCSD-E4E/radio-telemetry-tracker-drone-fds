"""Module for managing drone state, including GPS and PingFinder states."""

from __future__ import annotations

import bisect
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock

logger = logging.getLogger(__name__)

MAX_HISTORY = 1000

# GPS Constants
MIN_LATITUDE = -90
MAX_LATITUDE = 90
MIN_LONGITUDE = -180
MAX_LONGITUDE = 180
MIN_ALTITUDE = -1000  # meters
MAX_ALTITUDE = 100000  # meters (100km)
MIN_HEADING = 0
MAX_HEADING = 360
MAX_HDOP = 100
MAX_SATELLITES = 32
MAX_FIX_QUALITY = 6
MIN_SATELLITES = 4
MAX_HDOP_QUALITY = 5

# GPS State Definitions
class GPSState(Enum):
    """Enumeration of GPS states."""
    UNCREATED = "Uncreated"
    IDLE = "Idle"
    INITIALIZING = "Initializing"
    RUNNING = "Running"
    ERROR = "Error"

# PingFinder State Definitions
class PingFinderState(Enum):
    """Enumeration of PingFinder states."""
    UNCREATED = "Uncreated"
    IDLE = "Idle"
    INITIALIZING = "Initializing"
    RUNNING = "Running"
    ERROR = "Error"

# GPS Data
@dataclass
class GPSData:
    """Represents GPS coordinate data with a timestamp."""
    timestamp: float = field(default_factory=time.time)
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    heading: float | None = None
    easting: float | None = None
    northing: float | None = None
    epsg_code: int | None = None
    satellite_count: int | None = None
    hdop: float | None = None  # Horizontal Dilution of Precision
    fix_quality: int | None = None  # 0=invalid, 1=GPS fix, 2=DGPS fix, etc.
    is_valid: bool = False  # Overall validity flag

    def validate(self) -> bool:
        """Validate GPS data values are within reasonable ranges."""
        is_valid = True

        # Check latitude
        if self.latitude is not None:
            is_valid = is_valid and MIN_LATITUDE <= self.latitude <= MAX_LATITUDE

        # Check longitude
        if self.longitude is not None:
            is_valid = is_valid and MIN_LONGITUDE <= self.longitude <= MAX_LONGITUDE

        # Check altitude
        if self.altitude is not None:
            is_valid = is_valid and MIN_ALTITUDE <= self.altitude <= MAX_ALTITUDE

        # Check heading
        if self.heading is not None:
            is_valid = is_valid and MIN_HEADING <= self.heading <= MAX_HEADING

        # Check HDOP
        if self.hdop is not None:
            is_valid = is_valid and 0 < self.hdop < MAX_HDOP

        # Check satellite count
        if self.satellite_count is not None:
            is_valid = is_valid and 0 <= self.satellite_count <= MAX_SATELLITES

        # Check fix quality
        if self.fix_quality is not None:
            is_valid = is_valid and 0 <= self.fix_quality <= MAX_FIX_QUALITY

        return is_valid

    def check_quality(self) -> bool:
        """Check if GPS data meets quality thresholds."""
        # Require at least 4 satellites for a valid fix
        if self.satellite_count is not None and self.satellite_count < MIN_SATELLITES:
            return False
        # HDOP should be below 5 for good accuracy
        if self.hdop is not None and self.hdop > MAX_HDOP_QUALITY:
            return False
        # Must have a valid fix quality
        return not (self.fix_quality is not None and self.fix_quality == 0)

# Centralized StateManager
class StateManager:
    """Centralized State Manager with GPS and PingFinder states and data."""

    def __init__(self) -> None:
        """Initialize the state manager."""
        self._lock = Lock()
        self._gps_state = GPSState.UNCREATED
        self._ping_finder_state = PingFinderState.UNCREATED
        self._gps_data_history: list[tuple[float, GPSData]] = []
        self._current_gps_data: GPSData = GPSData()

    def set_gps_state(self, state: GPSState) -> None:
        """Set the GPS state."""
        with self._lock:
            old_state = self._gps_state
            self._gps_state = state
            if old_state != state:
                logger.info("[GPS] State changed from %s to %s", old_state.value, state.value)

    def update_gps_data(self, data: GPSData) -> None:
        """Update the current GPS data and maintain history."""
        with self._lock:
            bisect.insort(self._gps_data_history, (data.timestamp, data))
            self._current_gps_data = data
            if len(self._gps_data_history) > MAX_HISTORY:
                self._gps_data_history.pop(0)  # Remove the oldest entry

    def get_gps_state(self) -> str:
        """Retrieve the current GPS state."""
        with self._lock:
            return self._gps_state.value

    def get_gps_data_closest_to(self, timestamp: float) -> GPSData | None:
        """Retrieve the GPS data closest to the given timestamp."""
        with self._lock:
            if not self._gps_data_history:
                return None

            timestamps = [entry[0] for entry in self._gps_data_history]
            index = bisect.bisect_left(timestamps, timestamp)

            if index == 0:
                return self._gps_data_history[0][1]
            if index == len(self._gps_data_history):
                return self._gps_data_history[-1][1]

            before = self._gps_data_history[index - 1]
            after = self._gps_data_history[index]

            if abs(before[0] - timestamp) <= abs(after[0] - timestamp):
                return before[1]
            return after[1]

    def get_current_gps_data(self) -> GPSData:
        """Retrieve the current GPS data."""
        with self._lock:
            return self._current_gps_data

    def set_ping_finder_state(self, state: PingFinderState) -> None:
        """Set the PingFinder state."""
        with self._lock:
            old_state = self._ping_finder_state
            self._ping_finder_state = state
            if old_state != state:
                logger.info("[PingFinder] State changed from %s to %s", old_state.value, state.value)

    def get_ping_finder_state(self) -> str:
        """Retrieve the current PingFinder state."""
        with self._lock:
            return self._ping_finder_state.value
