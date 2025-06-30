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
    ErrorData,
    GPSData,
    StartRequestData,
    StartResponseData,
    StopRequestData,
    StopResponseData,
    SyncRequestData,
    SyncResponseData,
)

from radio_telemetry_tracker_drone_fds.config import PingFinderConfig
from radio_telemetry_tracker_drone_fds.state.state_manager import PingFinderState

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
        self._pending_actions: dict[int, tuple[str, dict]] = {}

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

        # Register acknowledgment handlers
        self._drone_comms.on_ack_success = self._handle_ack_success
        self._drone_comms.on_ack_timeout = self._handle_ack_timeout

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

    def _handle_ack_success(self, packet_id: int) -> None:
        """Handle successful acknowledgment of a response packet."""
        if packet_id not in self._pending_actions:
            return

        action_type, action_data = self._pending_actions.pop(packet_id)
        try:
            if action_type == "sync":
                self._execute_sync_action()
            elif action_type == "start":
                self._execute_start_action()
            elif action_type == "stop":
                self._execute_stop_action()
            elif action_type == "config":
                self._execute_config_action(action_data)
        except Exception:
            msg = f"Failed to execute {action_type} action after acknowledgment"
            logger.exception(msg)
            self._drone_comms.send_error(ErrorData())

    def _handle_ack_timeout(self, packet_id: int) -> None:
        """Handle acknowledgment timeout of a response packet."""
        if packet_id in self._pending_actions:
            action_type, _ = self._pending_actions.pop(packet_id)
            logger.error("%s response acknowledgment timed out for packet %d", action_type.capitalize(), packet_id)

    def _execute_sync_action(self) -> None:
        """Execute sync action after acknowledgment."""
        if self._ping_finder_module is not None:
            # Stop if running
            if self._state_manager.get_ping_finder_state() != "Idle":
                self._ping_finder_module.stop()
            # Set state to UNCREATED
            self._state_manager.set_ping_finder_state(PingFinderState.UNCREATED)
            # Clear the module reference
            self._ping_finder_module = None

    def _execute_start_action(self) -> None:
        """Execute start action after acknowledgment."""
        if self._ping_finder_module is None:
            msg = "Cannot start ping finder: not configured"
            logger.error(msg)
            raise RuntimeError(msg)
        self._ping_finder_module.start()

    def _execute_stop_action(self) -> None:
        """Execute stop action after acknowledgment."""
        if self._ping_finder_module is None:
            msg = "Cannot stop ping finder: not configured"
            logger.error(msg)
            raise RuntimeError(msg)
        self._ping_finder_module.stop()

    def _execute_config_action(self, config_data: dict) -> None:
        """Execute config action after acknowledgment."""
        config = PingFinderConfig.from_dict(config_data)
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

    def _handle_sync_request(self, _: SyncRequestData) -> None:
        """Handle sync request from base station."""
        gps_state = self._state_manager.get_gps_state()
        success = gps_state == "Running"

        # Send the sync response and store pending action
        packet_id, _, _ = self._drone_comms.send_sync_response(SyncResponseData(success=success))
        self._pending_actions[packet_id] = ("sync", {})

    def _handle_start_request(self, _: StartRequestData) -> None:
        """Handle start request from base station."""
        success = self._ping_finder_module is not None

        # Send the start response and store pending action
        packet_id, _, _ = self._drone_comms.send_start_response(StartResponseData(success=success))
        if success:
            self._pending_actions[packet_id] = ("start", {})

    def _handle_stop_request(self, _: StopRequestData) -> None:
        """Handle stop request from base station."""
        success = self._ping_finder_module is not None

        # Send the stop response and store pending action
        packet_id, _, _ = self._drone_comms.send_stop_response(StopResponseData(success=success))
        if success:
            self._pending_actions[packet_id] = ("stop", {})

    def _handle_config_request(self, data: ConfigRequestData) -> None:
        """Handle config request from base station."""
        try:
            # Convert ConfigRequestData to dict for storage
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
                "target_frequencies": list(data.target_frequencies),
                "output_dir": str(self._get_output_directory()),
            }

            # Send the config response and store pending action
            packet_id, _, _ = self._drone_comms.send_config_response(ConfigResponseData(success=True))
            self._pending_actions[packet_id] = ("config", config_dict)

        except Exception:
            logger.exception("Failed to prepare config")
            self._drone_comms.send_error(ErrorData())

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
