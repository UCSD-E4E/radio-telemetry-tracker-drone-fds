"""Tests for PingFinderModule functionality."""
import datetime as dt
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from radio_telemetry_tracker_drone_comms_package import DroneComms, PingData
from rct_dsp2 import SDR_TYPE_GENERATOR, PingFinder

from radio_telemetry_tracker_drone_fds.config import PingFinderConfig
from radio_telemetry_tracker_drone_fds.ping_finder.ping_finder_module import PingFinderModule
from radio_telemetry_tracker_drone_fds.state import GPSData, StateManager
from radio_telemetry_tracker_drone_fds.state.state_manager import PingFinderState

# Constants for test values
TEST_GAIN = 50.0
TEST_GAIN_NEW = 60.0
TEST_SAMPLING_RATE = 2048000
TEST_SAMPLING_RATE_NEW = 3072000
TEST_CENTER_FREQ = 173043000
TEST_EASTING = 500000
TEST_NORTHING = 3762151
TEST_ALTITUDE = 10
TEST_AMPLITUDE = 10.0
TEST_ESPG_CODE = 32633  # Example EPSG code for UTM zone 33N
TEST_OPERATIONAL_MODE = "ONLINE"  # Example operational mode

@pytest.fixture
def ping_finder_config_data() -> dict:
    """Fixture for PingFinderConfig test data."""
    return {
        "espg_code": TEST_ESPG_CODE,
        "operational_mode": TEST_OPERATIONAL_MODE,
        "gain": TEST_GAIN,
        "sampling_rate": TEST_SAMPLING_RATE,
        "center_frequency": TEST_CENTER_FREQ,
        "run_num": 1,
        "enable_test_data": True,
        "ping_width_ms": 20,
        "ping_min_snr": 10,
        "ping_max_len_mult": 1.5,
        "ping_min_len_mult": 0.5,
        "target_frequencies": [TEST_CENTER_FREQ],
        "output_dir": "test_output",
    }


@pytest.fixture
def ping_finder_config(ping_finder_config_data: dict) -> PingFinderConfig:
    """Fixture for PingFinderConfig."""
    return PingFinderConfig.from_dict(ping_finder_config_data)


@pytest.fixture
def mock_drone_comms() -> MagicMock:
    """Fixture for mocked DroneComms."""
    return cast(MagicMock, MagicMock(spec=DroneComms))


@pytest.fixture
def mock_ping_finder() -> MagicMock:
    """Fixture for mocked PingFinder."""
    mock = cast(MagicMock, MagicMock(spec=PingFinder))
    # Ensure start() and stop() methods don't raise exceptions
    mock.start.return_value = None
    mock.stop.return_value = None
    # Mock required attributes
    mock.sdr_type = SDR_TYPE_GENERATOR
    mock.gain = TEST_GAIN
    mock.sampling_rate = TEST_SAMPLING_RATE
    return mock


def test_ping_finder_module_initialization(ping_finder_config: PingFinderConfig, mock_ping_finder: MagicMock) -> None:
    """Test PingFinderModule initialization."""
    gps_module = MagicMock()
    state_manager = StateManager()
    with patch(
        "radio_telemetry_tracker_drone_fds.ping_finder.ping_finder_module.PingFinder",
        return_value=mock_ping_finder,
    ):
        ping_finder_module = PingFinderModule(
            gps_module=gps_module,
            config=ping_finder_config,
            state_manager=state_manager,
            sdr_type="GENERATOR",
        )
        assert ping_finder_module._ping_finder.sdr_type == SDR_TYPE_GENERATOR  # noqa: S101, SLF001


def test_ping_finder_module_start_stop(ping_finder_config: PingFinderConfig, mock_ping_finder: MagicMock) -> None:
    """Test PingFinderModule start and stop functionality."""
    gps_module = MagicMock()
    state_manager = StateManager()
    with patch(
        "radio_telemetry_tracker_drone_fds.ping_finder.ping_finder_module.PingFinder",
        return_value=mock_ping_finder,
    ):
        ping_finder_module = PingFinderModule(
            gps_module=gps_module,
            config=ping_finder_config,
            state_manager=state_manager,
            sdr_type="GENERATOR",
        )
        state_manager.set_ping_finder_state(PingFinderState.IDLE)
        ping_finder_module.start()
        assert state_manager.get_ping_finder_state() == "Running"  # noqa: S101
        ping_finder_module.stop()
        assert state_manager.get_ping_finder_state() == "Idle"  # noqa: S101


def test_ping_finder_module_callback(ping_finder_config: PingFinderConfig, mock_ping_finder: MagicMock) -> None:
    """Test PingFinderModule callback functionality."""
    gps_module = MagicMock()
    state_manager = StateManager()
    gps_data = GPSData(timestamp=dt.datetime.now(dt.timezone.utc).timestamp(),
                       easting=TEST_EASTING, northing=TEST_NORTHING, altitude=TEST_ALTITUDE)
    state_manager.update_gps_data(gps_data)
    with patch(
        "radio_telemetry_tracker_drone_fds.ping_finder.ping_finder_module.PingFinder",
        return_value=mock_ping_finder,
    ):
        ping_finder_module = PingFinderModule(
            gps_module=gps_module,
            config=ping_finder_config,
            state_manager=state_manager,
            sdr_type="GENERATOR",
        )
        # Test the callback functionality
        ping_finder_module._callback(  # noqa: SLF001
            dt.datetime.now(dt.timezone.utc),
            amplitude=TEST_AMPLITUDE,
            frequency=TEST_CENTER_FREQ,
        )
        # Since logging is used, we can only check if the method completes without error


def test_ping_finder_module_online_callback(
    ping_finder_config: PingFinderConfig, mock_drone_comms: MagicMock, mock_ping_finder: MagicMock,
) -> None:
    """Test PingFinderModule callback functionality in online mode."""
    gps_module = MagicMock()
    state_manager = StateManager()
    gps_data = GPSData(timestamp=dt.datetime.now(dt.timezone.utc).timestamp(),
                       easting=TEST_EASTING, northing=TEST_NORTHING, altitude=TEST_ALTITUDE)
    state_manager.update_gps_data(gps_data)

    with patch(
        "radio_telemetry_tracker_drone_fds.ping_finder.ping_finder_module.PingFinder",
        return_value=mock_ping_finder,
    ):
        ping_finder_module = PingFinderModule(
            gps_module=gps_module,
            config=ping_finder_config,
            state_manager=state_manager,
            sdr_type="GENERATOR",
            drone_comms=mock_drone_comms,
        )

        # Test the callback functionality with drone_comms
        timestamp = dt.datetime.now(dt.timezone.utc)
        ping_finder_module._callback(  # noqa: SLF001
            timestamp,
            amplitude=TEST_AMPLITUDE,
            frequency=TEST_CENTER_FREQ,
        )

        # Verify that ping data was sent through drone_comms
        mock_drone_comms.send_ping_data.assert_called_once()
        sent_ping_data = mock_drone_comms.send_ping_data.call_args[0][0]
        assert isinstance(sent_ping_data, PingData)  # noqa: S101
        assert sent_ping_data.amplitude == TEST_AMPLITUDE  # noqa: S101
        assert sent_ping_data.frequency == TEST_CENTER_FREQ  # noqa: S101
        assert sent_ping_data.easting == TEST_EASTING  # noqa: S101
        assert sent_ping_data.northing == TEST_NORTHING  # noqa: S101
        assert sent_ping_data.altitude == TEST_ALTITUDE  # noqa: S101


def test_ping_finder_module_reconfigure(ping_finder_config: PingFinderConfig, mock_ping_finder: MagicMock) -> None:
    """Test PingFinderModule reconfiguration."""
    gps_module = MagicMock()
    state_manager = StateManager()
    with patch(
        "radio_telemetry_tracker_drone_fds.ping_finder.ping_finder_module.PingFinder",
        return_value=mock_ping_finder,
    ):
        ping_finder_module = PingFinderModule(
            gps_module=gps_module,
            config=ping_finder_config,
            state_manager=state_manager,
            sdr_type="GENERATOR",
        )

        # Create new config with different values
        new_config = PingFinderConfig(
            gain=TEST_GAIN_NEW,
            sampling_rate=TEST_SAMPLING_RATE_NEW,
            center_frequency=ping_finder_config.center_frequency,
            run_num=ping_finder_config.run_num,
            enable_test_data=ping_finder_config.enable_test_data,
            ping_width_ms=ping_finder_config.ping_width_ms,
            ping_min_snr=ping_finder_config.ping_min_snr,
            ping_max_len_mult=ping_finder_config.ping_max_len_mult,
            ping_min_len_mult=ping_finder_config.ping_min_len_mult,
            target_frequencies=ping_finder_config.target_frequencies,
            output_dir=ping_finder_config.output_dir,
        )

        # Test reconfiguration
        ping_finder_module.reconfigure(new_config, "GENERATOR")
        assert ping_finder_module._ping_finder.sdr_type == SDR_TYPE_GENERATOR  # noqa: S101, SLF001
        # Verify that the new configuration was applied
        assert ping_finder_module._ping_finder.gain == TEST_GAIN_NEW  # noqa: S101, SLF001
        assert ping_finder_module._ping_finder.sampling_rate == TEST_SAMPLING_RATE_NEW  # noqa: S101, SLF001
