"""Module for handling ping finding operations using SDR."""

from __future__ import annotations

import csv
import datetime as dt
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from rct_dsp2 import PingFinder
from rct_dsp2.localization import LocationEstimator

if TYPE_CHECKING:
    from radio_telemetry_tracker_drone_fds.config import PingFinderConfig
    from radio_telemetry_tracker_drone_fds.gps_module import GPSModule
    from radio_telemetry_tracker_drone_fds.state_manager import StateManager

logger = logging.getLogger(__name__)


class PingFinderModule:
    """Handles ping finding operations using SDR."""

    def __init__(self, gps_module: GPSModule, config: PingFinderConfig, state_manager: StateManager) -> None:
        """Initialize PingFinderModule with configured PingFinder, GPSModule, and StateManager."""
        self._gps_module = gps_module
        self._ping_finder = PingFinder()
        self._state_manager = state_manager
        self._configure_ping_finder(config)
        self._stop_event = threading.Event()
        self._run_num = config.run_num
        self._initialize_csv_log(config)
        self._location_estimator = LocationEstimator(self._get_current_location)

        # Set initial state
        self._state_manager.update_ping_finder_state("configure")

    def _configure_ping_finder(self, config: PingFinderConfig) -> None:
        """Apply configuration to PingFinder instance."""
        for key, value in config.__dict__.items():
            if hasattr(self._ping_finder, key):
                setattr(self._ping_finder, key, value)
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
        gps_data = self._state_manager.get_gps_data()

        # Log ping data to CSV
        self._log_ping_to_csv(
            (
                now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                frequency,
                amplitude,
                gps_data.easting if gps_data.easting is not None else "N/A",
                gps_data.northing if gps_data.northing is not None else "N/A",
                gps_data.altitude if gps_data.altitude is not None else "N/A",
                gps_data.heading if gps_data.heading is not None else "N/A",
                gps_data.epsg_code if gps_data.epsg_code is not None else "N/A",
            ),
        )

        # Add ping to location estimator
        self._location_estimator.add_ping(now, amplitude, frequency)
        estimate = self._location_estimator.do_estimate(frequency)

        # Log GPS and estimation data
        logger.info("=" * 60)
        logger.info("Timestamp: %s", now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
        logger.info("Frequency: %d Hz", frequency)
        logger.info("Amplitude: %.2f", amplitude)
        logger.info("-" * 60)
        logger.info("GPS Data:")
        logger.info(f"  Easting:  {gps_data.easting:.2f}" if gps_data.easting else "  Easting:  N/A")
        logger.info(f"  Northing: {gps_data.northing:.2f}" if gps_data.northing else "  Northing: N/A")
        logger.info(f"  Altitude: {gps_data.altitude:.2f}" if gps_data.altitude else "  Altitude:  N/A")
        logger.info(f"  Heading:  {gps_data.heading:.2f}" if gps_data.heading else "  Heading:  N/A")
        logger.info(f"  EPSG Code: {gps_data.epsg_code}" if gps_data.epsg_code else "  EPSG Code:  N/A")

        if estimate is not None:
            self._log_estimation_to_csv(
                (
                    now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    frequency,
                    estimate[0],  # easting
                    estimate[1],  # northing
                    gps_data.epsg_code,
                ),
            )
            logger.info("-" * 60)
            logger.info("Estimated Location:")
            logger.info("  Easting:  %.2f", estimate[0])
            logger.info("  Northing: %.2f", estimate[1])
            logger.info("=" * 60)

    def start(self) -> None:
        """Start the ping finding operation in a separate thread."""
        if self._state_manager.get_ping_finder_state() == "Configured":
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run)
            self._thread.start()
            self._state_manager.update_ping_finder_state("start")

    def stop(self) -> None:
        """Stop the ping finding operation."""
        if self._state_manager.get_ping_finder_state() == "Running":
            self._stop_event.set()
            self._ping_finder.stop()
            if self._thread:
                self._thread.join()
            self._state_manager.update_ping_finder_state("stop")

    def _run(self) -> None:
        """Ping finding operation loop."""
        try:
            self._ping_finder.start()
            while not self._stop_event.is_set():
                self._stop_event.wait(0.1)
        except (OSError, RuntimeError):
            logger.exception("PingFinder error")
            self._state_manager.update_ping_finder_state("error")
        finally:
            if self._state_manager.get_ping_finder_state() != "Error":
                self._state_manager.update_ping_finder_state("stop")

    def _get_current_location(self, _: dt.datetime | None = None) -> tuple[float, float, float]:
        """Get current GPS location in UTM coordinates."""
        gps_data = self._state_manager.get_gps_data()
        if gps_data.easting is None or gps_data.northing is None or gps_data.altitude is None:
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
