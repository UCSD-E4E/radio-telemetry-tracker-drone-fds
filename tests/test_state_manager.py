"""Tests for StateManager functionality."""
import datetime as dt

import pytest

from radio_telemetry_tracker_drone_fds.state import GPSData, StateManager

# Constants for test values
TEST_LAT = 32.7157
TEST_LON = -117.1611
TEST_ALTITUDE = 545.4

def test_state_manager_gps_state() -> None:
    """Test StateManager's GPS state functionality."""
    state_manager = StateManager()
    assert state_manager.get_gps_state() == "Initializing"  # noqa: S101
    state_manager.update_gps_state("start_acquisition")
    assert state_manager.get_gps_state() == "Acquiring Signal"  # noqa: S101
    state_manager.update_gps_state("lock_signal")
    assert state_manager.get_gps_state() == "Locked"  # noqa: S101
    state_manager.update_gps_state("error")
    assert state_manager.get_gps_state() == "Error"  # noqa: S101

def test_state_manager_update_gps_data() -> None:
    """Test StateManager's GPS data functionality."""
    state_manager = StateManager()
    gps_data = GPSData(latitude=TEST_LAT, longitude=TEST_LON, altitude=TEST_ALTITUDE)
    state_manager.update_gps_data(gps_data)
    current_data = state_manager.get_current_gps_data()
    assert current_data.latitude == TEST_LAT  # noqa: S101
    assert current_data.longitude == TEST_LON  # noqa: S101

def test_state_manager_gps_data_history() -> None:
    """Test GPS data history functionality."""
    state_manager = StateManager()
    gps_data = GPSData(
        timestamp=dt.datetime.now(dt.timezone.utc).timestamp(),
        latitude=TEST_LAT,
        longitude=TEST_LON,
    )
    state_manager.update_gps_data(gps_data)

    # Create slightly different data
    new_data = GPSData(
        timestamp=dt.datetime.now(dt.timezone.utc).timestamp(),
        latitude=TEST_LAT + 0.0001,
        longitude=TEST_LON,
    )
    state_manager.update_gps_data(new_data)

    data = state_manager.get_current_gps_data()
    assert data.latitude == pytest.approx(TEST_LAT + 0.0001, rel=1e-6)  # noqa: S101
