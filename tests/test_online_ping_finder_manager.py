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
    return cast(MagicMock, MagicMock(spec=DroneComms))


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
    # Ensure start() and stop() methods don't raise exceptions
    mock.start.return_value = None
    mock.stop.return_value = None
    # Mock required attributes
    mock.sdr_type = "GENERATOR"
    mock.gain = TEST_GAIN
    mock.sampling_rate = TEST_SAMPLING_RATE
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
    # Test when GPS is not running
    online_manager._handle_sync_request(SyncRequestData())  # noqa: SLF001
    mock_drone_comms.send_sync_response.assert_called_with(SyncResponseData(success=False))

    # Test when GPS is running
    online_manager._state_manager.set_gps_state(GPSState.RUNNING)  # noqa: SLF001
    online_manager._handle_sync_request(SyncRequestData())  # noqa: SLF001
    mock_drone_comms.send_sync_response.assert_called_with(SyncResponseData(success=True))


def test_start_request_handler_not_configured(
    online_manager: OnlinePingFinderManager, mock_drone_comms: MagicMock,
) -> None:
    """Test start request handler when ping finder is not configured."""
    online_manager._handle_start_request(StartRequestData())  # noqa: SLF001
    mock_drone_comms.send_start_response.assert_called_with(StartResponseData(success=False))


def test_stop_request_handler_not_configured(
    online_manager: OnlinePingFinderManager, mock_drone_comms: MagicMock,
) -> None:
    """Test stop request handler when ping finder is not configured."""
    online_manager._handle_stop_request(StopRequestData())  # noqa: SLF001
    mock_drone_comms.send_stop_response.assert_called_with(StopResponseData(success=False))


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

    online_manager._handle_config_request(config_data)  # noqa: SLF001
    mock_drone_comms.send_config_response.assert_called_with(ConfigResponseData(success=True))
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
        online_manager._handle_config_request(config_data)  # noqa: SLF001

        # Test start
        online_manager._handle_start_request(StartRequestData())  # noqa: SLF001
        mock_drone_comms.send_start_response.assert_called_with(StartResponseData(success=True))
        assert online_manager._state_manager.get_ping_finder_state() == PingFinderState.RUNNING.value  # noqa: S101, SLF001

        # Test stop
        online_manager._handle_stop_request(StopRequestData())  # noqa: SLF001
        mock_drone_comms.send_stop_response.assert_called_with(StopResponseData(success=True))
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
