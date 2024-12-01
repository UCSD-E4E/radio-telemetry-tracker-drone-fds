"""Tests for GPS module functionality."""

from radio_telemetry_tracker_drone_fds.gps.gps_interface import SimulatedGPSInterface
from radio_telemetry_tracker_drone_fds.gps.gps_module import GPSModule
from radio_telemetry_tracker_drone_fds.state import StateManager

# Constants for test values
TEST_EPSG_CODE = 32611
TEST_ALTITUDE = 545.4
TEST_LAT = 32.7157
TEST_LON = -117.1611
TEST_NMEA = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n"


def test_gps_module_initialization() -> None:
    """Test GPS module initialization with correct EPSG code."""
    interface = SimulatedGPSInterface()
    state_manager = StateManager()
    gps_module = GPSModule(interface, epsg_code=TEST_EPSG_CODE, state_manager=state_manager)
    assert gps_module._epsg_code == TEST_EPSG_CODE  # noqa: S101, SLF001


def test_gps_module_process_buffer() -> None:
    """Test GPS module's ability to process NMEA sentences from buffer."""
    interface = SimulatedGPSInterface()
    state_manager = StateManager()
    gps_module = GPSModule(interface, epsg_code=TEST_EPSG_CODE, state_manager=state_manager)
    # Simulate receiving NMEA sentences
    gps_module._buffer = TEST_NMEA  # noqa: SLF001
    gps_module._process_buffer()  # noqa: SLF001
    gps_data = state_manager.get_current_gps_data()
    assert gps_data.altitude == TEST_ALTITUDE  # noqa: S101


def test_gps_module_update_gps_data() -> None:
    """Test GPS module's coordinate conversion functionality."""
    interface = SimulatedGPSInterface()
    state_manager = StateManager()
    gps_module = GPSModule(interface, epsg_code=TEST_EPSG_CODE, state_manager=state_manager)
    gps_data = gps_module._state_manager.get_current_gps_data()  # noqa: SLF001
    assert gps_data.easting is None  # noqa: S101
    assert gps_data.northing is None  # noqa: S101

    # Provide data with latitude and longitude
    new_data = gps_module._state_manager.get_current_gps_data()  # noqa: SLF001
    new_data.latitude = TEST_LAT
    new_data.longitude = TEST_LON
    gps_module._update_gps_data(new_data)  # noqa: SLF001
    gps_data = gps_module._state_manager.get_current_gps_data()  # noqa: SLF001
    assert gps_data.easting is not None  # noqa: S101
    assert gps_data.northing is not None  # noqa: S101
