"""GPS package for the radio telemetry tracker drone."""

from radio_telemetry_tracker_drone_fds.gps.gps_interface import (
    GPSInterface,
    I2CGPSInterface,
    SerialGPSInterface,
    SimulatedGPSInterface,
)
from radio_telemetry_tracker_drone_fds.gps.gps_module import GPSModule

__all__ = [
    "GPSInterface",
    "GPSModule",
    "I2CGPSInterface",
    "SerialGPSInterface",
    "SimulatedGPSInterface",
]
