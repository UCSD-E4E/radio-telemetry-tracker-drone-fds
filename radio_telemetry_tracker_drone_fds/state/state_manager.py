"""Module for managing drone state, including GPS and PingFinder states, using state machines."""

from __future__ import annotations

import bisect
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock

from transitions import Machine

logger = logging.getLogger(__name__)

MAX_HISTORY = 1000

# GPS State Definitions
class GPSState(Enum):
    """Enumeration of GPS states."""
    INITIALIZING = "Initializing"
    ACQUIRING = "Acquiring Signal"
    LOCKED = "Locked"
    ERROR = "Error"

class GPSStateMachine:
    """State machine for managing GPS state transitions."""

    def __init__(self) -> None:
        """Initialize the GPS state machine with states and transitions."""
        self.states = [state.value for state in GPSState]
        self.machine = Machine(model=self, states=self.states, initial=GPSState.INITIALIZING.value)

        # Define transitions
        self.machine.add_transition("initialize", "*", GPSState.INITIALIZING.value)
        self.machine.add_transition(
            "start_acquisition",
            [GPSState.INITIALIZING.value, GPSState.ERROR.value],
            GPSState.ACQUIRING.value,
        )
        self.machine.add_transition("lock_signal", GPSState.ACQUIRING.value, GPSState.LOCKED.value)
        self.machine.add_transition("error", "*", GPSState.ERROR.value)
        self.machine.add_transition("reset", [GPSState.ERROR.value, GPSState.LOCKED.value], GPSState.INITIALIZING.value)

# PingFinder State Definitions
class PingFinderState(Enum):
    """Enumeration of PingFinder states."""
    IDLE = "Idle"
    CONFIGURED = "Configured"
    RUNNING = "Running"
    ERROR = "Error"

class PingFinderStateMachine:
    """State machine for managing PingFinder state transitions."""

    def __init__(self) -> None:
        """Initialize the PingFinder state machine with states and transitions."""
        self.states = [state.value for state in PingFinderState]
        self.machine = Machine(model=self, states=self.states, initial=PingFinderState.IDLE.value)

        # Define transitions
        self.machine.add_transition("configure", PingFinderState.IDLE.value, PingFinderState.CONFIGURED.value)
        self.machine.add_transition("start", PingFinderState.CONFIGURED.value, PingFinderState.RUNNING.value)
        self.machine.add_transition("stop", "*", PingFinderState.IDLE.value)  # Allow stop from any state
        self.machine.add_transition("error", "*", PingFinderState.ERROR.value)
        self.machine.add_transition("reset", PingFinderState.ERROR.value, PingFinderState.IDLE.value)

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

# Centralized StateManager
class StateManager:
    """Centralized State Manager with GPS and PingFinder states and data."""

    def __init__(self) -> None:
        """Initialize the state manager with GPS and PingFinder state machines."""
        self._lock = Lock()
        self.gps_state_machine = GPSStateMachine()
        self.ping_finder_state_machine = PingFinderStateMachine()
        self._gps_data_history: list[tuple[float, GPSData]] = []  # List of (timestamp, GPSData)
        self._current_gps_data: GPSData = GPSData()

    def update_gps_state(self, trigger: str) -> None:
        """Trigger a state transition for the GPS state machine."""
        with self._lock:
            old_state = self.gps_state_machine.state
            try:
                getattr(self.gps_state_machine, trigger)()
                new_state = self.gps_state_machine.state
                if old_state != new_state:
                    logger.info("[GPS] State changed from %s to %s", old_state, new_state)
            except Exception:
                logger.exception("[GPS] Failed to trigger '%s'", trigger)

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
            return self.gps_state_machine.state

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

    # PingFinder State Methods
    def update_ping_finder_state(self, trigger: str) -> None:
        """Update the PingFinder state using a trigger."""
        with self._lock:
            old_state = self.ping_finder_state_machine.state
            try:
                getattr(self.ping_finder_state_machine, trigger)()
                new_state = self.ping_finder_state_machine.state
                if old_state != new_state:
                    logger.info("[PingFinder] State changed from %s to %s", old_state, new_state)
            except Exception:
                logger.exception("[PingFinder] Failed to trigger '%s'", trigger)

    def get_ping_finder_state(self) -> str:
        """Retrieve the current PingFinder state."""
        with self._lock:
            return self.ping_finder_state_machine.state
