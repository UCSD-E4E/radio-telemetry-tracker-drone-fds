"""Module for handling ping finding operations using SDR."""

from __future__ import annotations

import csv
import datetime as dt
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from radio_telemetry_tracker_drone_comms_package import DroneComms, LocEstData, PingData
from rct_dsp2 import SDR_TYPE_AIRSPY, SDR_TYPE_GENERATOR, SDR_TYPE_HACKRF, SDR_TYPE_USRP, PingFinder
from rct_dsp2.localization import LocationEstimator

from radio_telemetry_tracker_drone_fds.state.state_manager import PingFinderState, StateManager

if TYPE_CHECKING:
    from radio_telemetry_tracker_drone_fds.config import PingFinderConfig
    from radio_telemetry_tracker_drone_fds.gps.gps_module import GPSModule

from radio_telemetry_tracker_drone_fds.utils.logging_helper import log_estimation, log_ping

logger = logging.getLogger(__name__)


class PingFinderModule:
    """Handles ping finding operations using SDR."""

    def __init__(
        self,
        gps_module: GPSModule,
        config: PingFinderConfig,
        state_manager: StateManager,
        sdr_type: str,
        drone_comms: DroneComms | None = None,
    ) -> None:
        """Initialize PingFinderModule with configured PingFinder, GPSModule, and StateManager."""
        self._gps_module = gps_module
        self._ping_finder = PingFinder()
        self._state_manager = state_manager
        self._run_num = config.run_num
        self._stop_event = threading.Event()
        self._drone_comms = drone_comms
        self._thread: threading.Thread | None = None

        # Initialize and configure
        self._initialize_csv_log(config)
        self._configure_ping_finder(config, sdr_type)
        self._location_estimator = LocationEstimator(self._get_current_location)

        # Set to IDLE after initialization
        self._state_manager.set_ping_finder_state(PingFinderState.IDLE)

    def _configure_ping_finder(self, config: PingFinderConfig, sdr_type: str) -> None:
        """Apply configuration to PingFinder instance."""
        valid_sdr_types = {
            "USRP": SDR_TYPE_USRP,
            "AIRSPY": SDR_TYPE_AIRSPY,
            "HACKRF": SDR_TYPE_HACKRF,
            "GENERATOR": SDR_TYPE_GENERATOR,
        }

        sdr_type = sdr_type.upper()
        if sdr_type not in valid_sdr_types:
            msg = f"Invalid SDR_TYPE: {sdr_type}. Valid options: {', '.join(valid_sdr_types.keys())}"
            raise ValueError(msg)

        # Set SDR type
        self._ping_finder.sdr_type = valid_sdr_types[sdr_type]

        # Apply other configurations
        for key, value in config.__dict__.items():
            if hasattr(self._ping_finder, key):
                setattr(self._ping_finder, key, value)

        # Register callback
        self._ping_finder.register_callback(self._callback)

    def _initialize_csv_log(self, config: PingFinderConfig) -> None:
        """Set up CSV logging for pings and location estimations."""
        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._csv_ping_filename = output_dir / f"ping_log_{timestamp}_run{self._run_num}.csv"
        self._csv_estimation_filename = output_dir / f"location_estimation_log_{timestamp}_run{self._run_num}.csv"

        with self._csv_ping_filename.open("w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(
                [
                    "Run",
                    "Timestamp",
                    "Frequency",
                    "Amplitude",
                    "Easting",
                    "Northing",
                    "Altitude",
                    "Heading",
                    "EPSG Code",
                ],
            )

        with self._csv_estimation_filename.open("w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(
                [
                    "Run",
                    "Timestamp",
                    "Frequency",
                    "Easting",
                    "Northing",
                    "EPSG Code",
                ],
            )

    def _log_ping_to_csv(self, data: tuple) -> None:
        """Log ping data to CSV."""
        try:
            with self._csv_ping_filename.open("a", newline="") as csv_file:
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow([self._run_num, *list(data)])
        except Exception:
            logger.exception("Failed to write ping data to CSV.")

    def _log_estimation_to_csv(self, data: tuple) -> None:
        """Log location estimation to CSV."""
        try:
            with self._csv_estimation_filename.open("a", newline="") as csv_file:
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow([self._run_num, *list(data)])
        except Exception:
            logger.exception("Failed to write estimation data to CSV.")

    def _callback(self, now: dt.datetime, amplitude: float, frequency: int) -> None:
        """Callback invoked by PingFinder when a ping is detected."""
        logger.debug("PingFinderModule._callback called")

        # Use the ping's timestamp to get the closest GPS data
        target_timestamp = now.timestamp()
        gps_data = self._state_manager.get_gps_data_closest_to(target_timestamp)
        if gps_data is None:
            logger.error("No GPS data available for the ping at timestamp %s", now.isoformat())
            return

        # Log ping data using the logging helper
        log_ping(
            self._run_num,
            dt.datetime.fromtimestamp(gps_data.timestamp, tz=dt.timezone.utc).isoformat(),
            frequency,
            amplitude,
            gps_data,
        )

        # Send ping data if in ONLINE mode
        if self._drone_comms is not None:
            ping_data = PingData(
                frequency=frequency,
                amplitude=amplitude,
                easting=gps_data.easting,
                northing=gps_data.northing,
                altitude=gps_data.altitude,
                epsg_code=gps_data.epsg_code,
            )
            self._drone_comms.send_ping_data(ping_data)

        # Add ping to location estimator
        self._location_estimator.add_ping(now, amplitude, frequency)
        estimate = self._location_estimator.do_estimate(frequency)

        # Use logging helper to log estimation
        if estimate is not None:
            log_estimation(
                self._run_num,
                dt.datetime.fromtimestamp(gps_data.timestamp, tz=dt.timezone.utc).isoformat(),
                frequency,
                estimate,
                gps_data,
            )

            # Send location estimation if in ONLINE mode
            if self._drone_comms is not None:
                loc_est_data = LocEstData(
                    frequency=frequency,
                    easting=estimate[0],
                    northing=estimate[1],
                    epsg_code=gps_data.epsg_code,
                )
                self._drone_comms.send_loc_est_data(loc_est_data)

            logger.info("=" * 60)
            logger.info("Estimated Location:")
            logger.info("  Easting:  %.2f", estimate[0])
            logger.info("  Northing: %.2f", estimate[1])
            logger.info("=" * 60)

    def start(self) -> None:
        """Start the ping finding operation in a separate thread."""
        if self._state_manager.get_ping_finder_state() == PingFinderState.IDLE.value:
            # Set to INITIALIZING while starting up
            self._state_manager.set_ping_finder_state(PingFinderState.INITIALIZING)
            self._stop_event.clear()

            try:
                self._ping_finder.start()
                self._thread = threading.Thread(target=self._run)
                self._thread.start()
                # Set to RUNNING once thread is started
                self._state_manager.set_ping_finder_state(PingFinderState.RUNNING)
            except Exception:
                logger.exception("Failed to start PingFinder")
                self._state_manager.set_ping_finder_state(PingFinderState.ERROR)

    def stop(self) -> None:
        """Stop the ping finding operation."""
        current_state = self._state_manager.get_ping_finder_state()
        if current_state != PingFinderState.IDLE.value:  # Only proceed if not already idle
            self._stop_event.set()
            self._ping_finder.stop()
            if self._thread:
                self._thread.join()
            self._state_manager.set_ping_finder_state(PingFinderState.IDLE)

    def _run(self) -> None:
        """Ping finding operation loop."""
        try:
            while not self._stop_event.is_set():
                self._stop_event.wait(0.1)
        except (OSError, RuntimeError):
            logger.exception("PingFinder error")
            self._state_manager.set_ping_finder_state(PingFinderState.ERROR)
        finally:
            if self._state_manager.get_ping_finder_state() != PingFinderState.ERROR.value:
                self._state_manager.set_ping_finder_state(PingFinderState.IDLE)

    def _get_current_location(self, timestamp: dt.datetime | None = None) -> tuple[float, float, float]:
        """Get current GPS location in UTM coordinates based on the closest GPS data to the given timestamp."""
        if timestamp is None:
            timestamp = dt.datetime.now(tz=dt.timezone.utc)

        gps_data = self._state_manager.get_gps_data_closest_to(timestamp.timestamp())
        if gps_data is None or gps_data.easting is None or gps_data.northing is None or gps_data.altitude is None:
            msg = "GPS data not available for location estimation"
            logger.error(msg)
            raise ValueError(msg)
        return gps_data.easting, gps_data.northing, gps_data.altitude

    def get_final_estimations(self) -> list[tuple[float, float, float, float]]:
        """Return final estimations for all frequencies."""
        final_estimations = []
        for frequency in self._location_estimator.get_frequencies():
            estimate = self._location_estimator.do_estimate(frequency)
            if estimate is not None:
                final_estimations.append((frequency, *estimate))
        return final_estimations

    def reconfigure(self, config: PingFinderConfig, sdr_type: str) -> None:
        """Reconfigure the ping finder with new settings.

        This will stop any running operations and reinitialize with new config.
        """
        # Stop if running
        if self._state_manager.get_ping_finder_state() != PingFinderState.IDLE.value:
            self.stop()

        # Set to UNCREATED while reconfiguring
        self._state_manager.set_ping_finder_state(PingFinderState.UNCREATED)

        # Create new PingFinder instance
        self._ping_finder = PingFinder()
        self._run_num = config.run_num

        # Reinitialize with new config
        self._initialize_csv_log(config)
        self._configure_ping_finder(config, sdr_type)
        self._location_estimator = LocationEstimator(self._get_current_location)

        # Set to IDLE after reconfiguration
        self._state_manager.set_ping_finder_state(PingFinderState.IDLE)
