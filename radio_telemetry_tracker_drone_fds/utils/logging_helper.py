"""Utility module for logging various events in the Radio Telemetry Tracker Drone FDS."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from radio_telemetry_tracker_drone_fds.state import GPSData

logger = logging.getLogger(__name__)


def log_ping(
    run_num: int,
    now: str,
    frequency: int,
    amplitude: float,
    gps_data: GPSData,
) -> None:
    """Log ping data in a structured manner."""
    logger.info(
        "Ping Detected - Run: %d, Timestamp: %s, Frequency: %d Hz, Amplitude: %.2f, "
        "Easting: %s, Northing: %s, Altitude: %s, Heading: %s, EPSG Code: %s",
        run_num,
        now,
        frequency,
        amplitude,
        gps_data.easting if gps_data.easting is not None else "N/A",
        gps_data.northing if gps_data.northing is not None else "N/A",
        gps_data.altitude if gps_data.altitude is not None else "N/A",
        gps_data.heading if gps_data.heading is not None else "N/A",
        gps_data.epsg_code if gps_data.epsg_code is not None else "N/A",
    )


def log_estimation(
    run_num: int,
    now: str,
    frequency: int,
    estimate: tuple[float, float] | None,
    gps_data: GPSData,
) -> None:
    """Log location estimation data."""
    if estimate:
        logger.info(
            "Estimation - Run: %d, Timestamp: %s, Frequency: %d Hz, "
            "Easting: %.2f, Northing: %.2f, EPSG Code: %s",
            run_num,
            now,
            frequency,
            estimate[0],
            estimate[1],
            gps_data.epsg_code if gps_data.epsg_code is not None else "N/A",
        )
        logger.info(
            "Estimated Location - Easting: %.2f, Northing: %.2f",
            estimate[0],
            estimate[1],
        )


def log_heartbeat(
    gps_state: str,
    ping_finder_state: str,
    gps_data: GPSData,
) -> None:
    """Log heartbeat information."""
    logger.info(
        "Heartbeat - GPS State: %s, PingFinder State: %s",
        gps_state,
        ping_finder_state,
    )
    logger.info(
        "GPS Data - Easting: %s, Northing: %s, Altitude: %s, Heading: %s, EPSG Code: %s",
        f"{gps_data.easting:.3f}" if gps_data.easting is not None else "N/A",
        f"{gps_data.northing:.3f}" if gps_data.northing is not None else "N/A",
        gps_data.altitude if gps_data.altitude is not None else "N/A",
        gps_data.heading if gps_data.heading is not None else "N/A",
        gps_data.epsg_code if gps_data.epsg_code is not None else "N/A",
    )
