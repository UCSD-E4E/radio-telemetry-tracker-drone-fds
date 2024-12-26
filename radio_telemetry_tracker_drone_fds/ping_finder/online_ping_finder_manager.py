"""Module for managing ping finder lifecycle in online mode."""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

from radio_telemetry_tracker_drone_comms_package import (
    ConfigRequestData,
    ConfigResponseData,
    DroneComms,
    GPSData,
    StartRequestData,
    StartResponseData,
    StopRequestData,
    StopResponseData,
    SyncRequestData,
    SyncResponseData,
)

from radio_telemetry_tracker_drone_fds.config import PingFinderConfig

if TYPE_CHECKING:
    from radio_telemetry_tracker_drone_fds.config import HardwareConfig
    from radio_telemetry_tracker_drone_fds.gps import GPSModule
    from radio_telemetry_tracker_drone_fds.ping_finder.ping_finder_module import PingFinderModule
    from radio_telemetry_tracker_drone_fds.state import StateManager

logger = logging.getLogger(__name__)

# Import at the end to avoid circular imports
from radio_telemetry_tracker_drone_fds.ping_finder.ping_finder_module import PingFinderModule  # noqa: E402


class OnlinePingFinderManager:
    """Manages ping finder lifecycle in online mode."""

    def __init__(
        self,
        gps_module: GPSModule,
        state_manager: StateManager,
        drone_comms: DroneComms,
        hardware_config: HardwareConfig,
    ) -> None:
        """Initialize OnlinePingFinderManager.

        Args:
            gps_module: GPS module instance
            state_manager: State manager instance
            drone_comms: DroneComms instance for communication
            hardware_config: Hardware configuration
        """
        self._gps_module = gps_module
        self._state_manager = state_manager
        self._drone_comms = drone_comms
        self._hardware_config = hardware_config
        self._ping_finder_module: PingFinderModule | None = None

        # Register handlers and start DroneComms
        self._register_handlers()
        self._start_drone_comms()

    def _register_handlers(self) -> None:
        """Register handlers for start/stop/config requests."""
        # Register sync request handler
        self._drone_comms.register_sync_request_handler(self._handle_sync_request)

        # Register ping finder control handlers
        self._drone_comms.register_start_request_handler(self._handle_start_request)
        self._drone_comms.register_stop_request_handler(self._handle_stop_request)
        self._drone_comms.register_config_request_handler(self._handle_config_request)

    def _start_drone_comms(self) -> None:
        """Start DroneComms and GPS data sender thread."""
        # Start DroneComms
        self._drone_comms.start()

        # Start GPS data sending thread
        gps_sender_thread = threading.Thread(
            target=self._send_gps_data_loop,
            daemon=True,
        )
        gps_sender_thread.start()

    def _send_gps_data_loop(self) -> None:
        """Continuously send GPS data when GPS is running."""
        while True:
            if self._state_manager.get_gps_state() == "Running":
                gps_data = self._state_manager.get_current_gps_data()
                self._drone_comms.send_gps_data(GPSData(
                    easting=gps_data.easting,
                    northing=gps_data.northing,
                    altitude=gps_data.altitude,
                    heading=gps_data.heading,
                    epsg_code=gps_data.epsg_code,
                ))
            time.sleep(1)  # Send GPS data every second when running

    def _handle_sync_request(self, _: SyncRequestData) -> None:
        """Handle sync request from base station."""
        gps_state = self._state_manager.get_gps_state()
        success = gps_state == "Running"
        self._drone_comms.send_sync_response(SyncResponseData(success=success))

    def _handle_start_request(self, _: StartRequestData) -> None:
        """Handle start request from base station."""
        try:
            if self._ping_finder_module is None:
                logger.error("Cannot start ping finder: not configured")
                self._drone_comms.send_start_response(StartResponseData(success=False))
                return

            self._ping_finder_module.start()
            self._drone_comms.send_start_response(StartResponseData(success=True))
        except Exception:
            logger.exception("Failed to start ping finder")
            self._drone_comms.send_start_response(StartResponseData(success=False))

    def _handle_stop_request(self, _: StopRequestData) -> None:
        """Handle stop request from base station."""
        try:
            if self._ping_finder_module is None:
                logger.error("Cannot stop ping finder: not configured")
                self._drone_comms.send_stop_response(StopResponseData(success=False))
                return

            self._ping_finder_module.stop()
            self._drone_comms.send_stop_response(StopResponseData(success=True))
        except Exception:
            logger.exception("Failed to stop ping finder")
            self._drone_comms.send_stop_response(StopResponseData(success=False))

    def _handle_config_request(self, data: ConfigRequestData) -> None:
        """Handle config request from base station."""
        try:
            # Convert ConfigRequestData to PingFinderConfig
            config_dict = {
                "gain": data.gain,
                "sampling_rate": data.sampling_rate,
                "center_frequency": data.center_frequency,
                "run_num": data.run_num,
                "enable_test_data": data.enable_test_data,
                "ping_width_ms": data.ping_width_ms,
                "ping_min_snr": data.ping_min_snr,
                "ping_max_len_mult": data.ping_max_len_mult,
                "ping_min_len_mult": data.ping_min_len_mult,
                "target_frequencies": data.target_frequencies,
                "output_dir": str(self._get_output_directory()),
            }
            config = PingFinderConfig.from_dict(config_dict)

            # Create new ping finder module or reconfigure existing one
            if self._ping_finder_module is None:
                self._ping_finder_module = PingFinderModule(
                    gps_module=self._gps_module,
                    config=config,
                    state_manager=self._state_manager,
                    sdr_type=self._hardware_config.SDR_TYPE,
                    drone_comms=self._drone_comms,
                )
            else:
                self._ping_finder_module.reconfigure(config, self._hardware_config.SDR_TYPE)

            self._drone_comms.send_config_response(ConfigResponseData(success=True))
        except Exception:
            logger.exception("Failed to configure ping finder")
            self._drone_comms.send_config_response(ConfigResponseData(success=False))

    def _get_output_directory(self) -> str:
        """Get output directory based on hardware configuration."""
        import os
        from pathlib import Path

        if self._hardware_config.USE_USB_STORAGE:
            usb_media_path = Path("/media") / os.getenv("USER", "")
            if not usb_media_path.exists():
                logger.error("USB media path %s does not exist.", usb_media_path)
                msg = f"USB media path {usb_media_path} does not exist"
                raise FileNotFoundError(msg)

            # Find first mounted USB device
            for device in usb_media_path.iterdir():
                return str(device / "rtt_output")

            msg = "No USB storage device found"
            logger.error(msg)
            raise FileNotFoundError(msg)

        # If not using USB storage, use project root
        return str(Path.cwd() / "rtt_output")
