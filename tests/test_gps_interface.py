"""Tests for GPS interface implementations."""

import pytest

from radio_telemetry_tracker_drone_fds.gps.gps_interface import (
    I2CGPSInterface,
    SerialGPSInterface,
    SimulatedGPSInterface,
)

# Minimum number of NMEA sentences expected in a single GPS read
MIN_NMEA_SENTENCES = 2


def test_simulated_gps_interface() -> None:
    """Test that simulated GPS interface returns valid data."""
    interface = SimulatedGPSInterface(simulation_speed=1.0)
    data = interface.read_gps_data()
    assert data is not None  # noqa: S101
    assert isinstance(data, list)  # noqa: S101
    assert len(data) > 0  # noqa: S101


def test_simulated_gps_interface_data_format() -> None:
    """Test that simulated GPS data follows NMEA format specifications."""
    interface = SimulatedGPSInterface(simulation_speed=1.0)
    data = interface.read_gps_data()
    nmea_str = "".join(chr(c) for c in data)
    sentences = nmea_str.strip().split("\r\n")
    assert len(sentences) >= MIN_NMEA_SENTENCES  # noqa: S101
    for sentence in sentences:
        assert sentence.startswith("$")  # noqa: S101
        checksum_index = sentence.find("*")
        assert checksum_index != -1  # noqa: S101


@pytest.mark.skip(reason="Requires hardware I2C bus")
def test_i2c_gps_interface() -> None:
    """Test I2C GPS interface functionality.

    Note: This test is skipped by default as it requires physical hardware.
    """
    interface = I2CGPSInterface(bus_number=1, address=0x42)
    data = interface.read_gps_data()
    assert data is not None  # noqa: S101


@pytest.mark.skip(reason="Requires hardware Serial port")
def test_serial_gps_interface() -> None:
    """Test Serial GPS interface functionality.

    Note: This test is skipped by default as it requires physical hardware.
    """
    interface = SerialGPSInterface(port="/dev/ttyS0", baudrate=9600)
    data = interface.read_gps_data()
    assert data is not None  # noqa: S101
