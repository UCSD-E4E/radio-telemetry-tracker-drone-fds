"""Tests for PingFinderModule functionality."""
import datetime as dt
from unittest.mock import MagicMock

import pytest
from rct_dsp2 import SDR_TYPE_GENERATOR

from radio_telemetry_tracker_drone_fds.config import PingFinderConfig
from radio_telemetry_tracker_drone_fds.ping_finder.ping_finder_module import PingFinderModule
from radio_telemetry_tracker_drone_fds.state import GPSData, StateManager


@pytest.fixture
def ping_finder_config(ping_finder_config_data: dict) -> PingFinderConfig:
    """Fixture for PingFinderConfig."""
    return PingFinderConfig.from_dict(ping_finder_config_data)


def test_ping_finder_module_initialization(ping_finder_config: PingFinderConfig) -> None:
    """Test PingFinderModule initialization."""
    gps_module = MagicMock()
    state_manager = StateManager()
    ping_finder_module = PingFinderModule(
        gps_module=gps_module,
        config=ping_finder_config,
        state_manager=state_manager,
        sdr_type="GENERATOR",
    )
    assert ping_finder_module._ping_finder.sdr_type == SDR_TYPE_GENERATOR  # noqa: S101, SLF001


def test_ping_finder_module_start_stop(ping_finder_config: PingFinderConfig) -> None:
    """Test PingFinderModule start and stop functionality."""
    gps_module = MagicMock()
    state_manager = StateManager()
    ping_finder_module = PingFinderModule(
        gps_module=gps_module,
        config=ping_finder_config,
        state_manager=state_manager,
        sdr_type="GENERATOR",
    )
    state_manager.update_ping_finder_state("configure")
    ping_finder_module.start()
    assert state_manager.get_ping_finder_state() == "Running"  # noqa: S101
    ping_finder_module.stop()
    assert state_manager.get_ping_finder_state() == "Idle"  # noqa: S101


def test_ping_finder_module_callback(ping_finder_config: PingFinderConfig) -> None:
    """Test PingFinderModule callback functionality."""
    gps_module = MagicMock()
    state_manager = StateManager()
    gps_data = GPSData(timestamp=dt.datetime.now(dt.timezone.utc).timestamp(),
                       easting=500000, northing=3762151, altitude=10)
    state_manager.update_gps_data(gps_data)
    ping_finder_module = PingFinderModule(
        gps_module=gps_module,
        config=ping_finder_config,
        state_manager=state_manager,
        sdr_type="GENERATOR",
    )
    # Test the callback functionality
    ping_finder_module._callback(  # noqa: SLF001
        dt.datetime.now(dt.timezone.utc),
        amplitude=10.0,
        frequency=173043000,
    )
    # Since logging is used, we can only check if the method completes without error
