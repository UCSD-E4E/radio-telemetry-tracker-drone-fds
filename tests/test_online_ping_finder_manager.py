"""Tests for OnlinePingFinderManager functionality."""
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from radio_telemetry_tracker_drone_comms_package import (
    ConfigRequestData,
    ConfigResponseData,
    DroneComms,
    StartRequestData,
    StartResponseData,
    StopRequestData,
    StopResponseData,
    SyncRequestData,
    SyncResponseData,
)
from rct_dsp2 import PingFinder

from radio_telemetry_tracker_drone_fds.config import HardwareConfig
from radio_telemetry_tracker_drone_fds.ping_finder.online_ping_finder_manager import OnlinePingFinderManager
from radio_telemetry_tracker_drone_fds.state import StateManager
from radio_telemetry_tracker_drone_fds.state.state_manager import GPSState, PingFinderState

# Constants for test values
TEST_GAIN = 50.0
TEST_SAMPLING_RATE = 2048000
TEST_CENTER_FREQ = 173043000
TEST_PING_WIDTH_MS = 20
TEST_PING_MIN_SNR = 10



@pytest.fixture
def mock_drone_comms() -> MagicMock:
    """Fixture for mocked DroneComms."""
    mock = cast(MagicMock, MagicMock(spec=DroneComms))
    # Configure send methods to return (packet_id, need_ack, timestamp)
    mock.send_sync_response.return_value = (1, False, 0)
    mock.send_start_response.return_value = (2, False, 0)
    mock.send_stop_response.return_value = (3, False, 0)
    mock.send_config_response.return_value = (4, False, 0)
    mock.send_error.return_value = (5, False, 0)
    return mock


@pytest.fixture
def mock_gps_module() -> MagicMock:
    """Fixture for mocked GPSModule."""
    return cast(MagicMock, MagicMock())


@pytest.fixture
def mock_hardware_config() -> MagicMock:
    """Fixture for mocked HardwareConfig."""
    config = cast(MagicMock, MagicMock(spec=HardwareConfig))
    config.SDR_TYPE = "GENERATOR"
    config.USE_USB_STORAGE = False
    return config


@pytest.fixture
def mock_ping_finder() -> MagicMock:
    """Fixture for mocked PingFinder."""
    mock = cast(MagicMock, MagicMock(spec=PingFinder))

    # Configure methods to not raise exceptions and handle state transitions
    def mock_start() -> None:
        """Mock start that doesn't raise exceptions."""
        return

    def mock_stop() -> None:
        """Mock stop that doesn't raise exceptions."""
        return

    mock.start = MagicMock(side_effect=mock_start)
    mock.stop = MagicMock(side_effect=mock_stop)
    mock.register_callback = MagicMock(return_value=None)

    # Mock required attributes that will be set by configure
    mock.sdr_type = None
    mock.gain = None
    mock.sampling_rate = None
    mock.center_frequency = None
    mock.enable_test_data = None
    mock.ping_width_ms = None
    mock.ping_min_snr = None
    mock.ping_max_len_mult = None
    mock.ping_min_len_mult = None
    mock.target_frequencies = None

    return mock


@pytest.fixture
def online_manager(
    mock_gps_module: MagicMock,
    mock_drone_comms: MagicMock,
    mock_hardware_config: MagicMock,
    mock_ping_finder: MagicMock,
) -> OnlinePingFinderManager:
    """Fixture for OnlinePingFinderManager."""
    state_manager = StateManager()
    with patch(
        "radio_telemetry_tracker_drone_fds.ping_finder.ping_finder_module.PingFinder",
        return_value=mock_ping_finder,
    ):
        return OnlinePingFinderManager(
            gps_module=mock_gps_module,
            state_manager=state_manager,
            drone_comms=mock_drone_comms,
            hardware_config=mock_hardware_config,
        )


def test_initialization(online_manager: OnlinePingFinderManager, mock_drone_comms: MagicMock) -> None:
    """Test OnlinePingFinderManager initialization."""
    assert online_manager._ping_finder_module is None  # noqa: S101, SLF001
    mock_drone_comms.register_sync_request_handler.assert_called_once()
    mock_drone_comms.register_start_request_handler.assert_called_once()
    mock_drone_comms.register_stop_request_handler.assert_called_once()
    mock_drone_comms.register_config_request_handler.assert_called_once()
    mock_drone_comms.start.assert_called_once()


def test_sync_request_handler(online_manager: OnlinePingFinderManager, mock_drone_comms: MagicMock) -> None:
    """Test sync request handler."""
    # Set GPS state to Running
    online_manager._state_manager.set_gps_state(GPSState.RUNNING)  # noqa: SLF001

    # Handle sync request with required arguments
    sync_request = SyncRequestData(
        packet_id=1,
        timestamp=0,
        ack_timeout=2.0,
        max_retries=5,
    )
    online_manager._handle_sync_request(sync_request)  # noqa: SLF001
    mock_drone_comms.send_sync_response.assert_called_with(SyncResponseData(success=True))

    # Simulate acknowledgment callback
    packet_id = mock_drone_comms.send_sync_response.return_value[0]
    online_manager._handle_ack_success(packet_id)  # noqa: SLF001

    # Verify state is reset
    assert online_manager._ping_finder_module is None  # noqa: S101, SLF001
    assert online_manager._state_manager.get_ping_finder_state() == PingFinderState.UNCREATED.value  # noqa: S101, SLF001


def test_start_request_handler_not_configured(
    online_manager: OnlinePingFinderManager, mock_drone_comms: MagicMock,
) -> None:
    """Test start request handler when ping finder is not configured."""
    online_manager._handle_start_request(StartRequestData())  # noqa: SLF001
    mock_drone_comms.send_start_response.assert_called_with(StartResponseData(success=False))

    # No acknowledgment callback needed since no pending action was stored


def test_stop_request_handler_not_configured(
    online_manager: OnlinePingFinderManager, mock_drone_comms: MagicMock,
) -> None:
    """Test stop request handler when ping finder is not configured."""
    online_manager._handle_stop_request(StopRequestData())  # noqa: SLF001
    mock_drone_comms.send_stop_response.assert_called_with(StopResponseData(success=False))

    # No acknowledgment callback needed since no pending action was stored


def test_config_request_handler(online_manager: OnlinePingFinderManager, mock_drone_comms: MagicMock) -> None:
    """Test config request handler."""
    config_data = ConfigRequestData(
        gain=TEST_GAIN,
        sampling_rate=TEST_SAMPLING_RATE,
        center_frequency=TEST_CENTER_FREQ,
        run_num=1,
        enable_test_data=True,
        ping_width_ms=TEST_PING_WIDTH_MS,
        ping_min_snr=TEST_PING_MIN_SNR,
        ping_max_len_mult=1.5,
        ping_min_len_mult=0.5,
        target_frequencies=[TEST_CENTER_FREQ],
    )

    # Handle config request
    online_manager._handle_config_request(config_data)  # noqa: SLF001
    mock_drone_comms.send_config_response.assert_called_with(ConfigResponseData(success=True))

    # Simulate acknowledgment callback
    packet_id = mock_drone_comms.send_config_response.return_value[0]
    online_manager._handle_ack_success(packet_id)  # noqa: SLF001

    # Now the ping finder module should be created
    assert online_manager._ping_finder_module is not None  # noqa: S101, SLF001


def test_start_stop_after_config(
    online_manager: OnlinePingFinderManager,
    mock_drone_comms: MagicMock,
    mock_ping_finder: MagicMock,
) -> None:
    """Test start and stop requests after configuration."""
    # First configure the ping finder
    config_data = ConfigRequestData(
        gain=TEST_GAIN,
        sampling_rate=TEST_SAMPLING_RATE,
        center_frequency=TEST_CENTER_FREQ,
        run_num=1,
        enable_test_data=True,
        ping_width_ms=TEST_PING_WIDTH_MS,
        ping_min_snr=TEST_PING_MIN_SNR,
        ping_max_len_mult=1.5,
        ping_min_len_mult=0.5,
        target_frequencies=[TEST_CENTER_FREQ],
    )

    # Mock the PingFinder instance that will be created in PingFinderModule
    with patch(
        "radio_telemetry_tracker_drone_fds.ping_finder.ping_finder_module.PingFinder",
        return_value=mock_ping_finder,
    ):
        # Handle config request and simulate acknowledgment
        online_manager._handle_config_request(config_data)  # noqa: SLF001
        packet_id = mock_drone_comms.send_config_response.return_value[0]
        online_manager._handle_ack_success(packet_id)  # noqa: SLF001

        # Verify state is IDLE after configuration
        assert online_manager._state_manager.get_ping_finder_state() == PingFinderState.IDLE.value  # noqa: S101, SLF001

        # Test start request
        online_manager._handle_start_request(StartRequestData())  # noqa: SLF001
        mock_drone_comms.send_start_response.assert_called_with(StartResponseData(success=True))

        # Simulate start acknowledgment
        packet_id = mock_drone_comms.send_start_response.return_value[0]
        online_manager._handle_ack_success(packet_id)  # noqa: SLF001

        # Verify state is RUNNING after start
        assert online_manager._state_manager.get_ping_finder_state() == PingFinderState.RUNNING.value  # noqa: S101, SLF001

        # Test stop request
        online_manager._handle_stop_request(StopRequestData())  # noqa: SLF001
        mock_drone_comms.send_stop_response.assert_called_with(StopResponseData(success=True))

        # Simulate stop acknowledgment
        packet_id = mock_drone_comms.send_stop_response.return_value[0]
        online_manager._handle_ack_success(packet_id)  # noqa: SLF001

        # Verify state is IDLE after stop
        assert online_manager._state_manager.get_ping_finder_state() == PingFinderState.IDLE.value  # noqa: S101, SLF001


@patch("pathlib.Path.exists")
@patch("pathlib.Path.iterdir")
def test_output_directory_usb_storage(
    mock_iterdir: MagicMock,
    mock_exists: MagicMock,
    mock_hardware_config: MagicMock,
) -> None:
    """Test output directory determination with USB storage."""
    mock_hardware_config.USE_USB_STORAGE = True
    mock_exists.return_value = True

    # Create a mock device path that behaves like a Path object
    mock_device = cast(MagicMock, MagicMock())
    mock_device.__str__.return_value = "/media/user/usb0"
    mock_device.__truediv__.return_value = Path("/media/user/usb0/rtt_output")
    mock_iterdir.return_value = [mock_device]

    state_manager = StateManager()
    manager = OnlinePingFinderManager(
        gps_module=cast(MagicMock, MagicMock()),
        state_manager=state_manager,
        drone_comms=cast(MagicMock, MagicMock()),
        hardware_config=mock_hardware_config,
    )

    output_dir = manager._get_output_directory()  # noqa: SLF001
    assert output_dir == str(Path("/media/user/usb0/rtt_output"))  # noqa: S101


def test_output_directory_no_usb(online_manager: OnlinePingFinderManager) -> None:
    """Test output directory determination without USB storage."""
    output_dir = online_manager._get_output_directory()  # noqa: SLF001
    assert output_dir == str(Path.cwd() / "rtt_output")  # noqa: S101
