"""Module for handling ping finding operations using SDR."""

from __future__ import annotations

import csv
import datetime as dt
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rct_dsp2 import PingFinder
from rct_dsp2.localization import LocationEstimator

from radio_telemetry_tracker_drone_fds.drone_state import (
    PingFinderState,
    update_ping_finder_state,
)

if TYPE_CHECKING:
    from radio_telemetry_tracker_drone_fds.gps_module import GPSModule


class PingFinderModule:
    """Handles ping finding operations using SDR."""

    def __init__(self, gps_module: GPSModule, config: dict[str, Any]) -> None:
        """Initialize PingFinderModule with configured PingFinder and GPSModule.

        Args:
            gps_module (GPSModule): The GPS module instance.
            config (Dict[str, Any]): Configuration dictionary for PingFinder.
        """
        self._gps_module = gps_module
        self._ping_finder = PingFinder()
        self._configure_ping_finder(config)
        self._stop_event = threading.Event()
        self._csv_ping_filename = None
        self._csv_estimation_filename = None
        self._csv_writer_ping = None
        self._csv_writer_estimation = None
        self._run_num = config.get("run_num", 1)
        self._initialize_csv_log(config)
        self._location_estimator = LocationEstimator(self._get_current_location)
        update_ping_finder_state(PingFinderState.READY)

    def _configure_ping_finder(self, config: dict[str, Any]) -> None:
        for key, value in config.items():
            setattr(self._ping_finder, key, value)
        self._ping_finder.register_callback(self._callback)
        self._state = PingFinderState.READY

    def _initialize_csv_log(self, config: dict[str, Any]) -> None:
        output_dir = Path(config.get("output_dir", "./rtt_output/"))
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._csv_ping_filename = output_dir / f"ping_log_{timestamp}_run{self._run_num}.csv"
        self._csv_estimation_filename = (
            output_dir / f"location_estimation_log_{timestamp}_run{self._run_num}.csv"
        )

        with self._csv_ping_filename.open("w", newline="") as self._csv_file:
            self._csv_writer_ping = csv.writer(self._csv_file)
            self._csv_writer_ping.writerow(
                [
                    "Run",
                    "Timestamp",
                    "Frequency",
                    "Amplitude",
                    "Latitude",
                    "Longitude",
                    "Altitude",
                ],
            )

        with self._csv_estimation_filename.open("w", newline="") as self._csv_file:
            self._csv_writer_estimation = csv.writer(self._csv_file)
            self._csv_writer_estimation.writerow(
                [
                    "Run",
                    "Timestamp",
                    "Frequency",
                    "Latitude",
                    "Longitude",
                    "Altitude",
                ],
            )

    def _log_ping_to_csv(
        self,
        data: tuple[dt.datetime, float, int, float, float, float],
    ) -> None:
        with self._csv_ping_filename.open("a", newline="") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow([self._run_num, *list(data)])

    def _log_estimation_to_csv(
        self,
        data: tuple[dt.datetime, float, float, float, float],
    ) -> None:
        # If frequency already exists, overwrite the row
        with self._csv_estimation_filename.open("a", newline="") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow([self._run_num, *list(data)])

    def _callback(self, now: dt.datetime, amplitude: float, frequency: int) -> None:
        logging.debug("PingFinderModule._callback called")
        gps_data, _ = self._gps_module.get_gps_data()

        # Log to CSV
        self._log_ping_to_csv(
            (
                now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                frequency,
                amplitude,
                gps_data.latitude if gps_data.latitude is not None else "N/A",
                gps_data.longitude if gps_data.longitude is not None else "N/A",
                gps_data.altitude if gps_data.altitude is not None else "N/A",
            ),
        )

        # Add ping to LocationEstimator
        self._location_estimator.add_ping(now, amplitude, frequency)

        # Perform estimation
        estimate = self._location_estimator.do_estimate(frequency)

        # Log ping data
        logging.info("=" * 60)
        logging.info("Timestamp: %s", now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
        logging.info("Frequency: %d Hz", frequency)
        logging.info("Amplitude: %.2f", amplitude)
        logging.info("-" * 60)
        logging.info("GPS Data:")
        logging.info(
            f"  Latitude:  {gps_data.latitude:.6f}"
            if gps_data.latitude is not None
            else "  Latitude:  N/A",
        )
        logging.info(
            f"  Longitude: {gps_data.longitude:.6f}"
            if gps_data.longitude is not None
            else "  Longitude: N/A",
        )
        logging.info(
            f"  Altitude:  {gps_data.altitude:.2f}"
            if gps_data.altitude is not None
            else "  Altitude:  N/A",
        )

        # Log estimation if available
        if estimate is not None:
            logging.info("-" * 60)
            logging.info("Estimated Location:")
            logging.info("  Longitude: %.6f", estimate[0])
            logging.info("  Latitude:  %.6f", estimate[1])
            logging.info("  Altitude:  %.2f", estimate[2])

        logging.info("=" * 60)

    def start(self) -> None:
        """Start the ping finding operation in a separate thread."""
        if self.get_state() == PingFinderState.READY:
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run)
            self._thread.start()
            update_ping_finder_state(PingFinderState.RUNNING)

    def stop(self) -> None:
        """Stop the ping finding operation."""
        if self.get_state() == PingFinderState.RUNNING:
            self._stop_event.set()
            self._ping_finder.stop()
            if self._thread:
                self._thread.join()
            update_ping_finder_state(PingFinderState.STOPPED)

    def _run(self) -> None:
        try:
            self._ping_finder.start()
            while not self._stop_event.is_set():
                # Add a small sleep to prevent busy-waiting
                self._stop_event.wait(0.1)
        except (OSError, RuntimeError):
            logging.exception("PingFinder error")
            update_ping_finder_state(PingFinderState.ERRORED)
        finally:
            if self.get_state() != PingFinderState.ERRORED:
                update_ping_finder_state(PingFinderState.STOPPED)

    def get_state(self) -> PingFinderState:
        """Return the current state of the PingFinderModule."""
        from radio_telemetry_tracker_drone_fds.drone_state import get_current_state

        return get_current_state().ping_finder_state

    def _get_current_location(
        self,
        _: dt.datetime | None = None,
    ) -> tuple[float, float, float]:
        """Get current GPS location.

        Args:
            _: Optional timestamp parameter (unused but required by LocationEstimator)

        Returns:
            Tuple of (longitude, latitude, altitude)
        """
        gps_data, _ = self._gps_module.get_gps_data()
        return (
            gps_data.longitude,
            gps_data.latitude,
            gps_data.altitude,
        )

    def get_final_estimations(self) -> list[tuple[float, float, float, float]]:
        """Return final estimations for all frequencies."""
        final_estimations = []
        for frequency in self._location_estimator.get_frequencies():
            estimate = self._location_estimator.do_estimate(frequency)
            if estimate is not None:
                final_estimations.append((frequency, *estimate))
        return final_estimations
