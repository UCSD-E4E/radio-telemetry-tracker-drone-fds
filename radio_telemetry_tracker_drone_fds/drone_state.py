"""Module for defining drone state-related classes and enums."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GPSState(Enum):
    """Enumeration of GPS states."""

    NOT_READY = "Not Ready"
    INITIALIZING = "Initializing"
    WAITING = "Waiting"
    PARTIAL = "Partial"
    READY = "Ready"
    ERRORED = "Errored"


class PingFinderState(Enum):
    """Enumeration of possible states for the ping finder."""

    NOT_READY = "Not Ready"
    READY = "Ready"
    RUNNING = "Running"
    STOPPED = "Stopped"
    ERRORED = "Errored"


@dataclass
class GPSData:
    """Represents GPS coordinate data."""

    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    heading: float | None = None
    easting: float | None = None
    northing: float | None = None
    epsg_code: int | None = None

@dataclass
class DroneState:
    """Represents the current state of a drone, including GPS information."""

    gps_state: GPSState = GPSState.NOT_READY
    gps_data: GPSData = field(default_factory=GPSData)
    ping_finder_state: PingFinderState = PingFinderState.NOT_READY


# Global instance of DroneState
current_state = DroneState()


def update_gps_state(state: GPSState) -> None:
    """Update the current GPS state."""
    current_state.gps_state = state


def update_gps_data(data: GPSData) -> None:
    """Update the current state with new GPS data."""
    current_state.gps_data = data


def update_ping_finder_state(state: PingFinderState) -> None:
    """Update the current ping finder state."""
    current_state.ping_finder_state = state


def get_current_state() -> DroneState:
    """Return the current state of the drone."""
    return current_state
