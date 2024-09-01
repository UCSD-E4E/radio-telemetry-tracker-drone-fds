"""Module for processing GPS data in the radio telemetry tracker drone system."""

import logging

from radio_telemetry_tracker_drone_fds.gps_module import GPSData, GPSState


class DataProcessor:
    """Processes GPS data for the radio telemetry tracker drone system."""

    def __init__(self) -> None:
        """Initialize the DataProcessor."""
        # Initialize any necessary components for data processing and communication
        self.logger = logging.getLogger(__name__)

    def process_gps_data(self, gps_data: GPSData, gps_state: GPSState) -> None:
        """Process GPS data and perform necessary actions."""
        # Process GPS data and perform any necessary actions
        self.logger.info(
            "GPS State: %s, Lat: %s, Lon: %s, Alt: %s, Heading: %s",
            gps_state.value,
            gps_data.latitude,
            gps_data.longitude,
            gps_data.altitude,
            gps_data.heading,
        )
        # Add code here to send data to other devices or perform additional processing
