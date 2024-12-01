"""Test fixtures for the radio telemetry tracker drone FDS package."""

from typing import Any

import pytest

from radio_telemetry_tracker_drone_fds.state import StateManager


@pytest.fixture
def hardware_config_data() -> dict[str, Any]:
    """Provide mock hardware configuration data for testing.

    Returns:
        Dict containing hardware configuration parameters.
    """
    return {
        "GPS_INTERFACE": "SIMULATED",
        "EPSG_CODE": 32611,
        "GPS_I2C_BUS": 1,
        "GPS_ADDRESS": "0x42",
        "GPS_SERIAL_PORT": "/dev/ttyS0",
        "GPS_SERIAL_BAUDRATE": 9600,
        "GPS_SIMULATION_SPEED": 1.0,
        "CHECK_USB_FOR_CONFIG": False,
        "SDR_TYPE": "GENERATOR",
    }


@pytest.fixture
def ping_finder_config_data() -> dict[str, Any]:
    """Provide mock ping finder configuration data for testing.

    Returns:
        Dict containing ping finder configuration parameters.
    """
    return {
        "gain": 56.0,
        "sampling_rate": 2500000,
        "center_frequency": 173500000,
        "run_num": 1,
        "enable_test_data": False,
        "ping_width_ms": 25,
        "ping_min_snr": 25,
        "ping_max_len_mult": 1.5,
        "ping_min_len_mult": 0.5,
        "target_frequencies": [173043000],
        "output_dir": "./output",
    }


@pytest.fixture
def mock_state_manager() -> StateManager:
    """Provide a mock state manager instance for testing.

    Returns:
        A fresh StateManager instance.
    """
    return StateManager()
